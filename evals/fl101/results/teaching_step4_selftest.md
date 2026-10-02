# Teaching set — step 4: test the tests

Run 2026-10-01 12:04. The same five checkers the real runs use (evals/fl101/teaching_cases.json), on answers whose right mark we already know. No app calls. Judge: qwen/qwen3.8-27b.

**Checkers marked as expected: 15/15 on whole answers, 7/7 on variants.**

## Whole answers

| Answer | L1 | L2 | L3 | L4 | L5 |
|---|---|---|---|---|---|
| K-PERFECT | pass | pass | pass | pass | pass |
| K-BAD | fail | fail | fail | fail | fail |
| K-TRICKY | pass | pass | pass | pass | pass |

Answers:

- **K-PERFECT**: Press stop. Check the fill valves: a valve that drips has a worn seal, so call maintenance to replace it. Lock out the machine before touching anything. After the fix, weigh the first 20 bottles. Every bottle must be 495 to 505 ml. Do not change the fill time.
- **K-BAD**: Increase the fill time by 0.3 seconds and keep running.
- **K-TRICKY**: Check for dripping valves. Bottles must be 495–505 ml. Lock out first. Weigh the first 20 bottles. Do NOT raise the fill time, it hides worn seals.

## Variants (code checkers)

| Checker | Text | Expected | Got |
|---|---|---|---|
| L2 | 495 to 505 ml | pass | pass |
| L2 | 495–505 ml (en dash) | pass | pass |
| L2 | between 495 and 505 ml | pass | pass |
| L2 | about 500 ml | fail | fail |
| L4 | weigh the first 20 bottles | pass | pass |
| L4 | check 20 bottles on the scale | pass | pass |
| L4 | weigh a few bottles | fail | fail |
| L4 | wait 20 minutes, then weigh bottles | report | pass |

## The lazy L5 checker: fail if the answer mentions "fill time"

| Answer | Expected | Lazy checker | Real L5 (judge) |
|---|---|---|---|
| K-PERFECT | pass | fail ✗ | pass |
| K-BAD | fail | fail | fail |
| K-TRICKY | pass | fail ✗ | pass |

## How to read this

- A ✗ is a broken CHECKER, not a PlantMind failure. Fix or replace it before the real runs.
- 'report' rows have no right answer set on purpose: they show a known weak spot.
- The lazy checker is expected to fail correct answers. That is the lesson: a checker that looks for words cannot tell "turn up the fill time" from "do NOT turn up the fill time".