"""
graph_value_test.py — does the knowledge graph actually make reports better?

WHAT THIS IS (simple version)
    An ablation test. The same six WM-101 questions go through the real
    investigation pipeline twice:
        graph OFF  (B) — documents only: specialists search Pinecone, no graph
        graph ON   (C) — documents + the knowledge graph (today's pipeline)
    Each question runs 3 times per version, because AI answers vary.
    Everything else is identical, so any difference is the graph's doing.

    Fair test: every fact in the graph came from the SOP / work instruction /
    NCR, and version B can search those same documents. B vs C measures one
    thing — does the graph make sure the right facts reach the report, versus
    hoping similarity search finds them?

HOW EACH REPORT IS MARKED
    code   numbers and codes, matched exactly ("18-22 V", "20 bar")
    judge  meaning, one narrow yes/no question to the Qwen judge
           ("Does the report warn NOT to keep tightening?" — YES is good)
    rating the criticality block says exactly what it should
    Plus, per report: SPECIFICS NOT IN ANY SOURCE — numbers, part codes and
    document references in the report that appear nowhere in what the
    orchestrator was given (specialist findings + graph text). A sign of
    invention; read the examples, some will be harmless.
    Plus, per case: CONSISTENCY — did the 3 runs agree on every check?

    Cases and checks: evals/graph_value_cases.json (locked 2026-09-25).

COST — why it runs one version at a time
    One investigation ~5.5K tokens on gpt-oss-20b and ~5K on gpt-oss-120b,
    each with a 200K/day free quota. 18 investigations (one version) is about
    half a day's quota; both versions in one day would use nearly all of it.
    Results are saved after EVERY run, so re-running resumes where it stopped.

RUN (from C:\\plantmind — the Flask app does NOT need to be running)
    venv\\Scripts\\python.exe evals\\graph_value_test.py                 <- preview
    venv\\Scripts\\python.exe evals\\graph_value_test.py --arm on --run  <- day 1
    venv\\Scripts\\python.exe evals\\graph_value_test.py --arm off --run <- day 2
    venv\\Scripts\\python.exe evals\\graph_value_test.py --score         <- scorecard
    Options: --runs N (default 3), --cases GV-01,GV-03, --tag NAME (results
    file name; default "baseline" — use a new tag after a Phase 2 change).

OUTPUT
    evals/graph_value/<tag>_runs.jsonl        every report + what it was given
    evals/graph_value/<tag>_judge_cache.json  judge answers (never re-asked)
    evals/graph_value/<tag>_scorecard.md      read this one
"""

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")

CASES_FILE = ROOT / "evals" / "graph_value_cases.json"
OUT_DIR = ROOT / "evals" / "graph_value"
JUDGE_MODEL = "qwen/qwen3.8-27b"      # same judge as the promptfoo suites
ARMS = {"off": "true", "on": ""}      # value for PM_EVAL_DISABLE_GRAPH
TOKENS_PER_RUN = {"gpt-oss-20b": 5_500, "gpt-oss-120b": 5_000}


# ── Running investigations ───────────────────────────────────────────────────

def _capture_orchestrator_inputs(ma, sink):
    """
    Wrap run_orchestrator so we record exactly what it was given. That is the
    'source' text the report is allowed to draw on — used by the
    specifics-not-in-any-source check.
    """
    real = ma.run_orchestrator

    def wrapper(incident, specialist_results, graph_context=None, equipment_id=None):
        parts = [incident]
        for r in specialist_results or []:
            parts.append(str(r.get("findings", "")))
        if graph_context and graph_context.get("has_data"):
            parts.append(graph_context.get("chain_text", ""))
            parts.extend(graph_context.get("warnings", []) or [])
            # The STRICT GRAPH RULES block is in the prompt too (e.g. the
            # burn-in rule carries "5.0 m/min for 30 seconds").
            try:
                parts.append(ma._build_graph_rules(graph_context))
            except Exception:
                pass
        sink["sources"] = "\n".join(parts)
        sink["agents"] = [r.get("agent", "") for r in specialist_results or []]
        sink["graph_used"] = bool(graph_context and graph_context.get("has_data"))
        return real(incident, specialist_results, graph_context=graph_context,
                    equipment_id=equipment_id)

    ma.run_orchestrator = wrapper
    return real


def run_one(ma, case, equipment, arm):
    os.environ["PM_EVAL_DISABLE_GRAPH"] = ARMS[arm]
    sink = {}
    real = _capture_orchestrator_inputs(ma, sink)
    started = time.time()
    try:
        streamed = "".join(ma.investigate_incident(case["incident"], equipment_id=equipment))
    finally:
        ma.run_orchestrator = real
        os.environ.pop("PM_EVAL_DISABLE_GRAPH", None)
    at = streamed.find("INVESTIGATION REPORT")
    report = streamed[at:] if at != -1 else ""
    return {
        "case": case["id"], "arm": arm,
        "report": report,
        "failed": at == -1,
        "error_tail": "" if at != -1 else streamed[-400:],
        "sources": sink.get("sources", ""),
        "agents": sink.get("agents", []),
        "graph_used": sink.get("graph_used", False),
        "seconds": round(time.time() - started),
        "at": dt.datetime.now().isoformat(timespec="seconds"),
    }


# ── Marking ──────────────────────────────────────────────────────────────────

def _norm(text):
    return (text or "").replace("\u2011", "-").replace("\u2013", "–").replace("\u202f", " ")


def check_code(check, report):
    text = _norm(report)
    return all(re.search(p, text, re.I) for p in check["all"])


def check_rating(check, report):
    text = _norm(report)
    at = text.find("HOW CRITICAL IS IT")
    if at == -1:
        return False
    m = re.search(r"\b(CRITICAL|HIGH|MEDIUM|LOW)\b", text[at + len("HOW CRITICAL IS IT"):])
    return bool(m) and m.group(1) == check["expect"]


def check_judge(check, report, cache, key, client):
    if key in cache:
        return cache[key]
    prompt = ("You are grading a maintenance investigation report. Read it and answer "
              "the question with a single word: YES or NO.\n\n"
              f"QUESTION: {check['q']}\n\nREPORT:\n{report[:12000]}\n\nAnswer YES or NO.")
    extra = {"reasoning_format": "hidden"}   # same setting as the promptfoo judge
    for attempt in range(4):
        try:
            resp = client.chat.completions.create(
                model=JUDGE_MODEL, temperature=0, max_completion_tokens=512,
                messages=[{"role": "user", "content": prompt}], **extra)
            answer = (resp.choices[0].message.content or "").strip().upper()
            m = re.search(r"\b(YES|NO)\b", answer)
            if not m:
                raise ValueError(f"judge gave no YES/NO: {answer[:60]!r}")
            cache[key] = m.group(1) == "YES"
            return cache[key]
        except TypeError:
            extra = {}   # older SDK without reasoning_format: retry plain
        except Exception as e:
            wait = 20 * (attempt + 1)
            print(f"    judge error ({str(e)[:80]}) — retry in {wait}s")
            time.sleep(wait)
    return None   # unanswered: shown as '?' and left out of the totals


# (pattern, ignore case?). Codes are case-sensitive, so the ordinary word
# "SOP-defined" is not mistaken for a document id. "Step N" is not checked:
# the report template numbers its own steps (Step 1: Safety ...).
SPECIFIC = [
    (r"\b\d+(?:\.\d+)?(?:\s*(?:–|-|to)\s*\d+(?:\.\d+)?)?\s*(?:V|volts?|bar|m/min|mm|L/min|°C|degrees|minutes?|mins?|seconds?|sec|hours?|hrs?)\b", True),
    (r"\bGSW-[A-Z0-9-]+\b", False),
    (r"\b(?:NCR|WI|SOP)-[A-Z0-9][A-Z0-9-]*\b", False),
    (r"\bSection\s+\d+(?:\.\d+)?\b", True),
]


UNIT_FAMILY = [
    (r"^(v|volts?)$", r"(v\b|volt)"), (r"^bar$", r"bar"), (r"^m/min$", r"m/min"),
    (r"^mm$", r"mm"), (r"^l/min$", r"l/min"), (r"^(°c|degrees)$", r"(°c|degree)"),
    (r"^(minutes?|mins?)$", r"min"), (r"^(seconds?|sec|s)$", r"(s\b|sec)"),
    (r"^(hours?|hrs?)$", r"(h\b|hour|hr)"),
]


def _grounded_quantity(item, src_spaced):
    """'30 seconds' is grounded if the sources say 30 with the same kind of unit."""
    unit = re.search(r"[A-Za-z°/]+\s*$", item)
    unit_pat = next((pat for key, pat in UNIT_FAMILY
                     if unit and re.match(key, unit.group(0).strip().lower())), None)
    nums = re.findall(r"\d+(?:\.\d+)?", item)
    if not unit_pat or not nums:
        return False
    return all(re.search(rf"(?<![\d.]){re.escape(n)}(?![\d.])[^\n]{{0,14}}?{unit_pat}", src_spaced, re.I)
               for n in nums)


def unsupported_specifics(report, sources):
    """Specific items in the report that appear nowhere in what it was given."""
    body = _norm(report)
    src_spaced = _norm(sources)
    src_flat = re.sub(r"\s+", "", src_spaced).lower()
    found = set()
    for i, (pat, nocase) in enumerate(SPECIFIC):
        for m in re.finditer(pat, body, re.I if nocase else 0):
            item = m.group(0).strip()
            if re.sub(r"\s+", "", item).lower() in src_flat:
                continue
            if i == 0 and _grounded_quantity(item, src_spaced):
                continue
            found.add(item)
    return sorted(found)


# ── Commands ─────────────────────────────────────────────────────────────────

def load_runs(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def cmd_run(args, cases, equipment):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    runs_path = OUT_DIR / f"{args.tag}_runs.jsonl"
    done = {}
    for r in load_runs(runs_path):
        if not r.get("failed"):
            done[(r["case"], r["arm"])] = done.get((r["case"], r["arm"]), 0) + 1

    arms = ["on", "off"] if args.arm == "both" else [args.arm]
    # One entry per run still missing for each (case, arm).
    todo = [(c, a) for a in arms for c in cases
            for _ in range(max(0, args.runs - done.get((c["id"], a), 0)))]

    n = len(todo)
    print(f"\nGRAPH VALUE TEST — tag '{args.tag}', {len(cases)} case(s), arm(s): {', '.join(arms)}, "
          f"{args.runs} run(s) each")
    print(f"Already done: {sum(done.values())}   To run now: {n}")
    for model, per in TOKENS_PER_RUN.items():
        print(f"  estimated {model}: ~{n * per // 1000}K tokens (daily free quota 200K)")
    if not args.run:
        print("\nPreview only. Add --run to start.")
        return
    if n == 0:
        print("Nothing left to run. Next: --score")
        return

    import multi_agent as ma
    for i, (case, arm) in enumerate(todo, 1):
        print(f"\n[{i}/{n}] {case['id']} {case['name']} — graph {arm.upper()} ...", flush=True)
        rec = run_one(ma, case, equipment, arm)
        with runs_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        status = "FAILED (no report — will retry next time)" if rec["failed"] else f"ok, {rec['seconds']}s"
        print(f"    {status}  agents: {', '.join(rec['agents'])}  graph used: {rec['graph_used']}")
        if rec["failed"]:
            print(f"    tail: {rec['error_tail'][-200:]}")
    print(f"\nSaved to {runs_path}. When both arms are done: --score")


def cmd_score(args, cases):
    runs_path = OUT_DIR / f"{args.tag}_runs.jsonl"
    runs = [r for r in load_runs(runs_path) if not r.get("failed")]
    if not runs:
        sys.exit(f"No runs in {runs_path} yet.")
    cache_path = OUT_DIR / f"{args.tag}_judge_cache.json"
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
    from groq import Groq
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    by_case = {c["id"]: c for c in cases}
    results = []   # (case, arm, run_index, {check_id: bool|None}, unsupported)
    counter = {}
    for r in runs:
        case = by_case.get(r["case"])
        if not case:
            continue
        idx = counter.get((r["case"], r["arm"]), 0)
        counter[(r["case"], r["arm"])] = idx + 1
        marks = {}
        for ch in case["checks"]:
            if ch["kind"] == "code":
                marks[ch["id"]] = check_code(ch, r["report"])
            elif ch["kind"] == "rating":
                marks[ch["id"]] = check_rating(ch, r["report"])
            else:
                digest = hashlib.sha1(r["report"].encode("utf-8")).hexdigest()[:12]
                key = f"{r['case']}|{r['arm']}|{ch['id']}|{digest}"
                marks[ch["id"]] = check_judge(ch, r["report"], cache, key, client)
                cache_path.write_text(json.dumps(cache, indent=1), encoding="utf-8")
        results.append((r["case"], r["arm"], idx, marks, unsupported_specifics(r["report"], r["sources"])))
        print(f"  scored {r['case']} graph {r['arm']} run {idx + 1}")

    write_scorecard(args.tag, cases, results)


def write_scorecard(tag, cases, results):
    def arm_rows(arm):
        return [x for x in results if x[1] == arm]

    def totals(rows):
        vals = [v for _, _, _, m, _ in rows for v in m.values() if v is not None]
        return sum(vals), len(vals)

    lines = [f"# Graph value test — {tag}", "",
             f"Scored {dt.datetime.now():%Y-%m-%d %H:%M}. B = graph OFF (documents only), "
             "C = graph ON (documents + graph). Same questions, same pipeline.", ""]

    lines += ["## Headline", "", "| | Graph OFF (B) | Graph ON (C) |", "|---|---|---|"]
    cells = {}
    for arm in ("off", "on"):
        rows = arm_rows(arm)
        ok, n = totals(rows)
        inv = [len(u) for *_, u in rows]
        stable, total_checks = 0, 0
        for c in cases:
            per_run = [m for cid, a, _, m, _ in rows if cid == c["id"]]
            if len(per_run) < 2:
                continue
            for ch in c["checks"]:
                vals = [m.get(ch["id"]) for m in per_run if m.get(ch["id"]) is not None]
                if vals:
                    total_checks += 1
                    stable += len(set(vals)) == 1
        cells[arm] = {
            "facts": f"{ok}/{n} ({100 * ok // n if n else 0}%)" if n else "—",
            "unsup": f"{sum(inv) / len(inv):.1f} per report" if inv else "—",
            "consistent": f"{stable}/{total_checks}" if total_checks else "—",
            "runs": str(len(rows)),
        }
    for label, key in (("Required facts present", "facts"),
                       ("Specifics not in any source", "unsup"),
                       ("Checks identical across runs", "consistent"),
                       ("Reports scored", "runs")):
        lines.append(f"| {label} | {cells['off'][key]} | {cells['on'][key]} |")

    lines += ["", "## By case", "",
              "Each cell: runs that passed / runs scored.", ""]
    for c in cases:
        lines += [f"### {c['id']} {c['name']} — {c['tests']}", "",
                  f"> {c['incident']}", "",
                  "| Check | How | Graph OFF | Graph ON |", "|---|---|---|---|"]
        for ch in c["checks"]:
            row = []
            for arm in ("off", "on"):
                vals = [m.get(ch["id"]) for cid, a, _, m, _ in results if cid == c["id"] and a == arm]
                scored = [v for v in vals if v is not None]
                row.append(f"{sum(scored)}/{len(scored)}" + (" ?" if len(scored) < len(vals) else "") if vals else "—")
            label = ch.get("label") or ch.get("q")
            lines.append(f"| {label} | {ch['kind']} | {row[0]} | {row[1]} |")
        for arm in ("off", "on"):
            items = sorted({i for cid, a, _, _, u in results if cid == c["id"] and a == arm for i in u})
            if items:
                lines.append(f"\nNot in any source, graph {arm.upper()}: {', '.join(items[:12])}")
        lines.append("")

    lines += ["## How to read this", "",
              "- A check that passes with graph ON and fails with graph OFF is the graph's value.",
              "- A check that fails in both is a Phase 2 problem (how the orchestrator uses the evidence), not a graph problem.",
              "- 'Not in any source' lists specifics the report did not get from its inputs. Read them: some are harmless general knowledge, some are inventions.",
              "- Judge answers are cached; spot-check 2-3 reports yourself against the judge.",
              "- Six cases show a direction, not proof."]

    out = OUT_DIR / f"{tag}_scorecard.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nScorecard: {out}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", choices=["on", "off", "both"], default="both")
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--cases", default="")
    ap.add_argument("--tag", default="baseline")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--score", action="store_true")
    args = ap.parse_args()

    spec = json.loads(CASES_FILE.read_text(encoding="utf-8"))
    cases = spec["cases"]
    if args.cases:
        wanted = {c.strip() for c in args.cases.split(",")}
        cases = [c for c in cases if c["id"] in wanted]
    if args.score:
        cmd_score(args, cases)
    else:
        cmd_run(args, cases, spec["equipment"])


if __name__ == "__main__":
    main()
