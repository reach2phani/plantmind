"""
Phase 0 · Batch D2 check — does WM-101 alert guidance find the SOP now?

WHAT IT DOES
  Runs the exact lookup the alarm listener uses, BEFORE and AFTER the fix,
  and prints the start of each answer. Saves nothing (no alert is created).

NEEDS
  The app running (python app.py) — guidance comes from its /ask endpoint.

COST
  Two small Q&A calls: roughly 5-6K Groq tokens in total.

RUN
  python scripts\\phase0\\d_check_alert_guidance.py
"""
import os
import sys

PROJECT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, PROJECT_DIR)
os.chdir(PROJECT_DIR)

from mqtt_subscriber import get_rag_snippet, official_location  # noqa: E402

EQUIP   = "WM-101"
TOPIC_PLANT, TOPIC_LINE = "greenfield", "line1"          # what the MQTT topic says
ALARM   = "Wire feed motor overload — feed rate dropped below minimum."

print(f"\nBEFORE (topic names '{TOPIC_PLANT}' / '{TOPIC_LINE}'):")
before = get_rag_snippet(EQUIP, ALARM, TOPIC_PLANT, TOPIC_LINE)
print("  ", (before or "(empty)")[:220].replace("\n", " "))

plant, line = official_location(EQUIP, TOPIC_PLANT, TOPIC_LINE)
print(f"\nAFTER (official names '{plant}' / '{line}'):")
after = get_rag_snippet(EQUIP, ALARM, plant, line)
print("  ", (after or "(empty)")[:400].replace("\n", " "))

ok = after and not after.startswith("NOANSWER") and "No manuals found" not in after
print("\nRESULT:", "FIXED — alert guidance now comes from the WM-101 documents"
      if ok else "NOT FIXED — paste this output to Claude")
