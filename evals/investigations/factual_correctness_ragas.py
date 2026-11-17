"""
factual_correctness_ragas.py - did the facts the operator needed make it into the answer?

The SETTINGS live in heldout-v1/factual_correctness.json (locked). The judging is
RAGAS 0.4.3 FactualCorrectness's own two steps, with its prompts unchanged:
  1. split the reference (our locked needed facts) into claims
     (atomicity high, coverage high)
  2. check each claim against the answer (1 = the answer says it, 0 = it doesn't)
The score is OUR rule: reference claims the answer supports / all reference claims.
RAGAS's own combined "recall" formula is NOT used (it mixes answer claims into the
count; see why_not_ragas_score in the settings file).

This script only applies the settings: it stops if they, their lock, the facts'
locks or the RAGAS version differ from what it knows. It reads the SAVED run
(snapshot), so PlantMind is not run again. Every claim, verdict and reason is saved,
so a person can check each one.

Versions: --rubric 2 (default) takes the reference wording from
heldout-v1/factual_correctness_v2.json; --rubric 1 uses the original v1 settings
(the locked facts' own short wording).

Modes (cost goes up from top to bottom):
  --dry-run   build the reference and answer, print their size, call nothing   (free)
  --smoke     one tiny made-up example, to prove qwen + RAGAS work together (a few hundred tokens)
  (default)   the cases in --cases, default H2 only (the first-run check)   (judge tokens; ask first)

Usage (from C:\\plantmind):
  venv\\Scripts\\python.exe evals\\investigations\\factual_correctness_ragas.py --dry-run --cases H1 H2 H3 H4 H5
  venv\\Scripts\\python.exe evals\\investigations\\factual_correctness_ragas.py --smoke
  venv\\Scripts\\python.exe evals\\investigations\\factual_correctness_ragas.py --cases H2
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
from handover_recall import check_fact_locks  # noqa: E402  same fact locks as handover recall
from faithfulness_ragas import (strip_meta, remove_step_labels, with_limit_wait,  # noqa: E402
                                TPM_LIMIT, REPLY_LIMIT, JUDGE_ATTEMPTS)  # same answer text as faithfulness v2

ROOT = HERE.parent.parent.parent
NAME = "factual_correctness"
KNOWN = {
    "metric": NAME,
    "evaluator": {"tool": "ragas", "ragas_version": "0.4.3",
                  "metric_class": "ragas.metrics.collections.FactualCorrectness",
                  "mode": "recall", "atomicity": "high", "coverage": "high",
                  "judge_model": "qwen/qwen3.8-27b", "judge_provider": "groq",
                  "temperature": 0, "reasoning_format": "hidden"},
    "score": "reference claims supported by the answer / all reference claims",
    "prep": {"remove_step_labels": True},
}


RUBRICS = {1: (f"{NAME}.json", f"{NAME}.lock.json"),
           2: (f"{NAME}_v2.json", f"{NAME}_v2.lock.json")}


def check_settings(version):
    file_name, lock_name = RUBRICS[version]
    rub = json.loads((HERE / file_name).read_text(encoding="utf-8"))
    if rub.get("version") != version:
        sys.exit(f"{file_name}: version = {rub.get('version')!r}, expected {version}")
    if rub.get("metric") != KNOWN["metric"]:
        sys.exit(f"metric = {rub.get('metric')!r}: this script only knows {KNOWN['metric']!r}")
    ev = rub.get("evaluator") or {}
    for k, v in KNOWN["evaluator"].items():
        if ev.get(k) != v:
            sys.exit(f"evaluator.{k} = {ev.get(k)!r}: this script applies {v!r}")
    if rub.get("rules", {}).get("score") != KNOWN["score"]:
        sys.exit("score rule differs from what this script applies")
    if rub.get("prep") != KNOWN["prep"]:
        sys.exit(f"prep = {rub.get('prep')!r}: this script applies {KNOWN['prep']!r}")
    import ragas
    if ragas.__version__ != KNOWN["evaluator"]["ragas_version"]:
        sys.exit(f"RAGAS {ragas.__version__} installed, settings need {KNOWN['evaluator']['ragas_version']}")
    lock_path = HERE / lock_name
    if not lock_path.is_file():
        sys.exit(f"No {lock_name}: lock the settings before scoring")
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    if fingerprint(rub) != lock["rubric_fingerprint"]:
        sys.exit(f"{file_name} changed after it was locked: make a new version instead")
    return rub, lock


def case_facts(rub, labels, case):
    """v1: the locked facts' own wording. v2: the reworded reference from the settings
    file, checked one-to-one against the locked facts (same ids, fact_v1 = locked text)."""
    locked = labels["cases"][case]["facts"]
    if rub["version"] == 1:
        return locked
    mine = rub["cases"][case]
    if [f["id"] for f in mine] != [f["id"] for f in locked]:
        sys.exit(f"{case}: v2 fact ids differ from retrieval_labels.json")
    for m, f in zip(mine, locked):
        if m["fact_v1"] != f["fact"]:
            sys.exit(f"{case} {m['id']}: fact_v1 does not match the locked fact text")
    return [{"id": m["id"], "fact": m["reference"]} for m in mine]


def make_judge(usage):
    """RAGAS LLM on Groq (same client set-up as faithfulness), recording Groq's token usage."""
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
                       temperature=ev["temperature"], max_tokens=REPLY_LIMIT, max_retries=JUDGE_ATTEMPTS,
                       extra_body={"reasoning_format": ev["reasoning_format"]})


def reference_text(facts):
    """One sentence per needed fact, as the settings say."""
    return " ".join(f["fact"].strip().rstrip(".") + "." for f in facts)


STOP = set("the a an of to in on at for is are be by it its and or if with from as that this "
           "must should not no do".split())


def words(text):
    return {w for w in re.findall(r"[a-z0-9]+(?:[.\-][a-z0-9]+)*", (text or "").lower()) if w not in STOP}


def map_claim(claim, facts):
    """Code's guess: the fact sharing the most words with the claim. A person confirms."""
    cw = words(claim)
    best, best_score = None, 0.0
    for f in facts:
        fw = words(f["fact"])
        if not fw:
            continue
        s = len(cw & fw) / len(fw)
        if s > best_score:
            best, best_score = f["id"], s
    return best, round(best_score, 2)


def per_fact(facts, claims):
    out = []
    for f in facts:
        mine = [c for c in claims if c["fact"] == f["id"]]
        if not mine:
            status = "NO CLAIM"          # the splitting lost or merged this fact: a person checks
        elif all(c["verdict"] for c in mine):
            status = "PRESENT"
        elif any(c["verdict"] for c in mine):
            status = "PARTIAL"
        else:
            status = "MISSING"
        out.append({"id": f["id"], "fact": f["fact"], "status": status,
                    "claims": [claims.index(c) + 1 for c in mine]})
    return out


async def score_one(metric, reference, response, label):
    waits = []
    claims = await with_limit_wait(lambda: metric._decompose_claims(reference), f"{label} split", waits)
    if not claims:
        return {"score": None, "claims": [], "limit_waits_s": waits}
    verdicts = await with_limit_wait(lambda: metric._verify_claims(claims, response), f"{label} verdicts", waits)
    rows = [{"claim": v.statement, "verdict": int(v.verdict), "reason": v.reason} for v in verdicts.statements]
    if len(rows) != len(claims):
        print(f"  WARNING: {len(claims)} claims split but {len(rows)} verdicts returned: a person checks")
    sup = sum(r["verdict"] for r in rows)
    return {"score": round(sup / len(rows), 4) if rows else None, "supported": sup, "total": len(rows),
            "split_claims": claims, "claims": rows, "limit_waits_s": waits}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--rubric", type=int, choices=sorted(RUBRICS), default=2)
    ap.add_argument("--cases", nargs="+", default=["H2"])
    ap.add_argument("--side", default="after", choices=["before", "after"])
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--smoke", action="store_true")
    args = ap.parse_args()

    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    rub, lock = check_settings(args.rubric)
    labels = json.loads((HERE / "retrieval_labels.json").read_text(encoding="utf-8"))
    check_fact_locks(labels)

    jobs = {}
    if args.smoke:
        print("Smoke test: expect claim 'clean water' supported (1), claim 'red' not supported (0), score 0.5")
        facts = [{"id": "F1", "fact": "The bowl holds clean water"}, {"id": "F2", "fact": "The bowl is painted red"}]
        jobs["SMOKE"] = (facts, reference_text(facts), "The bowl holds clean water. It sits on the table.", None)
    else:
        for case in args.cases:
            lab = labels["cases"][case]
            facts = case_facts(rub, labels, case)
            run = json.loads((SNAP / "runs" / f"{case}-{args.side}.json").read_text(encoding="utf-8"))
            response = remove_step_labels(strip_meta(run["report_as_graded"]))
            ref = reference_text(facts)
            jobs[case] = (facts, ref, response, lab)
            ref_tok, resp_tok = len(ref) // 4, len(response) // 4
            print(f"{case}: {len(facts)} facts ~{ref_tok:,} tokens · answer ~{resp_tok:,} tokens"
                  f" · check call ~{ref_tok + resp_tok + 800:,} tokens in (limit {TPM_LIMIT:,}/min)"
                  f"{'' if lab.get('blind', True) else '  [facts not blind]'}")
            if ref_tok + resp_tok + 800 > TPM_LIMIT:
                print(f"  WARNING: {case}'s check call is likely bigger than one minute's allowance;"
                      " Groq may refuse it (413).")
        if args.dry_run:
            print("\nDry run: nothing sent.")
            return

    from ragas.metrics.collections import FactualCorrectness
    usage = []
    ev = KNOWN["evaluator"]
    metric = FactualCorrectness(llm=make_judge(usage), mode=ev["mode"],
                                atomicity=ev["atomicity"], coverage=ev["coverage"])
    out = {"run_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "side": args.side,
           "metric": NAME, "rubric_version": rub["version"], "rubric_fingerprint": fingerprint(rub),
           "locked": lock["locked"], "evaluator": ev,
           "run_settings": {"reply_limit": REPLY_LIMIT, "judge_attempts": JUDGE_ATTEMPTS}, "cases": {}}

    def save(case, res):
        # One file per case, written as soon as that case finishes: a later failure loses nothing.
        tag = "" if args.rubric == 1 else f"v{args.rubric}_"      # v1 file names stay as they were
        dest = HERE / "results" / f"{NAME}_{tag}{case if not args.smoke else 'smoke'}_{args.side}.json"
        dest.parent.mkdir(exist_ok=True)
        dest.write_text(json.dumps(dict(out, cases={case: res}), indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"  saved {dest.relative_to(ROOT)}")

    async def run_all():
        for case, (facts, ref, response, lab) in jobs.items():
            before = len(usage)
            try:
                res = await score_one(metric, ref, response, case)
            except Exception as e:
                print(f"\n{case}: FAILED ({type(e).__name__}: {str(e)[:200]}) - other cases continue")
                continue
            for c in res["claims"]:
                c["fact"], c["fact_match"] = map_claim(c["claim"], facts)
            res["per_fact"] = per_fact(facts, res["claims"])
            if lab is not None:
                res["case_fingerprint"] = fingerprint(lab)
                res["blind_facts"] = lab.get("blind", True)
            calls = usage[before:]
            res["tokens"] = {"calls": len(calls), "in": sum(c["in"] for c in calls),
                             "out": sum(c["out"] for c in calls),
                             "non_200": [c["status"] for c in calls if c["status"] != 200]}
            sc = res["score"]
            print(f"\n{case}: factual correctness (recall) = "
                  + (f"{sc:.2f} ({res['supported']}/{res['total']} claims)" if sc is not None else "no claims"))
            print("  Claims RAGAS split from our facts, and the verdict against the answer:")
            for i, c in enumerate(res["claims"], 1):
                print(f"  {i:>2} [{'IN ANSWER' if c['verdict'] else 'MISSING  '}] ({c['fact']}, match {c['fact_match']}) "
                      f"{c['claim']}")
                if not c["verdict"]:
                    print(f"       reason: {c['reason']}")
            print("  Per fact (code's mapping; a person confirms):")
            for f in res["per_fact"]:
                print(f"    {f['id']:<4} {f['status']:<9} claims {f['claims']}  {f['fact']}")
            t = res["tokens"]
            print(f"  tokens: {t['in']:,} in + {t['out']:,} out in {t['calls']} calls"
                  f"{'  (refused first: ' + str(t['non_200']) + ')' if t['non_200'] else ''}")
            save(case, res)

    asyncio.run(run_all())


if __name__ == "__main__":
    main()
