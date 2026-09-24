"""
equipment_definition.py — turn an equipment-definition message into graph facts.

THE PATTERN (from the manufacturing-ontology series)
    A machine is not typed into the graph by hand. Something that already owns
    the master data ANNOUNCES it, and a listener decides what it is and where
    it goes:

        Plant Setup  ->  MQTT  ->  this handler  ->  Neo4j

    Four jobs, in order:  validate -> what is it? -> where is it? -> write.

TWO RULES WORTH KNOWING
    1. Match on IDs, never on names. The message says EQCLASS-PRESS, not
       "Press". Names get renamed, translated and mistyped — your own lines
       table contains a plant called "Greenfiled Steel Works".
    2. Never silently lose context. If the type or the line cannot be resolved,
       the machine is still written down and the gap is REPORTED as
       "untyped" / "unplaced". Dropping the message loses the machine; guessing
       invents a fact. This does neither, and the warnings become a signal that
       someone added a machine type nobody has mapped yet.

WHERE THE MEANING LIVES
    Not here. This module carries and resolves; the ontology (Class nodes,
    written by ontology_bootstrap.py) decides what a "press" is. Keeping the
    meaning in the graph is what stops it scattering across integration code.

TEST IT WITHOUT MQTT
    venv\\Scripts\\python.exe equipment_definition.py          <- dry run, one sample
    venv\\Scripts\\python.exe equipment_definition.py --apply  <- actually write it
"""

import datetime as dt
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import knowledge_graph as kg  # noqa: E402

REQUIRED = ("equipment", "parent")


def validate(payload):
    """Return a list of problems. Empty list means the message is usable."""
    problems = []
    if not isinstance(payload, dict):
        return ["payload is not an object"]
    for key in REQUIRED:
        if not payload.get(key):
            problems.append(f"missing '{key}'")
    equip = payload.get("equipment") or {}
    if not equip.get("id"):
        problems.append("missing equipment.id — nothing stable to key on")
    return problems


def _resolve_class(definition_id, class_id):
    """
    What kind of thing is this?

    Two tiers, specific first — the article's example is the clearest reason:
    a source system may call three different vessels "Tank", while the make and
    model is enough to know one of them is really a buffer tank.

        1. the exact make/model (equipmentDefinition.id)
        2. the broad category    (equipmentClass.id)

    Whatever matches must sit under Equipment in the ontology, so a stray ID
    cannot type a machine as a Document.
    """
    if definition_id:
        rows = kg._run(
            "MATCH (c:Class) WHERE $d IN coalesce(c.sourceDefinitionIds, []) "
            "AND EXISTS { (c)-[:SUBCLASS_OF*]->(:Class {name:'Equipment'}) } "
            "RETURN c.name AS name LIMIT 1", {"d": definition_id})
        if rows:
            return rows[0]["name"], "equipmentDefinition.id"
    if class_id:
        rows = kg._run(
            "MATCH (c:Class {sourceClassId: $s}) "
            "WHERE EXISTS { (c)-[:SUBCLASS_OF*]->(:Class {name:'Equipment'}) } "
            "RETURN c.name AS name LIMIT 1", {"s": class_id})
        if rows:
            return rows[0]["name"], "equipmentClass.id"
    return None, None


def _resolve_location(work_center_id):
    """Where does it exist? The work centre must already be on the plant map."""
    if not work_center_id:
        return None
    rows = kg._run("MATCH (w:Instance {_id: $w}) RETURN w._id AS id LIMIT 1",
                   {"w": work_center_id})
    return rows[0]["id"] if rows else None


def handle_definition(payload, apply=True):
    """
    Process one equipment-definition message.
    Returns {equip_id, class, location, warnings, written}.
    """
    problems = validate(payload)
    if problems:
        print(f"[DEF] rejected: {'; '.join(problems)}")
        return {"written": False, "warnings": problems}

    equip = payload["equipment"]
    eq_id = equip["id"]
    eq_class = payload.get("equipmentClass") or {}
    eq_def = payload.get("equipmentDefinition") or {}
    source = payload.get("source") or {}

    class_name, matched_on = _resolve_class(eq_def.get("id"), eq_class.get("id"))
    work_center = _resolve_location((payload.get("parent") or {}).get("workCenterId"))

    warnings = []
    if not class_name:
        warnings.append(f"untyped — no ontology class for equipmentClass.id="
                        f"{eq_class.get('id')!r} / equipmentDefinition.id={eq_def.get('id')!r}")
    if not work_center:
        warnings.append(f"unplaced — work centre "
                        f"{(payload.get('parent') or {}).get('workCenterId')!r} is not on the plant map")

    props = {
        "_id": eq_id, "_label": equip.get("name") or eq_id, "_type": "Equipment",
        "equip_tag": eq_id,
        "name": equip.get("name") or eq_id,
        "assetTag": equip.get("assetTag") or eq_id,
        "lifecycleStatus": equip.get("lifecycleStatus") or "",
        "serialNumber": equip.get("serialNumber") or "",
        "manufacturer": eq_def.get("manufacturer") or "",
        "model": eq_def.get("model") or "",
        "equipmentClassId": eq_class.get("id") or "",
        "equipmentDefinitionId": eq_def.get("id") or "",
        # Provenance: who said so. The same discipline as putting "SOP §3" on a
        # fact — six months from now you can ask where this came from.
        "source": f"{source.get('origin', 'unknown')} via equipment definition message",
        "sourceSystem": source.get("system", ""),
        "schemaVersion": payload.get("schemaVersion", ""),
        "lastSeenAt": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "lastSeenQuality": payload.get("quality", ""),
        "contextWarnings": "; ".join(warnings),
    }

    if apply:
        # MERGE on the stable id: the same message arriving 50 times gives one
        # machine, not 50. created_at is set once; everything else stays current.
        kg._run("MERGE (e:Instance:Equipment {_id: $id}) "
                "ON CREATE SET e.created_at = datetime() SET e += $props",
                {"id": eq_id, "props": props})

        if class_name:
            # Authoritative: the latest message wins. Leaving the old type in
            # place would make the machine two types at once, and every query
            # would return it twice.
            kg._run("MATCH (e:Equipment {_id:$id})-[r:IS_INSTANCE_OF]->(:Class) DELETE r",
                    {"id": eq_id})
            kg._run("MATCH (e:Equipment {_id:$id}), (c:Class {name:$c}) "
                    "MERGE (e)-[:IS_INSTANCE_OF]->(c)", {"id": eq_id, "c": class_name})

        if work_center:
            # Same rule for location — a machine that moved line is not in two
            # places at once.
            kg._run("MATCH (e:Equipment {_id:$id})-[r:IS_LOCATED_AT]->() DELETE r",
                    {"id": eq_id})
            kg._run("MATCH (e:Equipment {_id:$id}), (w:Instance {_id:$w}) "
                    "MERGE (e)-[:IS_LOCATED_AT]->(w)", {"id": eq_id, "w": work_center})

    where = f"at {work_center}" if work_center else "UNPLACED"
    what = f"{class_name} (matched on {matched_on})" if class_name else "UNTYPED"
    print(f"[DEF] {eq_id}: {what}, {where}" + ("  [preview]" if not apply else ""))
    for w in warnings:
        print(f"[DEF]   warning: {w}")

    return {"equip_id": eq_id, "class": class_name, "location": work_center,
            "warnings": warnings, "written": apply}


# ── Try it without MQTT ──────────────────────────────────────────────────────
SAMPLE = {
    "schemaVersion": "1.0.0",
    "equipment": {"id": "HC-401", "assetTag": "HC-401", "name": "Hydraulic Press",
                  "lifecycleStatus": "active"},
    "equipmentClass": {"id": "EQCLASS-PRESS", "name": "Press"},
    "equipmentDefinition": {"id": None, "manufacturer": "", "model": ""},
    "parent": {"workCenterId": "WC-GSW-PROC-L2"},
    "source": {"origin": "PlantMind Plant Setup", "system": "supabase.equipment"},
    "quality": "Good",
}

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    apply = "--apply" in sys.argv
    print("\nSample equipment definition" + ("" if apply else "  (preview — nothing written)"))
    handle_definition(SAMPLE, apply=apply)
