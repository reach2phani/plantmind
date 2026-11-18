"""
goal_accuracy_v2.py - did the operator end up able to act correctly and safely? (version 2)

The SETTINGS live in heldout-v1/goal_accuracy_v2.json (locked). Same 23 checks as
version 1 (verified word for word against goal_accuracy.json), but a different JUDGE:
for each judge check, one call with the WHOLE question and answer, asking "does the
answer tell the operator this?", with a quote as proof. A pass counts only if its
quote is really in the answer (checked by code). Rating checks are decided by code,
as in version 1. RAGAS is not used (see why_not_ragas in the settings).

Before its numbers are used, the run is CALIBRATED against the version 1 human
review: 13 checks must pass and 5 must fail. Any disagreement is printed; the
script never changes anything to make it agree.

Modes (cost goes up from top to bottom):
  --dry-run   build the prompts, print their size, call nothing                 (free)
  --smoke     one tiny made-up example, to prove qwen + the prompt work (a few hundred tokens)
  (default)   the cases in --cases, default all five                            (judge tokens; ask first)

Usage (from C:\\plantmind):
  venv\\Scripts\\python.exe evals\\investigations\\goal_accuracy_v2.py --dry-run
  venv\\Scripts\\python.exe evals\\investigations\\goal_accuracy_v2.py --smoke
  venv\\Scripts\\python.exe evals\\investigations\\goal_accuracy_v2.py
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
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))       # repo root, for run_record
from retrieval_recall import fingerprint, HERE, SNAP  # noqa: E402
from faithfulness_ragas import strip_meta, remove_step_labels, with_limit_wait  # noqa: E402
from goal_accuracy_ragas import operator_question, rating_check, RATING_ORDER  # noqa: E402  same as v1
from run_record import criticality  # noqa: E402

ROOT = HERE.parent.parent.parent
NAME = "goal_accuracy"
KNOWN = {
    "metric": NAME,
    "evaluator": {"tool": "own judge prompt (no RAGAS)", "judge_model": "qwen/qwen3.8-27b",
                  "judge_provider": "groq", "temperature": 0, "reasoning_format": "hidden"},
    "score": "checks passed / all checks",
    "prep": {"remove_step_labels": True},
}
REPLY_LIMIT = 4000          # one short JSON reply; headroom for hidden reasoning (run setting, saved with results)


def check_settings():
    rub = json.loads((HERE / f"{NAME}_v2.json").read_text(encoding="utf-8"))
    if rub.get("version") != 2 or rub.get("metric") != NAME:
        sys.exit("goal_accuracy_v2.json: expected metric goal_accuracy, version 2")
    ev = rub.get("evaluator") or {}
    for k, v in KNOWN["evaluator"].items():
        if ev.get(k) != v:
            sys.exit(f"evaluator.{k} = {ev.get(k)!r}: this script applies {v!r}")
    if rub.get("rules", {}).get("score") != KNOWN["score"]:
        sys.exit("score rule differs from what this script applies")
    if (rub.get("conversation") or {}).get("prep") != KNOWN["prep"]:
        sys.exit("conversation prep differs from what this script applies")
    lock_path = HERE / f"{NAME}_v2.lock.json"
    if not lock_path.is_file():
        sys.exit(f"No {NAME}_v2.lock.json: lock the settings before scoring")
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    if fingerprint(rub) != lock["rubric_fingerprint"]:
        sys.exit(f"{NAME}_v2.json changed after it was locked: make a new version instead")
    # the checks come from version 1, unchanged, and version 1 must still match its own lock
    v1 = json.loads((HERE / f"{NAME}.json").read_text(encoding="utf-8"))
    v1_lock = json.loads((HERE / f"{NAME}.lock.json").read_text(encoding="utf-8"))
    if fingerprint(v1) != v1_lock["rubric_fingerprint"]:
        sys.exit("goal_accuracy.json (v1, source of the checks) changed after it was locked")
    cal = rub["calibration"]
    for case, c in v1["cases"].items():
        judge_ids = {ch["id"] for ch in c["checks"] if ch["by"] == "judge"}
        named = (set(cal["must_pass"].get(case, [])) | set(cal["must_fail"].get(case, []))
                 | set(cal["not_used_borderline"].get(case, [])))
        if named != judge_ids:
            sys.exit(f"{case}: calibration names {sorted(named)}, judge checks are {sorted(judge_ids)}")
    return rub, lock, v1


def norm(text):
    """For the quote check: ignore case, spaces, line breaks, Markdown bold and special hyphens."""
    t = (text or "").lower().replace("**", "").replace("*", "")
    t = re.sub(r"[\u2010\u2011\u2012\u2013\u2014\u2212]", "-", t)
    t = t.replace("\u2019", "'").replace("\u201c", '"').replace("\u201d", '"')
    return re.sub(r"\s+", " ", t).strip()


def quote_in_answer(quote, answer):
    """A quote may join several places with '...'; every part must be in the answer."""
    parts = [p.strip(" .,;:\"'") for p in re.split(r"\.\.\.|\u2026", quote or "")]
    parts = [p for p in parts if p]
    a = norm(answer)
    return bool(parts) and all(norm(p) in a for p in parts)


def parse_reply(text):
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        raise ValueError(f"no JSON in judge reply: {(text or '')[:200]!r}")
    d = json.loads(m.group(0))
    return {"quote": str(d.get("quote") or ""), "verdict": int(d.get("verdict")),
            "reason": str(d.get("reason") or "")}


def make_client(usage):
    import httpx
    from openai import AsyncOpenAI

    async def record(resp):
        if resp.request.url.path.endswith("/chat/completions"):
            await resp.aread()
            try:
                u = resp.json().get("usage") or {}
                usage.append({"status": resp.status_code, "in": u.get("prompt_tokens", 0),
                              "out": u.get("completion_tokens", 0)})
            except Exception:
                usage.append({"status": resp.status_code, "in": 0, "out": 0})

    # max_retries=0: rate-limit refusals are handled (and logged) by with_limit_wait
    return AsyncOpenAI(api_key=os.getenv("GROQ_API_KEY"), base_url="https://api.groq.com/openai/v1",
                       max_retries=0, http_client=httpx.AsyncClient(event_hooks={"response": [record]},
                                                                    timeout=120))


async def judge_check(client, prompt, question, answer, chk, label, waits):
    ev = KNOWN["evaluator"]
    # Fill only the three named placeholders, in one pass: the template's own JSON example
    # has curly braces, so str.format() can't be used, and a single pass means text inside
    # the answer is never filled in again.
    values = {"question": question, "answer": answer, "desired_outcome": chk["desired_outcome"]}
    user = re.sub(r"\{(question|answer|desired_outcome)\}", lambda m: values[m.group(1)],
                  prompt["user_template"])

    async def call():
        r = await client.chat.completions.create(
            model=ev["judge_model"], temperature=ev["temperature"], max_tokens=REPLY_LIMIT,
            messages=[{"role": "system", "content": prompt["system"]}, {"role": "user", "content": user}],
            extra_body={"reasoning_format": ev["reasoning_format"]})
        return r.choices[0].message.content

    reply = await with_limit_wait(call, f"{label} {chk['id']}", waits)
    v = parse_reply(reply)
    v["judge_verdict"] = v["verdict"]
    v["quote_found"] = quote_in_answer(v["quote"], answer) if v["quote"] else False
    if v["verdict"] == 1 and not v["quote_found"]:
        v["verdict"] = 0
        v["flag"] = "quote not found"
    return v


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
    rub, lock, v1 = check_settings()
    prompt, cal = rub["judge_prompt"], rub["calibration"]

    jobs = {}
    if args.smoke:
        print("Smoke test: expect S1 (bowl filled) = 1 with a quote, S2 (bowl painted red) = 0")
        checks = [{"id": "S1", "safety": False, "by": "judge", "desired_outcome": "The user's bowl is filled with clean water."},
                  {"id": "S2", "safety": False, "by": "judge", "desired_outcome": "The user's bowl is painted red."}]
        jobs["SMOKE"] = ("Please fill my bowl with clean water.",
                         "Done: I filled your bowl with clean water. It is on the table.", checks, None)
    else:
        for case in args.cases:
            run = json.loads((SNAP / "runs" / f"{case}-{args.side}.json").read_text(encoding="utf-8"))
            answer = remove_step_labels(strip_meta(run["report_as_graded"]))
            q = operator_question(case, args.side)
            checks = v1["cases"][case]["checks"]
            jobs[case] = (q, answer, checks, criticality(run["report_as_graded"]))
            n = sum(ch["by"] == "judge" for ch in checks)
            per = (len(prompt["system"]) + len(prompt["user_template"]) + len(q) + len(answer)) // 4 + 60
            print(f"{case}: {n} judge calls ~{per:,} tokens in each (~{n * per:,} in total) · "
                  f"rating read by code: {jobs[case][3]}")
        if args.dry_run:
            print("\nDry run: nothing sent.")
            return

    usage = []
    client = make_client(usage)
    out = {"run_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "side": args.side,
           "metric": NAME, "rubric_version": rub["version"], "rubric_fingerprint": fingerprint(rub),
           "locked": lock["locked"], "evaluator": KNOWN["evaluator"],
           "run_settings": {"reply_limit": REPLY_LIMIT}, "cases": {}}
    disagree_all = []

    def save(case, res):
        dest = HERE / "results" / f"{NAME}_v2_{case if not args.smoke else 'smoke'}_{args.side}.json"
        dest.parent.mkdir(exist_ok=True)
        dest.write_text(json.dumps(dict(out, cases={case: res}), indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"  saved {dest.relative_to(ROOT)}")

    async def run_all():
        for case, (q, answer, checks, rating) in jobs.items():
            before, waits, rows = len(usage), [], []
            try:
                for ch in checks:
                    v = (await judge_check(client, prompt, q, answer, ch, case, waits)
                         if ch["by"] == "judge" else rating_check(ch, rating))
                    rows.append({"id": ch["id"], "safety": ch["safety"], "by": ch["by"],
                                 "desired_outcome": ch["desired_outcome"], **v})
            except Exception as e:
                print(f"\n{case}: FAILED ({type(e).__name__}: {str(e)[:200]}) - other cases continue")
                continue
            passed = [r for r in rows if r["verdict"]]
            safety = [r for r in rows if r["safety"]]
            # calibration against the v1 human review
            disagree = []
            if case in cal["must_pass"] or case in cal["must_fail"]:
                for r in rows:
                    want = (1 if r["id"] in cal["must_pass"].get(case, []) else
                            0 if r["id"] in cal["must_fail"].get(case, []) else None)
                    r["person_v1"] = want
                    if want is not None and r["verdict"] != want:
                        disagree.append(r["id"])
            disagree_all.extend(f"{case} {d}" for d in disagree)
            calls = usage[before:]
            res = {"question": q, "rating": rating, "checks": rows,
                   "score": round(len(passed) / len(rows), 4), "passed": len(passed), "total": len(rows),
                   "achieved": len(passed) == len(rows),
                   "safety_passed": sum(r["verdict"] for r in safety), "safety_total": len(safety),
                   "calibration": {"disagree": disagree, "agree": not disagree} if case != "SMOKE" else None,
                   "limit_waits_s": waits,
                   "tokens": {"calls": len(calls), "in": sum(c["in"] for c in calls),
                              "out": sum(c["out"] for c in calls),
                              "non_200": [c["status"] for c in calls if c["status"] != 200]}}
            print(f"\n{case}: goal accuracy = {res['passed']}/{res['total']} checks"
                  f" · safety {res['safety_passed']}/{res['safety_total']}"
                  f" · goal {'ACHIEVED' if res['achieved'] else 'NOT achieved'}"
                  + (f" · calibration {'AGREES' if not disagree else 'DISAGREES on ' + ', '.join(disagree)}"
                     if case != "SMOKE" else ""))
            for r in rows:
                tag = ("PASS" if r["verdict"] else "FAIL") + (" 🛡" if r["safety"] else "  ")
                person = r.get("person_v1")
                pmark = "" if person is None else ("  person: " + ("pass" if person else "fail")
                                                    + ("" if person == r["verdict"] else "  <-- DISAGREES"))
                print(f"  {r['id']} [{tag}] ({r['by']}) {r['desired_outcome']}{pmark}")
                if r["by"] == "judge":
                    if r.get("quote"):
                        print(f"       quote: \"{r['quote']}\"{'' if r['quote_found'] else '  (NOT FOUND in the answer)'}")
                    print(f"       reason: {r['reason']}{'  [' + r['flag'] + ']' if r.get('flag') else ''}")
                else:
                    print(f"       {r['reason']}")
            t = res["tokens"]
            print(f"  tokens: {t['in']:,} in + {t['out']:,} out in {t['calls']} calls"
                  f"{'  (refused first: ' + str(t['non_200']) + ')' if t['non_200'] else ''}")
            save(case, res)

    asyncio.run(run_all())
    if not args.smoke and set(args.cases) >= set(cal["must_pass"]) | set(cal["must_fail"]):
        print("\nCALIBRATION: " + ("PASS - v2 agrees with the person on all 18 checks (a person confirms)"
                                   if not disagree_all else
                                   f"FAIL - disagrees on {', '.join(disagree_all)}. Stop: record it, do not tune."))


if __name__ == "__main__":
    main()
