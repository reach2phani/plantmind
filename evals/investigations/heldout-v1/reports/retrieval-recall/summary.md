# PlantMind evaluation: retrieval recall

> ## Retrieval recall: **80%**
> **40 of 50 required facts retrieved** · 5 operator scenarios · FL-101 bottle filler
> *Automated checker: 78% (39/50) · corrected by manual review: 80%*

## Did PlantMind's search find what the operator needed?

**What we tested:** five simulated operator scenarios, using synthetic SOPs. For each question, we listed the facts a correct answer needs, then checked whether PlantMind's search retrieved them.

| Operator scenario | Facts retrieved | Recall |
|---|---|---|
| Scale test failed before start-up | 6 / 7 | 86% |
| Jams after a changeover | 8 / 11 | 73% |
| Underfill after new seals | 9 / 11 | 82% |
| Broken glass on the floor | 9 / 11 | 82% |
| Reject rate increasing | 8 / 10* | 80% |
| **All** | **40 / 50** | **80%** |

\* *The automated checker scored this 7/10. Manual review found one fact written in different words, correcting it to 8/10.*

**One example:** for the jam-after-changeover scenario, search **did not retrieve the SOP's Infeed Jam section**. So the material given to the AI lacked a safety rule: *never reach into the infeed while it is running.*

## Three key findings

1. **Whole sections were missed.** Missing facts clustered in relevant SOP sections that weren't retrieved. In 4 of 5 cases, the SOP title page took one of the SOP helper's only 4 slots.
2. **The checker wasn't fully reliable.** The exact-word checker marked one fact as missing because a document phrased it differently. Manual verification caught the error.
3. **Retrieval isn't the only failure point.** In H1, search retrieved procedural requirements that the final answer still left out. The bigger losses happen after search.

## What this result means

PlantMind's search retrieved most required facts in these five tests, but missed some safety-relevant procedures. **80% describes fact-level retrieval coverage in a small test set, not overall AI accuracy, safety, or production readiness.**

**Next:** measure how well the helper agents preserve the facts that search retrieved (handover recall).

---

*Evidence: rubric `heldout-v1/retrieval_labels.json` (locked, commit `3236aaa`) · evaluator `evals/investigations/retrieval_recall.py` · results `heldout-v1/results/retrieval_recall_after.json`*
