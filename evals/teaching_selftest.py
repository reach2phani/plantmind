"""
teaching_selftest.py — Evals teaching set, step 4: test the tests.

WHAT THIS IS (simple version)
    Before trusting a marker, give it answers whose right mark we already know.
    It runs the SAME five checkers the real runs use (from
    evals/fl101/teaching_cases.json, through the same code in
    graph_value_test.py) on:
      - three whole answers we wrote ourselves: K-PERFECT, K-BAD, K-TRICKY
      - small variants for the two code checkers (L2 fill range, L4 20 bottles)
      - a deliberately LAZY L5 checker ("fail if the answer mentions the fill
        time"), to show why checkers need testing: a correct warning NOT to
        change the fill time mentions it too.
    Every result is written down, including the ones that come out wrong.
    A wrong result here means the CHECKER is broken, not PlantMind.

COST
    Code checks: free. Judge checks (L1, L3, L5 on the three answers): 9 short
    questions to the Qwen judge, cached, so re-runs are free. No app calls.

RUN (from C:\\plantmind)
    venv\\Scripts\\python.exe evals\\teaching_selftest.py

OUTPUT
    evals/fl101/results/teaching_step4_selftest.md     read this one
    evals/fl101/results/teaching_step4_selftest.json   raw results
"""

import datetime as dt
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evals"))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")

import graph_value_test as gv  # noqa: E402  (the checkers the real runs use)

SPEC = json.loads((ROOT / "evals" / "fl101" / "teaching_cases.json").read_text(encoding="utf-8"))
CHECKS = {c["id"]: c for c in SPEC["checks"]}
OUT = ROOT / "evals" / "fl101" / "results"

# Whole answers, written by us, with the marks a careful human would give.
ANSWERS = [
    ("K-PERFECT",
     "Press stop. Check the fill valves: a valve that drips has a worn seal, so call "
     "maintenance to replace it. Lock out the machine before touching anything. After the "
     "fix, weigh the first 20 bottles. Every bottle must be 495 to 505 ml. Do not change "
     "the fill time.",
     {"L1": True, "L2": True, "L3": True, "L4": True, "L5": True}),
    ("K-BAD",
     "Increase the fill time by 0.3 seconds and keep running.",
     {"L1": False, "L2": False, "L3": False, "L4": False, "L5": False}),
    ("K-TRICKY",
     "Check for dripping valves. Bottles must be 495–505 ml. Lock out first. Weigh the "
     "first 20 bottles. Do NOT raise the fill time, it hides worn seals.",
     {"L1": True, "L2": True, "L3": True, "L4": True, "L5": True}),
]

# Small variants for the code checkers. None = "report what happens".
VARIANTS = [
    ("L2", "495 to 505 ml", True),
    ("L2", "495–505 ml (en dash)", True),
    ("L2", "between 495 and 505 ml", True),
    ("L2", "about 500 ml", False),
    ("L4", "weigh the first 20 bottles", True),
    ("L4", "check 20 bottles on the scale", True),
    ("L4", "weigh a few bottles", False),
    ("L4", "wait 20 minutes, then weigh bottles", None),
]

# The lazy L5: what a quick first attempt often looks like.
LAZY_L5 = {"id": "L5-lazy", "kind": "code", "none": ["fill time"],
           "label": "LAZY L5: fail if the answer mentions the fill time"}


def mark(check, text, cache, client):
    if check["kind"] == "code":
        return gv.check_code(check, text)
    key = f"selftest|{check['id']}|{hashlib.sha1(text.encode('utf-8')).hexdigest()[:12]}"
    return gv.check_judge(check, text, cache, key, client)


def sign(v):
    return {True: "pass", False: "fail", None: "?"}[v]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    cache_path = OUT / "teaching_selftest_judge_cache.json"
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
    from groq import Groq
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    rows, wrong = [], 0
    print("\nSTEP 4 — TEST THE TESTS\n")
    print("Whole answers (expected → got):")
    for aid, text, expect in ANSWERS:
        for lid in ("L1", "L2", "L3", "L4", "L5"):
            got = mark(CHECKS[lid], text, cache, client)
            cache_path.write_text(json.dumps(cache, indent=1), encoding="utf-8")
            ok = got == expect[lid]
            wrong += not ok
            rows.append({"part": "answers", "answer": aid, "check": lid, "kind": CHECKS[lid]["kind"],
                         "expected": sign(expect[lid]), "got": sign(got), "as_expected": ok})
            print(f"  {aid:10s} {lid} ({CHECKS[lid]['kind']:5s}) expected {sign(expect[lid]):4s} "
                  f"got {sign(got):4s} {'OK' if ok else '<-- CHECKER WRONG'}")

    print("\nVariants for the code checkers:")
    for lid, text, expect in VARIANTS:
        got = gv.check_code(CHECKS[lid], text)
        ok = None if expect is None else got == expect
        if ok is False:
            wrong += 1
        rows.append({"part": "variants", "check": lid, "text": text,
                     "expected": "report" if expect is None else sign(expect), "got": sign(got),
                     "as_expected": ok})
        note = "(no right answer set: written down)" if expect is None else ("OK" if ok else "<-- CHECKER WRONG")
        print(f"  {lid} {text!r:42s} expected {('report' if expect is None else sign(expect)):6s} "
              f"got {sign(got):4s} {note}")

    print("\nThe lazy L5 checker (expected to be WRONG on correct warnings):")
    lazy = []
    for aid, text, expect in ANSWERS:
        got = gv.check_code(LAZY_L5, text)
        lazy.append({"answer": aid, "expected": sign(expect["L5"]), "got": sign(got),
                     "as_expected": got == expect["L5"]})
        print(f"  {aid:10s} expected {sign(expect['L5']):4s} got {sign(got):4s} "
              f"{'OK' if got == expect['L5'] else '<-- lazy checker wrong'}")

    # Scorecard
    ans = [r for r in rows if r["part"] == "answers"]
    var = [r for r in rows if r["part"] == "variants"]
    lines = ["# Teaching set — step 4: test the tests", "",
             f"Run {dt.datetime.now():%Y-%m-%d %H:%M}. The same five checkers the real runs use "
             "(evals/fl101/teaching_cases.json), on answers whose right mark we already know. "
             "No app calls. Judge: " + gv.JUDGE_MODEL + ".", "",
             f"**Checkers marked as expected: {sum(r['as_expected'] for r in ans)}/{len(ans)} on whole answers, "
             f"{sum(1 for r in var if r['as_expected'])}/{sum(1 for r in var if r['as_expected'] is not None)} "
             "on variants.**", "",
             "## Whole answers", "", "| Answer | " + " | ".join(("L1", "L2", "L3", "L4", "L5")) + " |",
             "|---|---|---|---|---|---|"]
    for aid, text, expect in ANSWERS:
        cells = []
        for lid in ("L1", "L2", "L3", "L4", "L5"):
            r = next(x for x in ans if x["answer"] == aid and x["check"] == lid)
            cells.append(f"{r['got']}" + ("" if r["as_expected"] else f" ✗ (expected {r['expected']})"))
        lines.append(f"| {aid} | " + " | ".join(cells) + " |")
    lines += ["", "Answers:", ""] + [f"- **{aid}**: {text}" for aid, text, _ in ANSWERS]
    lines += ["", "## Variants (code checkers)", "", "| Checker | Text | Expected | Got |", "|---|---|---|---|"]
    for r in var:
        flag = "" if r["as_expected"] in (True, None) else " ✗"
        lines.append(f"| {r['check']} | {r['text']} | {r['expected']} | {r['got']}{flag} |")
    lines += ["", "## The lazy L5 checker: fail if the answer mentions \"fill time\"", "",
              "| Answer | Expected | Lazy checker | Real L5 (judge) |", "|---|---|---|---|"]
    for lz in lazy:
        real = next(x for x in ans if x["answer"] == lz["answer"] and x["check"] == "L5")
        lines.append(f"| {lz['answer']} | {lz['expected']} | {lz['got']}"
                     + ("" if lz["as_expected"] else " ✗") + f" | {real['got']} |")
    lines += ["", "## How to read this", "",
              "- A ✗ is a broken CHECKER, not a PlantMind failure. Fix or replace it before the real runs.",
              "- 'report' rows have no right answer set on purpose: they show a known weak spot.",
              "- The lazy checker is expected to fail correct answers. That is the lesson: a checker "
              "that looks for words cannot tell \"turn up the fill time\" from \"do NOT turn up the fill time\"."]
    (OUT / "teaching_step4_selftest.md").write_text("\n".join(lines), encoding="utf-8")
    (OUT / "teaching_step4_selftest.json").write_text(
        json.dumps({"answers": ans, "variants": var, "lazy_l5": lazy}, indent=1, ensure_ascii=False),
        encoding="utf-8")
    print(f"\n{'All checkers behaved as expected.' if not wrong else f'{wrong} checker result(s) NOT as expected — fix before real runs.'}")
    print(f"Scorecard: {OUT / 'teaching_step4_selftest.md'}")


if __name__ == "__main__":
    main()
