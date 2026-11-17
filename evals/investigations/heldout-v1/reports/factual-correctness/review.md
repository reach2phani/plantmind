# Factual correctness: human review (settings v2)

*Confirmed by the user 2026-11-17. Settings `heldout-v1/factual_correctness_v2.json` (locked 2026-11-17, fingerprint `9ec2c1074bda`). Results `heldout-v1/results/factual_correctness_v2_{H1..H5}_after.json`.*

## What a person checked

The locked settings say: a person checks the first run (H2), and every fact the judge marked MISSING, against the answer and the source document. A fact counts as present only with the same meaning and the same numbers. If the answer says the same thing with a different value or from a different procedure, it is labelled **WRONG**.

**Codes:**
- **OK**: the judge is right.
- **J**: judge error.
- **B**: borderline.
- **WRONG**: the answer gives a different value for this fact.
- **SPLIT**: RAGAS's claim-splitting lost or merged the fact, so a person decided by hand.

## Why there is a version 2

The v1 first-run check on H2 found the judge wrong on **3 of 5** "missing" verdicts:
- star wheel fitted
- rails locked
- restart at 60 bottles per minute

The cause was our reference wording, not the judge. The facts had been written as short phrases for word-matching ("The rails are locked"), and the judge read them as statements about the machine's current state. v2 rewrote each fact as the SOP's own instruction ("Lock the guide rails in position"), with the same meaning and numbers. v2 on H2 removed all three errors and still marked "check the changeover record" as missing, so the judge did not simply get easier. **v2 judge errors: 0 of 22 missing verdicts.**

## Case by case

### H1 Scale test failed before start-up: 3 of 7 facts (judge 5/9 claims)

| Fact | Judge | Code | Answer says |
|---|---|---|---|
| F1 If the test fails, do not start | in | OK | "Do NOT start the machine." |
| F2 If the test fails, call the quality lead | in | OK | "notify the quality lead as required by the SOP" |
| F3 By hand it is only 5 bottles an hour | missing | OK | "Do NOT weigh bottles by hand or bypass the checkweigher." The writer had "every hour, take 5 bottles… weigh them by hand" (graph) and turned it into a wider ban that the SOP does not contain. |
| F4 The checkweigher weighs every bottle | missing | OK | not stated |
| F5 490/510 ml rejected, 500 ml passes | in | OK | "confirm that 490 ml and 510 ml bottles are rejected and the 500 ml bottle passes" |
| F6 Record on the pre-start checklist | missing | OK | only "record the failure and corrective action"; the checklist appears only as a suggested future addition |
| F7 The shift lead signs the pre-start checklist | missing | **WRONG** | "First-Bottle Check… signed off by the shift supervisor". That is the **seal-change** sign-off (WI-FL101-001 Step 10), handed over by the knowledge graph, not the pre-start sign-off. |

### H2 Jams after a changeover: 9 of 11 facts (judge 11/13 claims)

| Fact | Judge | Code | Answer says |
|---|---|---|---|
| F1, F3–F8, F10, F11 | in | OK | all present (position B, star wheel, rails locked, stop and lock out, 60 bpm, never reach in, gloves, chipped bottles, shift lead signs) |
| F2 Rails not reset are the most common cause | missing | **B** | names the rails as *this* jam's cause "(Evidence: SOP cause list…)", but never says they are the most common cause |
| F9 If a changeover happened, check the changeover record first | missing | OK | only to *write* the record afterwards: "record the change-over… and have the shift lead sign the record" |

### H3 Underfill after new seals: 5 of 11 facts (judge 5/11 claims)

**Split problem:** RAGAS read our sentences as running text:
- F1 ("call the maintenance supervisor") was merged into F2's condition and got no claim of its own.
- F4 ("stop production, raise a work order") was merged into F3's claims.

The code flagged both as NO CLAIM. Checked by hand:

| Fact | Judge | Code | Answer says |
|---|---|---|---|
| F1 Call the maintenance supervisor | no claim | **SPLIT**, present | "notify the maintenance supervisor immediately" |
| F2 Underfill after new seals: call the maintenance supervisor | missing | OK | not stated |
| F3 3+ underfill alarms in a shift = systemic fault | in | OK | "meeting the 'three-or-more alarms in one shift' systemic fault trigger" |
| F4 Stop production, raise a maintenance work order | in (claims 3–4) | **SPLIT**, present | "stop production, raise a maintenance work order" |
| F5 Check whether the nozzle is blocked | missing | **B** | "If no dripping, lock out the machine and clean the nozzle". That is the SOP's fix for a blocked nozzle, but the blockage is never named. |
| F6 Check the product supply pressure | missing | OK | not in Diagnosis, Fix or Verify |
| F7 Don't raise the fill time for underfill | in | OK | stated (three times) |
| F8 The checkweigher report shows which valves | in | OK | "Read the checkweigher report to identify which valves are underfilling" |
| F9 Supply pressure 1.5 to 2.0 bar | missing | OK | not stated |
| F10 A new seal will not seal on a scratched seat | missing | OK | not stated |
| F11 NCR-2026-012 is why not to raise the fill time | missing | OK | cites SOP sections only, not the NCR |

**Note:** H3's report ends with "[TRUNCATED: investigation report hit the output token limit and is incomplete.]". Its "Do NOT" list has three near-identical fill-time lines. The missing facts F6 and F9 belong in the Immediate action section, which *was* completed, so the truncation did not remove them.

### H4 Broken glass on the floor: 10 of 11 facts (judge 11/12 claims)

| Fact | Judge | Code | Answer says |
|---|---|---|---|
| F1–F7, F9–F11 | in | OK | all present |
| F8 Do not reach into the machine until locked out | missing | OK | only "Do NOT open any guard until the machine has stopped and is locked out"; no reach-in rule |

### H5 Reject rate increasing: 2 of 10 facts (judge 3/12 claims)

| Fact | Judge | Code | Answer says |
|---|---|---|---|
| F1 More than 1 in 100 over an hour: tell the shift lead | in | OK | "notify the shift lead immediately as required by SOP" |
| F2 A rising reject count is often the first sign of worn seals | missing | **WRONG** | blames "possible drift" and says "Recalibrate the checkweigher". Calibration drift is in no document, and worn seals are never mentioned. |
| F3 Look at the fill valves for dripping | missing | OK | only "No… valve-drip symptom reported"; never says to look |
| F4 The checkweigher report shows which valves | missing | OK | not stated |
| F5 Weigh 5 bottles by hand to confirm | missing | OK | not stated |
| F6 Do not change the fill time | missing | OK | not stated |
| F7 Record the checkweigher reject count | in | OK | "record reject count per SOP" |
| F8 Dripping valve: maintenance replaces the seal kit | missing | OK | not stated |
| F9 Seals every 3 months or 1,500 hours | missing (2 claims) | OK | not stated |
| F10 Check the product supply pressure | missing | OK | not stated |

## Where each missing fact was lost

These use the grounding results: retrieval recall, and handover recall after its manual review.

| Lost at | Facts | Count |
|---|---|---|
| **The writer had it and left it out** | H1 F3 · H2 F2, F9 · H3 F2, F5, F6, F9, F10, F11 · H4 F8 · H5 F9 | **11** |
| Dropped by a helper, no graph rescue | H1 F4, F6, F7 · H5 F2, F3, F5, F10 | 7 |
| Never found by search, no graph rescue | H5 F4, F6, F8 | 3 |
| **All missing (incl. 2 B and 2 WRONG)** | | **21** |

"The writer had it" includes facts that reached it only through the knowledge-graph text. Which facts were in the graph text was decided by word matching (handover recall's checker) and not re-checked here.

## Totals

| | H1 | H2 | H3 | H4 | H5 | All |
|---|---|---|---|---|---|---|
| Judge (claims) | 5/9 | 11/13 | 5/11 | 11/12 | 3/12 | **35/57 = 61%** |
| After review (facts) | 3/7 | 9/11 | 5/11 | 10/11 | 2/10 | **29/50 = 58%** |
| B counted present | 3/7 | 10/11 | 6/11 | 10/11 | 2/10 | 31/50 = 62% |
| WRONG | F7 | | | | F2 | **2** |
| Judge errors (v2) | 0/4 | 0/2 | 0/6 | 0/1 | 0/9 | **0/22** |
