# Graph value test — fresh

Scored 2026-10-06 07:55. B = graph OFF (documents only), C = graph ON (documents + graph). Same questions, same pipeline.

## Headline

| | Graph OFF (B) | Graph ON (C) |
|---|---|---|
| Required facts present | 30/87 (34%) | 64/87 (73%) |
| Specifics not in any source | 0.1 per report | 0.3 per report |
| Checks identical across runs | 25/29 | 22/29 |
| Unreviewed tip used as an instruction (lower is better) | 0/15 | 0/15 |
| Rating raised by the safety floor | 0/15 | 0/15 |
| Reports scored | 15 | 15 |

## By case

Each cell: runs that passed / runs scored.

### FR-01 Line stopped since Friday — Start-up after a long stop: rinse because stopped > 4 hours, slow start, first 20 bottles, then full speed

> Line's been sitting since Friday night. Anything special before we start filling again?

| Check | How | Graph OFF (B) | Graph ON (C) |
|---|---|---|---|
| checkweigher test bottles 490 and 510 ml before starting | code | 0/3 | 0/3 |
| 10-minute sanitation rinse (stopped more than 4 hours) | code | 0/3 | 0/3 |
| start at 60 bottles per minute | code | 0/3 | 2/3 |
| first 20 bottles all 495 to 505 ml | code | 0/3 | 0/3 |
| then raise to 120 bottles per minute | code | 0/3 | 0/3 |
| no welding facts from WM-101 | code | 3/3 | 3/3 |

Not in any source, graph ON: 12 hours, 24 hours

### FR-02 One valve light, but no drip — Underfill on one valve with no dripping: blocked nozzle, not a worn seal; lock out, clean the nozzle, check pressure

> Checkweigher keeps kicking out bottles from valve 12, but I don't see any drips. What now?

| Check | How | Graph OFF (B) | Graph ON (C) |
|---|---|---|---|
| no drip means a blocked nozzle: clean it | judge | 1/3 | 3/3 |
| stop and lock out before touching the valve | judge | 3/3 | 3/3 |
| check the product supply pressure | judge | 0/3 | 2/3 |
| does NOT tell the operator to turn up the fill time | judge | 2/3 | 3/3 |
| no welding facts from WM-101 | code | 3/3 | 3/3 |

Not in any source, graph OFF: 495 ml

### FR-03 Rejects creeping up, no alarm yet — A rising reject count before any alarm: tell the shift lead above 1 in 100, early sign of worn seals, check for drips

> Reject count's been creeping up all morning. No alarms yet, though. Is that something to worry about?

| Check | How | Graph OFF (B) | Graph ON (C) |
|---|---|---|---|
| more than 1 in 100 rejected over an hour: tell the shift lead | code | 0/3 | 3/3 |
| a rising reject count is often the first sign of worn seals | judge | 3/3 | 3/3 |
| check the fill valves for dripping | judge | 2/3 | 3/3 |
| bottles must be 495 to 505 ml | code | 0/3 | 3/3 |
| does NOT tell the operator to turn up the fill time | judge | 1/3 | 3/3 |
| no welding facts from WM-101 | code | 3/3 | 3/3 |

### FR-04 Changeover to 330 ml — Planned changeover: lock out, rails to position B and lock, star wheel, 20 bottles at 60 per minute, record

> Swapping to the 330s after lunch. What's the drill?

| Check | How | Graph OFF (B) | Graph ON (C) |
|---|---|---|---|
| lock out the machine first | judge | 0/3 | 3/3 |
| guide rails to position B for 330 ml | code | 0/3 | 3/3 |
| fit the matching star wheel | judge | 0/3 | 3/3 |
| run 20 bottles at 60 bottles per minute | code | 0/3 | 2/3 |
| record the changeover; the shift lead signs | judge | 0/3 | 2/3 |
| no welding facts from WM-101 | code | 3/3 | 3/3 |

Not in any source, graph OFF: 10 minutes

Not in any source, graph ON: 130 bpm, 30 minutes

### FR-05 Leak from the side of a valve — Leak at the valve body after a seal job: missing O-ring. The documents' answer is short: stays honest, no invented steps

> One of the valves is leaking from the side, not the nozzle. Maintenance only did the seals on it yesterday.

| Check | How | Graph OFF (B) | Graph ON (C) |
|---|---|---|---|
| check for a missing O-ring; fit a new one | code | 0/3 | 1/3 |
| stop and lock out before working on the valve | judge | 3/3 | 3/3 |
| valve work is for trained maintenance technicians only | judge | 0/3 | 0/3 |
| seal kit SEAL-FV-24 (holds the O-ring) | code | 0/3 | 2/3 |
| food-grade lubricant FGL-1 only | code | 0/3 | 2/3 |
| no welding facts from WM-101 | code | 3/3 | 3/3 |

## How to read this

- A check that passes with graph ON and fails with graph OFF is the graph's value.
- A check that fails in both is a Phase 2 problem (how the orchestrator uses the evidence), not a graph problem.
- 'Not in any source' lists specifics the report did not get from its inputs. Read them: some are harmless general knowledge, some are inventions.
- Judge answers are cached; spot-check 2-3 reports yourself against the judge.
- Six cases show a direction, not proof.