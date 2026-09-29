# FL-101 answer key (draft for review)

Written ONLY from the three FL-101 documents (demo_data/fl101/), before the
knowledge graph exists, so the graph cannot grade its own work. Every
expected fact names its source section. After review this becomes:
graph_value cases (JSON), promptfoo cases (YAML) and retrieval labels.

Machine: FL-101 Bottle Filler · Demo Bottling Plant · Filling Line 1

---

## 1. Graph value cases (graph ON vs OFF, 3 runs each)

Every case also has the ISOLATION check below.

### FL-01 Underfill, repeat alarms
> "FL-101 bottles are coming out underfilled. That's the third underfill alarm tonight."

| Must include | How | Source |
|---|---|---|
| Check the valves for dripping / worn fill valve seals | judge | SOP 12.1 |
| Allowed fill range 495 to 505 ml | code | SOP 10 |
| 3+ underfill alarms in one shift = systemic: stop, call maintenance | judge | SOP 12.1 |
| Lock out (LOTO) before replacing seals | judge | WI 6, SOP 6.2 |
| Sanitation rinse 10 minutes after a seal change | code | WI Step 9 |
| Weigh the first 20 bottles | code | WI Step 10 |
| **Must NOT:** increase / change the fill time in the repair steps | code (section) | SOP 10, NCR |

### FL-02 Overfill after a seal change
> "We just replaced the seals on FL-101 and the bottles are slightly overfilled for the first couple of minutes. Is something wrong?"

| Must include | How | Source |
|---|---|---|
| Slight overfill in the first 2 to 3 minutes after a seal change is expected, not a fault | judge | WI 8 (IMPORTANT) |
| Do not change settings | judge | WI 8 |
| Rinse + first 20 bottles 495 to 505 ml | code | WI Steps 9-10 |
| **Must NOT:** recommend replacing the seals again as the fix | judge | WI 8 |

### FL-03 Jams after a changeover
> "FL-101 bottles keep jamming at the infeed since we switched to 330 ml bottles this morning."

| Must include | How | Source |
|---|---|---|
| Guide rails not reset after the changeover is the likely cause | judge | SOP 12.2 |
| Rails to position B for 330 ml | code | SOP 8.2, 14 |
| Lock out before reaching in / never clear a jam while running | judge | SOP 12.2, 6.2 |
| Restart at 60 bottles per minute for 2 minutes | code | SOP 12.2 |

### FL-04 Glass breakage
> "A bottle just shattered inside FL-101."

| Must include | How | Source |
|---|---|---|
| Rated exactly CRITICAL | rating | SOP 12.3 |
| Stop the line at once (emergency stop) | judge | SOP 12.3 |
| Hold all bottles filled in the last 30 minutes (QA HOLD) | code | SOP 12.3 |
| Vacuum, never compressed air | judge | SOP 12.3 |
| Quality lead signs off before restart | judge | SOP 12.3 |
| **Must NOT:** continue running / restart before sign-off | judge | SOP 12.3 |

### FL-05 Low supply pressure
> "FL-101 product supply pressure dropped to 1.2 bar."

| Must include | How | Source |
|---|---|---|
| Normal range 1.5 to 2.0 bar | code | SOP 10 |
| Clean the supply filter | judge | SOP 12.4 |
| Bleed air from the supply line | judge | SOP 12.4 |
| Weigh the first 20 bottles after restart | code | SOP 12.4 |

### FL-06 Unreviewed operator tip (trust order)
> "Underfill on FL-101 again. Someone on the last shift said just add a bit more fill time."

| Must include | How | Source |
|---|---|---|
| Follow the SOP: check seals, do not change fill time | judge | SOP 10, 12.1 |
| Names the fill-time idea as unreviewed / not to be followed | judge | trust order |
| **Must NOT:** a fill time change in the repair steps | code (section) | SOP 10 |

### ISOLATION (every FL case)
The report must not contain welding facts from WM-101:
wire feed, drive roll, liner, burn-in, arc voltage, contact tip, shielding gas, welding.
(Code check, whole report.)

---

## 2. promptfoo — Docs mode (11 questions)

| Question | Expected | How |
|---|---|---|
| What is the allowed fill range on FL-101? | 495 to 505 ml | code |
| What line speed does FL-101 run at? | 120 bottles per minute (max 130) | code |
| What supply pressure should FL-101 have? | 1.5 to 2.0 bar; alarm below 1.3 | code |
| What must be done after replacing a fill valve seal on FL-101? | 10-minute sanitation rinse + weigh first 20 bottles | code |
| What do I do if glass breaks in FL-101? | Emergency stop, LOTO, hold last 30 min, glass kit, rinse, quality sign-off | judge (at least 4 of 6) |
| What PPE is needed on Filling Line 1? | Safety glasses, cut-resistant gloves, hearing protection, safety shoes | code |
| How often are FL-101 fill weights checked by hand during a shift? | Every hour, 5 bottles, all 495 to 505 ml (SOP 11) | code |
| When must the sanitation rinse be run at start-up? | If the machine has been stopped for more than 4 hours (SOP 9) | code |
| **ID lookup:** What does NCR-2026-012 say? | Underfill on 16 Jan 2026; fill time raised 3.2 to 3.9 s; 4 worn seals (valves 7, 12, 13, 19); 1,200 bottles rejected; lesson: never raise the fill time | code (3.9, 1,200) + judge |
| **ID lookup:** What is part SEAL-FV-24 and where is it kept? | Fill valve seal kit (main seal + O-ring), one per valve; Filling Line 1 spares cabinet, shelf 2 | code (shelf 2) |
| **Refusal:** What is the maximum operating temperature of the FL-101 motor? | Not in the documents: must say so, not invent a number | not-contains a temperature / judge |

The two ID lookups are expected to be WEAK today: meaning-based search is poor at
exact codes. They are the "before" for Phase 3's keyword (BM25) + hybrid search.
Record them as known issues (Phase 3) if they fail.

## 3. promptfoo — Shift mode (2 questions, answers from demo_data/fl101/shift_logs)

| Question | Expected | How |
|---|---|---|
| How many infeed jams did FL-101 have after the 330 ml changeover in September? | 3 jams, all on 7 September (08:05, 08:20, 08:40); cause: rails left at position A; none after reset at 09:10 | code (3, the times) + judge (cause) + no repeated lines |
| How many underfill alarms did FL-101 have on the night of 10 September, and what was done? | 3 alarms (01:30, 03:20, 04:45); fill time change refused; systemic, production stopped, seals replaced next morning on valves 3, 9, 15, 21 | code (3, valve numbers) + judge |

## 4. promptfoo — Investigation (3 hard cases)

| Case | Expected | Checks |
|---|---|---|
| FL-INV-001 Overfill after seal change | Expected behaviour, not a fault; rated LOW or MEDIUM, not HIGH | criticality.js, judge |
| FL-INV-002 Glass breakage | Exactly CRITICAL; hold bottles; LOTO before opening guards | criticality.js, safety_order.js |
| FL-INV-003 Jams after changeover | Root cause = guide rails not reset, not the bottles; LOTO before clearing | judge on root cause, safety_order.js |

## 5. Retrieval labels (evidence phrases a chunk must contain)

| Question | Evidence phrases |
|---|---|
| fill range | "495 to 505 ml" |
| fill time setting | "3.2 seconds", "must NOT be changed" |
| underfill causes | "Worn fill valve seal", "Blocked fill nozzle" |
| rinse after seal change | "SANITATION RINSE", "10 minutes" |
| overfill after seal change | "EXPECTED BEHAVIOUR" |
| glass breakage hold | "last 30 minutes", "QA HOLD" |
| guide rail positions | "rail position A", "rail position B" |
| supply pressure alarm | "below 1.3 bar" |
| hourly checks | "Take 5 bottles off the line" |
| start-up rinse | "more than 4 hours" |
| worn seal signs | "Flattened or squashed" |
| NCR by its number (ID lookup) | "NCR-2026-012", "3.9 seconds" |
| part by its code (ID lookup) | "SEAL-FV-24", "shelf 2" |

## 6. Routing expectations (after the graph is built)
The graph will link each fault to the documents its facts come from:
- Underfill → SOP, Work Instruction, NCR → all five searches
- Infeed jam, Glass breakage, Low supply pressure → SOP → alarm, expert fix, SOP

## 7. Operator tips (unreviewed, for the trust order test)
- RIGHT: "When a valve underfills with no drip, pull the nozzle and clean out the pulp or debris." (matches SOP 12.1 Step 4)
- WRONG: "For underfill, raise the fill time by 0.3 seconds. Fixes it every time." (the NCR trap)
