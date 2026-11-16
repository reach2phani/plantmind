# PlantMind evaluation: grounding report card

> **Does PlantMind's answer come from its documents?** 5 operator scenarios · FL-101 bottle filler · numbers after human review (automated checker in the tables)
>
> | Retrieval recall | Retrieval precision | Context precision | Handover recall | Faithfulness |
> |---|---|---|---|---|
> | **80%** | **29%** | **0.60** | **69%** | **64%** |
> | found the needed facts | useful pieces | useful pieces at the top | facts passed to the writer | answer statements backed by evidence |

## Where the needed facts went

```
50 facts the answers needed
 └─ 40 found by search                 (80%)   lost: 10 never found
     └─ 27 kept in the helper summaries   (54% of needed)   lost: 13 dropped by the helpers
         └─ 31 reached the writer, incl. graph  (62% of needed)   rescued by the graph: 4
```

Then, in the answer: **64%** of statements were backed by the writer's evidence (152 of 238, 4 scenarios). Whether every fact that reached the writer is in the answer (answer completeness) is not measured yet.

## The five metrics

| Step | Metric | Question | Automated | **After review** | Evaluator |
|---|---|---|---|---|---|
| Search | Retrieval recall | Did search find the needed facts? | 78% | **80%** (40/50) | code + person |
| Search | Retrieval precision | How many returned pieces were useful? | 28% | **29%** (20/68) | code + person |
| Search | Context precision | Were the useful pieces at the top? | 0.63 | **0.60** | code + person |
| Helpers | Handover recall | Did the helpers pass on what search found? | 26% | **69%** (27/39) | code + person |
| Writer | Faithfulness | Is every answer statement backed by evidence? | 64% | ranges per scenario below | AI judge (RAGAS + qwen), checked by a person |

## By scenario (after review)

| Scenario | Recall | Precision | Context precision | Handover | Reached writer | Faithfulness |
|---|---|---|---|---|---|---|
| H1 Scale test failed before start-up | 86% | 12% | 0.42 | 50% | 50% | 0.54 |
| H2 Jams after a changeover | 73% | 25% | 0.64 | 75% | 100% | 0.82 (0.77–0.87) |
| H3 Underfill after new seals | 82% | 44% | 0.69 | 89% | 100% | not run |
| H4 Broken glass on the floor | 82% | 42% | 0.82 | 89% | 100% | 0.72 (0.77–0.87) |
| H5 Reject rate increasing | 80% | 25% | 0.42 | 29% | 29% | 0.43 (0.43–0.59) |

*Faithfulness: judge score, with the range after a person checked its verdicts where one was done. Not run on H3: too large for one judge call on the free tier. Handover recall counts the facts the automated checker found by search (39); with the one retrieval correction (H5) it would be 27/40 = 68%.*

## Key findings

1. **Facts are lost at two places, about equally: search and the helpers.** Of the 50 needed facts, search never found 10. The helpers then dropped 13 of the 40 it found. The knowledge graph gave 4 of those back.
2. **Search returns too much of the wrong thing.** Only about 1 piece in 4 was useful. Cover and title pages took 16 of 68 slots, and the SOP title page ranked first in 4 of 5 scenarios. With only 4 slots per helper, junk pushes out needed sections, which is how the jam scenario lost its Infeed Jam section.
3. **The helpers pick one answer and drop what's around it.** In the reject-rate scenario, one procedure section held five needed facts. The helper passed on one ("tell the shift lead") and dropped the four checks next to it.
4. **The knowledge graph is the safety net, but only when the fault is recognised.** In three scenarios it brought "reached the writer" to 100%. In the two with no matching fault (scale test, reject rate), nothing rescued the dropped facts.
5. **Lost facts become invented facts.** The two scenarios with the fewest facts reaching the writer had the lowest faithfulness (0.54 and 0.43). With thin evidence, the writer fills the report template (root-cause fix, preventive action, who to notify, financial impact) with made-up content. In the reject-rate case, it invented a calibration plan in place of the checks the helper had dropped.

## What we learned about measuring

- **Measure every step, not just the answer.** One end score says *that* something failed. Per-step scores say *where*: here, search and the helpers fail for different reasons and need different fixes.
- **Automated checks need a person behind them.** Exact-word checking undercounted handover recall by a factor of 2.7 (26% vs 69%), because of rewording, Markdown and special hyphens. The AI judge was wrong on 56% of its "not supported" verdicts until its input was fixed (rubric v2), and was then wrong on 0–15%.
- **Lock the rules before looking, and record every correction as data.** Each corrected number here points to the review that made it.

## What this result means

**Most of what PlantMind tells an operator does come from its documents, but the path loses facts at every step, and the writer fills the gaps by inventing.** These are figures from a small test set (5 scenarios, 50 facts). They describe grounding only, not whether the answers are correct or safe.

**Not measured yet:** answer completeness (did every fact that reached the writer make it into the answer), and faithfulness for the underfill scenario (too large for one judge call on the free tier).

## Evidence and integrity

Every result below was made with the rubric that is locked now (checked by this script).

| Metric | Rubric | Fingerprint | Locked | Matches lock |
|---|---|---|---|---|
| Retrieval recall | `retrieval_labels.json` | `0c5704da82fe` | 2026-11-15 | ✓ |
| Retrieval precision | `retrieval_precision.json` | `7062cc5b75d8` | 2026-11-15 | ✓ |
| Context precision | `context_precision.json` | `60f5720498a9` | 2026-11-15 | ✓ |
| Handover recall | `handover_recall.json` | `8ff45ecb82ec` | 2026-11-16 | ✓ |
| Faithfulness | `faithfulness_v2.json` | `bd5db8095d1c` | 2026-11-15 | ✓ |

Human reviews: [retrieval recall](../retrieval-recall/summary.md) · [retrieval precision](../retrieval-precision/summary.md) · [handover recall](../handover-recall/manual-review.md) · [faithfulness H2](../faithfulness/H2-human-review.md) · [faithfulness H4–H5](../faithfulness/H4-H5-human-review.md) · corrections as data: `heldout-v1/grounding_corrections.json`

*Generated by `evals/investigations/grounding_card.py` on 2026-11-16. Numbers from code; findings written by a person.*
