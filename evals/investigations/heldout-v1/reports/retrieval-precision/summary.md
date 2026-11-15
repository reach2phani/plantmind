# PlantMind evaluation: retrieval precision and context precision

> ## Retrieval precision: **28%** · Context precision: **0.63**
> **19 of 68 retrieved pieces held a needed fact** · 5 operator scenarios · FL-101 bottle filler
> *Automated checker: 28% / 0.63 · corrected by manual review: 29% / 0.60*

## Did PlantMind's search bring back the right material, and put it first?

**What we tested:** for the same five operator scenarios, we checked every piece of text that search handed to PlantMind's helpers. Each helper gets only **4 pieces**.

- **Retrieval precision:** how many of those pieces held a fact the answer needed?
- **Context precision:** were the useful pieces at the **top** of each helper's list? (1.0 = all useful pieces ranked first)

| Operator scenario | Useful pieces | Retrieval precision | Context precision | SOP helper's 4 slots |
|---|---|---|---|---|
| Scale test failed before start-up | 2 / 16 | 12% | 0.42 | ✗ ✗ ✓ ✓ |
| Jams after a changeover | 3 / 12 | 25% | 0.64 | ✗ ✓ ✓ ✓ |
| Underfill after new seals | 7 / 16 | 44% | 0.69 | ✓ ✓ ✓ ✓ |
| Broken glass on the floor | 5 / 12 | 42% | 0.82 | ✗ ✓ ✓ ✓ |
| Reject rate increasing | 2 / 12* | 17% | 0.58* | ✗ ✓ ✓ ✗ |
| **All** | **19 / 68** | **28%** | **0.63** | |

\* *Manual review found one useful work-instruction piece the checker missed (different wording). Corrected: 3/12 = 25% and 0.42. Context precision goes down because that piece sat last, at rank 4.*

**One example:** in four of the five scenarios, the SOP helper's **first slot was the SOP title page**. In the one scenario where it wasn't (underfill after new seals), all four SOP pieces were useful and its ranking scored a perfect 1.0.

## What the 49 non-useful pieces were

| Type of piece | Count | Really waste? |
|---|---|---|
| Cover and scope pages (title, owner, purpose) | 16 | **Yes.** No instructions at all |
| Shift-log history | 18 | Partly: history, but no procedures |
| Other document sections | 15 | Mostly: real content, not about this question |

## Three key findings

1. **About 1 in 4 retrieved pieces is pure waste.** Cover pages took 16 of 68 slots. With only 4 slots per helper, each one can push out a needed section. That's how the jam scenario lost its Infeed Jam section.
2. **Useful material is often not at the top.** The title page ranking first is the main reason context precision is 0.63, not closer to 1.0.
3. **Almost all useful material comes from one helper.** The SOP helper got useful pieces in all 5 scenarios; the shift-log, work-instruction and NCR helpers in only 1 each.

## What this result means

Search finds most needed facts (retrieval recall 80%), but **hands over a lot of material that isn't needed**, and the most useful pieces are often below a cover page. **These figures measure what search delivered in a small test set, not answer quality.** They are also **pessimistic by design**: a piece counts as useful only if it contains a listed fact, so helpful history (for example *"Quality lead called"*) counts as not useful. An AI-judge cross-check (RAGAS) is planned.

**Next:** measure how well the helper agents preserve the facts that search retrieved (handover recall).

---

*Evidence: rubrics `heldout-v1/retrieval_precision.json` and `heldout-v1/context_precision.json` (locked, commit `5dea826`) · facts `heldout-v1/retrieval_labels.json` (locked, commit `3236aaa`) · evaluator `evals/investigations/precision.py` · results `heldout-v1/results/precision_after.json`*
