"""
run_consistency.py — Phase 1 step 1.7: same question, three times — same answer?

WHAT THIS IS FOR (simple version)
    AI models are not perfectly repeatable: ask the same question twice and the
    wording — sometimes the substance — can change. For a plant-floor safety
    answer that matters. A test that passed ONCE might pass only 1 time in 3,
    and a single run cannot tell you which.

    This runs 8 hand-picked risky cases 3 times each, with the cache OFF (the
    cache would just replay the first answer), and reports for each case:
        3/3  steady pass      — trustworthy
        0/3  steady fail      — a real, repeatable bug (good: easy to fix and verify)
        1/3 or 2/3  FLAKY     — the dangerous kind: sometimes right, sometimes not
    For the two investigations it also lists the criticality rating each run
    gave — a safety rating that changes between runs is itself a failure.

THE 8 CASES AND WHY
    Ask suite       GF-SI-001   the Shift answer that looped 45 times — always, or once?
                    GF-QA-010   refusal under user pressure — does it ever cave?
                    GF-QA-009   half-real comparison — does it ever half-answer?
    Generated       G1-007      the "keep adjusting tension" trap
                    G3-003      shielding gas — hold the parts back
                    G2-010      burn-in instability is expected (passed once, known issue)
    Investigations  GF-INV-002  burn-in rated HIGH — every time?
                    GF-INV-003  gas rated CRITICAL — every time?

COST — run on a day you are not also running the full baseline
    About 50-60K tokens on gpt-oss-20b and ~30K on gpt-oss-120b (measured with
    evals/ops_report.py, step 1.6). Takes roughly 15-20 minutes.

RUN (from C:\\plantmind, with the app running: python app.py)
    venv\\Scripts\\python.exe evals\\run_consistency.py
    venv\\Scripts\\python.exe evals\\run_consistency.py --report-only
        -> re-print the report from the last run without calling anything
"""

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PF = ROOT / "evals" / "promptfoo"
OUT = ROOT / "evals" / "results"
PROMPTFOO = "promptfoo@0.123.1"  # pinned: a tool update must not change scores
REPEAT = 3

RUNS = [
    # (label, config file, description regex)
    ("ask",           "promptfooconfig.yaml", r"GF-SI-001|GF-QA-010|GF-QA-009"),
    ("generated",     "generated.yaml",       r"G1-007|G3-003|G2-010"),
    ("investigation", "investigate.yaml",     r"GF-INV-002|GF-INV-003"),
]

LEVELS = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]


def read_criticality(text):
    """Same logic as lib/criticality.js: first rating word after the heading line."""
    t = (text or "").upper()
    at = t.find("HOW CRITICAL IS IT")
    if at == -1:
        return None
    window = t[at:at + 400]
    start = window.find("\n")
    start = 0 if start == -1 else start
    hits = [(window.find(l, start), l) for l in LEVELS if window.find(l, start) != -1]
    return min(hits)[1] if hits else None


def run_suite(label, config, pattern):
    out = OUT / f"consistency_{label}.json"
    cmd = (f'npx --yes {PROMPTFOO} eval -c "{PF / config}" --env-file "{ROOT / ".env"}" '
           f'--filter-pattern "{pattern}" --repeat {REPEAT} --no-cache --no-table '
           f'-o "{out}"')
    print(f"\n>>> {label}: {pattern}  (x{REPEAT}, cache off)")
    # promptfoo exits non-zero when any test fails — that is expected here,
    # failures are the data. Only a missing output file means the run broke.
    subprocess.run(cmd, shell=True, cwd=ROOT)
    if not out.exists():
        sys.exit(f"promptfoo did not write {out} — check the output above.")
    return out


def summarise(paths):
    per_case = defaultdict(list)
    for label, path in paths:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        results = data.get("results", {})
        results = results.get("results", results) if isinstance(results, dict) else results
        for r in results:
            desc = (r.get("testCase") or {}).get("description", "?")
            failed = [
                (c.get("assertion") or {}).get("type", "?")
                for c in ((r.get("gradingResult") or {}).get("componentResults") or [])
                if not c.get("pass")
            ]
            output = (r.get("response") or {}).get("output") or ""
            per_case[desc].append({
                "pass": bool(r.get("success")),
                "failed_checks": failed,
                "criticality": read_criticality(output) if label == "investigation" else None,
                "error": r.get("error"),
            })
    return per_case


def report(per_case):
    print("\n" + "=" * 78)
    print("CONSISTENCY — each case run 3 times, cache off")
    print("=" * 78)
    flaky = 0
    rows = []
    for desc, runs in per_case.items():
        n, ok = len(runs), sum(r["pass"] for r in runs)
        if ok in (0, n):
            verdict = "steady PASS" if ok == n else "steady FAIL"
        else:
            verdict = "FLAKY"
            flaky += 1
        ratings = [r["criticality"] for r in runs if r["criticality"] is not None]
        rating_note = ""
        if ratings:
            rating_note = f"  ratings: {' / '.join(ratings)}"
            if len(set(ratings)) > 1:
                rating_note += "  <- RATING CHANGED BETWEEN RUNS"
        print(f"\n{ok}/{n}  {verdict:<12} {desc[:60]}{rating_note}")
        for i, r in enumerate(runs, 1):
            if not r["pass"]:
                why = r["error"] or ", ".join(r["failed_checks"]) or "?"
                why = " ".join(str(why).split())  # one line
                print(f"        run {i}: {why[:140]}{'...' if len(why) > 140 else ''}")
        rows.append({"case": desc, "passed": ok, "runs": n, "verdict": verdict,
                     "ratings": ratings, "details": runs})

    print(f"\n{len(per_case)} cases, {flaky} flaky.")
    if flaky:
        print("Flaky = sometimes right, sometimes wrong. A single test run cannot be "
              "trusted for these; always judge them over several runs.")
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report-only", action="store_true",
                    help="re-print the report from the last run's saved files")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    if args.report_only:
        paths = [(l, OUT / f"consistency_{l}.json") for l, _, _ in RUNS]
        missing = [str(p) for _, p in paths if not p.exists()]
        if missing:
            sys.exit(f"No saved run found: {missing}")
    else:
        paths = [(l, run_suite(l, c, p)) for l, c, p in RUNS]

    rows = report(summarise(paths))
    stamp = dt.datetime.now().strftime("%Y-%m-%d_%H%M")
    (OUT / f"consistency_report_{stamp}.json").write_text(
        json.dumps({"run_at": stamp, "repeat": REPEAT, "cases": rows},
                   indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved evals/results/consistency_report_{stamp}.json")


if __name__ == "__main__":
    main()
