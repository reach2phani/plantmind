"""
PlantMind — MQTT Subscriber (mqtt_subscriber.py)
=================================================
Listens to all plant MQTT topics from HiveMQ.
Writes alarm events to Supabase live_events table.
Runs pattern detection on every alarm received.
Saves enriched alerts to chat_history for the Alerts tab.

Run: python mqtt_subscriber.py
Stop: Ctrl+C

Requires:
  - Flask app.py running on localhost:5000 (for RAG snippets)
  - HiveMQ credentials in .env
  - Supabase credentials in .env
  - live_events table created in Supabase
  - chat_history.read column added (ALTER TABLE chat_history ADD COLUMN read boolean DEFAULT true)
"""

import paho.mqtt.client as mqtt
import ssl
import json
import os
import time
import requests
from datetime import datetime, timedelta, timezone
from collections import deque
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG — all from .env
# ─────────────────────────────────────────────────────────────────────────────

MQTT_HOST     = os.getenv("MQTT_HOST")
MQTT_PORT     = int(os.getenv("MQTT_PORT", 8883))
MQTT_USERNAME = os.getenv("MQTT_USERNAME")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")

SUPABASE_URL  = os.getenv("SUPABASE_URL")
SUPABASE_KEY  = os.getenv("SUPABASE_KEY")

PATTERN_THRESHOLD    = int(os.getenv("PATTERN_THRESHOLD", 3))
PATTERN_WINDOW_DAYS  = int(os.getenv("PATTERN_WINDOW_DAYS", 7))
COOLDOWN_MINUTES     = int(os.getenv("PROACTIVE_COOLDOWN_MINUTES", 60))

FLASK_URL = "http://localhost:5000"

# ─────────────────────────────────────────────────────────────────────────────
# SUPABASE — lazy init (avoids Windows httpx conflict)
# ─────────────────────────────────────────────────────────────────────────────

_supabase = None

def get_supabase():
    global _supabase
    if _supabase is None:
        _supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _supabase

# ─────────────────────────────────────────────────────────────────────────────
# IN-MEMORY LIVE FEED
# Holds last 50 events (sensor + alarm) for /api/live-events
# Sensor readings are NOT saved to Supabase — only held here
# ─────────────────────────────────────────────────────────────────────────────

live_feed = deque(maxlen=50)

# ─────────────────────────────────────────────────────────────────────────────
# COOLDOWN TRACKER
# Prevents the same equip_tag firing multiple auto-alerts within COOLDOWN_MINUTES
# Keys: equip_tag — Values: datetime of last alert
# ─────────────────────────────────────────────────────────────────────────────

_cooldowns = {}

# ─────────────────────────────────────────────────────────────────────────────
# CONSOLE HELPERS
# ─────────────────────────────────────────────────────────────────────────────

RED    = "\033[91m"
YELLOW = "\033[93m"
GREEN  = "\033[92m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def log(level, line, equip_tag, message):
    now = datetime.now().strftime("%H:%M:%S")
    if level == "ALARM":
        color = RED
    elif level == "PATTERN":
        color = CYAN + BOLD
    elif level == "SENSOR":
        color = ""
    else:
        color = GREEN
    print(f"[{now}] {color}{level:<8}{RESET} {line}/{equip_tag} | {message}")

# ─────────────────────────────────────────────────────────────────────────────
# RAG SNIPPET
# Calls Flask /ask to get SOP guidance for the alarm
# Gracefully returns empty string if Flask is not running
# ─────────────────────────────────────────────────────────────────────────────

def get_rag_snippet(equip_tag, alarm_message, plant_site, line):
    """
    Ask the existing RAG pipeline what the SOP says about this alarm.
    Uses the /ask endpoint already built in app.py.
    Returns a short guidance string or empty string on failure.
    """
    question = (
        f"{equip_tag} has triggered a pattern of alarms. "
        f"Latest alarm: {alarm_message}. "
        f"What does the SOP or maintenance procedure say about "
        f"this condition and what immediate action is required?"
    )

    try:
        resp = requests.post(
            f"{FLASK_URL}/ask",
            json={
                "question":   question,
                "mode":       "doc",
                "plant_site": plant_site,
                "line":       line,
                "equip_tag":  equip_tag
            },
            timeout=30,
            stream=True
        )

        if resp.status_code == 200:
            # Consume the streaming response fully
            snippet = ""
            for chunk in resp.iter_content(chunk_size=None):
                if chunk:
                    snippet += chunk.decode("utf-8", errors="ignore")
            return snippet.strip()
        else:
            print(f"  [RAG] Flask returned {resp.status_code} — alert saved without SOP snippet")
            return ""

    except requests.exceptions.ConnectionError:
        print(f"  [RAG] Flask not running — alert saved without SOP snippet")
        return ""
    except Exception as e:
        print(f"  [RAG] Error getting snippet: {e}")
        return ""

# ─────────────────────────────────────────────────────────────────────────────
# PATTERN DETECTOR
# Called after every alarm is saved to live_events
# ─────────────────────────────────────────────────────────────────────────────

def check_pattern(plant_site, line, equip_tag, latest_payload):
    """
    Count alarms for equip_tag in the last PATTERN_WINDOW_DAYS days.
    If count >= PATTERN_THRESHOLD and cooldown clear:
      - Get RAG snippet from Flask
      - Save enriched alert to chat_history (mode=proactive, read=False)
      - Update cooldown
    """

    # 1. Cooldown check
    if equip_tag in _cooldowns:
        elapsed = (datetime.now() - _cooldowns[equip_tag]).total_seconds()
        if elapsed < COOLDOWN_MINUTES * 60:
            remaining = int((COOLDOWN_MINUTES * 60 - elapsed) / 60)
            print(f"  [PATTERN] {equip_tag} — cooldown active ({remaining} min remaining)")
            return

    # 2. Count alarms in window
    try:
        since = (datetime.now(timezone.utc) - timedelta(days=PATTERN_WINDOW_DAYS)).isoformat()

        result = get_supabase()\
            .table("live_events")\
            .select("id", count="exact")\
            .eq("equip_tag", equip_tag)\
            .eq("event_type", "alarm")\
            .gte("created_at", since)\
            .execute()

        count = result.count if result.count is not None else 0

    except Exception as e:
        print(f"  [PATTERN] Supabase count error: {e}")
        return

    print(f"  [PATTERN] {equip_tag} — {count} alarms in last {PATTERN_WINDOW_DAYS} days (threshold: {PATTERN_THRESHOLD})")

    # 3. Threshold check
    if count < PATTERN_THRESHOLD:
        return

    # 4. Threshold crossed — get SOP guidance
    log("PATTERN", line, equip_tag,
        f"{BOLD}{count} alarms in {PATTERN_WINDOW_DAYS} days — threshold crossed{RESET}")
    print(f"  [PATTERN] Getting SOP guidance from RAG pipeline...")

    alarm_message = latest_payload.get("message", f"{equip_tag} alarm")
    severity      = latest_payload.get("severity", "MEDIUM")
    value         = latest_payload.get("value", "")
    unit          = latest_payload.get("unit", "")

    snippet = get_rag_snippet(equip_tag, alarm_message, plant_site, line)

    # 5. Build alert answer
    # Combines alarm pattern context + SOP snippet
    value_str = f"{value} {unit}".strip()
    alert_answer = (
        f"**Proactive Pattern Alert — {equip_tag}**\n\n"
        f"{count} alarms detected in the last {PATTERN_WINDOW_DAYS} days. "
        f"Latest reading: {value_str}. Pattern is escalating.\n\n"
    )
    if snippet:
        alert_answer += f"**SOP Guidance:**\n{snippet}"
    else:
        alert_answer += "SOP guidance unavailable — run an investigation for full analysis."

    # 6. Save enriched alert to chat_history
    try:
        get_supabase().table("chat_history").insert({
            "mode":       "proactive",
            "question":   f"Auto-detected pattern: {equip_tag} — {count} alarms in {PATTERN_WINDOW_DAYS} days",
            "answer":     alert_answer,
            "equip_tag":  equip_tag,
            "plant_site": plant_site,
            "line":       line,
            "sources":    "",
            "read":       False
        }).execute()

        print(f"  [PATTERN] ✅ Alert saved to chat_history — will appear in Alerts tab")

    except Exception as e:
        print(f"  [PATTERN] ❌ Failed to save alert: {e}")
        return

    # 7. Update cooldown
    _cooldowns[equip_tag] = datetime.now()
    print(f"  [PATTERN] Cooldown set for {equip_tag} — {COOLDOWN_MINUTES} min")

# ─────────────────────────────────────────────────────────────────────────────
# MQTT MESSAGE HANDLER
# ─────────────────────────────────────────────────────────────────────────────

def on_message(client, userdata, msg):
    """
    Called every time a message arrives on any subscribed topic.

    Topic format: plant/{plant_site}/{line}/{equip_tag}/{event_type}
    Example:      plant/northgate/line4/WR-401/alarm
    """

    # 1. Parse topic
    try:
        parts = msg.topic.split("/")
        if len(parts) != 5:
            return  # unexpected topic format — ignore

        _,  plant_site, line, equip_tag, event_type = parts

    except Exception as e:
        print(f"[SUB] Topic parse error: {e} — topic: {msg.topic}")
        return

    # 2. Parse payload
    try:
        payload = json.loads(msg.payload.decode("utf-8"))
    except Exception as e:
        print(f"[SUB] Payload parse error: {e}")
        return

    # 3. Add to live feed (all events — sensor and alarm)
    live_feed.append({
        "plant_site": plant_site,
        "line":       line,
        "equip_tag":  equip_tag,
        "event_type": event_type,
        "payload":    payload,
        "received_at": datetime.now().isoformat()
    })

    # 4. Route by event type
    if event_type == "sensor":
        # Log first sensor value — do not save to Supabase
        first_key   = list(payload.keys())[0]
        first_value = payload[first_key]
        log("SENSOR", line, equip_tag, f"{first_key}={first_value}")

    elif event_type == "alarm":
        # Log alarm
        severity = payload.get("severity", "?")
        value    = payload.get("value", "")
        unit     = payload.get("unit", "")
        log("ALARM", line, equip_tag,
            f"{unit}={value} | {severity} → saving to Supabase")

        # Save to live_events
        try:
            get_supabase().table("live_events").insert({
                "plant_site": plant_site,
                "line":       line,
                "equip_tag":  equip_tag,
                "event_type": event_type,
                "value":      payload.get("value"),
                "unit":       payload.get("unit"),
                "severity":   payload.get("severity"),
                "message":    payload.get("message")
            }).execute()

        except Exception as e:
            print(f"  [DB] ❌ Failed to save alarm: {e}")
            return

        # Run pattern detection
        check_pattern(plant_site, line, equip_tag, payload)

# ─────────────────────────────────────────────────────────────────────────────
# MQTT CONNECTION CALLBACKS
# ─────────────────────────────────────────────────────────────────────────────

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"✅ Connected to HiveMQ — {MQTT_HOST}")
        # Subscribe to all plant topics with wildcard
        client.subscribe("plant/#", qos=1)
        print(f"✅ Subscribed to plant/# — listening for all equipment")
        print(f"\n{'─'*60}")
        print(f"  Pattern threshold : {PATTERN_THRESHOLD} alarms")
        print(f"  Pattern window    : {PATTERN_WINDOW_DAYS} days")
        print(f"  Cooldown          : {COOLDOWN_MINUTES} minutes")
        print(f"  Flask RAG URL     : {FLASK_URL}")
        print(f"{'─'*60}\n")
    else:
        codes = {
            1: "incorrect protocol",
            2: "invalid client id",
            3: "server unavailable",
            4: "bad credentials",
            5: "not authorised"
        }
        reason = codes.get(rc, f"unknown code {rc}")
        print(f"❌ Connection failed — {reason}")
        exit(1)

def on_disconnect(client, userdata, rc):
    if rc != 0:
        print(f"⚠️  Unexpected disconnect (code {rc}) — attempting reconnect...")
        time.sleep(5)
        try:
            client.reconnect()
        except Exception as e:
            print(f"❌ Reconnect failed: {e}")

def on_subscribe(client, userdata, mid, granted_qos):
    print(f"[MQTT] Subscription confirmed — QoS {granted_qos}")

# ─────────────────────────────────────────────────────────────────────────────
# LIVE FEED ACCESSOR
# Called by Flask /api/live-events route
# Returns the in-memory deque as a list (most recent first)
# ─────────────────────────────────────────────────────────────────────────────

def get_live_feed():
    """Return last 50 events, most recent first."""
    return list(reversed(live_feed))

# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":

    # Validate env vars
    missing = [v for v in ["MQTT_HOST", "MQTT_USERNAME", "MQTT_PASSWORD",
                            "SUPABASE_URL", "SUPABASE_KEY"] if not os.getenv(v)]
    if missing:
        print(f"❌ Missing env vars: {', '.join(missing)}")
        print("   Check your .env file")
        exit(1)

    print("\n" + "═" * 60)
    print("  PlantMind MQTT Subscriber — Northgate Automotive")
    print("═" * 60)
    print(f"  Broker   : {MQTT_HOST}:{MQTT_PORT}")
    print(f"  Username : {MQTT_USERNAME}")
    print(f"  Flask    : {FLASK_URL} (for RAG snippets)")
    print("═" * 60 + "\n")

    # Build MQTT client
    client = mqtt.Client(client_id="plantmind-subscriber")
    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    client.tls_set(tls_version=ssl.PROTOCOL_TLS)

    client.on_connect    = on_connect
    client.on_disconnect = on_disconnect
    client.on_subscribe  = on_subscribe
    client.on_message    = on_message

    print("Connecting to HiveMQ...")
    client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)

    # Blocking loop — runs forever, processes messages as they arrive
    try:
        client.loop_forever()
    except KeyboardInterrupt:
        print("\n\n[SUB] Subscriber stopped by user")
        client.disconnect()
        print("[SUB] Disconnected from HiveMQ cleanly")
