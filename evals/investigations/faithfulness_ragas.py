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
REPLY_LIMIT = 16000       # judge reply cap (run setting, not a judging rule; saved with every result)
JUDGE_ATTEMPTS = 1        # no automatic re-asking of the judge on a bad reply
LIMIT_WAIT_TRIES = 6      # on a rate-limit refusal (nothing generated, nothing spent): wait and ask again
LIMIT_WAIT_SECONDS = 65   # default wait when Groq gives no "try again in" hint (limits reset each minute)


RUBRICS = {1: ("faithfulness.json", "faithfulness.lock.json", None),
           2: ("faithfulness_v2.json", "faithfulness_v2.lock.json",
               {"question_in_evidence": True, "remove_step_labels": True})}


def check_rubric(version):
    name, lock_name, prep = RUBRICS[version]
    rub = json.loads((HERE / name).read_text(encoding="utf-8"))
    if rub.get("version") != version:
        sys.exit(f"{name}: version = {rub.get('version')!r}, expected {version}")
    for key in ("metric", "look_in"):
        if rub.get(key) != KNOWN[key]:
            sys.exit(f"{key} = {rub.get(key)!r}: this script only knows {KNOWN[key]!r}")
    if rub.get("evaluator") != KNOWN["evaluator"]:
        sys.exit("evaluator settings differ from what this script applies")
    if rub.get("rules", {}).get("score") != KNOWN["score"]:
        sys.exit("score rule differs from what this script applies")
    if rub.get("prep") != prep:
        sys.exit(f"{name}: prep = {rub.get('prep')!r}: this script applies {prep!r} for version {version}")
    import ragas
    if ragas.__version__ != KNOWN["evaluator"]["ragas_version"]:
        sys.exit(f"RAGAS {ragas.__version__} installed, rubric needs {KNOWN['evaluator']['ragas_version']}")
    lock_path = HERE / lock_name
    if not lock_path.is_file():
        sys.exit(f"No {lock_name}: lock the rubric before scoring")
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    if fingerprint(rub) != lock["rubric_fingerprint"]:
        sys.exit(f"{name} changed after it was locked: make a new version instead")
    return rub, lock


def strip_meta(report):
    """Same cut as eval_summary._strip_meta: drop the code-written blocks."""
    text = report.replace("\r\n", "\n")
    text = re.sub(r"REPORT CONFIDENCE:.*?(?=\n\s*\n)", "", text, flags=re.S)
    text = re.sub(r"SOURCE DATA:.*?(?=\n\s*\n)", "", text, flags=re.S)
    return text.strip()


STEP_LABEL = re.compile(r"(?im)^(\s*)step\s*\d+\s*[:.\-–—]\s*")


def remove_step_labels(text):
    """v2: 'Step 2: Diagnosis - inspect X' -> 'Diagnosis - inspect X'. The judge
    checked step NUMBERS against the documents' own numbering (H2 review:
    13 judge errors). The actions themselves are unchanged."""
    return STEP_LABEL.sub(r"\1", text)


def writer_evidence(case, side, question_in_evidence=False):
    """The writer's input, from the saved trace: (question) + helper summaries + graph text."""
    trace = json.loads((SNAP / "traces" / f"{case}-{side}.json").read_text(encoding="utf-8"))
    step = next((s for s in trace["steps"] if s["name"] == "orchestrator"), None)
    if not step:
        sys.exit(f"{case}-{side}: no orchestrator step in the trace")
    inp = step["input"]
    contexts = [f"{r['agent'].upper()} FINDINGS\n{r['findings']}" for r in inp.get("specialist_results") or []]
    if question_in_evidence and inp.get("incident"):
        contexts.insert(0, "OPERATOR'S QUESTION (what the operator reported)\n" + inp["incident"])
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
    # REPLY_LIMIT: the verdict reply repeats every statement with a reason; H1's ~45
    # statements did not fit in 4,096 tokens (2026-11-15). JUDGE_ATTEMPTS = 1: a failed
    # judge call costs one call, not three (instructor retried the same cut-off reply).
    # Rate-limit refusals (429) are still retried by the HTTP client and cost nothing.
    return llm_factory(ev["judge_model"], provider="openai", client=client,
                       temperature=ev["temperature"], max_tokens=REPLY_LIMIT,
                       max_retries=JUDGE_ATTEMPTS,
                       extra_body={"reasoning_format": ev["reasoning_format"]})


def _limit_refusal(exc):
    """True when Groq refused the call over a rate limit (429), e.g. its output
    allowance (OTPM) shrank for a while (seen 2026-11-15: 1,000, then back up).
    A refused call generates nothing, so waiting and asking again costs nothing.
    A cut-off reply (max_tokens) is NOT a refusal and is never re-asked."""
    text = str(exc)
    return "429" in text or "rate_limit" in text or "RateLimitError" in type(exc).__name__


async def with_limit_wait(make_call, label, waits):
    for attempt in range(1, LIMIT_WAIT_TRIES + 1):
        try:
            return await make_call()
        except Exception as e:
            if not _limit_refusal(e) or attempt == LIMIT_WAIT_TRIES:
                raise
            m = re.search(r"try again in\s+(?:(\d+)m\s*)?([\d.]+)s", str(e))
            wait = min(120, (int(m.group(1) or 0) * 60 + float(m.group(2)) + 2) if m else LIMIT_WAIT_SECONDS)
            waits.append(round(wait))
            print(f"  {label}: Groq refused over a rate limit; waiting {wait:.0f}s (try {attempt}/{LIMIT_WAIT_TRIES})")
            await asyncio.sleep(wait)


async def score_one(metric, question, response, contexts, label):
    waits = []
    statements = await with_limit_wait(lambda: metric._create_statements(question, response),
                                       f"{label} split", waits)
    if not statements:
        return {"score": None, "statements": [], "limit_waits_s": waits}
    verdicts = await with_limit_wait(lambda: metric._create_verdicts(statements, "\n".join(contexts)),
                                     f"{label} verdicts", waits)
    rows = [{"statement": v.statement, "verdict": int(v.verdict), "reason": v.reason} for v in verdicts.statements]
    return {"score": metric._compute_score(verdicts), "statements": rows, "limit_waits_s": waits}


def _matches(item, text):
    t = (text or "").lower()
    return (all(any(w.lower() in t for w in group) for group in item["all_of"])
            and not any(w.lower() in t for w in item.get("none_of", [])))


def calibration_check(rub, case, statements):
    """Both directions: known-true topics must be supported, known-made-up topics must not.
    Prints every matching statement so a person can confirm (word matching can hit by accident)."""
    cal = (rub.get("calibration") or {}).get("cases", {}).get(case)
    if not cal:
        return None
    report, ok = [], True
    for kind, want in (("must_support", 1), ("must_not_support", 0)):
        for item in cal.get(kind, []):
            hits = [(i, s) for i, s in enumerate(statements, 1) if _matches(item, s["statement"])]
            bad = [i for i, s in hits if s["verdict"] != want]
            ok = ok and not bad and bool(hits)
            report.append({"kind": kind, "topic": item["topic"], "matched": [i for i, _ in hits],
                           "wrong": bad, "no_match": not hits})
    print(f"\n  CALIBRATION ({case}): {'PASS' if ok else 'FAIL'}  (a person confirms)")
    for r in report:
        mark = "ok  " if (not r["wrong"] and not r["no_match"]) else "FAIL"
        extra = " (no statement matched)" if r["no_match"] else (f" wrong verdict on #{r['wrong']}" if r["wrong"] else "")
        print(f"    {mark} {r['kind']:<17} {r['topic']:<45} statements {r['matched']}{extra}")
    return {"pass": ok, "topics": report}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--rubric", type=int, choices=sorted(RUBRICS), default=2)
    ap.add_argument("--cases", nargs="+", default=["H1"])
    ap.add_argument("--side", default="after", choices=["before", "after"])
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--smoke", action="store_true")
    args = ap.parse_args()

    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    rub, lock = check_rubric(args.rubric)
    prep = rub.get("prep") or {}

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
            question, contexts = writer_evidence(case, args.side, prep.get("question_in_evidence", False))
            response = strip_meta(run["report_as_graded"])
            if prep.get("remove_step_labels"):
                response = remove_step_labels(response)
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
           "locked": lock["locked"], "evaluator": KNOWN["evaluator"],
           "run_settings": {"reply_limit": REPLY_LIMIT, "judge_attempts": JUDGE_ATTEMPTS}, "cases": {}}

    def save(case, res):
        # One file per case, written as soon as that case finishes: a later failure loses nothing.
        tag = "" if args.rubric == 1 else f"v{args.rubric}_"      # v1 file names stay as they were
        dest = HERE / "results" / f"faithfulness_{tag}{case if not args.smoke else 'smoke'}_{args.side}.json"
        dest.parent.mkdir(exist_ok=True)
        dest.write_text(json.dumps(dict(out, cases={case: res}), indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"  saved {dest.relative_to(ROOT)}")

    async def run_all():
        # One event loop for every case: the HTTP client belongs to the loop it was first used in.
        for case, (question, response, contexts) in jobs.items():
            before = len(usage)
            try:
                res = await score_one(metric, question, response, contexts, case)
            except Exception as e:
                print(f"\n{case}: FAILED ({type(e).__name__}: {str(e)[:200]}) - other cases continue")
                continue
            calls = usage[before:]
            res["tokens"] = {"calls": len(calls), "in": sum(c["in"] for c in calls),
                             "out": sum(c["out"] for c in calls),
                             "non_200": [c["status"] for c in calls if c["status"] != 200]}
            sc = res["score"]
            print(f"\n{case}: faithfulness = {sc:.2f}" if sc is not None else f"\n{case}: no statements")
            for i, s in enumerate(res["statements"], 1):
                print(f"  {i:>2} [{'SUPPORTED' if s['verdict'] else 'NOT SUPPORTED'}] {s['statement']}")
                if not s["verdict"]:
                    print(f"       reason: {s['reason']}")
            t = res["tokens"]
            print(f"  tokens: {t['in']:,} in + {t['out']:,} out in {t['calls']} calls"
                  f"{'  (refused first: ' + str(t['non_200']) + ')' if t['non_200'] else ''}")
            res["calibration"] = calibration_check(rub, case, res["statements"])
            save(case, res)

    asyncio.run(run_all())


if __name__ == "__main__":
    main()
