"""
graph_value_test.py — does the knowledge graph actually make reports better?

WHAT THIS IS (simple version)
    An ablation test. The same questions about one machine go through the
    real investigation pipeline twice (cases file per machine: --file):
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

    Cases and checks: evals/graph_value_cases.json (WM-101, locked 2026-09-25)
    and evals/fl101/graph_value_cases.json (FL-101, the second machine). Each
    file names its machine; any machine with a cases file works the same way.

COST — why it runs one version at a time
    One investigation ~5.5K tokens on gpt-oss-20b and ~5K on gpt-oss-120b,
    each with a 200K/day free quota. 18 investigations (one version) is about
    half a day's quota; both versions in one day would use nearly all of it.
    Results are saved after EVERY run, so re-running resumes where it stopped.

RUN (from C:\\plantmind — the Flask app does NOT need to be running)
    venv\\Scripts\\python.exe evals\\graph_value_test.py                 <- preview
    venv\\Scripts\\python.exe evals\\graph_value_test.py --arm on --run  <- day 1
    venv\\Scripts\\python.exe evals\\graph_value_test.py --arm off --run <- day 2
    venv\\Scripts\\python.exe evals\\graph_value_test.py --arm facts --run <- separation run:
        graph facts to the report, searches picked as with no graph (3rd scorecard column)
    venv\\Scripts\\python.exe evals\\graph_value_test.py --score         <- scorecard
    Options: --runs N (default 3), --cases GV-01,GV-03, --tag NAME (results
    file name; default: the cases file's default_tag, else "baseline"),
    --file PATH (another machine's cases, e.g. evals/fl101/graph_value_cases.json).

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
# Each arm = the eval switches it sets (read per call by multi_agent.py).
#   off   documents only: no graph at all
#   on    documents + graph: the graph hands its facts to the writer AND forces searches
#   facts separation run: the graph hands its facts to the writer, but the searches
#         are picked exactly as with no graph (graph chapter, 2026-10-05)
ARMS = {
    "off":   {"PM_EVAL_DISABLE_GRAPH": "true", "PM_EVAL_GRAPH_NO_ROUTING": ""},
    "on":    {"PM_EVAL_DISABLE_GRAPH": "",     "PM_EVAL_GRAPH_NO_ROUTING": ""},
    "facts": {"PM_EVAL_DISABLE_GRAPH": "",     "PM_EVAL_GRAPH_NO_ROUTING": "true"},
}
ARM_ORDER = ["off", "facts", "on"]
ARM_LABEL = {"off": "Graph OFF (B)", "facts": "Graph facts only (F)", "on": "Graph ON (C)"}
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
        # For component evaluation (which part failed?): what each search
        # returned and what each specialist made of it, the graph text, and
        # which fault the graph matched and how sure it was.
        sink["specialists"] = [{"agent": r.get("agent", ""),
                                "search": str(r.get("raw_data", ""))[:6000],
                                "findings": str(r.get("findings", ""))}
                               for r in specialist_results or []]
        gc = graph_context or {}
        sink["graph_text"] = gc.get("chain_text", "") if gc.get("has_data") else ""
        sink["matched_faults"] = gc.get("matched_faults", [])
        sink["match_confidence"] = gc.get("match_confidence", "")
        sink["match_method"] = gc.get("match_method", "")
        ma.LAST_WRITER_EVIDENCE = ""
        report = real(incident, specialist_results, graph_context=graph_context,
                      equipment_id=equipment_id)
        # C2 switch: the pieces the writer was ACTUALLY given (it fills only the
        # spare room under the per-minute limit) are writer input too.
        sink["evidence"] = getattr(ma, "LAST_WRITER_EVIDENCE", "")
        if sink["evidence"]:
            sink["sources"] += "\n" + sink["evidence"]
        return report

    ma.run_orchestrator = wrapper
    return real


_app = None


def find_machine(text):
    """
    The machine the Investigate page would pick from these words, with no
    machine selected: the app's own finder (tag in the text, else plain words
    such as "the filler", plurals and small typos allowed). None = the page
    would show "No matching equipment manual found".
    """
    global _app
    if _app is None:
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):   # app.py prints on import
            import app as _a
        _app = _a
    return _app.extract_equipment_id(text) or _app.resolve_equipment_reference(text)


def run_one(ma, case, equipment, arm):
    os.environ.update(ARMS[arm])
    # equipment "find": no machine is given, it is found from the words.
    machine = find_machine(case["incident"]) if equipment == "find" else equipment
    sink = {}
    real = _capture_orchestrator_inputs(ma, sink)
    real_check = ma.check_report
    real_conf = ma.assess_confidence

    def check_wrapper(report, graph_context, specialist_results):
        out, events = real_check(report, graph_context, specialist_results)
        sink["guard_events"] = events
        return out, events

    def conf_wrapper(*a, **kw):
        result = real_conf(*a, **kw)
        sink["confidence"] = result
        return result

    ma.check_report = check_wrapper
    ma.assess_confidence = conf_wrapper
    started = time.time()
    try:
        streamed = "".join(ma.investigate_incident(case["incident"], equipment_id=machine))
    finally:
        ma.run_orchestrator = real
        ma.check_report = real_check
        ma.assess_confidence = real_conf
        for name in ARMS[arm]:
            os.environ.pop(name, None)
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
        "guard_events": sink.get("guard_events", []),
        # Component evaluation: each part's output for this run.
        "machine": machine,
        "matched_faults": sink.get("matched_faults", []),
        "match_confidence": sink.get("match_confidence", ""),
        "match_method": sink.get("match_method", ""),
        "confidence": sink.get("confidence", {}),
        "specialists": sink.get("specialists", []),
        "graph_text": sink.get("graph_text", ""),
        # C2: was the writer also given the pieces the specialists read?
        "writer_evidence": bool(getattr(ma, "WRITER_GETS_EVIDENCE", False)),
        "evidence": sink.get("evidence", ""),
        "seconds": round(time.time() - started),
        "at": dt.datetime.now().isoformat(timespec="seconds"),
    }


# ── Marking ──────────────────────────────────────────────────────────────────

def _norm(text):
    """
    Plain characters before any check, exactly like evals/promptfoo/lib/normalise.js:
    models write dashes, quotes and spaces that LOOK plain but aren't, and a
    correct answer must never fail on a non-breaking hyphen. (Was a 3-character
    version that also left the en dash as it was.)
    """
    return (re.sub(r"[‐-―−]", "-", text or "")
            .translate({0x2018: "'", 0x2019: "'", 0x201B: "'", 0x201C: '"', 0x201D: '"',
                        0x00A0: " ", 0x2007: " ", 0x2009: " ", 0x202F: " "})
            .replace("…", "..."))


def check_code(check, report):
    """
    'all': every pattern must appear. 'none': no pattern may appear.
    'section': look only inside that report section (e.g. the repair steps,
    where an unreviewed tip may not appear, although naming it as a lead to
    check under diagnosis is allowed).
    """
    text = _norm(report)
    if check.get("section"):
        at = text.find(check["section"])
        end = text.find("PLANT MANAGER SUMMARY", at)
        text = text[at:end if end != -1 else len(text)] if at != -1 else ""
    return (all(re.search(p, text, re.I) for p in check.get("all", []))
            and not any(re.search(p, text, re.I) for p in check.get("none", [])))


def guard_events_for(r, case, ctx_cache, tip_cache, equipment):
    """
    Guardrail events for a report: saved at run time since Phase 2a step 5;
    for older reports, worked out now by running the same check on the saved
    report (free: one Pinecone search per case, no AI calls).
    """
    if "guard_events" in r:
        return r["guard_events"]
    import multi_agent as ma
    import knowledge_graph as kg
    if case["id"] not in tip_cache:
        text, _ = ma.search_expert_fixes(f"fix for {equipment} {case['incident'][:100]}",
                                         equipment_filter=equipment)
        tip_cache[case["id"]] = [b for b in text.split("\n\n---\n\n") if ma.REVIEW_UNREVIEWED in b]
        ctx_cache[case["id"]] = kg.get_fault_chain(equipment, incident_text=case["incident"])
    ctx = ctx_cache[case["id"]] if r["arm"] in ("on", "facts") else None
    _, events = ma.check_report(r["report"], ctx, [{"unreviewed": tip_cache[case["id"]]}])
    return events


def check_rating(check, report):
    text = _norm(report)
    at = text.find("HOW CRITICAL IS IT")
    if at == -1:
        return False
    m = re.search(r"\b(CRITICAL|HIGH|MEDIUM|LOW)\b", text[at + len("HOW CRITICAL IS IT"):])
    allowed = check.get("expect_any") or [check["expect"]]   # e.g. ["LOW", "MEDIUM"]
    return bool(m) and m.group(1) in allowed


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
    # Units: welding (WM-101) and bottling (FL-101: ml, bottles per minute).
    (r"\b\d+(?:\.\d+)?(?:\s*(?:–|-|to)\s*\d+(?:\.\d+)?)?\s*(?:V|volts?|bar|m/min|mm|ml|L/min|°C|degrees|bottles per minute|bpm|minutes?|mins?|seconds?|sec|hours?|hrs?)\b", True),
    # Part and document codes of any machine (GSW-DROLL-08, SEAL-FV-24, GBP-001).
    # Was GSW- only, so an invented filler part number would go uncounted.
    (r"\b[A-Z]{2,5}-[A-Z0-9]{1,6}(?:-[A-Z0-9]+)*\b", False),
    (r"\b(?:NCR|WI|SOP)-[A-Z0-9][A-Z0-9-]*\b", False),
    (r"\bSection\s+\d+(?:\.\d+)?\b", True),
]


UNIT_FAMILY = [
    (r"^(v|volts?)$", r"(v\b|volt)"), (r"^bar$", r"bar"), (r"^m/min$", r"m/min"),
    (r"^mm$", r"mm"), (r"^ml$", r"ml\b"), (r"^bpm$", r"(bpm|bottles per minute)"),
    (r"^l/min$", r"l/min"), (r"^(°c|degrees)$", r"(°c|degree)"),
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
    # The C2 switch is set by --evidence only, never by .env, so a results file
    # always holds one setting. Refuse to mix settings in one file.
    ma.WRITER_GETS_EVIDENCE = args.evidence
    saved = {r.get("writer_evidence", False) for r in load_runs(runs_path)}
    if saved and saved != {args.evidence}:
        print(f"\n{runs_path.name} already holds runs with writer evidence = {saved}. "
              f"Use another --tag for evidence = {args.evidence}.")
        return
    print(f"Writer also gets the pieces the specialists read (C2 switch): "
          f"{'ON' if args.evidence else 'OFF'}")
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


def cmd_score(args, cases, equipment):
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
    guards = []    # guardrail events per report, same order as results
    ctx_cache, tip_cache = {}, {}
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
        guards.append((r["arm"], guard_events_for(r, case, ctx_cache, tip_cache, equipment)))
        print(f"  scored {r['case']} graph {r['arm']} run {idx + 1}")

    write_scorecard(args.tag, cases, results, guards)


def write_scorecard(tag, cases, results, guards=()):
    def arm_rows(arm):
        return [x for x in results if x[1] == arm]

    def totals(rows):
        vals = [v for _, _, _, m, _ in rows for v in m.values() if v is not None]
        return sum(vals), len(vals)

    # The separation arm gets a column only when it was run (older scorecards unchanged).
    arms = [a for a in ARM_ORDER if a != "facts" or arm_rows("facts")]
    head = "| " + " | ".join(ARM_LABEL[a] for a in arms) + " |"
    lines = [f"# Graph value test — {tag}", "",
             f"Scored {dt.datetime.now():%Y-%m-%d %H:%M}. B = graph OFF (documents only), "
             "C = graph ON (documents + graph). Same questions, same pipeline.", ""]
    if "facts" in arms:
        lines += ["F = separation run: the graph's facts go to the report, but the searches are picked "
                  "as with no graph. B → F = value of the facts; F → C = extra value of the searches "
                  "the graph forces.", ""]

    lines += ["## Headline", "", "| " + head, "|---" * (len(arms) + 1) + "|"]
    cells = {}
    for arm in arms:
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
        g = [ev for a, ev in guards if a == arm]
        tipped = sum(any("operator tip" in e or "operator claim" in e for e in ev) for ev in g)
        raised = sum(any(e.startswith("criticality raised") for e in ev) for ev in g)
        cells[arm]["tips"] = f"{tipped}/{len(g)}" if g else "—"
        cells[arm]["raised"] = f"{raised}/{len(g)}" if g else "—"
    for label, key in (("Required facts present", "facts"),
                       ("Specifics not in any source", "unsup"),
                       ("Checks identical across runs", "consistent"),
                       ("Unreviewed tip used as an instruction (lower is better)", "tips"),
                       ("Rating raised by the safety floor", "raised"),
                       ("Reports scored", "runs")):
        lines.append(f"| {label} | " + " | ".join(cells[a][key] for a in arms) + " |")

    lines += ["", "## By case", "",
              "Each cell: runs that passed / runs scored.", ""]
    for c in cases:
        lines += [f"### {c['id']} {c['name']} — {c['tests']}", "",
                  f"> {c['incident']}", "",
                  "| Check | How " + head, "|---|---" + "|---" * len(arms) + "|"]
        for ch in c["checks"]:
            row = []
            for arm in arms:
                vals = [m.get(ch["id"]) for cid, a, _, m, _ in results if cid == c["id"] and a == arm]
                scored = [v for v in vals if v is not None]
                row.append(f"{sum(scored)}/{len(scored)}" + (" ?" if len(scored) < len(vals) else "") if vals else "—")
            label = ch.get("label") or ch.get("q")
            lines.append(f"| {label} | {ch['kind']} | " + " | ".join(row) + " |")
        for arm in arms:
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
    ap.add_argument("--arm", choices=["on", "off", "both", "facts"], default="both",
                    help="facts = separation run: graph facts to the writer, searches picked as with no graph")
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--cases", default="")
    ap.add_argument("--tag", default=None)
    ap.add_argument("--file", default=str(CASES_FILE),
                    help="cases file; each file names its machine")
    ap.add_argument("--evidence", action="store_true",
                    help="C2 switch: the writer also gets the pieces the specialists read")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--score", action="store_true")
    args = ap.parse_args()

    spec = json.loads(Path(args.file).read_text(encoding="utf-8"))
    cases = spec["cases"]
    args.tag = args.tag or spec.get("default_tag", "baseline")
    # A cases file may write its checkers ONCE for every case (the teaching
    # set: same 5-line key for all 3 wordings), and keep its own results folder.
    for c in cases:
        c.setdefault("checks", spec.get("checks", []))
    if spec.get("out_dir"):
        global OUT_DIR
        OUT_DIR = ROOT / spec["out_dir"]
    if args.cases:
        wanted = {c.strip() for c in args.cases.split(",")}
        cases = [c for c in cases if c["id"] in wanted]
    if args.score:
        cmd_score(args, cases, spec["equipment"])
    else:
        cmd_run(args, cases, spec["equipment"])


if __name__ == "__main__":
    main()
