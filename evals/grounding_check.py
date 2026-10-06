"""
Reliability check: are the repair steps REAL (from this machine's documents)
or generic filler?

WHY (plain words)
    The required-fact checks only ask "is fact X in the report?". A report can
    pass them and still be half filler: FR-01 (restart after the weekend, 6 Oct
    2026) said "start in test mode and watch for 5 minutes". FL-101's documents
    have no test mode and no 5 minutes; the real answer (SOP 9: rinse, 60 per
    minute, weigh 20 bottles, 120 per minute) was missing. The made-up-numbers
    check didn't catch it.

WHAT IT DOES
    For every saved report:
      1. takes the numbered steps under HOW TO ADDRESS IT (Step 1, Step 2, ...)
      2. finds, for each step, the 2 closest passages in the machine's own
         documents (SOP, work instruction, NCR, shift logs; free, Pinecone)
      3. asks the judge ONE question per report: for each step, is it stated
         in its passages (yes), partly, or not at all (generic or invented)?
         And: when information was missing, did the report say so, or fill in?
    Result: % of steps grounded in the documents, per question and graph arm,
    plus every "not grounded" step listed for a person to read.

    Grounded means "the machine's documents say this", whatever the writer was
    given. General good practice that the documents don't state counts as NOT
    grounded on purpose: that is the filler we want to see.

COST
    Pinecone (free) + one judge call per report (~4K tokens, judge model's own
    quota). Answers are cached by report, so a re-run costs nothing.

RUN
    venv\\Scripts\\python.exe evals\\grounding_check.py --file evals\\fl101\\fresh_cases.json --tag fresh_fix2

OUTPUT
    <results folder>/<tag>_grounding.md      read this one
    <results folder>/<tag>_grounding_cache.json
"""

import argparse
import hashlib
import json
import os
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evals"))
os.environ["LANGSMITH_TRACING"] = "false"

from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")

from graph_value_test import JUDGE_MODEL, OUT_DIR as DEFAULT_OUT, _norm  # noqa: E402

PASSAGES_PER_STEP = 2
DOC_TYPES = ["SOP", "Work Instruction", "NCR", "Shift Log"]   # not operator tips: they are unreviewed


def steps_of(report):
    """The numbered steps under HOW TO ADDRESS IT, each with its continuation lines."""
    text = _norm(report)
    at = text.find("HOW TO ADDRESS IT")
    if at == -1:
        return []
    end = min([i for i in (text.find("Root cause fix", at), text.find("PLANT MANAGER", at)) if i != -1]
              or [len(text)])
    steps, cur = [], None
    for line in text[at:end].splitlines():
        if re.match(r"\s*-?\s*Step\s*\d+", line):
            cur = line.strip(" -")
            steps.append(cur)
        elif cur is not None and line.strip() and not re.match(r"\s*-\s*\w[\w ]*:", line):
            steps[-1] += " " + line.strip()
    return [s.rstrip(" -") for s in steps]


_ma = None


def passages_for(step, equipment):
    """The closest passages in the machine's documents (free: Pinecone only)."""
    global _ma
    if _ma is None:
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):
            import multi_agent
        _ma = multi_agent
    vec = _ma.pc.inference.embed(model="multilingual-e5-large", inputs=[step[:1000]],
                                 parameters={"input_type": "query", "truncate": "END"})[0].values
    res = _ma.pine_index.query(vector=vec, top_k=PASSAGES_PER_STEP, include_metadata=True,
                               filter={"equip_tag": {"$eq": equipment}, "doc_type": {"$in": DOC_TYPES}})
    return [f"[{m.metadata.get('doc_type')}: {m.metadata.get('name')}]\n{m.metadata.get('text', '')}"
            for m in res.matches]


def ask_judge(client, incident, steps, passages):
    blocks = []
    for i, (s, ps) in enumerate(zip(steps, passages), 1):
        blocks.append(f"STEP {i}: {s}\nPASSAGES FROM THE MACHINE'S DOCUMENTS:\n" + "\n---\n".join(ps))
    prompt = (
        "You check whether the steps in a maintenance report come from the machine's own documents.\n"
        f"The operator asked: \"{incident}\"\n\n"
        "For EACH step below, compare it with the passages shown under it and answer:\n"
        "  yes    = what the step tells the operator to do (actions, numbers, names) is stated in the passages\n"
        "  partly = some of it is stated, some is added (generic advice or a detail not in the passages)\n"
        "  no     = it is not stated in the passages: generic advice or invented detail\n"
        "Judge only against the passages, not general knowledge.\n\n"
        + "\n\n".join(blocks) +
        "\n\nAlso answer GAPS: does the report say plainly when it lacks a needed procedure or value "
        "(yes), or does it fill the gap with generic or invented steps (no)? Answer 'none' if nothing "
        "was missing.\n\n"
        'Reply with JSON only: {"steps": [{"n": 1, "grounded": "yes|partly|no", "why": "short"}, ...], '
        '"gaps": "yes|no|none"}')
    extra = {"reasoning_format": "hidden"}
    for attempt in range(4):
        try:
            resp = client.chat.completions.create(
                model=JUDGE_MODEL, temperature=0, max_completion_tokens=1500,
                messages=[{"role": "user", "content": prompt}], **extra)
            raw = resp.choices[0].message.content or ""
            m = re.search(r"\{.*\}", raw, re.S)
            data = json.loads(m.group(0)) if m else None
            if not data or len(data.get("steps", [])) != len(steps):
                raise ValueError(f"judge answer unusable: {raw[:80]!r}")
            return data
        except TypeError:
            extra = {}
        except Exception as e:
            wait = 20 * (attempt + 1)
            print(f"    judge error ({str(e)[:80]}) — retry in {wait}s")
            time.sleep(wait)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True, help="cases file (names the machine and results folder)")
    ap.add_argument("--tag", required=True, help="runs to check: <results folder>/<tag>_runs.jsonl")
    ap.add_argument("--arm", default="", help="only this graph arm (on / off / facts)")
    ap.add_argument("--cases", default="", help="only these case ids, comma-separated")
    args = ap.parse_args()

    spec = json.loads(Path(args.file).read_text(encoding="utf-8"))
    out_dir = ROOT / spec["out_dir"] if spec.get("out_dir") else DEFAULT_OUT
    equipment = spec["equipment"]
    incidents = {c["id"]: c["incident"] for c in spec["cases"]}
    wanted = {c for c in args.cases.split(",") if c}
    runs = [json.loads(l) for l in (out_dir / f"{args.tag}_runs.jsonl").read_text(encoding="utf-8").splitlines()
            if l.strip()]
    runs = [r for r in runs if not r.get("failed") and r["case"] in incidents
            and (not args.arm or r["arm"] == args.arm) and (not wanted or r["case"] in wanted)]

    cache_path = out_dir / f"{args.tag}_grounding_cache.json"
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
    from groq import Groq
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    per = defaultdict(lambda: {"yes": 0, "partly": 0, "no": 0, "reports": 0, "gaps": []})
    not_grounded, counter = [], defaultdict(int)
    for r in runs:
        counter[(r["case"], r["arm"])] += 1
        run_no = counter[(r["case"], r["arm"])]
        steps = steps_of(r["report"])
        if not steps:
            print(f"  {r['case']} graph {r['arm']} run {run_no}: no numbered steps found, skipped")
            continue
        key = hashlib.sha1(r["report"].encode("utf-8")).hexdigest()[:12]
        if key not in cache:
            passages = [passages_for(s, equipment) for s in steps]
            answer = ask_judge(client, incidents[r["case"]], steps, passages)
            if answer is None:
                print(f"  {r['case']} graph {r['arm']} run {run_no}: judge gave no usable answer")
                continue
            cache[key] = {"steps": steps, "answer": answer}
            cache_path.write_text(json.dumps(cache, indent=1, ensure_ascii=False), encoding="utf-8")
        got = cache[key]["answer"]
        cell = per[(r["case"], r["arm"])]
        cell["reports"] += 1
        cell["gaps"].append(got.get("gaps", "?"))
        for s, g in zip(cache[key]["steps"], got["steps"]):
            verdict = str(g.get("grounded", "")).lower()
            verdict = verdict if verdict in ("yes", "partly", "no") else "no"
            cell[verdict] += 1
            if verdict != "yes":
                not_grounded.append((r["case"], r["arm"], run_no, verdict, s, g.get("why", "")))
        print(f"  checked {r['case']} graph {r['arm']} run {run_no}: "
              + " ".join(str(g.get("grounded")) for g in got["steps"]))

    def pct(c):
        n = c["yes"] + c["partly"] + c["no"]
        return f"{c['yes']}/{n} ({100 * c['yes'] // n if n else 0}%) · partly {c['partly']} · no {c['no']}"

    arms = sorted({a for _, a in per})
    L = [f"# Are the repair steps real? — {args.tag}", "",
         "Made by `evals/grounding_check.py`. Each numbered step under HOW TO ADDRESS IT is compared "
         f"with the {PASSAGES_PER_STEP} closest passages in {equipment}'s own documents (SOP, work "
         "instruction, NCR, shift logs) by the judge. **yes** = stated there; **partly** = some of it "
         "added; **no** = generic advice or invented. General good practice the documents don't state "
         "counts as 'no' on purpose: that is the filler this check looks for.", "",
         "## Steps grounded in the documents", "",
         "| Question | " + " | ".join(f"Graph {a.upper()}" for a in arms) + " |",
         "|---" * (len(arms) + 1) + "|"]
    for cid in incidents:
        if any((cid, a) in per for a in arms):
            L.append(f"| {cid} | " + " | ".join(pct(per[(cid, a)]) if (cid, a) in per else "—" for a in arms) + " |")
    tot = {a: {k: sum(per[(c, a)][k] for c in incidents if (c, a) in per) for k in ("yes", "partly", "no")}
           for a in arms}
    L.append("| **All** | " + " | ".join(f"**{pct(tot[a])}**" for a in arms) + " |")
    L += ["", "## Says so when information is missing (instead of filling in)", "",
          "| Question | " + " | ".join(f"Graph {a.upper()}" for a in arms) + " |",
          "|---" * (len(arms) + 1) + "|"]
    for cid in incidents:
        if any((cid, a) in per for a in arms):
            L.append(f"| {cid} | " + " | ".join(", ".join(per[(cid, a)]["gaps"]) if (cid, a) in per else "—"
                                                  for a in arms) + " |")
    L += ["", "## Steps NOT grounded (read these)", "",
          "| Question | Graph | Run | Judge | Step | Why |", "|---|---|---|---|---|---|"]
    for cid, arm, n, v, s, why in not_grounded:
        L.append(f"| {cid} | {arm} | {n} | {v} | {s[:220].replace('|', '/')} | {str(why)[:160].replace('|', '/')} |")
    L += ["", "Honest limits: the judge sees only the 2 closest passages per step, so a step stated "
          "elsewhere in the documents can be marked 'no'. Read the 'no' rows before using the number."]
    out = out_dir / f"{args.tag}_grounding.md"
    out.write_text("\n".join(L), encoding="utf-8")
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
