# baseline-v1 — notes

Written by hand (summary.md is generated and gets replaced on a re-run).

## Runs
| Repeat | Date | Run label | Commit in run record | Code fingerprint |
|---|---|---|---|---|
| r1 | 2026-10-29 | baseline-v1-1029-r1 | 5e1c5d0+dirty | 7211bcfb13 |
| r2 | 2026-10-30 | baseline-v1-1030-r2 | 627d5e4 | 7211bcfb13 |
| r3 | 2026-11-01 | baseline-v1-1101-r3 | ee7b7a2 | 7211bcfb13 |

**The "+dirty" warning on r1 is expected.** r1 ran before the rule "commit before a run"
was in place. Between r1 and r3 only eval and dashboard files changed. The code
fingerprint (multi_agent.py, knowledge_graph.py, models.py) is the same in all three runs, so
PlantMind answered with the same code every time. Also known: the run record reads the
commit once when Flask starts, so Flask was restarted before each run.

## Grading
- Judge: qwen/qwen3.8-27b, temperature 0. All 15 answers fully graded.
- The first summary run on 2026-11-02 left one check unmeasured (r3 TC4 GR:specs-correct): Groq
  answered "request too large" because the judge's per-minute quota was used up, not because the
  request was too big. On the re-run, the judge cache kept every other verdict, and the
  missing check was graded. Fix later: on "too large", wait for a fresh minute once
  before giving up.

## Results
TS 8/15 (53%) · OQ 8/15 (53%) · SR 7/15 (47%) · GR 9/15 (60%) · CE 15/15 (100%)

## What the baseline shows
1. **"Do NOT" warnings are missing from the immediate actions.** This is the top issue: TC2 no-reach
   (failed 3/3), TC3 no-early-restart (2/3), TC4 guards and no compressed air (r3), TC5 (r2).
2. **The criticality rating varies between runs.** TC1 and TC3 were rated MEDIUM in r3 (HIGH
   in r1 and r2). That is below PlantMind's own floor, so it is a safety failure.
3. **TC2 rail positions are missing** (3/3): the report says "check the rails" but never names
   position A (500 ml) or position B (330 ml).
4. **TC5 fails Task Success in every run** (rinse / 5-minute check).
5. **Cost and speed pass.** About 80% of each ~60 s investigation is waiting for the free-tier quota.

## Verdicts to spot-check (judge may be wrong)
- r3 TC1 GR:specs-correct called "15 min per valve" a wrong specification, but the prompt says time
  estimates are not specifications.
- TC5 "0.5 %" (from earlier runs).
- OQ:plain flags codes such as FL-101 / LOTO. The rubric wording is probably too strict.
