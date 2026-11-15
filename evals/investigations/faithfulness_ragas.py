"""
faithfulness_ragas.py - is everything the answer says backed by what the writer was given?

The RUBRIC lives in heldout-v1/faithfulness.json (Option A: the writer's own input).
The evaluator is RAGAS 0.4.3 Faithfulness with qwen/qwen3.8-27b on Groq as the judge
(temperature 0, hidden reasoning), the same judge as promptfoo. This script only
applies the rubric: it stops if the rubric, its lock, or the RAGAS version differ
from what it knows.

It reads the SAVED run (snapshot), so PlantMind is not run again. Every statement
and verdict is saved, so a person can check each one.

Modes (cost goes up from top to bottom):
  --dry-run   build the evidence and answer, print their size, call nothing   (free)
  --smoke     one tiny made-up example, to prove qwen + RAGAS work together (a few hundred tokens)
  (default)   the cases in --cases, default H1 only                         (judge tokens; ask first)

Usage (from C:\\plantmind):
  venv\\Scripts\\python.exe evals\\investigations\\faithfulness_ragas.py --dry-run
  venv\\Scripts\\python.exe evals\\investigations\\faithfulness_ragas.py --smoke
  venv\\Scripts\\python.exe evals\\investigations\\faithfulness_ragas.py --cases H1
"""
import argparse
import asyncio
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from retrieval_recall import fingerprint, HERE, SNAP  # noqa: E402

ROOT = HERE.parent.parent.parent
KNOWN = {
    "metric": "faithfulness",
    "look_in": "writer_input",
    "evaluator": {"tool": "ragas", "ragas_version": "0.4.3",
                  "metric_class": "ragas.metrics.collections.Faithfulness",
                  "prompts": "RAGAS built-in StatementGeneratorPrompt and NLIStatementPrompt, unchanged",
                  "judge_model": "qwen/qwen3.8-27b", "judge_provider": "groq",
                  "temperature": 0, "reasoning_format": "hidden"},
    "score": "supported statements / all statements",
}
TPM_LIMIT = 7000          # qwen input tokens per minute on Groq free tier (groq_judge.js)


def check_rubric():
    rub = json.loads((HERE / "faithfulness.json").read_text(encoding="utf-8"))
    for key in ("metric", "look_in"):
        if rub.get(key) != KNOWN[key]:
            sys.exit(f"{key} = {rub.get(key)!r}: this script only knows {KNOWN[key]!r}")
    if rub.get("evaluator") != KNOWN["evaluator"]:
        sys.exit("evaluator settings differ from what this script applies")
    if rub.get("rules", {}).get("score") != KNOWN["score"]:
        sys.exit("score rule differs from what this script applies")
    import ragas
    if ragas.__version__ != KNOWN["evaluator"]["ragas_version"]:
        sys.exit(f"RAGAS {ragas.__version__} installed, rubric needs {KNOWN['evaluator']['ragas_version']}")
    lock_path = HERE / "faithfulness.lock.json"
    if not lock_path.is_file():
        sys.exit("No faithfulness.lock.json: lock the rubric before scoring")
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    if fingerprint(rub) != lock["rubric_fingerprint"]:
        sys.exit("faithfulness.json changed after it was locked: make a new version instead")
    return rub, lock


def strip_meta(report):
    """Same cut as eval_summary._strip_meta: drop the code-written blocks."""
    text = report.replace("\r\n", "\n")
    text = re.sub(r"REPORT CONFIDENCE:.*?(?=\n\s*\n)", "", text, flags=re.S)
    text = re.sub(r"SOURCE DATA:.*?(?=\n\s*\n)", "", text, flags=re.S)
    return text.strip()


def writer_evidence(case, side):
    """The writer's input, from the saved trace: helper summaries + graph text."""
    trace = json.loads((SNAP / "traces" / f"{case}-{side}.json").read_text(encoding="utf-8"))
    step = next((s for s in trace["steps"] if s["name"] == "orchestrator"), None)
    if not step:
        sys.exit(f"{case}-{side}: no orchestrator step in the trace")
    inp = step["input"]
    contexts = [f"{r['agent'].upper()} FINDINGS\n{r['findings']}" for r in inp.get("specialist_results") or []]
    g = inp.get("graph_context") or {}
    if g.get("has_data") and g.get("chain_text"):
        contexts.append("KNOWLEDGE GRAPH CONTEXT\n" + g["chain_text"])
        if g.get("warnings"):
            contexts.append("MANDATORY REQUIREMENTS FROM KNOWLEDGE GRAPH\n" + "\n".join(g["warnings"]))
        if g.get("exact_values"):
            contexts.append("EXACT VALUES FROM KNOWLEDGE GRAPH\n" + "\n".join(map(str, g["exact_values"])))
        if g.get("downtime"):
            contexts.append(f"Estimated downtime: {g['downtime']}")
    return inp.get("incident") or "", contexts


def make_judge(usage):
    """RAGAS LLM on Groq, recording the token usage Groq reports for every call."""
    import httpx
    from openai import AsyncOpenAI
    from ragas.llms import llm_factory

    async def record(resp):
        if resp.request.url.path.endswith("/chat/completions"):
            await resp.aread()
            try:
                u = resp.json().get("usage") or {}
                usage.append({"status": resp.status_code, "in": u.get("prompt_tokens", 0),
                              "out": u.get("completion_tokens", 0)})
            except Exception:
                usage.append({"status": resp.status_code, "in": 0, "out": 0})

    client = AsyncOpenAI(api_key=os.getenv("GROQ_API_KEY"), base_url="https://api.groq.com/openai/v1",
                         max_retries=8, http_client=httpx.AsyncClient(event_hooks={"response": [record]},
                                                                      timeout=120))
    ev = KNOWN["evaluator"]
    return llm_factory(ev["judge_model"], provider="openai", client=client,
                       temperature=ev["temperature"], max_tokens=4096,
                       extra_body={"reasoning_format": ev["reasoning_format"]})


async def score_one(metric, question, response, contexts):
    statements = await metric._create_statements(question, response)
    if not statements:
        return {"score": None, "statements": []}
    verdicts = await metric._create_verdicts(statements, "\n".join(contexts))
    rows = [{"statement": v.statement, "verdict": int(v.verdict), "reason": v.reason} for v in verdicts.statements]
    return {"score": metric._compute_score(verdicts), "statements": rows}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", nargs="+", default=["H1"])
    ap.add_argument("--side", default="after", choices=["before", "after"])
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--smoke", action="store_true")
    args = ap.parse_args()

    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    rub, lock = check_rubric()

    if args.smoke:
        question = "What does the bowl hold?"
        response = "The bowl holds clean water. The bowl is painted red."
        contexts = ["The bowl holds clean water."]
        print("Smoke test: expect statement 1 supported (1), statement 2 not supported (0), score 0.5")
        jobs = {"SMOKE": (question, response, contexts)}
    else:
        jobs = {}
        for case in args.cases:
            run = json.loads((SNAP / "runs" / f"{case}-{args.side}.json").read_text(encoding="utf-8"))
            question, contexts = writer_evidence(case, args.side)
            response = strip_meta(run["report_as_graded"])
            jobs[case] = (question, response, contexts)
            ev_tok = sum(len(c) for c in contexts) // 4
            resp_tok = len(response) // 4
            print(f"{case}: {len(contexts)} evidence blocks ~{ev_tok:,} tokens · answer ~{resp_tok:,} tokens"
                  f" · verdict call ~{ev_tok + resp_tok + 800:,} tokens in (limit {TPM_LIMIT:,}/min)")
            if ev_tok + resp_tok + 800 > TPM_LIMIT:
                print(f"  WARNING: {case}'s verdict call is likely bigger than one minute's allowance;"
                      " Groq may refuse it (413).")
        if args.dry_run:
            print("\nDry run: nothing sent.")
            return

    from ragas.metrics.collections import Faithfulness
    usage = []
    metric = Faithfulness(llm=make_judge(usage))
    out = {"run_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "side": args.side,
           "metric": "faithfulness", "rubric_version": rub["version"], "rubric_fingerprint": fingerprint(rub),
           "locked": lock["locked"], "evaluator": KNOWN["evaluator"], "cases": {}}

    async def run_all():
        # One event loop for every case: the HTTP client belongs to the loop it was first used in.
        results = {}
        for case, (question, response, contexts) in jobs.items():
            before = len(usage)
            res = await score_one(metric, question, response, contexts)
            res["_calls"] = usage[before:]
            results[case] = res
        return results

    for case, res in asyncio.run(run_all()).items():
        calls = res.pop("_calls")
        res["tokens"] = {"calls": len(calls), "in": sum(c["in"] for c in calls),
                         "out": sum(c["out"] for c in calls),
                         "non_200": [c["status"] for c in calls if c["status"] != 200]}
        out["cases"][case] = res
        sc = res["score"]
        print(f"\n{case}: faithfulness = {sc:.2f}" if sc is not None else f"\n{case}: no statements")
        for i, s in enumerate(res["statements"], 1):
            print(f"  {i:>2} [{'SUPPORTED' if s['verdict'] else 'NOT SUPPORTED'}] {s['statement']}")
            if not s["verdict"]:
                print(f"       reason: {s['reason']}")
        t = res["tokens"]
        print(f"  tokens: {t['in']:,} in + {t['out']:,} out in {t['calls']} calls"
              f"{'  (retries: ' + str(t['non_200']) + ')' if t['non_200'] else ''}")

    name = "smoke" if args.smoke else "_".join(args.cases)
    dest = HERE / "results" / f"faithfulness_{name}_{args.side}.json"
    dest.parent.mkdir(exist_ok=True)
    dest.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved {dest.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
