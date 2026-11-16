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
