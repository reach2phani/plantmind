"""
ontology_bootstrap.py — give PlantMind's graph a blueprint layer and a plant map.

WHAT THIS ADDS (and why it is worth doing)
    Today the graph knows facts about ONE machine, and the machine's type is
    just a word in a property. It cannot answer "show me every welder" without
    matching text, and it does not know that WM-101 sits on a line, in an area,
    in a plant.

    This adds the two layers the manufacturing-ontology pattern is built on:

      CLASS LAYER (the blueprint — what COULD exist)
          Welder -> Equipment -> PhysicalEntity
          WorkCenter -> Location
        A class carries a stable sourceClassId ("EQCLASS-WELDER"), so incoming
        data is matched on an ID, never on a display name. Your own data shows
        why: the lines table contains a plant called "Greenfiled Steel Works",
        misspelt, with duplicate lines under it. Names drift. IDs do not.

      INSTANCE LAYER (what ACTUALLY exists)
          SITE-GSW contains AREA-GSW-FAB contains WC-GSW-FAB-L1
          WM-101 IS_INSTANCE_OF Welder, IS_LOCATED_AT WC-GSW-FAB-L1

    Nothing existing is changed or removed. The fault chain, the report diagram
    and the graph health check all keep working: the report diagram follows
    only five link types (HAS_FAULT, CAUSED_BY, FIXED_BY, REQUIRES,
    DOCUMENTED_IN) and the fault chain only reads nodes carrying an equip_tag,
    which the new location and class nodes deliberately do not have.

    Equipment is LOCATED_AT a work center, never CONTAINED by it: containment
    is for places, and a machine is a physical thing, not a place. That
    distinction is the ontology earning its keep.

RUN (from C:\\plantmind)
    venv\\Scripts\\python.exe ontology_bootstrap.py           <- preview only
    venv\\Scripts\\python.exe ontology_bootstrap.py --apply
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")

import knowledge_graph as kg  # noqa: E402

# ── A. The blueprint: (class, its parent, stable id from source systems) ─────
# Kept deliberately small — only the types your equipment table actually uses,
# plus the three roots they hang from. A blueprint nobody can hold in their
# head stops being useful.
CLASSES = [
    ("PhysicalEntity", None,            None, "Anything physical in the plant"),
    ("Location",       None,            None, "Somewhere things can be"),
    ("Equipment",      "PhysicalEntity", None, "A machine that does work"),
    ("Site",           "Location",      None, "A plant"),
    ("Area",           "Location",      None, "A part of a plant"),
    ("WorkCenter",     "Location",      None, "A line or cell where work happens"),
    # Equipment types — sourceClassId matches equipment.type in Supabase.
    ("Welder",         "Equipment", "EQCLASS-WELDER",       "Joins metal with an arc"),
    ("Press",          "Equipment", "EQCLASS-PRESS",        "Forms metal under force"),
    ("Furnace",        "Equipment", "EQCLASS-FURNACE",      "Heat treatment"),
    ("GasCutter",      "Equipment", "EQCLASS-GAS-CUTTER",   "Cuts metal with a gas flame"),
    ("Robot",          "Equipment", "EQCLASS-ROBOT",        "Programmable manipulator"),
    ("Conveyor",       "Equipment", "EQCLASS-CONVEYOR",     "Moves material"),
    ("Pump",           "Equipment", "EQCLASS-PUMP",         "Moves fluid"),
    ("PaintBooth",     "Equipment", "EQCLASS-PAINT-BOOTH",  "Applies coating"),
    ("AssemblyTool",   "Equipment", "EQCLASS-ASSEMBLY-TOOL", "Fastens parts"),
]

# ── B. The plant map (Greenfield only — the plant this project is scoped to) ──
SITE = ("SITE-GSW", "Greenfield Steel Works", "Site")
AREAS = [
    ("AREA-GSW-FAB",  "Fabrication Area", "Area", SITE[0]),
    ("AREA-GSW-PROC", "Processing Area",  "Area", SITE[0]),
]
WORK_CENTERS = [
    ("WC-GSW-FAB-L1",  "Fabrication Line 1", "WorkCenter", "AREA-GSW-FAB"),
    ("WC-GSW-PROC-L2", "Processing Line 2",  "WorkCenter", "AREA-GSW-PROC"),
]

# ── C. Put the machine we already model onto that map ────────────────────────
# Only WM-101. The other three Greenfield machines arrive through the MQTT
# pipeline next — that is the whole point: the plant announces its own assets
# instead of someone typing them into the database.
PLACE_EXISTING = [("WM-101", "Welder", "WC-GSW-FAB-L1")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    # Parameter named _cypher, not c: the Cypher queries below use $c for a
    # class name, and a plain "c" collided with it.
    run = ((lambda _cypher, **p: kg._run(_cypher, p)) if args.apply
           else (lambda _cypher, **p: None))

    print("\nONTOLOGY BOOTSTRAP" + ("" if args.apply else "   (PREVIEW — nothing will change)"))
    print("=" * 74)

    print("\nA. BLUEPRINT (class layer)")
    for name, parent, source_id, desc in CLASSES:
        arrow = f" -> {parent}" if parent else ""
        print(f"   Class {name}{arrow}" + (f"   [{source_id}]" if source_id else ""))
        run("MERGE (c:Class {name: $n}) SET c.description = $d, c.sourceClassId = $s, "
            "c._label = $n, c._type = 'Class'", n=name, d=desc, s=source_id)
    for name, parent, _, _ in CLASSES:
        if parent:
            run("MATCH (c:Class {name:$n}), (p:Class {name:$p}) MERGE (c)-[:SUBCLASS_OF]->(p)",
                n=name, p=parent)

    print("\nB. PLANT MAP (instance layer)")
    print(f'   {SITE[0]:<16} {SITE[1]}')
    run("MERGE (n:Instance:Location:Site {_id:$i}) SET n._label=$l, n._type='Site', "
        "n.name=$l, n.source='Supabase plant_sites'", i=SITE[0], l=SITE[1])
    run("MATCH (n:Instance {_id:$i}), (c:Class {name:'Site'}) MERGE (n)-[:IS_INSTANCE_OF]->(c)",
        i=SITE[0])

    for _id, label, cls, parent in AREAS + WORK_CENTERS:
        print(f'   {_id:<16} {label:<20} in {parent}')
        run(f"MERGE (n:Instance:Location:{cls} {{_id:$i}}) SET n._label=$l, n._type=$t, "
            "n.name=$l, n.source='Supabase lines/plant_sites'", i=_id, l=label, t=cls)
        run("MATCH (n:Instance {_id:$i}), (c:Class {name:$c}) MERGE (n)-[:IS_INSTANCE_OF]->(c)",
            i=_id, c=cls)
        # CONTAINS runs parent -> child, so the plant reads top-down.
        run("MATCH (p:Instance {_id:$p}), (n:Instance {_id:$i}) MERGE (p)-[:CONTAINS]->(n)",
            p=parent, i=_id)

    print("\nC. PUT THE EXISTING MACHINE ON THE MAP")
    for tag, cls, wc in PLACE_EXISTING:
        print(f"   {tag} IS_INSTANCE_OF {cls}, IS_LOCATED_AT {wc}")
        run("MATCH (e:Equipment {_id:$t}) SET e:Instance", t=tag)
        run("MATCH (e:Equipment {_id:$t}), (c:Class {name:$c}) MERGE (e)-[:IS_INSTANCE_OF]->(c)",
            t=tag, c=cls)
        run("MATCH (e:Equipment {_id:$t}), (w:Instance {_id:$w}) MERGE (e)-[:IS_LOCATED_AT]->(w)",
            t=tag, w=wc)

    print("\n" + "=" * 74)
    if not args.apply:
        print("Preview only. To apply:  venv\\Scripts\\python.exe ontology_bootstrap.py --apply")
        return

    # ── Prove it worked, by asking questions only the new layers can answer ──
    print("VERIFY\n")
    q1 = kg._run("MATCH (e:Instance)-[:IS_INSTANCE_OF]->(:Class {name:'Welder'}) "
                 "RETURN e._id AS id, e._label AS name", {})
    print("  Every welder (by meaning, not by name):", q1)
    q2 = kg._run("MATCH (s:Site)-[:CONTAINS]->(a:Area)-[:CONTAINS]->(w:WorkCenter)"
                 "<-[:IS_LOCATED_AT]-(e) RETURN s.name AS site, a.name AS area, "
                 "w.name AS line, e._id AS machine", {})
    print("  Where each machine sits:")
    for r in q2:
        print(f'     {r["machine"]}: {r["site"]} > {r["area"]} > {r["line"]}')
    q3 = kg._run("MATCH (:Instance {_id:'WM-101'})-[:IS_INSTANCE_OF]->(c:Class)"
                 "-[:SUBCLASS_OF*]->(p:Class) RETURN c.name AS is_a, collect(p.name) AS which_is_a", {})
    print("  What WM-101 is, all the way up:", q3)


if __name__ == "__main__":
    main()
