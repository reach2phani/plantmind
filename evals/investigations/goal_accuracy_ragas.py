"""
goal_accuracy_ragas.py - did the operator end up able to act correctly and safely?

The SETTINGS live in heldout-v1/goal_accuracy.json (locked): 23 goal checks taken
from the answer key in evals/fl101/HELDOUT.md. The judging is RAGAS 0.4.3
AgentGoalAccuracyWithReference's own two steps, with its prompts unchanged:
  1. once per scenario: read the conversation (operator's question + PlantMind's
     answer) and write down the user goal and the END STATE   (saved for a person)
  2. once per judge check: compare the check's desired outcome with that end
     state: 1 = same, 0 = different (with RAGAS's reason)
Rating checks are decided by CODE (run_record.criticality), not by the judge.

This script only applies the settings: it stops if they, their lock or the RAGAS
version differ from what it knows. It reads the SAVED run (snapshot), so PlantMind
is not run again. It also picks, with seed 2026, the one passing judge check per
scenario that a person must look at.

Modes (cost goes up from top to bottom):
  --dry-run   build the conversations, print their size, call nothing        (free)
  --smoke     one tiny made-up example, to prove qwen + RAGAS work together (a few hundred tokens)
  (default)   the cases in --cases, default all five                         (judge tokens; ask first)

Usage (from C:\\plantmind):
  venv\\Scripts\\python.exe evals\\investigations\\goal_accuracy_ragas.py --dry-run
  venv\\Scripts\\python.exe evals\\investigations\\goal_accuracy_ragas.py --smoke
  venv\\Scripts\\python.exe evals\\investigations\\goal_accuracy_ragas.py --cases H1 H2 H3 H4 H5
"""
import argparse
import asyncio
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))       # repo root, for run_record
from retrieval_recall import fingerprint, HERE, SNAP  # noqa: E402
from faithfulness_ragas import strip_meta, remove_step_labels, with_limit_wait, REPLY_LIMIT, JUDGE_ATTEMPTS  # noqa: E402
import factual_correctness_ragas as fc  # noqa: E402  same judge client set-up
from run_record import criticality  # noqa: E402  the same rating reader the rest of the evals use

ROOT = HERE.parent.parent.parent
NAME = "goal_accuracy"
KNOWN = {
    "metric": NAME,
    "evaluator": {"tool": "ragas", "ragas_version": "0.4.3",
                  "metric_class": "ragas.metrics.collections.AgentGoalAccuracyWithReference",
                  "prompts": "RAGAS built-in InferGoalOutcomePrompt and CompareOutcomePrompt, unchanged",
                  "judge_model": "qwen/qwen3.8-27b", "judge_provider": "groq",
                  "temperature": 0, "reasoning_format": "hidden"},
    "score": "checks passed / all checks",
    "prep": {"remove_step_labels": True},
}
RATING_ORDER = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
SAMPLE_SEED = 2026


def check_settings():
    rub = json.loads((HERE / f"{NAME}.json").read_text(encoding="utf-8"))
    if rub.get("metric") != KNOWN["metric"]:
        sys.exit(f"metric = {rub.get('metric')!r}: this script only knows {KNOWN['metric']!r}")
    ev = rub.get("evaluator") or {}
    for k, v in KNOWN["evaluator"].items():
        if ev.get(k) != v:
            sys.exit(f"evaluator.{k} = {ev.get(k)!r}: this script applies {v!r}")
    if rub.get("rules", {}).get("score") != KNOWN["score"]:
        sys.exit("score rule differs from what this script applies")
    if (rub.get("conversation") or {}).get("prep") != KNOWN["prep"]:
        sys.exit("conversation prep differs from what this script applies")
    for k in ("judge_model", "judge_provider", "temperature", "reasoning_format"):
        if fc.KNOWN["evaluator"][k] != KNOWN["evaluator"][k]:
            sys.exit(f"judge set-up borrowed from factual_correctness_ragas.py differs on {k}")
    for case, c in rub["cases"].items():
        for chk in c["checks"]:
            if chk["by"] not in ("judge", "code"):
                sys.exit(f"{case} {chk['id']}: unknown 'by' = {chk['by']!r}")
            if chk["by"] == "code" and chk.get("min_rating") not in RATING_ORDER:
                sys.exit(f"{case} {chk['id']}: code check needs a min_rating from {RATING_ORDER}")
    import ragas
    if ragas.__version__ != KNOWN["evaluator"]["ragas_version"]:
        sys.exit(f"RAGAS {ragas.__version__} installed, settings need {KNOWN['evaluator']['ragas_version']}")
    lock_path = HERE / f"{NAME}.lock.json"
    if not lock_path.is_file():
        sys.exit(f"No {NAME}.lock.json: lock the settings before scoring")
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    if fingerprint(rub) != lock["rubric_fingerprint"]:
        sys.exit(f"{NAME}.json changed after it was locked: make a new version instead")
    return rub, lock


def operator_question(case, side):
    trace = json.loads((SNAP / "traces" / f"{case}-{side}.json").read_text(encoding="utf-8"))
    step = next((s for s in trace["steps"] if s["name"] == "orchestrator"), None)
    q = (step or {}).get("input", {}).get("incident")
    if not q:
        sys.exit(f"{case}-{side}: no operator question in the trace")
    return q


def rating_check(chk, rating):
    ok = rating in RATING_ORDER and RATING_ORDER.index(rating) >= RATING_ORDER.index(chk["min_rating"])
    return {"verdict": int(ok), "reason": f"report rating {rating or 'not found'}; minimum {chk['min_rating']} (code)"}


async def judge_scenario(metric, conversation, checks, label):
    from ragas.metrics.collections.agent_goal_accuracy.util import CompareOutcomeInput, CompareOutcomeOutput
    waits = []
    wf = await with_limit_wait(lambda: metric._infer_goal_outcome(conversation), f"{label} end state", waits)
    out = {}
    for chk in checks:
        prompt = metric.compare_outcome_prompt.to_string(
            CompareOutcomeInput(desired_outcome=chk["desired_outcome"], arrived_outcome=wf.end_state))
        r = await with_limit_wait(lambda: metric.llm.agenerate(prompt, CompareOutcomeOutput),
                                  f"{label} {chk['id']}", waits)
        out[chk["id"]] = {"verdict": int(r.verdict), "reason": r.reason}
    return wf, out, waits


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", nargs="+", default=["H1", "H2", "H3", "H4", "H5"])
    ap.add_argument("--side", default="after", choices=["before", "after"])
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--smoke", action="store_true")
    args = ap.parse_args()

    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    rub, lock = check_settings()

    jobs = {}
    if args.smoke:
        print("Smoke test: expect S1 (bowl filled) = 1 and S2 (bowl painted red) = 0")
        checks = [{"id": "S1", "safety": False, "by": "judge", "desired_outcome": "The user's bowl is filled with clean water."},
                  {"id": "S2", "safety": False, "by": "judge", "desired_outcome": "The user's bowl is painted red."}]
        jobs["SMOKE"] = ("Please fill my bowl with clean water.", "Done: I filled your bowl with clean water.",
                         checks, None)
    else:
        for case in args.cases:
            c = rub["cases"][case]
            run = json.loads((SNAP / "runs" / f"{case}-{args.side}.json").read_text(encoding="utf-8"))
            response = remove_step_labels(strip_meta(run["report_as_graded"]))
            rating = criticality(run["report_as_graded"])
            q = operator_question(case, args.side)
            jobs[case] = (q, response, c["checks"], rating)
            n_judge = sum(ch["by"] == "judge" for ch in c["checks"])
            conv_tok = (len(q) + len(response)) // 4
            print(f"{case}: question ~{len(q) // 4:,} + answer ~{len(response) // 4:,} tokens · "
                  f"end-state call ~{conv_tok + 900:,} in · {n_judge} check calls ~600 in each · "
                  f"rating read by code: {rating}")
        if args.dry_run:
            print("\nDry run: nothing sent.")
            return

    from ragas.messages import HumanMessage, AIMessage
    from ragas.metrics.collections import AgentGoalAccuracyWithReference
    usage = []
    metric = AgentGoalAccuracyWithReference(llm=fc.make_judge(usage))
    out = {"run_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "side": args.side,
           "metric": NAME, "rubric_version": rub["version"], "rubric_fingerprint": fingerprint(rub),
           "locked": lock["locked"], "evaluator": KNOWN["evaluator"],
           "run_settings": {"reply_limit": REPLY_LIMIT, "judge_attempts": JUDGE_ATTEMPTS}, "cases": {}}

    def save(case, res):
        dest = HERE / "results" / f"{NAME}_{case if not args.smoke else 'smoke'}_{args.side}.json"
        dest.parent.mkdir(exist_ok=True)
        dest.write_text(json.dumps(dict(out, cases={case: res}), indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"  saved {dest.relative_to(ROOT)}")

    async def run_all():
        for case, (q, response, checks, rating) in jobs.items():
            before = len(usage)
            conversation = metric._format_conversation([HumanMessage(content=q), AIMessage(content=response)])
            judge_checks = [ch for ch in checks if ch["by"] == "judge"]
            try:
                wf, verdicts, waits = await judge_scenario(metric, conversation, judge_checks, case)
            except Exception as e:
                print(f"\n{case}: FAILED ({type(e).__name__}: {str(e)[:200]}) - other cases continue")
                continue
            rows = []
            for ch in checks:
                v = verdicts[ch["id"]] if ch["by"] == "judge" else rating_check(ch, rating)
                rows.append({"id": ch["id"], "safety": ch["safety"], "by": ch["by"],
                             "desired_outcome": ch["desired_outcome"], **v})
            passed = [r for r in rows if r["verdict"]]
            safety = [r for r in rows if r["safety"]]
            judge_passes = [r["id"] for r in rows if r["by"] == "judge" and r["verdict"]]
            sample = random.Random(f"{SAMPLE_SEED}-{case}").choice(judge_passes) if judge_passes else None
            calls = usage[before:]
            res = {"question": q, "rating": rating,
                   "user_goal": wf.user_goal, "end_state": wf.end_state,
                   "checks": rows,
                   "score": round(len(passed) / len(rows), 4), "passed": len(passed), "total": len(rows),
                   "achieved": len(passed) == len(rows),
                   "safety_passed": sum(r["verdict"] for r in safety), "safety_total": len(safety),
                   "person_sample_pass": sample, "limit_waits_s": waits,
                   "tokens": {"calls": len(calls), "in": sum(c["in"] for c in calls),
                              "out": sum(c["out"] for c in calls),
                              "non_200": [c["status"] for c in calls if c["status"] != 200]}}
            print(f"\n{case}: goal accuracy = {res['passed']}/{res['total']} checks"
                  f" · safety {res['safety_passed']}/{res['safety_total']}"
                  f" · goal {'ACHIEVED' if res['achieved'] else 'NOT achieved'}")
            print(f"  user goal (RAGAS step 1): {wf.user_goal}")
            print(f"  END STATE (RAGAS step 1, a person reads this): {wf.end_state}")
            for r in rows:
                tag = ("PASS" if r["verdict"] else "FAIL") + (" 🛡" if r["safety"] else "  ")
                print(f"  {r['id']} [{tag}] ({r['by']}) {r['desired_outcome']}")
                if not r["verdict"] or r["by"] == "code":
                    print(f"       reason: {r['reason']}")
            print(f"  person checks this pass too (seed {SAMPLE_SEED}): {sample}")
            t = res["tokens"]
            print(f"  tokens: {t['in']:,} in + {t['out']:,} out in {t['calls']} calls"
                  f"{'  (refused first: ' + str(t['non_200']) + ')' if t['non_200'] else ''}")
            save(case, res)

    asyncio.run(run_all())


if __name__ == "__main__":
    main()
