"""
check_floor.py - free check of the severity floor (step 4, Nov 2026).

For each FL-101 eval question, builds the real knowledge-graph context (live
Neo4j, fault matcher's AI tie-break switched off) and runs the guardrail
check_report() on made-up reports rated LOW / MEDIUM / HIGH / CRITICAL. Shows
the floor each question gets and what the guardrail does to each rating.
No AI calls. Reload fl101_graph.json first.

Expected: TC1-TC3 floor HIGH, TC4 CRITICAL, TC5 none (a short overfill after
a seal change is normal; the eval expects LOW). A rating is only ever raised.

Usage:
  venv\\Scripts\\python.exe evals\\check_floor.py
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")

import yaml  # noqa: E402
import knowledge_graph as kg  # noqa: E402
import multi_agent as ma  # noqa: E402

_match = kg.match_faults
kg.match_faults = lambda nodes, edges, text, use_ai=True: _match(nodes, edges, text, use_ai=False)

EXPECTED = {"TC1": "HIGH", "TC2": "HIGH", "TC3": "HIGH", "TC4": "CRITICAL", "TC5": None}
RANK = ma._RANK


def fake_report(level):
    return ("HOW CRITICAL IS IT:\n"
            f"- {level}\n"
            "- One sentence justification\n\n"
            "HOW TO ADDRESS IT:\n- Immediate action:\n  Step 1: Safety\n")


def rating_of(report):
    import re
    at = report.find("HOW CRITICAL IS IT")
    m = re.search(r"\b(CRITICAL|HIGH|MEDIUM|LOW)\b", report[at + 18:])
    return m.group(1) if m else None


cfg = yaml.safe_load((ROOT / "evals/promptfoo/eval_fl101.yaml").read_text(encoding="utf-8"))
plant = cfg["defaultTest"]["vars"]
ok_all = True
for t in cfg["tests"]:
    tc, q = t["vars"]["tc"], t["vars"]["question"]
    question = f"[Plant: {plant.get('plant_site', '')}, Line: {plant.get('line', '')}] {q}"
    g = kg.get_fault_chain("FL-101", incident_text=question)
    floor, why = ma._criticality_floor(g)
    good = floor == EXPECTED[tc]
    print(f"\n{tc} - {t['description']}  (matched: {', '.join(g.get('matched_faults') or []) or '?'}, "
          f"{g.get('match_confidence')})")
    print(f"   [{'OK ' if good else 'WRONG'}] floor: {floor or 'none'} (expected {EXPECTED[tc] or 'none'})"
          + (f"  - {why[:90]}" if why else ""))
    ok_all &= good
    for level in ("LOW", "MEDIUM", "HIGH", "CRITICAL"):
        out, events = ma.check_report(fake_report(level), g, [])
        after = rating_of(out)
        want = floor if floor and RANK[level] < RANK[floor] else level
        right = after == want
        ok_all &= right
        print(f"   [{'OK ' if right else 'WRONG'}] writer says {level:<8} -> report says {after}"
              + ("  (raised, note added)" if after != level else ""))

print("\nFLOOR BEHAVES AS EXPECTED FOR EVERY QUESTION" if ok_all
      else "\nSOMETHING IS WRONG - do not run the eval yet")
