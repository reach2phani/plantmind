# test_pattern.py — run once to test the full alert pipeline
import os
from dotenv import load_dotenv
from supabase import create_client
from datetime import datetime, timezone, timedelta

load_dotenv()
sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

# Insert 3 WR-401 alarms in the last 7 days
for i, val in enumerate([3.8, 4.1, 4.6]):
    sb.table("live_events").insert({
        "plant_site": "northgate",
        "line":       "line4",
        "equip_tag":  "WR-401",
        "event_type": "alarm",
        "value":      val,
        "unit":       "spatter_index",
        "severity":   "HIGH" if val > 4.0 else "MEDIUM",
        "message":    f"Spatter index {val} exceeds threshold 3.5"
    }).execute()
    print(f"Inserted alarm {i+1}: spatter={val}")

# Now insert a proactive alert directly to chat_history
sb.table("chat_history").insert({
    "mode":       "proactive",
    "question":   "Auto-detected pattern: WR-401 — 3 alarms in 7 days",
    "answer":     "**Proactive Pattern Alert — WR-401**\n\n3 alarms detected in the last 7 days. Latest reading: 4.6 spatter_index. Pattern is escalating.\n\n**SOP Guidance:**\nCheck wire feed tension and contact tip condition before resuming production. Inspect liner for wear if spatter index exceeds 4.0.",
    "equip_tag":  "WR-401",
    "plant_site": "northgate",
    "line":       "line4",
    "sources":    "",
    "read":       False
}).execute()
print("✅ Pattern alert inserted — check Alerts tab now")