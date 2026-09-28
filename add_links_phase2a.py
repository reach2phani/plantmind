"""
add_links_phase2a.py — two safety links the graph was missing.

WHY
    Phase 2a scoped the graph hand-over to the matched fault's own links. That
    exposed two links the graph never had. Before, both facts reached every
    report by accident, because every note was sent every time:

    1. LOTO applies to the whole machine.
       Its own note says: required before "Any maintenance, liner replacement,
       drive roll replacement" (WM-101-SOP Section 7). The graph linked it only
       to the liner and drive roll job, so a contact tip replacement lost it.
       Added the same way PPE is: WM-101 -REQUIRES_SAFETY-> LOTO.

    2. A wire feed fault triggers the quality flag.
       The flag's own note says it is triggered by "Arc instability event,
       shielding gas low alarm, wire feed fault" (SOP 4.2 and 4.4). Only the
       first two were linked. Added: Wire Feed Motor Overload -TRIGGERS-> flag.

    Safety rule used: when sources could be read either way, the more cautious
    reading wins.

WHAT IT CHANGES
    Adds the two links to wm101_graph.json (the source of truth) AND to Neo4j.
    MERGE, so running it twice gives two links, not four. Nothing is removed.

RUN (from C:\\plantmind)
    venv\\Scripts\\python.exe add_links_phase2a.py           <- preview
    venv\\Scripts\\python.exe add_links_phase2a.py --apply
    Then check: venv\\Scripts\\python.exe evals\\graph_health.py   (8/8)
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")

import knowledge_graph as kg  # noqa: E402

GRAPH_FILE = ROOT / "wm101_graph.json"
EQUIP = "WM-101"
ADDED_BY = "Phase 2a hand-over fix 2026-09-28"

LINKS = [
    {"from": "WM-101", "to": "loto_procedure", "type": "REQUIRES_SAFETY",
     "properties": {"added_by": ADDED_BY,
                    "reason": "LOTO is required before any maintenance (WM-101-SOP Section 7)"}},
    {"from": "wire_feed_overload", "to": "quality_flag", "type": "TRIGGERS",
     "properties": {"added_by": ADDED_BY,
                    "reason": "Quality flag is triggered by a wire feed fault (WM-101-SOP Sections 4.2 and 4.4)"}},
]
ALLOWED_TYPES = {"REQUIRES_SAFETY", "TRIGGERS"}   # the type goes into Cypher text


def main():
    apply = "--apply" in sys.argv
    print("\nADD MISSING SAFETY LINKS" + ("" if apply else "   (PREVIEW — nothing will change)"))
    print("=" * 72)

    raw = GRAPH_FILE.read_text(encoding="utf-8")
    data = json.loads(raw)
    existing = {(r["from"], r["type"], r["to"]) for r in data["relationships"]}
    node_ids = {n["id"] for n in data["nodes"]}

    to_file = []
    for link in LINKS:
        key = (link["from"], link["type"], link["to"])
        for end in (link["from"], link["to"]):
            if end not in node_ids:
                sys.exit(f"Stopped: '{end}' is not in {GRAPH_FILE.name}")
        in_file = key in existing
        in_db = kg._run(
            f"MATCH (a {{_id:$a}})-[r:{link['type']}]->(b {{_id:$b}}) RETURN count(r) AS n",
            {"a": link["from"], "b": link["to"]})[0]["n"] > 0
        print(f"  {link['from']} -{link['type']}-> {link['to']}")
        print(f"      file: {'already there' if in_file else 'ADD'}   "
              f"Neo4j: {'already there' if in_db else 'ADD'}")
        if not in_file:
            to_file.append(link)
        if apply and not in_db:
            assert link["type"] in ALLOWED_TYPES
            kg._run(f"MATCH (a {{_id:$a}}), (b {{_id:$b, equip_tag:$e}}) "
                    f"MERGE (a)-[r:{link['type']}]->(b) SET r += $p",
                    {"a": link["from"], "b": link["to"], "e": EQUIP, "p": link["properties"]})

    if apply and to_file:
        data["relationships"].extend(to_file)
        GRAPH_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    print("=" * 72)
    if not apply:
        print("Preview only. To apply:  venv\\Scripts\\python.exe add_links_phase2a.py --apply")
        return
    for link in LINKS:
        n = kg._run(f"MATCH (a {{_id:$a}})-[r:{link['type']}]->(b {{_id:$b}}) RETURN count(r) AS n",
                    {"a": link["from"], "b": link["to"]})[0]["n"]
        print(f"  VERIFY {link['from']} -{link['type']}-> {link['to']}: {n} link(s)")
    print("Next: venv\\Scripts\\python.exe evals\\graph_health.py")


if __name__ == "__main__":
    main()
