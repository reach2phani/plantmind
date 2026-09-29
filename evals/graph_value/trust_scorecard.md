# Graph value test — trust

Scored 2026-09-28 15:46. B = graph OFF (documents only), C = graph ON (documents + graph). Same questions, same pipeline.

## Headline

| | Graph OFF (B) | Graph ON (C) |
|---|---|---|
| Required facts present | — | 77/81 (95%) |
| Specifics not in any source | — | 0.3 per report |
| Checks identical across runs | — | 24/27 |
| Unreviewed tip used as an instruction (lower is better) | — | 1/18 |
| Rating raised by the safety floor | — | 0/18 |
| Reports scored | 0 | 18 |

## By case

Each cell: runs that passed / runs scored.

### GV-01 New spool — Finds the defective-spool cause from the 'new spool' clue

> WM-101 wire feed motor overload alarm. It started right after we fitted a new wire spool this morning.

| Check | How | Graph OFF | Graph ON |
|---|---|---|---|
| Does the report identify a defective or newly fitted wire spool as a likely cause? | judge | — | 3/3 |
| Does the report recommend replacing the suspect spool with a known-good spool? | judge | — | 3/3 |
| tension reset to finger-tight + quarter turn | code | — | 3/3 |
| Does the report avoid telling the operator to increase drive-roll tension, or to keep adjusting it, as the fix? | judge | — | 3/3 |
| repair steps do not use the unreviewed 18 to 22 tension tip | code | — | 3/3 |

### GV-02 Tension trap — Warns against the known wrong response and treats repeat alarms as systemic

> Third wire feed overload alarm on WM-101 this shift. The operator has been tightening the drive rolls each time.

| Check | How | Graph OFF | Graph ON |
|---|---|---|---|
| Does the report explicitly warn NOT to keep adjusting or tightening the drive-roll tension? | judge | — | 3/3 |
| Does the report say to stop production and inspect the drive rolls and the liner? | judge | — | 3/3 |
| Does the report treat three or more overload alarms in one shift as a systemic or recurring equipment fault rather than operator error? | judge | — | 3/3 |
| Does the report require lockout/tagout (LOTO) before the repair work? | judge | — | 3/3 |
| burn-in at 5.0 m/min for 30 s | code | — | 3/3 |

### GV-03 Unstable after liner change — Connects liner replacement to burn-in, a fact in a different document

> We just replaced the liner on WM-101 and the wire feed is a bit unstable for the first few minutes. Is something wrong?

| Check | How | Graph OFF | Graph ON |
|---|---|---|---|
| Does the report say that some wire feed instability in the first minutes after a liner replacement is expected or normal, not a new fault? | judge | — | 3/3 |
| burn-in at 5.0 m/min for 30 s | code | — | 3/3 |
| Does the report avoid recommending another liner replacement as the immediate fix? | judge | — | 3/3 |

### GV-04 Arc voltage — Gives the documented spec and does not use the disputed operator value

> WM-101 arc voltage is reading 17 V and the arc is unstable. What should it be?

| Check | How | Graph OFF | Graph ON |
|---|---|---|---|
| normal range 18-22 V | code | — | 3/3 |
| Does the report avoid instructing the operator to set, reset or target an arc voltage of 15-16 V or 15.5 V? | judge | — | 3/3 |
| Does the report recommend checking or cleaning the earth clamp? | judge | — | 3/3 |
| Does the report say parts welded during the arc instability should be flagged or quarantined for QC inspection? | judge | — | 3/3 |

Not in any source, graph ON: 2 minutes

### GV-05 Gas alarm — Critical safety response and what to do with affected parts

> Shielding gas pressure low alarm on WM-101 in the middle of a run.

| Check | How | Graph OFF | Graph ON |
|---|---|---|---|
| Does the report say to stop welding immediately? | judge | — | 2/3 |
| replace cylinder below 20 bar | code | — | 3/3 |
| Does the report say to check the regulator and the hose connections for leaks? | judge | — | 3/3 |
| Does the report say what to do with parts welded after the alarm (scrap them, or hold them for inspection)? | judge | — | 3/3 |
| criticality rated CRITICAL | rating | — | 3/3 |

Not in any source, graph ON: Section 4.2

### GV-06 Hot contact tip — Specific numbers and the safe order: cool first, then replace

> WM-101 contact tip temperature high alarm. The tip bore looks oval.

| Check | How | Graph OFF | Graph ON |
|---|---|---|---|
| 10 minutes cooling | code | — | 3/3 |
| Does the report say to let the tip cool before touching or replacing it? | judge | — | 3/3 |
| Does the report recommend replacing the contact tip? | judge | — | 3/3 |
| stickout 10-15 mm | code | — | 1/3 |
| hand-tight + quarter turn | code | — | 2/3 |

Not in any source, graph ON: 2 minutes, 200 °C, 8 hours

## How to read this

- A check that passes with graph ON and fails with graph OFF is the graph's value.
- A check that fails in both is a Phase 2 problem (how the orchestrator uses the evidence), not a graph problem.
- 'Not in any source' lists specifics the report did not get from its inputs. Read them: some are harmless general knowledge, some are inventions.
- Judge answers are cached; spot-check 2-3 reports yourself against the judge.
- Six cases show a direction, not proof.