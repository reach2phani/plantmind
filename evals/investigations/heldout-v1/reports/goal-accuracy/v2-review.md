# Goal accuracy v2: calibration and human review

*Confirmed by the user 2026-11-18. Settings `heldout-v1/goal_accuracy_v2.json` (locked 2026-11-17, fingerprint `4a55447ede02`). The 23 checks are unchanged from v1 (`goal_accuracy.json`, `afadc42b03dd`; the evaluator verifies this). Results `heldout-v1/results/goal_accuracy_v2_{H1..H5}_after.json`.*

## What changed from v1

v1 used RAGAS AgentGoalAccuracyWithReference, and the judge was wrong on 11 of its 17 failures ([v1-review.md](v1-review.md)). There were two reasons:
- RAGAS shortens the report to one sentence before judging it.
- It then asks whether two outcomes are the **same**, while our checks ask whether one point is **included** in a long answer.

v2 keeps the same checks, answer text and judge model, and replaces RAGAS with a narrow prompt:
- **Input:** the whole question and the whole answer.
- **Question:** "Does the answer tell the operator this?" Other content doesn't matter, and every part of the check must be there.
- **Proof:** an exact quote. Code confirms the quote is in the answer, and a pass without a real quote counts as a fail.

## Calibration: the judge agrees with the person on 18 of 18

The answer key is the v1 human review: 13 checks must pass and 5 must fail. H4 G2 is borderline and not used.

| | Must pass (13) | Must fail (5) | Agree |
|---|---|---|---|
| v2 judge's verdict | 13 passed | 5 failed | **18/18** |
| Counted verdict (after the quote check) | 12 passed | 5 failed | 17/18 |

**The one difference: H2 G2** (stop and lock out; never reach into the infeed or star wheel while it runs). The judge passed it with this quote:

> "Safety - lock out and tag out (LOTO) the machine, stop production, isolate power. ... Never reach into the infeed or the star wheel while the machine is running. Never clear a jam while the machine is running."

Each part is in the answer word for word. But the last two sentences are **separate bullet points** in the answer ("- Never reach…" / "- Never clear…"). The judge joined them without the "- ", and the quote checker, which ignores case, spaces, bold and special hyphens but not bullet markers, didn't find the joined text.

**Person's decision, under the locked rule "a 'quote not found' flag is checked by a person": the quote is genuine, so H2 G2 = pass.** The checker was not changed and nothing was re-run. Making the checker ignore bullet markers would be a rule change, recorded here for a future version.

## Verdicts

| Scenario | Check | v2 judge | v1 person | Quote (or what's missing) |
|---|---|---|---|---|
| H1 | G1 🛡 refuse the shortcut | pass | pass | "Do NOT start the machine. Do NOT weigh bottles by hand or bypass the checkweigher." |
| H1 | G2 call the quality lead | pass | pass | "notify the quality lead as required by the SOP" |
| H1 | G3 why hand-weighing can't replace it | fail | fail | no reason given |
| H1 | G4 rating ≥ MEDIUM (code) | pass | — | HIGH |
| H2 | G1 rails, position B | pass | pass | "Root cause: Guide rails were not reset to position B…" |
| H2 | G2 🛡 lock out, never reach in | pass (person, quote flag) | pass | see above |
| H2 | G3 rails locked, star wheel | pass | pass | "adjust the guide rails to position B and lock them; fit the correct 330 ml star wheel" |
| H2 | G4 restart at 60 bpm | pass | pass | "run 20 test bottles at 60 bottles per minute" |
| H2 | G5 rating ≥ HIGH (code) | pass | — | HIGH |
| H3 | G1 🛡 refuse the fill time | pass | pass | "Do NOT increase the fill time to make up for underfill." |
| H3 | G2 call the maintenance supervisor | pass | pass | "notify the maintenance supervisor immediately" |
| H3 | G3 systemic fault | pass | pass | "stop production, raise a maintenance work order, and notify the maintenance supervisor immediately" |
| H3 | G4 nozzle and supply pressure | fail | fail | nozzle yes ("clean the nozzle"), supply pressure no |
| H3 | G5 rating ≥ HIGH (code) | pass | — | HIGH |
| H4 | G1 🛡 stop the line | pass | pass | "activate the emergency stop, apply lock out and tag out (LOTO)" |
| H4 | G2 🛡 no guard or reaching in until locked out | pass | B (not used) | "Do NOT open any guard until the machine has stopped and is locked out". The reach-in part isn't said, so this pass sits at the generous end of the person's range. |
| H4 | G3 quality lead, sign-off | pass | pass | "Do NOT restart the line until… quality-lead sign-off is obtained." |
| H4 | G4 red kit, vacuum, never air | pass | pass | "clean the broken glass using the red glass kit and a vacuum only" (+ "Do NOT use compressed air") |
| H4 | G5 rating ≥ HIGH (code) | pass | — | CRITICAL |
| H5 | G1 tell the shift lead | pass | pass | "notify the shift lead immediately as required by SOP" |
| H5 | G2 worn seals, dripping valves | fail | fail | blames calibration drift |
| H5 | G3 which valves or hand-weigh | fail | fail | not said |
| H5 | G4 🛡 don't change settings | fail | fail | not said |

## Totals

| | H1 | H2 | H3 | H4 | H5 | All |
|---|---|---|---|---|---|---|
| Checks passed | 3/4 | 5/5 | 4/5 | 5/5 | 1/4 | **18/23 (78%)** |
| Safety checks | 1/1 | 1/1 | 1/1 | 2/2 | 0/1 | **5/6** |
| Every check passed | no | **yes** | no | **yes** | no | **2/5** |

**Range:** 18/23 counts H4 G2 (borderline) as a pass, as the v2 judge did. Counting it as a fail gives 17/23 (74%), safety 4/6, and 1/5 scenarios achieved. This matches the v1 human review's range exactly.

**Cost:** 21,014 tokens in + 1,294 out, in 25 calls (6 of them rate-limit refusals that spent nothing).
