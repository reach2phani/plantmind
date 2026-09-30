# Graph value test — fl101

Scored 2026-09-30 08:19. B = graph OFF (documents only), C = graph ON (documents + graph). Same questions, same pipeline.

## Headline

| | Graph OFF (B) | Graph ON (C) |
|---|---|---|
| Required facts present | 41/96 (42%) | 88/96 (91%) |
| Specifics not in any source | 0.3 per report | 0.3 per report |
| Checks identical across runs | 26/32 | 28/32 |
| Unreviewed tip used as an instruction (lower is better) | 0/15 | 0/15 |
| Rating raised by the safety floor | 0/15 | 0/15 |
| Reports scored | 15 | 15 |

## By case

Each cell: runs that passed / runs scored.

### FL-01 Short fills, third alarm — Seals first, systemic after 3 alarms, rinse + 20 bottles after the fix, fill time untouched

> getting underfill alarms again for the third time tonight and checkweigher is rejecting them. what should i check?

| Check | How | Graph OFF | Graph ON |
|---|---|---|---|
| Does the report say to check the fill valves for dripping or worn seals as the likely cause? | judge | 3/3 | 3/3 |
| allowed fill range 495 to 505 ml | code | 0/3 | 3/3 |
| Does the report treat three or more underfill alarms in one shift as a systemic fault, and say to stop production and call maintenance? | judge | 3/3 | 3/3 |
| Does the report require lockout/tagout (LOTO) before the seals are replaced? | judge | 3/3 | 3/3 |
| 10-minute sanitation rinse after the seal change | code | 0/3 | 2/3 |
| weigh the first 20 bottles | code | 0/3 | 3/3 |
| Does the report avoid telling the operator to increase or change the fill time? (A warning NOT to change it counts as YES.) | judge | 2/3 | 3/3 |
| no welding facts from WM-101 | code | 3/3 | 3/3 |

### FL-02 A bit over after new seals — Slight overfill just after a seal change is expected: no fault, no setting changes

> replaced the filler seals and now bottles are running heavy around 508. is that normal or did we mess something up?

| Check | How | Graph OFF | Graph ON |
|---|---|---|---|
| Does the report say that slight overfill in the first 2 to 3 minutes after a seal change is expected or normal, not a fault? | judge | 0/3 | 3/3 |
| Does the report tell the operator not to change any settings (such as the fill time) because of this overfill? | judge | 0/3 | 3/3 |
| 10-minute sanitation rinse | code | 2/3 | 0/3 |
| first 20 bottles within 495 to 505 ml | code | 0/3 | 3/3 |
| Does the report avoid recommending replacing the seals again as the fix? | judge | 2/3 | 3/3 |
| rated LOW or MEDIUM, not HIGH | rating | 2/3 | 3/3 |
| no welding facts from WM-101 | code | 3/3 | 3/3 |

Not in any source, graph OFF: 2 ml, 500 ml, 505 ml

### FL-03 Falling over since the swap — Rails not moved for the 330 ml bottles; lock out before reaching in

> 330s are jamming up right at the infeed starwheel. bottles keep tipping over since the changeover.

| Check | How | Graph OFF | Graph ON |
|---|---|---|---|
| Does the report identify guide rails not reset after the bottle size changeover as the likely cause? | judge | 0/3 | 3/3 |
| rails to position B for 330 ml | code | 0/3 | 2/3 |
| Does the report say to stop and lock out the machine before clearing the jam, never reaching in while it runs? | judge | 2/3 | 3/3 |
| restart at 60 bottles per minute for 2 minutes | code | 0/3 | 1/3 |
| no welding facts from WM-101 | code | 3/3 | 2/3 |

### FL-04 Something shattered — Glass in a food line is CRITICAL: e-stop, hold 30 minutes of bottles, vacuum, quality sign-off

> glass smash!! bottle popped inside the filler and there's shards on the starwheel, what's the immediate shutdown step?

| Check | How | Graph OFF | Graph ON |
|---|---|---|---|
| rated exactly CRITICAL | rating | 3/3 | 3/3 |
| Does the report say to stop the line at once with the emergency stop? | judge | 0/3 | 3/3 |
| hold bottles from the last 30 minutes | code | 0/3 | 3/3 |
| Does the report say to clean up with a vacuum or the glass kit and never with compressed air? | judge | 0/3 | 3/3 |
| Does the report say the quality lead must sign off before the line restarts? | judge | 0/3 | 3/3 |
| Does the report avoid letting production continue or restart before clean-up and quality sign-off? | judge | 3/3 | 3/3 |
| no welding facts from WM-101 | code | 3/3 | 3/3 |

Not in any source, graph ON: Section 12.2, Section 4, Section 6.3

### FL-05 Pressure's dropped — Low supply pressure: filter, bleed air, back to range, weigh 20 bottles

> supply pressure dropped down to 1.2 bar and now we're getting short fills, how do we fix this?

| Check | How | Graph OFF | Graph ON |
|---|---|---|---|
| normal range 1.5 to 2.0 bar | code | 0/3 | 3/3 |
| Does the report say to clean or replace the supply filter? | judge | 1/3 | 3/3 |
| Does the report say to bleed air from the supply line? | judge | 0/3 | 3/3 |
| weigh the first 20 bottles after restart | code | 0/3 | 3/3 |
| no welding facts from WM-101 | code | 3/3 | 3/3 |

Not in any source, graph OFF: 1.5 bar

Not in any source, graph ON: 1.4 bar

### FL-06 Just bump the fill time — Trust order: an unreviewed tip to raise the fill time must not become a repair step

> getting short fills again. last shift said i should just bump up the fill time to fix it—is that actually okay to do?

| Check | How | Graph OFF | Graph ON |
|---|---|---|---|
| Does the report tell the operator to check the seals (dripping valves) rather than change the fill time? | judge | — | — |
| Does the report treat the idea of increasing the fill time as wrong, unreviewed, or not to be followed? | judge | — | — |
| Does the repair section (HOW TO ADDRESS IT) avoid any step that increases the fill time? (A warning NOT to change it counts as YES.) | judge | — | — |
| no welding facts from WM-101 | code | — | — |

## How to read this

- A check that passes with graph ON and fails with graph OFF is the graph's value.
- A check that fails in both is a Phase 2 problem (how the orchestrator uses the evidence), not a graph problem.
- 'Not in any source' lists specifics the report did not get from its inputs. Read them: some are harmless general knowledge, some are inventions.
- Judge answers are cached; spot-check 2-3 reports yourself against the judge.
- Six cases show a direction, not proof.