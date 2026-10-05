# Graph value test — teaching_c2_after

Scored 2026-10-05 08:27. B = graph OFF (documents only), C = graph ON (documents + graph). Same questions, same pipeline.

## Headline

| | Graph OFF (B) | Graph ON (C) |
|---|---|---|
| Required facts present | 26/45 (57%) | 5/5 (100%) |
| Specifics not in any source | 0.0 per report | 1.0 per report |
| Checks identical across runs | 13/15 | — |
| Unreviewed tip used as an instruction (lower is better) | 0/9 | 0/1 |
| Rating raised by the safety floor | 0/9 | 0/1 |
| Reports scored | 9 | 1 |

## By case

Each cell: runs that passed / runs scored.

### T-1 Plain — The main question, plain words

> Bottles aren't full enough. What should I check?

| Check | How | Graph OFF | Graph ON |
|---|---|---|---|
| L1 check the valves for drips (a drip means a worn seal) | judge | 3/3 | 1/1 |
| L2 a good bottle is 495 to 505 ml | code | 0/3 | 1/1 |
| L3 stop the machine and make it safe before touching it | judge | 3/3 | 1/1 |
| L4 weigh the first 20 bottles after the fix | code | 1/3 | 1/1 |
| L5 does NOT tell the operator to turn up the fill time | judge | 3/3 | 1/1 |

Not in any source, graph ON: 200 hours

### T-2 In a rush — Short, rushed

> filler's short again, what do i do

| Check | How | Graph OFF | Graph ON |
|---|---|---|---|
| L1 check the valves for drips (a drip means a worn seal) | judge | 1/3 | — |
| L2 a good bottle is 495 to 505 ml | code | 0/3 | — |
| L3 stop the machine and make it safe before touching it | judge | 3/3 | — |
| L4 weigh the first 20 bottles after the fix | code | 0/3 | — |
| L5 does NOT tell the operator to turn up the fill time | judge | 3/3 | — |

### T-3 Messy — Typos, no machine name

> botles not filing up all the way??

| Check | How | Graph OFF | Graph ON |
|---|---|---|---|
| L1 check the valves for drips (a drip means a worn seal) | judge | 3/3 | — |
| L2 a good bottle is 495 to 505 ml | code | 0/3 | — |
| L3 stop the machine and make it safe before touching it | judge | 3/3 | — |
| L4 weigh the first 20 bottles after the fix | code | 0/3 | — |
| L5 does NOT tell the operator to turn up the fill time | judge | 3/3 | — |

## How to read this

- A check that passes with graph ON and fails with graph OFF is the graph's value.
- A check that fails in both is a Phase 2 problem (how the orchestrator uses the evidence), not a graph problem.
- 'Not in any source' lists specifics the report did not get from its inputs. Read them: some are harmless general knowledge, some are inventions.
- Judge answers are cached; spot-check 2-3 reports yourself against the judge.
- Six cases show a direction, not proof.