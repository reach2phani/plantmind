# PlantMind evaluation: faithfulness

> ## Faithfulness: **64%** of answer statements backed by evidence
> **152 of 238 statements** · 4 operator scenarios · FL-101 bottle filler
> *AI judge (RAGAS + qwen), rubric v2 · after human review, the checked cases range from 0.43 to 0.87*

## Did PlantMind's answer stick to the evidence it was given?

**What we tested:** we split each final answer into short statements and asked an AI judge, for each one: *is this backed by what the writer was given?* "What the writer was given" means the operator's question, the helper summaries and the knowledge-graph text, exactly as saved in the run's trace.

- **Faithfulness** = statements backed by evidence ÷ all statements.
- It checks **"did the writer make it up?"**, not "is it correct?" and not "does it fit the question?".

| Operator scenario | Statements backed | Judge score | Human-reviewed range |
|---|---|---|---|
| Scale test failed before start-up | 43 / 79 | 0.54 | not reviewed (calibration passed) |
| Jams after a changeover | 56 / 68 | 0.82 | 0.77–0.87 |
| Broken glass on the floor | 34 / 47 | 0.72 | 0.77–0.87 |
| Reject rate increasing | 19 / 44 | 0.43 | 0.43–0.59 |
| Underfill after new seals | not run | | answer and evidence too large for one judge call on the free tier |
| **All four** | **152 / 238** | **64%** | |

*The range exists because some statements are borderline: the content is in the evidence, but the answer states it more strongly (for example, a likely cause stated as the cause).*

**One example:** the operator asked whether a 2% reject rate needs reporting. The procedure's whole answer is one line: *"If the checkweigher rejects more than 1 bottle in 100 over an hour, tell the shift lead."* PlantMind said that, then added a calibration plan, a quality hold, a "calibration drift" root cause, daily checks and a call to maintenance. **None of that was in its evidence.**

## Can we trust the judge?

We checked before trusting the score.

1. **Calibration in both directions.** On two scenarios with known answers, every known-invented claim had to be rejected and every known-true claim accepted. Both passed.
2. **A person checked the judge's "not supported" verdicts** on three scenarios:

| Check | Judge wrong |
|---|---|
| Rubric v1, jams scenario | **18 of 32** (56%): marked down step numbers and facts from the operator's own question |
| Rubric v2, broken-glass scenario | **2 of 13** (15%) |
| Rubric v2, reject-rate scenario | **0 of 25** (0%) |

**Rubric v2 didn't loosen the judge.** It changed only what the judge was given: the operator's question was added to the evidence, and "Step 1:", "Step 2:" labels were removed from the answer. Invented claims were still rejected. See [v2-changes.md](v2-changes.md).

## Three key findings

1. **The less evidence there is, the more PlantMind invents.** The reject-rate answer had the thinnest evidence and the most invention: 18 made-up statements. The jams answer had rich, step-by-step evidence and scored highest.
2. **The report template pulls in made-up content.** Every scenario fills the *root-cause fix*, *preventive action*, *who to notify* and *financial impact* slots, whether or not the evidence covers them: training, audits, sensor repairs, calls to the plant manager.
3. **Two worse kinds of invention appeared:**
   - **A borrowed source:** "record the reject count *per the SOP*", which the SOP doesn't say.
   - **Template text leaking into the answer:** an instruction meant for the writer ("None required by the documents") became an instruction to the operator.

## What this result means

Most of what PlantMind tells an operator comes from its evidence: the safety rules, the procedure steps and the key numbers. But about **one statement in three is added**. Most additions are harmless extras (training, audits). Some send people for nothing: notifying a supervisor when no escalation trigger applies. Some claim a source they don't have.

**These figures measure grounding in a small test set (4 scenarios), not whether the answers are correct or safe.** An answer can be fully faithful to a wrong helper summary. The judge is also known to be a little strict on "confirm/verify" wording, and it doesn't check step order.

**Next:** measure how well the helper agents keep the facts that search found (handover recall).

---

*Evidence: rubric `heldout-v1/faithfulness_v2.json` (locked, commit `6f7f32a`) · v1 rubric and results kept: `heldout-v1/faithfulness.json` · evaluator `evals/investigations/faithfulness_ragas.py` (RAGAS 0.4.3, judge qwen/qwen3.8-27b) · results `heldout-v1/results/faithfulness_v2_{H1,H2,H4,H5}_after.json` · human reviews [H2-human-review.md](H2-human-review.md), [H4-H5-human-review.md](H4-H5-human-review.md)*
