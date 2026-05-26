"""
PlantMind Plant Simulator
=========================
Simulates Northgate Automotive plant equipment publishing
sensor readings and alarm events to HiveMQ via MQTT.

Equipment:
  Line 2: P-201  — Pump
  Line 3: AT-301 — Assembly Tool
  Line 4: CV-401 — Conveyor Belt
         PC-701 — Paint Booth
         WR-401 — Welding Robot (primary story machine)

Run: python simulator.py
Stop: Ctrl+C

Each machine runs as a SimPy process.
1 sim_minute = 0.3 real seconds
WR-401 reaches HIGH alarm territory in ~4 real minutes.
Pattern detection fires (3 alarms) in ~6-8 real minutes.
"""

import simpy
import paho.mqtt.client as mqtt
import ssl
import json
import random
import os
import time
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ─── MQTT connection ────────────────────────────────────────────────────────

MQTT_HOST     = os.getenv("MQTT_HOST")
MQTT_PORT     = int(os.getenv("MQTT_PORT", 8883))
MQTT_USERNAME = os.getenv("MQTT_USERNAME")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")

# Real seconds per SimPy time unit (1 sim_minute)
SIM_SPEED = 0.3

# Plant site prefix
SITE = "northgate"

# ─── MQTT client setup ──────────────────────────────────────────────────────

mqtt_client = mqtt.Client(client_id="plantmind-simulator")
mqtt_client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
mqtt_client.tls_set(tls_version=ssl.PROTOCOL_TLS)

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("✅ Simulator connected to HiveMQ")
        print("─" * 60)
    else:
        print(f"❌ Connection failed — code {rc}")
        exit(1)

def on_disconnect(client, userdata, rc):
    if rc != 0:
        print(f"⚠️  Unexpected disconnect — code {rc}")

mqtt_client.on_connect = on_connect
mqtt_client.on_disconnect = on_disconnect

# ─── Publisher helper ───────────────────────────────────────────────────────

def publish(line, equip_tag, event_type, payload):
    """Publish a message to the correct MQTT topic."""
    topic = f"plant/{SITE}/{line}/{equip_tag}/{event_type}"
    mqtt_client.publish(topic, json.dumps(payload), qos=1)

    # Console output
    now = datetime.now().strftime("%H:%M:%S")
    if event_type == "alarm":
        severity = payload.get("severity", "")
        value    = payload.get("value", "")
        unit     = payload.get("unit", "")
        color    = "\033[91m" if severity == "HIGH" else "\033[93m" if severity == "MEDIUM" else "\033[92m"
        reset    = "\033[0m"
        print(f"[{now}] {color}ALARM{reset}  {line}/{equip_tag} | {unit}={value} | {severity}")
    else:
        # sensor — show first key/value pair
        first_key   = list(payload.keys())[0]
        first_value = payload[first_key]
        print(f"[{now}] sensor {line}/{equip_tag} | {first_key}={first_value:.2f}")

# ─── Severity helper ────────────────────────────────────────────────────────

def get_severity(wear):
    if wear < 0.40:
        return "LOW"
    elif wear < 0.70:
        return "MEDIUM"
    else:
        return "HIGH"

# ════════════════════════════════════════════════════════════════════════════
# MACHINE SIMULATORS
# Each is a SimPy process that loops forever.
# ════════════════════════════════════════════════════════════════════════════

# ─── WR-401 — Welding Robot (Line 4) ────────────────────────────────────────
# Primary story machine. Starts degraded, escalates to HIGH alarms.
# Thresholds from SOP: spatter_index limit = 3.5

def wr401_process(env):
    wear       = 0.35   # starts slightly degraded
    wear_rate  = 0.04   # per sim_hour
    line       = "line4"
    tag        = "WR-401"

    # Alarm probability per sim_tick by wear band
    def alarm_prob(w):
        if w < 0.40: return 0.03
        if w < 0.60: return 0.15
        if w < 0.80: return 0.40
        return 0.70

    print(f"[SIM] WR-401 starting — wear={wear*100:.0f}% — spatter threshold=3.5")

    while True:
        # Sensor reading — spatter_index follows wear level
        # Normal operating range 1.0–3.5. Fault range 3.5–5.0+
        spatter    = round((wear * 5.0) + random.gauss(0, 0.25), 2)
        spatter    = max(0.5, spatter)  # never negative
        wire_feed  = round(5.0 - (wear * 1.5) + random.gauss(0, 0.1), 2)
        tip_temp   = round(280 + (wear * 120) + random.gauss(0, 5), 1)

        publish(line, tag, "sensor", {
            "spatter_index":   spatter,
            "wire_feed_speed": wire_feed,
            "tip_temp_c":      tip_temp
        })

        # Alarm check
        if random.random() < alarm_prob(wear):
            severity = get_severity(wear)

            if wear < 0.40:
                msg = f"Spatter index {spatter} approaching threshold 3.5. Monitor closely."
            elif wear < 0.70:
                msg = f"Spatter index {spatter} exceeds threshold 3.5. Check wire feed tension and contact tip."
            else:
                msg = f"Spatter index {spatter} critically high. Threshold 3.5. Inspect liner immediately. Risk of scrap."

            publish(line, tag, "alarm", {
                "value":    spatter,
                "unit":     "spatter_index",
                "severity": severity,
                "message":  msg
            })

        # Wear progression — per sim_hour = every 60 sim_ticks
        wear += wear_rate / 60
        wear  = round(wear, 4)

        # Reset at full wear (simulates maintenance done)
        if wear >= 1.0:
            wear = 0.10
            print(f"\033[96m[SIM] WR-401 maintenance complete — wear reset to 10%\033[0m")

        yield env.timeout(1)

# ─── CV-401 — Conveyor Belt (Line 4) ────────────────────────────────────────
# Medium degradation. Belt speed deviation triggers alarms.
# Normal belt speed: 1.2 m/s. Alarm if deviation > 15%

def cv401_process(env):
    wear      = 0.20
    wear_rate = 0.025
    line      = "line4"
    tag       = "CV-401"
    normal_speed = 1.2   # m/s

    def alarm_prob(w):
        if w < 0.50: return 0.02
        if w < 0.75: return 0.12
        return 0.35

    print(f"[SIM] CV-401 starting — wear={wear*100:.0f}% — normal speed={normal_speed}m/s")

    while True:
        # Sensor reading
        # Speed drops as belt wears
        speed    = round(normal_speed - (wear * 0.4) + random.gauss(0, 0.05), 2)
        speed    = max(0.1, speed)
        motor_t  = round(45 + (wear * 55) + random.gauss(0, 2), 1)

        publish(line, tag, "sensor", {
            "belt_speed_ms": speed,
            "motor_temp_c":  motor_t
        })

        # Alarm — speed deviation > 15% from normal
        deviation = abs(speed - normal_speed) / normal_speed
        if random.random() < alarm_prob(wear) and deviation > 0.05:
            severity = get_severity(wear)
            msg = (
                f"Belt speed {speed} m/s — {deviation*100:.1f}% deviation from normal {normal_speed} m/s. "
                f"Motor temp {motor_t}°C. Check belt tension and drive motor."
            )
            publish(line, tag, "alarm", {
                "value":    speed,
                "unit":     "belt_speed_ms",
                "severity": severity,
                "message":  msg
            })

        wear += wear_rate / 60
        wear  = round(wear, 4)

        if wear >= 1.0:
            wear = 0.10
            print(f"\033[96m[SIM] CV-401 maintenance complete — wear reset to 10%\033[0m")

        yield env.timeout(1)

# ─── PC-701 — Paint Booth (Line 4) ──────────────────────────────────────────
# Slow degradation. Temperature and humidity out of range triggers alarms.
# Normal temp range: 18–25°C. Normal humidity: 45–65%

def pc701_process(env):
    wear      = 0.15
    wear_rate = 0.015
    line      = "line4"
    tag       = "PC-701"

    def alarm_prob(w):
        if w < 0.60: return 0.01
        if w < 0.80: return 0.08
        return 0.25

    print(f"[SIM] PC-701 starting — wear={wear*100:.0f}% — temp range 18–25°C")

    while True:
        # Sensor reading
        # Temperature drifts as HVAC degrades
        temp     = round(21.5 + (wear * 12) + random.gauss(0, 0.8), 1)
        humidity = round(55 - (wear * 20) + random.gauss(0, 2), 1)
        humidity = max(20, min(90, humidity))

        publish(line, tag, "sensor", {
            "booth_temp_c":   temp,
            "humidity_pct":   humidity
        })

        # Alarm — temp outside 18–25°C range
        if random.random() < alarm_prob(wear) and (temp > 25 or temp < 18):
            severity = get_severity(wear)
            msg = (
                f"Paint booth temperature {temp}°C outside spec range 18–25°C. "
                f"Humidity {humidity}%. Check HVAC system. Paint quality at risk."
            )
            publish(line, tag, "alarm", {
                "value":    temp,
                "unit":     "booth_temp_c",
                "severity": severity,
                "message":  msg
            })

        wear += wear_rate / 60
        wear  = round(wear, 4)

        if wear >= 1.0:
            wear = 0.10
            print(f"\033[96m[SIM] PC-701 maintenance complete — wear reset to 10%\033[0m")

        yield env.timeout(1)

# ─── AT-301 — Assembly Torque Tool (Line 3) ─────────────────────────────────
# Very slow degradation. Torque out of spec triggers alarms.
# Normal torque range: 45–55 Nm

def at301_process(env):
    wear      = 0.10
    wear_rate = 0.010
    line      = "line3"
    tag       = "AT-301"

    def alarm_prob(w):
        if w < 0.60: return 0.008
        if w < 0.80: return 0.06
        return 0.20

    print(f"[SIM] AT-301 starting — wear={wear*100:.0f}% — torque spec 45–55Nm")

    while True:
        # Sensor reading
        torque = round(50 - (wear * 15) + random.gauss(0, 1.2), 1)
        angle  = round(90 + (wear * 30) + random.gauss(0, 2), 1)

        publish(line, tag, "sensor", {
            "torque_nm":  torque,
            "angle_deg":  angle
        })

        # Alarm — torque outside 45–55 Nm
        if random.random() < alarm_prob(wear) and (torque < 45 or torque > 55):
            severity = get_severity(wear)
            msg = (
                f"Torque reading {torque} Nm outside spec range 45–55 Nm. "
                f"Angle {angle}°. Calibrate tool and check fastener seating."
            )
            publish(line, tag, "alarm", {
                "value":    torque,
                "unit":     "torque_nm",
                "severity": severity,
                "message":  msg
            })

        wear += wear_rate / 60
        wear  = round(wear, 4)

        if wear >= 1.0:
            wear = 0.10
            print(f"\033[96m[SIM] AT-301 maintenance complete — wear reset to 10%\033[0m")

        yield env.timeout(1)

# ─── P-201 — Pump (Line 2) ───────────────────────────────────────────────────
# Very slow degradation. Pressure drop triggers alarms.
# Normal pressure: 3.0–4.0 bar

def p201_process(env):
    wear      = 0.10
    wear_rate = 0.008
    line      = "line2"
    tag       = "P-201"

    def alarm_prob(w):
        if w < 0.60: return 0.005
        if w < 0.80: return 0.05
        return 0.18

    print(f"[SIM] P-201  starting — wear={wear*100:.0f}% — pressure range 3.0–4.0 bar")

    while True:
        # Sensor reading
        pressure  = round(3.5 - (wear * 1.8) + random.gauss(0, 0.1), 2)
        pressure  = max(0.1, pressure)
        flow_rate = round(12 - (wear * 6) + random.gauss(0, 0.3), 2)
        flow_rate = max(0.1, flow_rate)

        publish(line, tag, "sensor", {
            "pressure_bar":    pressure,
            "flow_rate_lpm":   flow_rate
        })

        # Alarm — pressure below 3.0 bar
        if random.random() < alarm_prob(wear) and pressure < 3.0:
            severity = get_severity(wear)
            msg = (
                f"Pump pressure {pressure} bar below minimum threshold 3.0 bar. "
                f"Flow rate {flow_rate} L/min. Check for blockage or seal wear."
            )
            publish(line, tag, "alarm", {
                "value":    pressure,
                "unit":     "pressure_bar",
                "severity": severity,
                "message":  msg
            })

        wear += wear_rate / 60
        wear  = round(wear, 4)

        if wear >= 1.0:
            wear = 0.10
            print(f"\033[96m[SIM] P-201  maintenance complete — wear reset to 10%\033[0m")

        yield env.timeout(1)

# ─── SimPy realtime wrapper ──────────────────────────────────────────────────

class RealtimeEnvironment:
    """
    Wraps SimPy environment to run at a real-time speed.
    Each sim step (1 sim_minute) pauses for SIM_SPEED real seconds.
    """
    def __init__(self):
        self.env = simpy.Environment()

    def run(self):
        # Register all machine processes
        self.env.process(wr401_process(self.env))
        self.env.process(cv401_process(self.env))
        self.env.process(pc701_process(self.env))
        self.env.process(at301_process(self.env))
        self.env.process(p201_process(self.env))

        print(f"\n[SIM] All machines running — 1 sim_minute = {SIM_SPEED}s real time")
        print(f"[SIM] WR-401 pattern detection fires in ~6-8 real minutes")
        print(f"[SIM] Press Ctrl+C to stop\n")

        # Step through sim one tick at a time with real sleep
        while True:
            self.env.step()
            time.sleep(SIM_SPEED)

# ─── Entry point ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Validate env vars
    if not all([MQTT_HOST, MQTT_USERNAME, MQTT_PASSWORD]):
        print("❌ Missing MQTT env vars — check .env file")
        print("   Required: MQTT_HOST, MQTT_USERNAME, MQTT_PASSWORD")
        exit(1)

    print("\n" + "═" * 60)
    print("  PlantMind Plant Simulator — Northgate Automotive")
    print("═" * 60)
    print(f"  Broker:   {MQTT_HOST}")
    print(f"  Username: {MQTT_USERNAME}")
    print(f"  Site:     {SITE}")
    print("═" * 60 + "\n")

    # Connect MQTT
    print("Connecting to HiveMQ...")
    mqtt_client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
    mqtt_client.loop_start()   # non-blocking background loop

    # Give MQTT a moment to connect
    time.sleep(2)

    # Start SimPy
    try:
        rt = RealtimeEnvironment()
        rt.run()
    except KeyboardInterrupt:
        print("\n\n[SIM] Simulator stopped by user")
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
        print("[SIM] Disconnected from HiveMQ cleanly")
