"""
graph_rebuild_phase1b.py — Phase 1B: repair the WM-101 knowledge graph.

READ THIS FIRST
    This script CHANGES the live Neo4j graph. It is written to be reviewed
    before it is run. Nothing happens unless you pass --apply.

        venv\\Scripts\\python.exe graph_rebuild_phase1b.py              <- shows the plan only
        venv\\Scripts\\python.exe graph_rebuild_phase1b.py --apply      <- makes the changes
        venv\\Scripts\\python.exe graph_rebuild_phase1b.py --apply --keep-hc401

    Before applying anything it writes a full backup of every WM-101 and
    HC-401 note to backups/, so the change can be undone.

WHY TARGETED EDITS, NOT A RELOAD
    knowledge_graph.load_graph() deletes EVERY note for the machine and loads
    the file again. That would also delete the operator knowledge promoted
    through the review queue, which lives only in Neo4j and is in no file.
    So this script edits precisely what needs to change and leaves the rest
    alone. The seed file wm101_graph.json is updated to match, so a future
    reload rebuilds the same corrected graph.

WHAT IT FIXES (each one is a failing rule in evals/graph_health.py)
    Rule 2  five notes were floating with no connection, including all three
            specifications. The correct arc voltage (18-22 V) could never be
            reached by following links, while the WRONG operator note (15-16 V)
            was properly connected. That is the voltage bug, at its root.
    Rule 3  a specification was joined as if it were a cause.
    Rule 4  "shielding gas low" had no fix.
    Rule 1  the operator note had no source recorded.
    Rule 5  two notes disagreed about arc voltage, with nothing marking which
            one to trust.
    Rule 6  a note about HC-401 sat in the graph with no such machine in it.

    It also adds the missing "defective wire spool" cause, which is why the
    GF-INV-001 investigation blames the drive rolls.
"""

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")

import knowledge_graph as kg  # noqa: E402

EQUIP = "WM-101"
BACKUP_DIR = ROOT / "backups"
SEED_FILE = ROOT / "wm101_graph.json"
TODAY = dt.date.today().isoformat()

# ─────────────────────────────────────────────────────────────────────────────
# NEW NOTES
# Every new note carries a source. That is rule 1, and it is what lets a
# reviewer later judge whether a fact deserves to be trusted.
# ─────────────────────────────────────────────────────────────────────────────
NEW_NODES = [
    {
        "id": "defective_wire_spool", "type": "Component",
        "label": "Defective or Poor-Quality Wire Spool",
        "properties": {
            "source": "Greenfield shift log 2025-06-25 (night) + NCR-2024-047 context",
            "evidence": "25 June night shift: three overload alarms; technician "
                        "identified a defective wire spool and replaced it (GSW-WIRE-0625).",
            "check": "Inspect the wire on the spool for kinks, rust, inconsistent "
                     "diameter or birdnesting. Compare against a known-good spool.",
            "distinguishing_sign": "Overloads begin shortly after a NEW spool is fitted, "
                                   "while drive rolls and liner are recently serviced.",
            "added_by": f"Phase 1B graph rebuild {TODAY}",
        },
    },
    {
        "id": "wire_spool_replacement", "type": "Procedure",
        "label": "Wire Spool Replacement",
        "properties": {
            "source": "WM-101-SOP Section 2.1 (wire feed system) + shift log 2025-06-25",
            "steps": "Stop production. Release drive roll tension. Remove the suspect "
                     "spool. Fit a known-good spool of the correct diameter. Re-set "
                     "tension to finger-tight plus a quarter turn. Run a test bead.",
            "expected_time": "10 to 15 minutes",
            "added_by": f"Phase 1B graph rebuild {TODAY}",
        },
    },
    {
        "id": "GSW-WIRE-0625", "type": "Part",
        "label": "GSW-WIRE-0625",
        "properties": {
            "source": "Greenfield parts inventory",
            "description": "MIG welding wire spool, 0.8 mm",
            "added_by": f"Phase 1B graph rebuild {TODAY}",
        },
    },
    {
        "id": "gas_supply_restore", "type": "Procedure",
        "label": "Shielding Gas Supply Check and Restore",
        "properties": {
            "source": "WM-101-SOP Section 4.4",
            "steps": "Stop welding. Check the cylinder gauge; below 20 bar, replace the "
                     "cylinder. If the cylinder is adequate, check the regulator and all "
                     "hose connections. Test flow at the torch over paper. Do not resume "
                     "until flow is confirmed at 10-15 L/min.",
            "quality_note": "Parts welded during the alarm window must be held back for "
                            "inspection before release (plant ruling, SOP Rev 1.1 pending).",
            "added_by": f"Phase 1B graph rebuild {TODAY}",
        },
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# NEW LINKS  (from, relationship, to, why)
# ─────────────────────────────────────────────────────────────────────────────
NEW_LINKS = [
    # Rule 2 — connect the orphan specifications to the fault they govern.
    ("arc_instability", "HAS_PARAMETER", "arc_voltage_spec",
     "The correct 18-22 V spec was unreachable; this is the voltage bug's root cause."),
    ("wire_feed_overload", "HAS_PARAMETER", "wire_feed_speed_spec",
     "Wire feed speed limits belong to the overload fault."),
    ("shielding_gas_low", "HAS_PARAMETER", "gas_flow_spec",
     "Flow rate 10-15 L/min belongs to the gas fault."),
    ("wire_feed_overload", "HAS_PARAMETER", "drive_roll_tension_spec",
     "Rule 3 — a specification is a parameter of the fault, never a cause of it."),

    # Rule 2 — connect the orphan safety note and the SOP itself.
    (EQUIP, "REQUIRES_SAFETY", "ppe_required",
     "PPE applies to the machine, not to one procedure."),
    (EQUIP, "DOCUMENTED_IN", "WM-101-SOP",
     "The SOP was in the graph but joined to nothing."),

    # Rule 4 — give the gas fault a fix.
    ("gas_cylinder_low", "FIXED_BY", "gas_supply_restore", "Rule 4."),
    ("gas_hose_leak", "FIXED_BY", "gas_supply_restore", "Rule 4."),

    # GF-INV-001 — the missing cause, its fix and its part.
    ("wire_feed_overload", "CAUSED_BY", "defective_wire_spool",
     "Documented on 25 June but missing from the graph; GF-INV-001 fails without it."),
    ("defective_wire_spool", "FIXED_BY", "wire_spool_replacement", "The fix for the new cause."),
    ("defective_wire_spool", "REPLACED_WITH", "GSW-WIRE-0625", "The part to fit."),
]

# Links to remove: a specification masquerading as a cause (rule 3).
REMOVE_LINKS = [
    ("wire_feed_overload", "CAUSED_BY", "drive_roll_tension_spec",
     "A tension SPECIFICATION is not a cause of the fault. Replaced by HAS_PARAMETER."),
]


def run(cypher, apply, **params):
    if not apply:
        return None
    return kg._run(cypher, params)


def backup():
    BACKUP_DIR.mkdir(exist_ok=True)
    nodes = kg._run(
        "MATCH (n) WHERE n.equip_tag IN ['WM-101','HC-401'] "
        "RETURN labels(n)[0] AS type, properties(n) AS props", {})
    rels = kg._run(
        "MATCH (a)-[r]->(b) WHERE a.equip_tag IN ['WM-101','HC-401'] "
        "RETURN a._id AS from, type(r) AS rel, b._id AS to, properties(r) AS props", {})
    path = BACKUP_DIR / f"graph_backup_{dt.datetime.now():%Y-%m-%d_%H%M}.json"
    path.write_text(json.dumps({"nodes": nodes, "relationships": rels},
                               indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"  Backup written: {path}  ({len(nodes)} notes, {len(rels)} links)")
    return path


def main():
    ap = argparse.ArgumentParser(description="Repair the WM-101 knowledge graph (Phase 1B).")
    ap.add_argument("--apply", action="store_true", help="actually make the changes")
    ap.add_argument("--keep-hc401", action="store_true",
                    help="leave the stray HC-401 note in place instead of removing it")
    args = ap.parse_args()
    apply = args.apply

    print("\nPHASE 1B — WM-101 GRAPH REBUILD" + ("" if apply else "   (PREVIEW ONLY — nothing will change)"))
    print("=" * 78)

    if apply:
        print("\n0. BACKUP")
        backup()

    # ── 1. new notes ─────────────────────────────────────────────────────────
    print("\n1. ADD MISSING NOTES")
    for n in NEW_NODES:
        props = dict(n["properties"])
        props.update({"_id": n["id"], "_label": n["label"], "_type": n["type"],
                      "equip_tag": EQUIP, "plant_site": "greenfield", "line": "line1"})
        print(f"   + {n['type']:<10} {n['id']:<24} {n['label']}")
        run(f"MERGE (n:{n['type']} {{_id: $id}}) SET n += $props", apply, id=n["id"], props=props)

    # ── 2. remove wrong links ────────────────────────────────────────────────
    print("\n2. REMOVE WRONG LINKS")
    for a, rel, b, why in REMOVE_LINKS:
        print(f"   - {a} -{rel}-> {b}\n       {why}")
        run(f"MATCH (a {{_id:$a}})-[r:{rel}]->(b {{_id:$b}}) DELETE r", apply, a=a, b=b)

    # ── 3. add links ─────────────────────────────────────────────────────────
    print("\n3. ADD MISSING LINKS")
    for a, rel, b, why in NEW_LINKS:
        print(f"   + {a} -{rel}-> {b}\n       {why}")
        run(f"MATCH (a {{_id:$a}}) MATCH (b {{_id:$b}}) MERGE (a)-[:{rel}]->(b)",
            apply, a=a, b=b)

    # ── 4. label the operator notes ──────────────────────────────────────────
    # Rules 1 and 5. The wrong arc-voltage note is NOT deleted: it is marked
    # disputed and told which fact overrules it. Operator knowledge is never
    # quietly erased — it is labelled, so both the reviewer and the AI can see
    # that the SOP wins. The original capture stays searchable in Pinecone.
    print("\n4. LABEL THE OPERATOR NOTES (source, and which fact wins)")
    print("   ~ arc-voltage operator note -> status: disputed, contradicts arc_voltage_spec")
    run("""
        MATCH (p:Pattern) WHERE p.equip_tag = $e AND p.operator_summary IS NOT NULL
          AND (toLower(p.operator_summary) CONTAINS 'arc voltage')
        SET p.source = coalesce(p.source, 'Operator capture, promoted via review queue'),
            p.status = 'disputed',
            // One line on purpose: splitting a string across lines works in Python
            // but NOT inside a Cypher query, where the two halves are just two
            // strings with nothing joining them. That crashed the first run.
            p.disputed_reason = 'States normal arc voltage as 15-16 V. WM-101-SOP Section 3 specifies 18-22 V. The SOP is authoritative; this note must not be used as a specification.',
            p.overruled_by = 'arc_voltage_spec',
            p.reviewed_at = $today
        """, apply, e=EQUIP, today=TODAY)

    print("   ~ every operator note without a source gets one")
    run("""
        MATCH (p:Pattern) WHERE p.equip_tag = $e AND (p.source IS NULL OR p.source = '')
        SET p.source = 'Operator capture, promoted via review queue'
        """, apply, e=EQUIP)

    # ── 5. the stray HC-401 note ─────────────────────────────────────────────
    print("\n5. STRAY HC-401 NOTE")
    if args.keep_hc401:
        print("   ~ kept (--keep-hc401). Rule 6 will still fail.")
    else:
        print("   - remove the promoted HC-401 note: there is no HC-401 machine in the graph,")
        print("     so nothing can ever reach it. The operator's capture itself is untouched")
        print("     in Supabase and still searchable in Pinecone.")
        run("MATCH (p:Pattern {equip_tag:'HC-401'}) DETACH DELETE p", apply)

    print("\n" + "=" * 78)
    if apply:
        print("Applied. Now re-run the health check:")
    else:
        print("Preview only — nothing changed. To apply:")
        print("   venv\\Scripts\\python.exe graph_rebuild_phase1b.py --apply")
        print("Then:")
    print("   venv\\Scripts\\python.exe evals\\graph_health.py")
    print("\nNOTE: wm101_graph.json is NOT updated by this script. It is updated in a")
    print("separate reviewed step, so the file and the live graph stay in step.")


if __name__ == "__main__":
    main()
