"""
run_baseline.py — Phase 1 step 1.9: one command, one dated scorecard.

WHAT THIS IS FOR (simple version)
    Every later phase (graph rebuild, token cuts, chunking, LangGraph) must be
    judged against a fixed "before" number. This produces it: it runs every
    eval we have, the same way every time, and writes one scorecard.

WHAT IT DOES, IN ORDER
    1. Health check — Supabase, Pinecone and Neo4j must all be up. If not, it
       STOPS. A paused database must never show up as a quality drop.
    2. Budget check — reads tokens already used today and stops if this run
       would push gpt-oss-20b past 95% of its 200K daily quota.
    3. Runs the three promptfoo suites (fresh answers, cache OFF — a baseline
       must describe today's app, not replay old answers):
           ask (13)  ·  generated (18)  ·  investigation (4)
    4. Runs the retrieval eval (search only, free).
    5. Runs the ops report for exactly this run's time window.
    6. Writes the scorecard: every failure is marked KNOWN (listed in
       evals/known_issues.json, with the phase that fixes it) or NEW (needs
       triage). A known issue that suddenly PASSES is flagged too.

COST (measured in step 1.6 — this is the expensive one, run it deliberately)
    ~115K tokens on gpt-oss-20b (58% of a day), ~22K on gpt-oss-120b, plus the
    Qwen judge on its own quota. About 15-20 minutes.
    Do NOT run it on the same day as run_consistency.py.

RUN (from C:\\plantmind, with the app running: python app.py)
    venv\\Scripts\\python.exe evals\\run_baseline.py
    venv\\Scripts\\python.exe evals\\run_baseline.py --skip-investigations
        -> ~95K cheaper-ish on 20b, skips the 4 investigation cases
    venv\\Scripts\\python.exe evals\\run_baseline.py --force
        -> run even if the budget check says no (you have been warned)

OUTPUT
    evals/baselines/baseline_<date>_<time>.md    <- read this one
    evals/baselines/baseline_<date>_<time>.json  <- the full detail
"""

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
PF = ROOT / "evals" / "promptfoo"
RESULTS = ROOT / "evals" / "results"
BASELINES = ROOT / "evals" / "baselines"
KNOWN = ROOT / "evals" / "known_issues.json"
APP = "http://localhost:5000"

PROMPTFOO = "promptfoo@0.123.1"   # pinned: a tool update must not move the scores

SUITES = [
    # (label, config, tests, est. tokens on gpt-oss-20b, est. on gpt-oss-120b)
    ("ask",           "promptfooconfig.yaml", 13, 39_000, 0),
    ("generated",     "generated.yaml",       18, 54_000, 0),
    ("investigation", "investigate.yaml",      4, 22_000, 22_000),
]
FAST, DEEP = "openai/gpt-oss-20b", "openai/gpt-oss-120b"
BUDGET_CEILING = 0.95


def step(msg):
    print(f"\n{'=' * 78}\n{msg}\n{'=' * 78}")


# ─────────────────────────────────────────────────────────────────────────────
# 1-2. Pre-flight
# ─────────────────────────────────────────────────────────────────────────────
def preflight(suites, force):
    step("1. Health check")
    try:
        h = requests.get(f"{APP}/api/health", timeout=60).json()
    except requests.RequestException:
        sys.exit("The app is not reachable on localhost:5000 — start it with: python app.py")

    for name, c in h.get("checks", {}).items():
        print(f"  {name:<10} {c.get('status'):<6} {c.get('detail') or c.get('error', '')}")
    if h.get("status") != "ok":
        sys.exit(f"\nSTOPPED: health is '{h.get('status')}'. A baseline taken with a service "
                 "down would record an outage as a quality result. Fix it and re-run.")

    step("2. Budget check")
    today = h.get("tokens_today", {})
    ok = True
    for model, idx in ((FAST, 3), (DEEP, 4)):
        used = (today.get(model) or {}).get("used", 0)
        limit = (today.get(model) or {}).get("daily_limit", 200_000)
        est = sum(s[idx] for s in suites)
        after = (used + est) / limit
        flag = "  <- TOO HIGH" if after > BUDGET_CEILING else ""
        print(f"  {model:<22} used today {used:>7,}  + this run ~{est:>7,}  = {after:>4.0%} of quota{flag}")
        ok = ok and after <= BUDGET_CEILING
    if not ok and not force:
        sys.exit("\nSTOPPED: this run would go past 95% of a model's daily quota, leaving "
                 "nothing for demos and risking rate-limit failures mid-run (which would "
                 "look like quality failures). Run tomorrow (quota resets 00:00 UTC), use "
                 "--skip-investigations, or --force.")
    return h


# ─────────────────────────────────────────────────────────────────────────────
# 3. Suites
# ─────────────────────────────────────────────────────────────────────────────
def run_suite(label, config, stamp):
    out = RESULTS / f"baseline_{label}_{stamp}.json"
    # Two at a time, not promptfoo's default of four. Four /ask questions at
    # once went past Groq's 8,000 tokens-per-minute limit and one answer came
    # back as a 429 — which then looked like a quality failure.
    cmd = (f'npx --yes {PROMPTFOO} eval -c "{PF / config}" --env-file "{ROOT / ".env"}" '
           f'--no-cache --no-table -j 2 -o "{out}"')
    print(f"\n>>> {label}  ({config})")
    # promptfoo exits non-zero when tests fail — expected; failures are data.
    subprocess.run(cmd, shell=True, cwd=ROOT)
    if not out.exists():
        sys.exit(f"STOPPED: promptfoo wrote no results for {label} — see the output above.")
    data = json.loads(out.read_text(encoding="utf-8"))
    res = data.get("results", {})
    return res.get("results", res) if isinstance(res, dict) else res


def classify(label, results, known):
    rows = []
    for r in results:
        desc = (r.get("testCase") or {}).get("description", "?")
        grading = r.get("gradingResult")
        output = str((r.get("response") or {}).get("output") or "")
        # An app-side failure (rate limit, outage) comes back as ordinary answer
        # text, so promptfoo scores it as a quality FAIL and the scorecard
        # reported a NEW bug that never existed. Judge the answer, not the
        # weather: these are ERRORs, and they are re-run, not triaged.
        broke = ("rate limit" in output.lower() or "429" in output[:60]
                 or output.startswith("Error: ") or "temporarily unavailable" in output.lower())
        if r.get("success"):
            status = "PASS"
        elif broke or grading is None or r.get("failureReason") == 2:
            status = "ERROR"          # the call itself failed — not a quality result
        else:
            status = "FAIL"
        issue = next((k for k in known if k["match"] in desc), None)
        reasons = [
            " ".join(str(c.get("reason") or "").split())[:160]
            for c in ((grading or {}).get("componentResults") or []) if not c.get("pass")
        ]
        rows.append({
            "suite": label, "test": desc, "status": status,
            "known_issue": issue["phase"] if issue else None,
            "issue": issue["issue"] if issue else None,
            "reasons": reasons or ([str(r.get("error"))[:160]] if r.get("error") else []),
            "latency_ms": r.get("latencyMs"),
        })
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# 4-5. Retrieval + ops
# ─────────────────────────────────────────────────────────────────────────────
def run_retrieval():
    step("4. Retrieval eval (search only, zero Groq tokens)")
    subprocess.run([sys.executable, str(ROOT / "evals" / "retrieval_eval.py")], cwd=ROOT)
    files = sorted((ROOT / "evals" / "retrieval_results").glob("retrieval_*.json"))
    return json.loads(files[-1].read_text(encoding="utf-8"))["scores"] if files else None


def run_ops(since_iso):
    step("5. Ops report — cost and speed of this run")
    p = subprocess.run([sys.executable, str(ROOT / "evals" / "ops_report.py"), "--since", since_iso],
                       cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    print(p.stdout)
    return p.stdout.strip()


# ─────────────────────────────────────────────────────────────────────────────
# 6. Scorecard
# ─────────────────────────────────────────────────────────────────────────────
def scorecard(rows, retrieval, ops_text, health, stamp, started):
    step("6. Scorecard")
    suites = {}
    for r in rows:
        s = suites.setdefault(r["suite"], {"PASS": 0, "FAIL": 0, "ERROR": 0})
        s[r["status"]] += 1

    new_fail = [r for r in rows if r["status"] == "FAIL" and not r["known_issue"]]
    known_fail = [r for r in rows if r["status"] == "FAIL" and r["known_issue"]]
    errors = [r for r in rows if r["status"] == "ERROR"]
    known_pass = [r for r in rows if r["status"] == "PASS" and r["known_issue"]]

    total = len(rows)
    passed = sum(1 for r in rows if r["status"] == "PASS")

    md = [f"# PlantMind baseline — {stamp}", "",
          f"Started {started} UTC · promptfoo {PROMPTFOO.split('@')[1]} · "
          f"models: {health.get('models', {}).get('fast')} / {health.get('models', {}).get('deep')} · "
          f"judge: qwen/qwen3.8-27b", "",
          "## Score", "",
          "| Suite | Pass | Fail | Error |", "|---|---|---|---|"]
    for name, s in suites.items():
        md.append(f"| {name} | {s['PASS']} | {s['FAIL']} | {s['ERROR']} |")
    md += ["", f"**Total: {passed}/{total} pass ({passed / total:.0%})** · "
               f"{len(known_fail)} known failures · **{len(new_fail)} NEW failures** · "
               f"{len(errors)} errors", ""]

    if retrieval:
        md += ["## Retrieval (did search find the right chunk)", "",
               f"Found in top 12: {retrieval['found_in_top_12']}/{retrieval['n']} · "
               f"top 3: {retrieval['found_in_top_3']}/{retrieval['n']} · "
               f"MRR {retrieval['mrr']}", ""]

    def section(title, items, show_issue):
        out = [f"## {title} ({len(items)})", ""]
        for r in items:
            out.append(f"- **{r['test']}** [{r['suite']}]")
            if show_issue:
                out.append(f"  - {r['known_issue']}: {r['issue']}")
            for why in r["reasons"][:2]:
                out.append(f"  - {why}")
        return out + [""]

    md += section("NEW failures — triage each: real bug, or wrong check?", new_fail, False)
    md += section("Errors — the call failed, not the quality (rate limit? outage?)", errors, False)
    md += section("Known failures — expected, fixed in a later phase", known_fail, True)
    if known_pass:
        md += section("Known issues that PASSED — fix landed, or lucky? Confirm with run_consistency.py",
                      known_pass, True)
    md += ["## Cost and speed (ops report)", "", "```", ops_text, "```", ""]

    BASELINES.mkdir(parents=True, exist_ok=True)
    md_path = BASELINES / f"baseline_{stamp}.md"
    md_path.write_text("\n".join(md), encoding="utf-8")
    (BASELINES / f"baseline_{stamp}.json").write_text(json.dumps({
        "stamp": stamp, "started_utc": started, "promptfoo": PROMPTFOO,
        "models": health.get("models"), "suites": suites,
        "total": total, "passed": passed, "retrieval": retrieval,
        "new_failures": len(new_fail), "known_failures": len(known_fail),
        "errors": len(errors), "rows": rows,
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"  Total {passed}/{total} pass · {len(known_fail)} known · "
          f"{len(new_fail)} NEW · {len(errors)} errors")
    for r in new_fail:
        print(f"  NEW: {r['test']}")
    print(f"\n  Scorecard: {md_path}")


def main():
    ap = argparse.ArgumentParser(description="Run every eval and write a dated scorecard.")
    ap.add_argument("--skip-investigations", action="store_true")
    ap.add_argument("--force", action="store_true", help="ignore the budget check")
    args = ap.parse_args()

    suites = [s for s in SUITES if not (args.skip_investigations and s[0] == "investigation")]
    started = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    stamp = dt.datetime.now().strftime("%Y-%m-%d_%H%M")
    RESULTS.mkdir(parents=True, exist_ok=True)

    health = preflight(suites, args.force)
    known = json.loads(KNOWN.read_text(encoding="utf-8"))["issues"]

    step("3. promptfoo suites (fresh answers, cache off)")
    rows = []
    for label, config, *_ in suites:
        rows += classify(label, run_suite(label, config, stamp), known)

    retrieval = run_retrieval()
    ops_text = run_ops(started)
    scorecard(rows, retrieval, ops_text, health, stamp, started)


if __name__ == "__main__":
    main()
