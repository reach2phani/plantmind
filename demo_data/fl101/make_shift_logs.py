"""
make_shift_logs.py — writes the FL-101 demo shift logs for September 2026.

DEMO DATA — written for the PlantMind learning project. Not from a real plant.

The logs tell one month's story on Filling Line 1, in the same 10 columns as
the other PlantMind shift logs. The events line up with the FL-101 SOP, work
instruction and NCR, so investigations can connect "what happened" (these
logs) with "what the documents say".

Story: seals due for replacement -> valve 9 starts dripping -> a 330 ml
changeover with the rails left in position A causes 3 infeed jams -> 3
underfill alarms in one night (fill time change refused) -> seals replaced,
expected overfill while seals settle -> one glass breakage handled by the
book -> a blocked supply filter drops the pressure to 1.2 bar.

Rows for the capper (CP-102) and labeller (LB-103) are included, as on a real
line log.

RUN (from C:\\plantmind)
    venv\\Scripts\\python.exe demo_data\\fl101\\make_shift_logs.py
Writes demo_data/fl101/shift_logs/DemoBottling-Shift-Log-<date>-<shift>.csv
"""

import csv
from pathlib import Path

OUT = Path(__file__).resolve().parent / "shift_logs"
LINE = "Filling Line 1"
COLUMNS = ["shift_date", "shift", "line", "time", "category", "equipment",
           "description", "action_taken", "operator", "status"]

# (date, shift, [(time, category, equipment, description, action, operator, status)])
LOGS = [
    ("2026-09-01", "Day", [
        ("06:05", "Routine", "FL-101", "Pre-start checks complete. No dripping valves. Rails at position A for 500 ml. Supply pressure 1.8 bar. Glass kit on hook.", "Checklist signed by shift lead.", "A. Moreno", "OK"),
        ("06:12", "Quality Check", "FL-101", "Checkweigher test bottles: 490 ml rejected, 500 ml passed, 510 ml rejected.", "No action.", "A. Moreno", "OK"),
        ("06:30", "Production", "FL-101", "Started at 60 bottles per minute. First 20 bottles 499-502 ml. Raised to 120 bottles per minute.", "No action.", "A. Moreno", "Running"),
        ("08:00", "Quality Check", "FL-101", "Hourly weights 500, 501, 499, 500, 502 ml. Reject count 3 per 1,000.", "No action.", "A. Moreno", "OK"),
        ("09:40", "Routine", "CP-102", "Capper torque check 1.6 Nm on 5 caps.", "No action.", "A. Moreno", "OK"),
        ("11:00", "Maintenance", "FL-101", "Maintenance planner note: seal kits last changed 2 June. 3-month replacement due this week.", "Seal change to be scheduled.", "M. Varga", "Noted"),
        ("13:50", "Handover", "FL-101", "Good shift. 47,800 bottles filled. Rejects 0.3 in 100.", "Seal change still to be booked.", "A. Moreno", "Handover complete"),
    ]),
    ("2026-09-03", "Night", [
        ("22:05", "Routine", "FL-101", "Pre-start checks complete. Supply pressure 1.8 bar. Rails at position A.", "Checklist signed.", "P. Singh", "OK"),
        ("23:00", "Quality Check", "FL-101", "Hourly weights 499, 498, 500, 497, 499 ml. Reject count 6 per 1,000.", "Within range. Watching reject count.", "P. Singh", "OK"),
        ("00:40", "Routine", "LB-103", "Label roll changed. Label position checked.", "No action.", "P. Singh", "OK"),
        ("02:00", "Quality Check", "FL-101", "Valve check: valve 9 dripping slightly between fills. Checkweigher shows valve 9 filling 494-496 ml.", "Reported to shift lead. Maintenance asked to include valve 9 in the seal change.", "P. Singh", "Noted"),
        ("04:00", "Quality Check", "FL-101", "Hourly weights 498, 496, 499, 500, 497 ml. Reject count 8 per 1,000.", "Shift lead informed. Seal change not yet booked.", "P. Singh", "Noted"),
        ("05:50", "Handover", "FL-101", "Rejects rising slowly through the night (0.8 in 100). Valve 9 dripping.", "Day shift to chase seal change.", "P. Singh", "Handover complete"),
    ]),
    ("2026-09-07", "Day", [
        ("06:05", "Routine", "FL-101", "Pre-start checks complete. Supply pressure 1.7 bar.", "Checklist signed.", "J. Kim", "OK"),
        ("07:30", "Changeover", "FL-101", "Changeover to 330 ml bottles for customer order. Star wheel changed to 330 ml.", "Changeover record left for shift lead to sign.", "J. Kim", "Complete"),
        ("08:05", "Alarm", "FL-101", "Infeed jam - bottles stopped at infeed. 330 ml bottles falling over at the guide rails.", "Pressed STOP, cleared bottles, restarted.", "J. Kim", "Resolved"),
        ("08:20", "Alarm", "FL-101", "Infeed jam again at the same place.", "Pressed STOP and cleared bottles. Shift lead reminded operator to lock out before reaching in (SOP 6.2).", "J. Kim", "Resolved"),
        ("08:40", "Alarm", "FL-101", "Third infeed jam since the changeover. One chipped bottle found in the infeed.", "Machine locked out. Chipped bottle removed. Shift lead called.", "J. Kim", "Escalated"),
        ("09:10", "Changeover", "FL-101", "Shift lead checked changeover record: guide rails were still in position A (500 ml). Should be position B for 330 ml.", "Rails moved to position B and locked. Restarted at 60 bottles per minute for 2 minutes, then normal speed.", "M. Varga", "Resolved"),
        ("11:00", "Quality Check", "FL-101", "No jams since the rails were reset. Hourly weights for 330 ml bottles in range.", "No action.", "J. Kim", "OK"),
        ("13:50", "Handover", "FL-101", "3 infeed jams this morning, all caused by rails left at position A after the changeover. Running well since 09:10.", "Reminder to all: reset rails from changeover sheet CS-FL101.", "J. Kim", "Handover complete"),
    ]),
    ("2026-09-08", "Day", [
        ("06:05", "Routine", "FL-101", "Pre-start checks complete for 330 ml. Rails at position B.", "Checklist signed.", "A. Moreno", "OK"),
        ("09:00", "Quality Check", "FL-101", "330 ml run normal. No jams. Reject count 5 per 1,000.", "No action.", "A. Moreno", "OK"),
        ("13:00", "Changeover", "FL-101", "Changeover back to 500 ml. Locked out. Rails moved to position A and locked. 500 ml star wheel fitted.", "20 bottles run at 60 bottles per minute: no jams, all 496-503 ml. Record signed by shift lead.", "A. Moreno", "Complete"),
        ("13:50", "Handover", "FL-101", "Back on 500 ml. Valve 9 still dripping. Seal change booked for 11 September.", "No action.", "A. Moreno", "Handover complete"),
    ]),
    ("2026-09-10", "Night", [
        ("22:05", "Routine", "FL-101", "Pre-start checks. Valves 9 and 15 dripping between fills.", "Reported. Seal change booked for tomorrow.", "P. Singh", "Noted"),
        ("23:00", "Quality Check", "FL-101", "Reject count 14 per 1,000 - above 1 in 100.", "Shift lead told as per SOP 11.", "P. Singh", "Noted"),
        ("01:30", "Alarm", "FL-101", "Underfill alarm - Fill level low - bottles under target volume. Checkweigher report: valves 9 and 15 underfilling (491-494 ml).", "Pressed STOP. Valves 9 and 15 dripping. No maintenance on nights. Restarted and watched.", "P. Singh", "Resolved"),
        ("02:10", "Routine", "CP-102", "Cap supply topped up.", "No action.", "P. Singh", "OK"),
        ("03:20", "Alarm", "FL-101", "Second underfill alarm tonight. Same valves 9 and 15.", "Operator asked to raise the fill time to stop the underfill. Shift lead said no: fill time must not be changed (SOP 10, NCR-2026-012).", "L. Haddad", "Resolved"),
        ("04:45", "Alarm", "FL-101", "Third underfill alarm this shift. Valves 9, 15 and now 3 underfilling.", "Systemic fault (3 alarms in one shift). Production stopped. Maintenance work order raised. Maintenance supervisor called.", "L. Haddad", "Escalated"),
        ("05:50", "Handover", "FL-101", "Line stopped since 04:45 for worn seals. Fill time left at 3.2 seconds.", "Seal change first thing on day shift.", "L. Haddad", "Production stopped"),
    ]),
    ("2026-09-11", "Day", [
        ("06:10", "Maintenance", "FL-101", "Seal change started. Locked out. Bowl drained. Replacing seal kits on valves 3, 9, 15 and 21 (SEAL-FV-24).", "Work instruction WI-FL101-001 followed.", "T. Novak", "In Progress"),
        ("06:55", "Maintenance", "FL-101", "Old seals flattened and cracked at the edge. Seals had about 1,720 running hours - past the 1,500-hour limit.", "Recorded in maintenance log.", "T. Novak", "Noted"),
        ("07:05", "Maintenance", "FL-101", "New seals fitted. Tools and parts counted. Lock removed. Sanitation rinse 10 minutes done.", "No action.", "T. Novak", "Complete"),
        ("07:20", "Quality Check", "FL-101", "First-bottle check: first 6 bottles 506-509 ml in the first 2 minutes, then 499-502 ml.", "Operator worried about overfill. Technician explained slight overfill while new seals settle is expected (WI-FL101-001). Checkweigher rejected the 6 bottles. All later bottles in range.", "T. Novak", "OK"),
        ("07:30", "Maintenance", "FL-101", "First-bottle check signed off by shift supervisor. Production restarted at 120 bottles per minute.", "No action.", "M. Varga", "Resolved"),
        ("10:00", "Quality Check", "FL-101", "Reject count back to 2 per 1,000. No dripping valves.", "No action.", "A. Moreno", "OK"),
        ("13:50", "Handover", "FL-101", "Seals replaced on 4 valves. Running well.", "Next seal change due December.", "A. Moreno", "Handover complete"),
    ]),
    ("2026-09-14", "Night", [
        ("22:05", "Routine", "FL-101", "Pre-start checks complete. No dripping valves. Supply pressure 1.8 bar.", "Checklist signed.", "P. Singh", "OK"),
        ("00:00", "Quality Check", "FL-101", "Hourly weights 500, 500, 501, 499, 500 ml. Reject count 2 per 1,000.", "No action.", "P. Singh", "OK"),
        ("02:30", "Routine", "LB-103", "Labeller glue temperature checked.", "No action.", "P. Singh", "OK"),
        ("05:50", "Handover", "FL-101", "Quiet shift. 55,200 bottles filled.", "No action.", "P. Singh", "Handover complete"),
    ]),
    ("2026-09-17", "Day", [
        ("06:05", "Routine", "FL-101", "Pre-start checks complete. Glass check sheet signed.", "Checklist signed.", "J. Kim", "OK"),
        ("10:42", "Alarm", "FL-101", "Glass breakage detected in filler. Bottle shattered at the discharge star wheel.", "Emergency stop pressed. Machine locked out before any guard was opened. Quality lead called.", "J. Kim", "Emergency stop"),
        ("10:50", "Quality", "FL-101", "All bottles filled 10:12-10:42 put on QA HOLD (about 3,600 bottles). 14 open bottles within 2 metres of the break thrown away.", "QA HOLD labels fitted to 4 pallets.", "N. Adeyemi", "In Progress"),
        ("11:05", "Quality", "FL-101", "Glass cleaned up with the red glass kit and vacuum. No compressed air used. Sanitation rinse 10 minutes done.", "Glass breakage log completed.", "J. Kim", "Complete"),
        ("11:40", "Quality", "FL-101", "Quality lead inspected the filler and signed off restart.", "Line restarted.", "N. Adeyemi", "Resolved"),
        ("13:30", "Quality", "FL-101", "Held bottles inspected. 3,580 released, 20 rejected. Broken bottle came from a chipped batch from the bottle supplier.", "Supplier complaint raised for the chipped batch.", "N. Adeyemi", "Complete"),
        ("13:50", "Handover", "FL-101", "One glass breakage handled by the book. About 1 hour lost.", "Watch for chipped bottles from the same supplier batch.", "J. Kim", "Handover complete"),
    ]),
    ("2026-09-21", "Night", [
        ("22:05", "Routine", "FL-101", "Pre-start checks. Supply pressure 1.6 bar. Filter tag shows last cleaned 2 September.", "Filter clean overdue - noted for day shift.", "P. Singh", "Noted"),
        ("00:15", "Alarm", "FL-101", "Product supply pressure low - below 1.3 bar. Reading 1.2 bar. Some underfilled bottles rejected.", "Pressed STOP. Supply filter FLT-PS-10 found blocked. Filter cleaned. Air bled from the supply line.", "P. Singh", "Resolved"),
        ("00:40", "Quality Check", "FL-101", "Pressure back to 1.7 bar. First 20 bottles 498-502 ml.", "Restarted at normal speed.", "P. Singh", "OK"),
        ("03:00", "Quality Check", "FL-101", "Hourly weights 500, 499, 501, 500, 500 ml.", "No action.", "P. Singh", "OK"),
        ("05:50", "Handover", "FL-101", "One low pressure alarm at 00:15 - blocked filter, weekly clean was missed.", "Weekly filter clean added to Monday day-shift checklist.", "P. Singh", "Handover complete"),
    ]),
    ("2026-09-24", "Day", [
        ("06:05", "Routine", "FL-101", "Pre-start checks complete. Supply pressure 1.8 bar.", "Checklist signed.", "A. Moreno", "OK"),
        ("06:20", "Maintenance", "FL-101", "Weekly supply filter clean done (FLT-PS-10).", "Filter tag updated.", "A. Moreno", "Complete"),
        ("09:00", "Quality Check", "FL-101", "Hourly weights 501, 500, 500, 499, 501 ml. Reject count 2 per 1,000.", "No action.", "A. Moreno", "OK"),
        ("11:15", "Routine", "CP-102", "Capper torque check 1.6 Nm on 5 caps.", "No action.", "A. Moreno", "OK"),
        ("13:50", "Handover", "FL-101", "Good shift. No alarms.", "No action.", "A. Moreno", "Handover complete"),
    ]),
    ("2026-09-26", "Night", [
        ("22:05", "Routine", "FL-101", "Pre-start checks complete. No dripping valves.", "Checklist signed.", "P. Singh", "OK"),
        ("01:00", "Quality Check", "FL-101", "Hourly weights 500, 500, 499, 500, 501 ml. Reject count 1 per 1,000.", "No action.", "P. Singh", "OK"),
        ("05:50", "Handover", "FL-101", "Quiet shift. 56,000 bottles filled.", "No action.", "P. Singh", "Handover complete"),
    ]),
]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for date, shift, rows in LOGS:
        path = OUT / f"DemoBottling-Shift-Log-{date}-{shift}.csv"
        with path.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(COLUMNS)
            for time, cat, equip, desc, action, op, status in rows:
                w.writerow([date, shift, LINE, time, cat, equip, desc, action, op, status])
        print(f"  {path.name}: {len(rows)} rows")
    print(f"Wrote {len(LOGS)} shift logs to {OUT}")


if __name__ == "__main__":
    main()
