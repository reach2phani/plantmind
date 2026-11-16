# Faithfulness rubric v2: what changed, and what it no longer checks

**The judge did not change.** Same judge (qwen/qwen3.8-27b, temperature 0), same RAGAS prompts (built-in, unchanged), same score (supported statements ÷ all statements). Version 2 changes only **what the judge is given**.

## The two changes

| Change | v1 | v2 | Why it's fair |
|---|---|---|---|
| **Operator's question added to the evidence** | Evidence = helper summaries + graph text | Evidence also includes the operator's question | The writer had the question too. Facts the operator gave (e.g. "changed to 330 ml") are not invented |
| **"Step N:" labels removed from the answer** | The judge checked "Step 2 of the action is…" against documents that have no "Step 2" | The judge checks the action itself | Faithfulness asks whether the action is backed by evidence, not whether the step number matches |

These fixed the two causes of judge error found in the H2 human review (15 of the 18 errors). The other 3 (too strict on conditional "required" actions) can't be fixed without changing RAGAS's prompts, so they remain a known limit.

## Calibration now checks both directions

- **Must be supported:** statements known to be true (from the human review) must be marked supported.
- **Must not be supported:** statements known to be made up must be marked not supported.
- `none_of` words keep borderline statements (for example "the rails *were not* reset", stated as fact) out of the "must be supported" test. This changes which statements are used to test the judge, not how the score is counted.

## Why v2 is not just a softer judge (H2)

| | H2 faithfulness |
|---|---|
| Judge, v1 | 0.47 |
| Human review | 0.77–0.87 |
| Judge, v2 | **0.82**: inside the human range, not above it |

- All 7 known-invented statements are still "not supported".
- 12 statements are still flagged: invented fixes, over-escalation, a likely cause stated as fact.

## What v2 no longer checks, or might miss

1. **Step order.** v2 doesn't notice steps in the wrong order (for example, removing the lock before setting the rails). This was never part of faithfulness, but needs its own check if it matters.
2. **Lenient "supported" verdicts.** One probable case on H2: #45 "No additional quality actions are required…" was marked supported; the human review called it unsupported (a template phrase). Spot-check the "supported" verdicts too, not just the "not supported" ones.

*Rubric: `heldout-v1/faithfulness_v2.json` (locked, commit `6f7f32a`) · v1 kept unchanged: `heldout-v1/faithfulness.json` · H2 result: `heldout-v1/results/faithfulness_v2_H2_after.json`*
