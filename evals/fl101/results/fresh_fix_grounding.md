# Are the repair steps real? — fresh_fix

Made by `evals/grounding_check.py`. Each numbered step under HOW TO ADDRESS IT is compared with the 2 closest passages in FL-101's own documents (SOP, work instruction, NCR, shift logs) by the judge. **yes** = stated there; **partly** = some of it added; **no** = generic advice or invented. General good practice the documents don't state counts as 'no' on purpose: that is the filler this check looks for.

## Steps grounded in the documents

| Question | Graph ON |
|---|---|
| FR-01 | 4/17 (23%) · partly 6 · no 7 |
| FR-02 | 9/15 (60%) · partly 6 · no 0 |
| **All** | **13/32 (40%) · partly 12 · no 7** |

## Says so when information is missing (instead of filling in)

| Question | Graph ON |
|---|---|
| FR-01 | no, no, no |
| FR-02 | no, no, none |

## Steps NOT grounded (read these)

| Question | Graph | Run | Judge | Step | Why |
|---|---|---|---|---|---|
| FR-02 | on | 1 | partly | Step 3: Fix - Lock out the machine and clean the nozzle of valve 12 (SOP Section 12.1, WI-FL101-001). Then check product supply pressure (Section 12.4); if pressure is below 1.5 bar, follow low-pressure procedure: clean  | The SOP instructs to lock out and clean the nozzle if there is no dripping, and Section 12.4 details the low-pressure procedure (clean filter, bleed air, restor |
| FR-02 | on | 1 | partly | Step 4: Verify - Restart machine, weigh first 20 bottles; all must be 495-505 ml. If any bottle is out of range, repeat nozzle cleaning or raise a maintenance work order. | The Work Instruction mandates weighing the first 20 bottles (495-505 ml) and stopping to check the valve if out of range. However, the step adds 'or raise a mai |
| FR-02 | on | 1 | partly | Step 5: Quality - Quarantine any bottles produced during the alarm; record results in the shift log and maintenance log; sign off first-bottle check. | The Work Instruction requires the shift supervisor to sign off the first-bottle check and record details in the maintenance log. However, the step adds 'Quarant |
| FR-02 | on | 2 | partly | Step 1: Safety - Press STOP (normal stop), apply LOTO per SAF-003 (lock out main isolator, tag with name/date, verify machine cannot start). | The LOTO steps (lock main isolator, tag name/date, verify stop) are in the passages, but 'Press STOP (normal stop)' is not explicitly stated as a prerequisite i |
| FR-02 | on | 2 | partly | Step 4: Verify - Perform first-bottle check: run first 20 bottles, all must weigh 495-505 ml. If any out of range, repeat nozzle cleaning or raise maintenance work order. | The check (20 bottles, 495-505 ml) is in the passages. However, the instruction to 'raise maintenance work order' if out of range is not stated; the document sa |
| FR-02 | on | 2 | partly | Step 5: Quality - Quarantine the first 20 bottles until verification is complete; record results in the maintenance log and sign-off by shift supervisor. | Recording results and supervisor sign-off are in the passages. However, 'Quarantine the first 20 bottles' is not stated; the document says to weigh them and imp |
| FR-01 | on | 1 | partly | Step 1: Safety - Verify that any LOTO devices placed during the Friday shutdown have been removed and that the main isolator is switched ON. Follow LOTO (SAF-003) procedure: ensure only the person who placed a lock remov | The LOTO procedure (SAF-003), lock removal rule, and tagging details are in the passages. However, the specific instruction to verify the main isolator is switc |
| FR-01 | on | 1 | partly | Step 4: Diagnosis - Perform a visual inspection of the filling heads, valves, and seals for any obvious damage or wear; ensure no foreign material is present on the floor or in the machine. | Inspecting valves/seals for damage/dripping is in Section 8.1. However, the instruction to ensure 'no foreign material is present on the floor' is not in the pa |
| FR-01 | on | 1 | no | Step 5: Fix - If any wear or damage is observed, replace the affected part per the standard maintenance work instruction (not provided here); otherwise proceed. | The step refers to a 'standard maintenance work instruction (not provided here)'. The passages do not contain a generic 'replace affected part' instruction; the |
| FR-01 | on | 1 | no | Step 6: Verify - Start the machine in test mode, observe for any alarms for at least 5 minutes, and run a short trial fill to confirm proper fill level and no underfill/overfill warnings. | The passages do not mention 'test mode', observing for 'at least 5 minutes', or running a 'short trial fill'. The Work Instruction specifies a 'sanitation rinse |
| FR-01 | on | 1 | partly | Step 7: Quality - Inspect the first product batch for fill accuracy; quarantine any bottles that do not meet specification. | Inspecting fill accuracy is supported by the 'First-Bottle Check' (weighing 20 bottles) and Checkweigher test. However, the specific instruction to 'quarantine' |
| FR-01 | on | 2 | partly | Step 3: Inspection - Visually confirm all guard doors are closed and safety switches engaged; ensure no debris or spilled product on floor; verify that no jam or foreign material is present. | Checking guard doors is in SOP 8.5. Checking for debris/spills is supported by SOP 6.4 ('Keep the floor dry'). However, 'verify that no jam or foreign material  |
| FR-01 | on | 2 | no | Step 4: Verify machine readiness - Perform a brief "dry run" at low speed to confirm seals are intact and no under-fill alarms appear; watch for any abnormal noises or leaks. | The passages do not mention performing a 'dry run' at low speed, watching for abnormal noises, or checking for leaks as a pre-start verification step. They list |
| FR-01 | on | 2 | no | Step 5: Quality - If product was previously in the line, purge the first 30 seconds of product into a waste container and inspect for proper fill level before routing to the line. | There is no instruction in the provided passages to purge the first 30 seconds of product into a waste container. The checkweigher section (8.4) mentions passin |
| FR-01 | on | 3 | partly | Step 1: Safety - Verify that no maintenance or jam clearing is required; if none, LOTO is NOT required. Ensure all personnel wear required PPE (safety shoes, cut-resistant gloves, hearing protection, safety glasses) as p | PPE list matches SOP 6.1. However, the condition 'if none [maintenance/jam], LOTO is NOT required' is an inference; the SOP states LOTO is required *before* tho |
| FR-01 | on | 3 | partly | Step 2: Inspection - Visually inspect the line for any foreign objects, leaks, or jammed bottles; confirm all guard doors are closed and safety switches engaged per FL-101-SOP 6.3-6.4. | Checking guard doors and safety switches is supported by SOP 6.3 and 8.5. Checking for leaks is supported by SOP 6.4 ('Report leaks'). However, 'visually inspec |
| FR-01 | on | 3 | no | Step 3: Power-up - Switch on power at the main isolator, ensuring the machine is not locked out. Verify that the machine starts and runs without unexpected alarms. | The passages describe how to switch OFF power for LOTO (SOP 6.2) and define LOTO, but do not provide a procedure for switching ON power or verifying the machine |
| FR-01 | on | 3 | no | Step 4: Verify - Run a short trial fill (e.g., 5 bottles) and check fill level, bottle integrity, and that no underfill or overfill alarms trigger. | The passages specify passing three specific test bottles (490, 500, 510 ml) through the checkweigher (SOP 8.4) or weighing the first 20 bottles (Work Instructio |
| FR-01 | on | 3 | no | Step 5: Quality - Inspect the trial bottles for proper fill and glass condition; quarantine any defective units per standard quality procedures. | The passages mention QA HOLD labels and that bottles on QA HOLD must be inspected by the quality lead, but do not provide a procedure for the operator to 'quara |

Honest limits: the judge sees only the 2 closest passages per step, so a step stated elsewhere in the documents can be marked 'no'. Read the 'no' rows before using the number.