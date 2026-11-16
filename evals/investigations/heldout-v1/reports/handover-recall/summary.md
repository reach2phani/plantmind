# PlantMind evaluation: handover recall

> ## Handover recall: **69%**
> **27 of 39 facts found by search were passed on to the writer** · 5 operator scenarios · FL-101 bottle filler
> *Automated checker: 26% · corrected by manual review: 69% · with the knowledge graph, 79% reached the writer*

## Did PlantMind's helpers pass on the facts that search found?

**What we tested:** PlantMind's writer never sees the search results. Each helper agent reads its search pieces and writes a **summary**, and the writer works only from those summaries (plus the knowledge-graph text). So a fact can be found by search and still be lost in a summary.

- **Handover recall** = facts kept in the helper summaries ÷ facts search found.
- Facts search never found aren't counted here; they're search's failure, already measured by retrieval recall.

| Operator scenario | Found by search | Kept by the helpers | Handover recall | Reached the writer (incl. graph) |
|---|---|---|---|---|
| Scale test failed before start-up | 6 | 3 | 50% | 50% |
| Jams after a changeover | 8 | 6 | 75% | 100% |
| Underfill after new seals | 9 | 8 | 89% | 100% |
| Broken glass on the floor | 9 | 8 | 89% | 100% |
| Reject rate increasing | 7 | 2 | 29% | 29% |
| **All** | **39** | **27** | **69%** | **79%** |

**One example:** in the reject-rate scenario, one procedure section held five needed facts. The helper kept one, *"more than 1 in 100 over an hour: tell the shift lead"*. It dropped the four next to it: look at the fill valves for drips, hand-weigh 5 bottles, record the reject count, and *"a rising reject count is often the first sign of worn seals"*.

## The automated checker was badly wrong

| | Handover recall |
|---|---|
| Automated checker (exact wording) | 26% |
| After manual review | **69%** |

The checker missed 17 facts the helpers had actually kept, all because of **formatting**:

| Cause | Facts |
|---|---|
| Small rewording ("1.5 – 2.0 bar" instead of "1.5 to 2.0 bar") | 9 |
| Markdown bold marks (`**Stop the line immediately**`) | 5 |
| A special hyphen character ("cut‑resistant", "NCR‑2026‑012") | 3 |

## Three key findings

1. **The helpers pick one answer and drop what's around it.** The 12 real drops were mostly the *context* around the main answer: checks to make, who signs, what a pattern means. Two examples:
   - **Reject rate:** the helper kept the one-line rule and dropped the investigation steps in the same section.
   - **Scale test:** the helper used the test-bottle section and ignored the pre-start-checks section entirely.
2. **The knowledge graph is the safety net.** When the operator's words matched a known fault, the graph delivered the dropped facts: three scenarios reached **100%**. When there was no fault match (scale test, reject rate), nothing rescued the drops.
3. **Lost facts become invented facts.** The two scenarios with the lowest handover and no graph rescue had the two lowest faithfulness scores (0.54 and 0.43). With thin evidence, the writer fills the report template with made-up content. In the reject-rate case, it invented a calibration plan in place of the dropped checks.

## What this result means

Search finds most facts (retrieval recall 80%), and the helpers pass on most of those (69%). But **the summarise step is where the answer's supporting detail gets lost**, and only the knowledge graph makes up for it. A system where helpers **fetch** rather than **summarise** (passing the needed sections on whole) would remove this loss. That's a design question for later, not a change made here.

**These figures come from a small test set (5 scenarios, 39 facts).** The corrected number depends on a person's judgement, under a rule written down before the results were seen.

**Next:** combine the grounding metrics (retrieval recall, retrieval precision, context precision, handover recall and faithfulness) into one report card.

---

*Evidence: rubric `heldout-v1/handover_recall.json` (locked 2026-11-16, fingerprint `8ff45ecb82ec`) · facts `heldout-v1/retrieval_labels.json` (locked) · evaluator `evals/investigations/handover_recall.py` · results `heldout-v1/results/handover_recall_after.json` · manual review [manual-review.md](manual-review.md) (confirmed by the user 2026-11-16)*
