"""
export_trace.py - save one LangSmith trace to a file, with people's names removed.

Read-only: it fetches a finished trace from LangSmith and writes one JSON file.
No Groq tokens, no Pinecone, no changes in LangSmith, no app code touched.
The file keeps each step's name, nesting, times, tokens, input and output.
It leaves out metadata (hosts, environment details), so no keys reach the file.

Usage:
  venv\\Scripts\\python.exe evals\\export_trace.py
  venv\\Scripts\\python.exe evals\\export_trace.py --trace <id> --label <name>
  venv\\Scripts\\python.exe evals\\export_trace.py --selftest      <- name removal only, offline
"""
import argparse
import csv
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)

TRACE = "01a1b1d4-ecfe-70f3-b27d-f933872cb3cf"      # final-1106-r2, question TC5
LABEL = "final-1106-r2-TC5"
OUT_DIR = ROOT / "evals" / "fl101" / "results"
FACT = re.compile(r"10 minutes|10-minute", re.I)    # the fact the summary follows
NAME_MARK = "[name removed]"
SPACE = r"[   ]"


def known_names():
    """Everyone named in the demo data: the shift logs' operator column, plus 'Approved by' lines."""
    names = set()
    for f in (ROOT / "demo_data" / "fl101" / "shift_logs").glob("*.csv"):
        with open(f, encoding="utf-8", errors="ignore", newline="") as fh:
            names.update(row["operator"].strip() for row in csv.DictReader(fh) if row.get("operator"))
    for f in (ROOT / "demo_data" / "fl101").glob("*.txt"):
        names.update(m.strip() for m in re.findall(r"—\s*([A-Z]\. [A-Z][\w'-]+)", f.read_text(encoding="utf-8")))
    return {n for n in names if n}


def make_scrubber(names):
    """Names from the data, plus any 'K. Brandt' shape the AI may have copied or respelled."""
    known = [SPACE.join(re.escape(p) for p in n.split()) for n in sorted(names, key=len, reverse=True)]
    shape = rf"(?<!position )\b[A-Z]\.{SPACE}?[A-Z][a-z]+(?:-[A-Z][a-z]+)?\b"   # not "position B. Restarted"
    pattern = re.compile("|".join(known + [shape]))
    removed = set()

    def swap(match):
        removed.add(match.group())
        return NAME_MARK

    def scrub(value):
        if isinstance(value, str):
            return pattern.sub(swap, value)
        if isinstance(value, list):
            return [scrub(v) for v in value]
        if isinstance(value, dict):
            return {k: scrub(v) for k, v in value.items()}
        return value
    scrub.removed = removed
    return scrub


def clean_step(run, scrub):
    seconds = None
    if run.start_time and run.end_time:
        seconds = round((run.end_time - run.start_time).total_seconds(), 2)
    return {
        "id": str(run.id),
        "parent_id": str(run.parent_run_id) if run.parent_run_id else None,
        "order": run.dotted_order,
        "name": run.name,
        "type": run.run_type,
        "start": run.start_time.isoformat() if run.start_time else None,
        "seconds": seconds,
        "tokens": {"input": run.prompt_tokens, "output": run.completion_tokens, "total": run.total_tokens},
        "error": scrub(run.error) if run.error else None,
        "input": scrub(json.loads(json.dumps(run.inputs, default=str))),
        "output": scrub(json.loads(json.dumps(run.outputs, default=str))),
    }


def summary(steps):
    """Print the tree, with how often the followed fact appears in each step's input and output."""
    depth = {}
    print(f"\n{'step':<46}{'type':<11}{'sec':>7}{'tokens':>8}  fact in/out")
    for s in steps:
        depth[s["id"]] = depth.get(s["parent_id"], -1) + 1
        name = "  " * depth[s["id"]] + s["name"]
        count = lambda v: len(FACT.findall(json.dumps(v, ensure_ascii=False)))
        sec = "" if s["seconds"] is None else s["seconds"]
        print(f"{name[:45]:<46}{s['type']:<11}{sec:>7}{(s['tokens']['total'] or ''):>8}  {count(s['input'])}/{count(s['output'])}")


def selftest():
    names = known_names()
    scrub = make_scrubber(names)
    assert names, "no names found in the demo data"
    sample = {"a": f"Approved by: {sorted(names)[0]}", "b": ["Notify K. Brandt today"], "c": 5,
              "d": "Run the sanitation rinse for 10 minutes. FL-101 Step 9. Moved to position B. Restarted."}
    out = scrub(sample)
    assert NAME_MARK in out["a"] and NAME_MARK in out["b"][0], out
    assert out["c"] == 5 and out["d"] == sample["d"], out
    print(f"self-test passed: {len(names)} names known, real text left alone")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--trace", default=TRACE)
    ap.add_argument("--label", default=LABEL)
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        selftest()
        return

    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    from langsmith import Client

    project = os.getenv("LANGSMITH_PROJECT", "plantmind")
    runs = list(Client().list_runs(project_name=project, trace_id=args.trace))
    if not runs:
        sys.exit(f"No trace {args.trace} in project '{project}'. It may have expired: LangSmith may not keep traces forever.")

    scrub = make_scrubber(known_names())
    steps = sorted((clean_step(r, scrub) for r in runs), key=lambda s: s["order"] or "")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"trace_{args.label}.json"
    path.write_text(json.dumps({"trace_id": args.trace, "label": args.label, "project": project,
                                "note": "Exported from LangSmith. People's names removed. Metadata left out.",
                                "steps": steps}, indent=1, ensure_ascii=False), encoding="utf-8")
    summary(steps)
    print(f"\nSaved {len(steps)} steps to {path.relative_to(ROOT)}")
    print(f"Removed as names (check none is a real word): {sorted(scrub.removed) or 'none'}")


if __name__ == "__main__":
    main()
