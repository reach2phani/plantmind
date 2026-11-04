"""
check_must_show.py - free check before a token-spending run (after-fix-1).

For each FL-101 eval question, rebuilds the knowledge graph's MANDATORY
REQUIREMENTS list (the must-show list the writer is given) and checks that
every safety rule the failure map expects for that scenario is on it.
No AI calls: the fault matcher's small-model tie-break is switched off.
Reads the LIVE graph in Neo4j, so reload fl101_graph.json first.

Usage:
  venv\\Scripts\\python.exe evals\\check_must_show.py
"""
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")

import yaml  # noqa: E402
import knowledge_graph as kg  # noqa: E402

_match = kg.match_faults
kg.match_faults = lambda nodes, edges, text, use_ai=True: _match(nodes, edges, text, use_ai=False)

cfg = yaml.safe_load((ROOT / "evals/promptfoo/eval_fl101.yaml").read_text(encoding="utf-8"))
fmap = json.loads((ROOT / "evals/fl101/failure_map.json").read_text(encoding="utf-8"))
plant = cfg["defaultTest"]["vars"]

ok_all = True
for t in cfg["tests"]:
    tc, q = t["vars"]["tc"], t["vars"]["question"]
    question = f"[Plant: {plant.get('plant_site', '')}, Line: {plant.get('line', '')}] {q}"
    g = kg.get_fault_chain("FL-101", incident_text=question)
    warnings = g.get("warnings") or []
    print(f"\n{tc} - {t['description']}  (matched: {', '.join(g.get('matched_faults') or []) or '?'}, "
          f"{g.get('match_confidence')}, source {g.get('source', 'neo4j')})")
    for w in warnings:
        print(f"   - {w[:130]}")
    exact = g.get("exact_values") or []
    print(f"   exact values ({len(exact)}):")
    for v in exact:
        print(f"   = {v[:160]}")
    # Step 2: the TC2 rail positions must be on the exact-values list.
    for metric, c in fmap["checks"].items():
        if c.get("type") != "missing_exact_value" or f":{tc}-" not in metric:
            continue
        hit = any(re.search(p, v, re.I) for p in c.get("phrases", []) for v in exact)
        if not hit:
            ok_all = False
        print(f"   [{'OK ' if hit else 'MISSING'}] {metric}: {c['fact']}")
    # Step 5: who signs off must be on the must-show list (TC5 failed it 3 of 6 runs).
    for metric in ("TS:TC5-signoff",):
        c = fmap["checks"][metric]
        if f":{tc}-" not in metric:
            continue
        hit = any(re.search(p, w, re.I) for p in c.get("phrases", []) for w in warnings)
        if not hit:
            ok_all = False
        print(f"   [{'OK ' if hit else 'MISSING'}] {metric}: {c['fact']}")
    for metric, c in fmap["checks"].items():
        if c.get("type") != "missing_safety_warning" or f"-{tc}-" not in metric:
            continue
        hit = any(re.search(p, w, re.I) for p in c.get("phrases", []) for w in warnings)
        implied = "IMPLIED" in c.get("source", "")
        mark = "OK " if hit else ("-- " if implied else "MISSING")
        if not hit and not implied:
            ok_all = False
        print(f"   [{mark}] {metric}: {c['fact']}"
              + ("  (not in the graph by design: only implied by the documents; the template rule covers it)"
                 if not hit and implied else ""))

print("\nALL EXPECTED RULES AND VALUES ON THE MUST-SHOW LISTS" if ok_all
      else "\nSOME EXPECTED RULES OR VALUES ARE MISSING - do not run the eval yet")
