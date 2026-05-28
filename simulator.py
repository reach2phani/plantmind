"""
PlantMind — Plant Simulator (simulator.py)
==========================================
Simulates Greenfield Steel Works equipment using SimPy.
Publishes sensor readings and alarm events to HiveMQ via MQTT.

Equipment simulated:
  Fabrication Line 1:
    WM-101 — MIG Welder          <- primary story machine
    GC-201 — Gas Cutter
  Processing Line 2:
    HT-301 — Heat Treatment Furnace
    HC-401 — Hydraulic Press

All alarm messages use plain operator language.

Topic structure:
  plant/greenfield/{line}/{equip_tag}/sensor
  plant/greenfield/{line}/{equip_tag}/alarm

Run: python simulator.py
Stop: Ctrl+C
"""

import simpy
import paho.mqtt.client as mqtt
import ssl
import json
import os
import random
import time
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

MQTT_HOST     = os.getenv("MQTT_HOST")
MQTT_PORT     = int(os.getenv("MQTT_PORT", 8883))
MQTT_USERNAME = os.getenv("MQTT_USERNAME")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")
PLANT_SITE    = "greenfield"

_mqtt_client = None

def get_mqtt_client():
    global _mqtt_client
    if _mqtt_client is not None:
        return _mqtt_client
    client = mqtt.Client(client_id="plantmind-simulator")
    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    client.tls_set(tls_version=ssl.PROTOCOL_TLS)
    def on_connect(c, userdata, flags, rc):
        if rc == 0:
            print(f"[MQTT] Connected to HiveMQ")
        else:
            print(f"[MQTT] Connection failed code {rc}")
    def on_disconnect(c, userdata, rc):
        if rc != 0:
            print(f"[MQTT] Disconnected unexpectedly, reconnecting...")
            time.sleep(3)
            try: c.reconnect()
            except Exception as e: print(f"[MQTT] Reconnect failed: {e}")
    client.on_connect    = on_connect
    client.on_disconnect = on_disconnect
    print(f"[MQTT] Connecting to {MQTT_HOST}:{MQTT_PORT}...")
    client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
    client.loop_start()
    time.sleep(1.5)
    _mqtt_client = client
    return client

def publish(line, equip_tag, event_type, payload):
    topic = f"plant/{PLANT_SITE}/{line}/{equip_tag}/{event_type}"
    get_mqtt_client().publish(topic, json.dumps(payload), qos=1)

RED = "\033[91m"; YELLOW = "\033[93m"; RESET = "\033[0m"

def log_sensor(line, equip_tag, readings):
    now = datetime.now().strftime("%H:%M:%S")
    s = "  ".join([f"{k}={v}" for k, v in readings.items()])
    print(f"[{now}] SENSOR   {line}/{equip_tag} | {s}")

def log_alarm(line, equip_tag, severity, message):
    now = datetime.now().strftime("%H:%M:%S")
    c = RED if severity == "HIGH" else YELLOW
    print(f"[{now}] {c}ALARM{RESET}    {line}/{equip_tag} | {severity} | {message[:70]}")

SIM_STEP_REAL_SECONDS = 0.4


def wm101_process(env):
    line = "line1"; equip_tag = "WM-101"; wear = 0.30
    print(f"[SIM] WM-101 MIG Welder starting. Wear: {wear:.0%}")
    while True:
        wire_feed  = round(5.0 + random.gauss(0, 0.2) - (wear * 1.5), 2)
        arc_volts  = round(20.0 + random.gauss(0, 0.5) - (wear * 3.0), 1)
        tip_temp   = int(round(160 + (wear * 80) + random.gauss(0, 8), 0))
        publish(line, equip_tag, "sensor", {
            "wire_feed_m_min": wire_feed,
            "arc_voltage_v":   arc_volts,
            "tip_temp_c":      tip_temp
        })
        log_sensor(line, equip_tag, {"wire_feed": wire_feed, "arc_v": arc_volts, "tip_c": tip_temp})

        if wear < 0.40:   alarm_prob = 0.04; severity = "LOW"
        elif wear < 0.65: alarm_prob = 0.18; severity = "MEDIUM"
        elif wear < 0.85: alarm_prob = 0.45; severity = "HIGH"
        else:             alarm_prob = 0.75; severity = "HIGH"

        if random.random() < alarm_prob:
            if wear < 0.45:
                msg  = "Wire feed motor overload — feed rate dropped below minimum. Check drive roll tension and wire liner for resistance."
                unit = "wire_feed_m_min"; val = wire_feed
            elif wear < 0.70:
                if random.random() < 0.5:
                    msg  = "Wire feed motor overload — feed rate dropped below minimum. Liner resistance high — inspect liner for blockage at torch neck."
                    unit = "wire_feed_m_min"; val = wire_feed
                else:
                    msg  = f"Arc instability detected — voltage fluctuating outside tolerance. Current: {arc_volts}V. Normal range: 18-22V. Check earth clamp and contact tip."
                    unit = "arc_voltage_v"; val = arc_volts
            else:
                r = random.random()
                if r < 0.40:
                    msg  = "Wire feed motor overload — feed rate dropped below minimum. Drive rolls worn — full liner and drive roll inspection required."
                    unit = "wire_feed_m_min"; val = wire_feed
                elif r < 0.70:
                    msg  = f"Arc instability detected — voltage fluctuating outside tolerance. Current: {arc_volts}V. Parts welded during this event must be flagged for quality inspection."
                    unit = "arc_voltage_v"; val = arc_volts
                else:
                    msg  = f"Contact tip temperature high — {tip_temp}C exceeds 220C threshold. Stop welding. Allow 10 minutes cooling before inspecting tip."
                    unit = "tip_temp_c"; val = tip_temp

            publish(line, equip_tag, "alarm", {"value": val, "unit": unit, "severity": severity, "message": msg})
            log_alarm(line, equip_tag, severity, msg)

        wear += 0.04 + random.gauss(0, 0.005)
        if wear >= 1.0:
            wear = 0.10
            print(f"\n[SIM] WM-101 — maintenance done. Wear reset to {wear:.0%}\n")
        yield env.timeout(1)
        time.sleep(SIM_STEP_REAL_SECONDS)


def gc201_process(env):
    line = "line1"; equip_tag = "GC-201"; wear = 0.15
    print(f"[SIM] GC-201 Gas Cutter starting. Wear: {wear:.0%}")
    while True:
        o2_pressure = round(10.0 - (wear * 3.0) + random.gauss(0, 0.3), 1)
        cut_speed   = int(round(100 - (wear * 15) + random.gauss(0, 2), 0))
        publish(line, equip_tag, "sensor", {"oxygen_pressure_bar": o2_pressure, "cut_speed_pct": cut_speed})
        if wear > 0.50 and random.random() < 0.10:
            if o2_pressure < 8.0:
                msg = f"Cutting oxygen pressure drop — supply pressure {o2_pressure} bar. Normal range 8-12 bar. Check cylinder valve and regulator."
                sev = "MEDIUM"
            else:
                msg = f"Cut speed deviation — actual {cut_speed}% of programmed speed. Check nozzle condition and oxygen pressure."
                sev = "LOW"
            publish(line, equip_tag, "alarm", {"value": o2_pressure, "unit": "oxygen_pressure_bar", "severity": sev, "message": msg})
            log_alarm(line, equip_tag, sev, msg)
        wear += 0.015 + random.gauss(0, 0.003)
        if wear >= 1.0: wear = 0.10
        yield env.timeout(1)
        time.sleep(SIM_STEP_REAL_SECONDS * 1.5)


def ht301_process(env):
    line = "line2"; equip_tag = "HT-301"; wear = 0.10; target = 850
    print(f"[SIM] HT-301 Heat Treatment Furnace starting. Wear: {wear:.0%}")
    while True:
        actual = round(target - (wear * 25) + random.gauss(0, 3), 1)
        tc_res = round(1.0 + (wear * 0.8) + random.gauss(0, 0.05), 2)
        publish(line, equip_tag, "sensor", {"furnace_temp_c": actual, "target_temp_c": target, "tc_resistance_ohm": tc_res})
        if wear > 0.40 and random.random() < 0.10:
            dev = abs(actual - target)
            if dev > 15:
                msg = f"Furnace temperature deviation — target {target}C, actual {actual}C. Deviation {dev:.1f}C exceeds 15C threshold. Check thermocouple connections."
                sev = "HIGH" if dev > 25 else "MEDIUM"
                publish(line, equip_tag, "alarm", {"value": actual, "unit": "furnace_temp_c", "severity": sev, "message": msg})
                log_alarm(line, equip_tag, sev, msg)
        wear += 0.012 + random.gauss(0, 0.002)
        if wear >= 1.0: wear = 0.10
        yield env.timeout(1)
        time.sleep(SIM_STEP_REAL_SECONDS * 2.0)


def hc401_process(env):
    line = "line2"; equip_tag = "HC-401"; wear = 0.12
    print(f"[SIM] HC-401 Hydraulic Press starting. Wear: {wear:.0%}\n")
    while True:
        pressure  = round(210 - (wear * 40) + random.gauss(0, 2), 1)
        oil_temp  = round(45 + (wear * 20) + random.gauss(0, 1.5), 1)
        cycle_t   = round(12 + (wear * 8) + random.gauss(0, 0.5), 1)
        publish(line, equip_tag, "sensor", {"hydraulic_pressure_bar": pressure, "oil_temp_c": oil_temp, "cycle_time_s": cycle_t})
        if wear > 0.45 and random.random() < 0.09:
            if pressure < 185:
                msg = f"Hydraulic pressure drop — actual {pressure} bar against set point 210 bar. Check fluid level and inspect seals for leaks."
                sev = "HIGH" if pressure < 170 else "MEDIUM"
            else:
                msg = f"Cycle time overrun — press taking {cycle_t}s against spec 12s. Check hydraulic pressure and oil temperature."
                sev = "LOW"
            publish(line, equip_tag, "alarm", {"value": pressure, "unit": "hydraulic_pressure_bar", "severity": sev, "message": msg})
            log_alarm(line, equip_tag, sev, msg)
        wear += 0.010 + random.gauss(0, 0.002)
        if wear >= 1.0: wear = 0.10
        yield env.timeout(1)
        time.sleep(SIM_STEP_REAL_SECONDS * 1.8)


if __name__ == "__main__":
    missing = [v for v in ["MQTT_HOST", "MQTT_USERNAME", "MQTT_PASSWORD"] if not os.getenv(v)]
    if missing:
        print(f"Missing env vars: {', '.join(missing)}")
        exit(1)

    print("\n" + "="*60)
    print("  PlantMind Simulator — Greenfield Steel Works")
    print("="*60)
    print(f"  Broker  : {MQTT_HOST}:{MQTT_PORT}")
    print(f"  Plant   : {PLANT_SITE}")
    print()
    print("  Equipment:")
    print("    line1/WM-101 — MIG Welder       (wear=30%)")
    print("    line1/GC-201 — Gas Cutter       (wear=15%)")
    print("    line2/HT-301 — Furnace          (wear=10%)")
    print("    line2/HC-401 — Hydraulic Press  (wear=12%)")
    print()
    print("  Timeline:")
    print("    ~4 min  — WM-101 enters HIGH alarm territory")
    print("    ~6 min  — Pattern fires (3 alarms)")
    print("    ~8 min  — Alert card on /alerts")
    print("="*60 + "\n")

    get_mqtt_client()
    time.sleep(1)

    env = simpy.Environment()
    env.process(wm101_process(env))
    env.process(gc201_process(env))
    env.process(ht301_process(env))
    env.process(hc401_process(env))

    print("[SIM] All machines running. Press Ctrl+C to stop.\n")
    print("-"*60)

    try:
        env.run()
    except KeyboardInterrupt:
        print("\n[SIM] Stopped by user")
        get_mqtt_client().loop_stop()
        get_mqtt_client().disconnect()
        print("[SIM] Disconnected cleanly")
