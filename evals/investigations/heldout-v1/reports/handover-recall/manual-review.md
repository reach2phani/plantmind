# Handover recall: manual review of the DROPPED facts

**Rule (locked in `handover_recall.json` before the run):** a fact counts as KEPT only if a helper summary states the same instruction or fact with the same meaning and the same numbers. A vaguer version does not count. Each decision quotes the summary text.

**Automated checker:** 10 of 39 kept (26%); 29 facts sent here for review.
**Proposed by Claude, confirmed by the user on 2026-11-16** (all decisions agreed, including the two borderline DROPPED calls H3 F3 and H2 F11).

## The 29 reviewed facts

| Case | Fact | Review | Summary text (quoted) | Why the checker missed it |
|---|---|---|---|---|
| H1 | F4 The checkweigher weighs every bottle | DROPPED | (nothing; SOP helper gives only the rejection limits) | |
| H1 | F5 490 and 510 ml rejected, 500 ml passes | **KEPT** | SOP: "490 ml and 510 ml must be rejected; 500 ml must pass" | rewording |
| H1 | F6 Record on the pre-start checklist | DROPPED | (nothing) | |
| H1 | F7 The shift lead signs it | DROPPED | (nothing) | |
| H2 | F2 Rails not reset after a changeover are the usual cause | DROPPED | Closest: SOP "If jams persist, inspect the guide rails for correct positioning". A check, not "the usual cause" | |
| H2 | F5 Stop and lock out before clearing a jam | **KEPT** | SOP: "Lockout/Tagout (LOTO) before any maintenance, jam clearing, or part change" | rewording |
| H2 | F8 Wear cut-resistant gloves | **KEPT** | SOP: "PPE: … cut‑resistant gloves" | special hyphen |
| H2 | F11 The shift lead signs the changeover record | DROPPED | Closest: SOP "Record the change‑over in the shift log and sign it". It doesn't say the **shift lead** signs | |
| H3 | F1 Call the maintenance supervisor | **KEPT** | SOP: "…raise a maintenance work order, and notify the maintenance supervisor" | rewording |
| H3 | F3 3 underfill alarms in one shift = a systemic fault | DROPPED | Closest: SOP "If three or more underfill alarms in one shift, stop production…". The trigger and its action are kept (F4); the meaning "this is a systemic fault, not a one-off" is not | |
| H3 | F5 Check for a blocked nozzle | **KEPT** | SOP: "If no dripping → lock out the machine … and clean the nozzle of that valve" | rewording |
| H3 | F6 Check the product supply pressure | **KEPT** | SOP: "Check product supply pressure (Section 12.4)" | rewording ("the" missing) |
| H3 | F7 Do not raise the fill time | **KEPT** | SOP: "Do NOT increase fill time; it hides the root cause…" | rewording |
| H3 | F8 The checkweigher report shows which valves | **KEPT** | SOP: "Read the checkweigher report to identify which valves are underfilling" | rewording |
| H3 | F9 Supply pressure should be 1.5 to 2.0 bar | **KEPT** | SOP: "Product supply pressure: 1.5 – 2.0 bar" | dash instead of "to" |
| H3 | F11 NCR-2026-012 is the reason not to raise the fill time | **KEPT** | SOP: "Do NOT increase fill time … (see NCR‑2026‑012)" | special hyphen |
| H4 | F1 Stop the line | **KEPT** | SOP: "\*\*Stop the line immediately\*\* using the emergency stop" | Markdown bold |
| H4 | F4 The quality lead signs off before restart | **KEPT** | SOP: "\*\*Obtain sign‑off from the quality lead\*\* before restarting the line" | Markdown + rewording |
| H4 | F7 Do not open any guard until locked out | **KEPT** | SOP: "\*\*Do not open any guard\*\* until the machine has fully stopped and is locked out" | Markdown |
| H4 | F8 Do not reach in until locked out | DROPPED | Closest: SOP "LOTO procedure before any maintenance or clearing a jam". Reaching in is not mentioned | |
| H4 | F9 Bottles from the last 30 minutes on QA HOLD | **KEPT** | SOP: "\*\*Place all bottles filled in the last 30 minutes on QA HOLD\*\*" | Markdown + rewording |
| H4 | F10 Throw away open bottles within 2 metres | **KEPT** | SOP: "\*\*Dispose of any open bottles within 2 m of the broken glass\*\*" | Markdown + rewording |
| H4 | F11 Record it in the glass breakage log | **KEPT** | SOP: "\*\*Record the event\*\* in the glass breakage log" | Markdown |
| H5 | F2 A rising reject count is often the first sign of worn seals | DROPPED | Closest: Alarm "Elevated reject rates have historically coincided with underfill alarms and valve‑drip issues". From the logs, and a different claim | |
| H5 | F3 Look at the fill valves for dripping | DROPPED | (nothing; the SOP helper says "no further escalation… unless additional symptoms appear") | |
| H5 | F5 Hand-weigh 5 bottles to confirm | DROPPED | (nothing) | |
| H5 | F7 Record the checkweigher reject count | DROPPED | (nothing) | |
| H5 | F9 Seals every 3 months or 1,500 running hours | **KEPT** | SOP: "Seal replacement interval: every 3 months or 1,500 running hours, whichever comes first" | rewording ("every" once) |
| H5 | F10 Check the product supply pressure | DROPPED | Closest: SOP lists "Product supply pressure: 1.5 – 2.0 bar" as a spec, not an instruction to check it | |

## Result

| Case | Found by search | Kept: checker | **Kept: corrected** | Reached the writer (with graph): corrected |
|---|---|---|---|---|
| H1 Scale test | 6 | 2 (33%) | **3 (50%)** | 3 (50%) |
| H2 Jams | 8 | 4 (50%) | **6 (75%)** | 8 (100%) |
| H3 Underfill | 9 | 1 (11%) | **8 (89%)** | 9 (100%) |
| H4 Broken glass | 9 | 2 (22%) | **8 (89%)** | 9 (100%) |
| H5 Reject rate | 7 | 1 (14%) | **2 (29%)** | 2 (29%) |
| **All** | **39** | **10 (26%)** | **27 (69%)** | **31 (79%)** |

## Why the checker missed 17 of the 27 kept facts

| Cause | Facts |
|---|---|
| Small rewording ("the" missing, "1.5 – 2.0" vs "1.5 to 2.0", "every" once) | 9 |
| Markdown bold marks (`**`) inside the words | 5 |
| Special non-breaking hyphen (‑) in "cut‑resistant", "NCR‑2026‑012", "sign‑off" | 3 |

## The 12 truly dropped facts: where search had found them

| Case | Dropped facts | Search piece | What the helper did |
|---|---|---|---|
| H1 | F4, F6, F7 | SOP piece 7 (rank 4) | Kept piece 9 (the test-bottle rule), ignored piece 7 (the pre-start checks) entirely |
| H2 | F2, F11 | SOP piece 19 (rank 4) | Took the steps from piece 19, dropped the "usual cause" and "shift lead signs" |
| H3 | F3 | SOP piece 14 | Kept the 3-alarm action, dropped the "systemic fault" meaning |
| H4 | F8 | SOP piece 6 | Kept the guard rule, dropped "never reach in" |
| H5 | F2, F3, F5, F7 | **SOP piece 12: the same piece as F1, which it kept** | Kept the one-line answer ("tell the shift lead"), dropped the 4 "what to check" facts next to it |
| H5 | F10 | SOP piece 8 | Kept the pressure number as a spec, not the instruction to check it |
