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
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

# Same topic shape the rest of PlantMind already uses:
#   plant/{site}/{line}/{equip_tag}/{event_type}
TOPIC = "plant/{site}/{line}/{tag}/definition"


def _slug(text):
    """'Fabrication Line 1' -> 'fabrication-line-1'. Topics dislike spaces."""
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")


_official = None


def _official_lines():
    """
    The (plant, line) pairs Plant Setup says exist: names from plant_sites and
    active rows in lines, exactly as saved. Read once per process.
    """
    global _official
    if _official is None:
        try:
            from llm_logger import _get_supabase
            sb = _get_supabase()
            plants = {r["name"] for r in (sb.table("plant_sites").select("name").execute().data or [])}
            rows = sb.table("lines").select("name,plant_site,active").execute().data or []
            _official = {(r["plant_site"], r["name"]) for r in rows
                         if r.get("plant_site") in plants and r.get("active") is not False}
        except Exception as e:
            print(f"[PUB] could not read the plant list: {str(e)[:80]}")
            return set()
    return _official


def work_center_id(plant_site, line):
    """
    Which work centre on the plant map this machine belongs to.

    1. The explicit map below, for lines placed by hand (ontology_bootstrap.py).
    2. Otherwise, generated from the names, BUT only when the plant and the line
       exactly match the official lists in Plant Setup (Phase 2a D1). Before,
       any new line needed a code edit here and in ontology_bootstrap.py (it
       did for FL-101). Still no guessing from free text: the misspelt
       "Greenfiled Steel Works" row in the lines table is not in plant_sites,
       so it stays off the map instead of creating a fake plant.
    """
    mapping = {
        ("greenfield-steel-works", "fabrication-line-1"): "WC-GSW-FAB-L1",
        ("greenfield-steel-works", "processing-line-2"):  "WC-GSW-PROC-L2",
        ("demo-bottling-plant", "filling-line-1"):        "WC-DBP-FILL-L1",
    }
    known = mapping.get((_slug(plant_site), _slug(line)))
    if known:
        return known
    if plant_site and line and (plant_site.strip(), line.strip()) in _official_lines():
        return f"WC-{_slug(plant_site).upper()}-{_slug(line).upper()}"
    return None


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
        # The names travel with the id, so the listener can add a line it has
        # not seen yet to the plant map (Phase 2a D1).
        "parent": {"workCenterId": work_center_id(row.get("plant_site"), row.get("line")),
                   "siteName": (row.get("plant_site") or "").strip(),
                   "workCenterName": (row.get("line") or "").strip()},
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
        # paho 2.x only finishes connecting while its network loop runs.
        # Publishing straight after connect() and hanging up at once meant
        # the message never left the laptop — while this still printed
        # "announced". Now: wait for the connection, wait for the broker to
        # confirm receipt, and raise (-> "could not announce") if either fails.
        client.loop_start()
        try:
            for _ in range(50):                      # up to 5 s to connect
                if client.is_connected():
                    break
                time.sleep(0.1)
            if not client.is_connected():
                raise ConnectionError("broker did not accept the connection within 5 s")
            info = client.publish(topic, json.dumps(payload), qos=1, retain=True)
            info.wait_for_publish(timeout=10)
            if not info.is_published():
                raise TimeoutError("broker did not confirm the message within 10 s")
        finally:
            client.loop_stop()
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
