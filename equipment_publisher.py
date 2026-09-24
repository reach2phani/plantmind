"""
equipment_publisher.py — announce a machine to the plant's message bus.

WHAT THIS IS
    When someone adds or edits a machine in Plant Setup, the app pins a note on
    the noticeboard: "HC-401 exists, it is a press, it sits on Processing Line
    2." Anything that cares can listen — today the knowledge-graph subscriber,
    tomorrow a dashboard. Plant Setup does not know Neo4j exists.

    In a real plant this publisher would be SAP or an edge gateway. Here it is
    Plant Setup, because that is where your master data honestly lives.

TWO DESIGN RULES
    RETAINED: the broker keeps the last message per topic, so a subscriber
    started tomorrow still receives every machine. The industrial name for this
    is a birth certificate: announce what you are when you connect.

    NEVER BLOCK THE SAVE: if the broker is unreachable, the machine is still
    saved in Supabase and this logs the failure. Announcing must not be able to
    break the thing it is announcing. Use announce_all() to catch up afterwards.

RUN (announce every machine currently in Supabase — the catch-up)
    venv\\Scripts\\python.exe equipment_publisher.py           <- preview
    venv\\Scripts\\python.exe equipment_publisher.py --apply
"""

import datetime as dt
import json
import os
import re
import ssl
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

# Same topic shape the rest of PlantMind already uses:
#   plant/{site}/{line}/{equip_tag}/{event_type}
TOPIC = "plant/{site}/{line}/{tag}/definition"


def _slug(text):
    """'Fabrication Line 1' -> 'fabrication-line-1'. Topics dislike spaces."""
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")


def work_center_id(plant_site, line):
    """
    Which work centre on the plant map this machine belongs to.

    Kept as a small explicit map rather than guessed from the name. Guessing
    from names is exactly what the misspelt "Greenfiled Steel Works" row in
    your lines table would break.
    """
    mapping = {
        ("greenfield-steel-works", "fabrication-line-1"): "WC-GSW-FAB-L1",
        ("greenfield-steel-works", "processing-line-2"):  "WC-GSW-PROC-L2",
    }
    return mapping.get((_slug(plant_site), _slug(line)))


def build_definition(row):
    """Turn a Supabase equipment row into an equipment-definition message."""
    tag = row.get("equip_tag") or ""
    eq_type = (row.get("type") or "").strip()
    return {
        "schemaVersion": "1.0.0",
        "equipment": {
            "id": tag,
            "assetTag": tag,
            "name": row.get("name") or tag,
            "lifecycleStatus": "active" if row.get("active", True) else "inactive",
        },
        # The stable ID is what the listener matches on. The readable name is
        # carried too, but nothing depends on it.
        "equipmentClass": {
            "id": f"EQCLASS-{_slug(eq_type).upper()}" if eq_type else None,
            "name": eq_type,
        },
        "equipmentDefinition": {
            "id": None,
            "manufacturer": row.get("manufacturer") or "",
            "model": "",
        },
        "parent": {"workCenterId": work_center_id(row.get("plant_site"), row.get("line"))},
        "source": {"origin": "PlantMind Plant Setup", "system": "supabase.equipment"},
        "quality": "Good",
        "timestamp": int(dt.datetime.utcnow().timestamp() * 1000),
    }


def _client():
    import paho.mqtt.client as mqtt
    c = mqtt.Client(protocol=mqtt.MQTTv311)
    c.username_pw_set(os.getenv("MQTT_USERNAME"), os.getenv("MQTT_PASSWORD"))
    c.tls_set(cert_reqs=ssl.CERT_REQUIRED, tls_version=ssl.PROTOCOL_TLS)
    c.connect(os.getenv("MQTT_HOST"), int(os.getenv("MQTT_PORT", "8883")), 30)
    return c


def publish_definition(row):
    """
    Announce one machine. Returns True if it went out.

    Never raises: a failure here must not stop Plant Setup saving.
    """
    try:
        payload = build_definition(row)
        topic = TOPIC.format(site=_slug(row.get("plant_site")),
                             line=_slug(row.get("line")),
                             tag=row.get("equip_tag"))
        client = _client()
        client.publish(topic, json.dumps(payload), qos=1, retain=True)
        client.disconnect()
        print(f"[PUB] announced {row.get('equip_tag')} -> {topic}")
        return True
    except Exception as e:
        print(f"[PUB] could not announce {row.get('equip_tag')}: {str(e)[:100]} "
              f"(the machine is still saved; run equipment_publisher.py to catch up)")
        return False


def announce_all(apply=True, everywhere=False):
    """
    Announce every machine in Supabase — the catch-up / rebuild path.

    Scoped to plants that are actually on the plant map (Greenfield today).
    The five Northgate machines would all arrive untyped and unplaced, which
    proves the warnings work but leaves five flagged machines in the graph for
    no benefit. Pass everywhere=True to include them deliberately.
    """
    from llm_logger import _get_supabase
    rows = (_get_supabase().table("equipment").select("*").execute().data or [])
    if not everywhere:
        skipped = [r for r in rows if not work_center_id(r.get("plant_site"), r.get("line"))]
        rows = [r for r in rows if work_center_id(r.get("plant_site"), r.get("line"))]
        if skipped:
            print(f"\nSkipping {len(skipped)} machine(s) whose line is not on the plant map: "
                  + ", ".join(r.get("equip_tag", "?") for r in skipped))
            print("(use --everywhere to announce them anyway, as untyped/unplaced)")
    print(f"\n{len(rows)} machine(s) to announce\n" + "=" * 68)
    sent = 0
    for row in rows:
        wc = work_center_id(row.get("plant_site"), row.get("line"))
        note = wc or "NO WORK CENTRE ON THE MAP — will arrive unplaced"
        print(f'  {row.get("equip_tag"):<8} {(row.get("type") or "?"):<14} {note}')
        if apply and publish_definition(row):
            sent += 1
    print("=" * 68)
    print(f"Announced {sent}." if apply else
          "Preview only. To announce:  venv\\Scripts\\python.exe equipment_publisher.py --apply")


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    announce_all(apply="--apply" in sys.argv, everywhere="--everywhere" in sys.argv)
