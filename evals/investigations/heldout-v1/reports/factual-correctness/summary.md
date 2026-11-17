# PlantMind evaluation: factual correctness

> ## Factual correctness: **58%**
> **29 of the 50 facts operators needed are in PlantMind's answers**, and 2 more are stated wrongly · 5 operator scenarios · FL-101 bottle filler
> *AI judge: 61% of claims · after human review: 58% of facts (62% if the 2 borderline facts count) · judge errors 0 of 22*

## Did the operator get the facts they needed?

**What we tested:** for each scenario we had already locked the list of facts a correct answer must contain (50 in total, from the SOP and work instruction). We checked which of them are in PlantMind's final answer.

- **Factual correctness (recall)** = needed facts in the answer ÷ all needed facts.
- This is a **task-success** measure ("did the operator get the right facts?"), not a grounding one. Faithfulness (grounding) asks whether the answer copied its evidence honestly; this asks whether the answer is actually complete and right.

| Operator scenario | Facts in the answer | Score | Wrong |
|---|---|---|---|
| Broken glass on the floor | 10 of 11 | **91%** | |
| Jams after a changeover | 9 of 11 | **82%** | |
| Underfill after new seals | 5 of 11 | **45%** | |
| Scale test failed before start-up | 3 of 7 | **43%** | 1 |
| Reject rate increasing | 2 of 10 | **20%** | 1 |
| **All** | **29 of 50** | **58%** | **2** |

## The two wrong facts

| Scenario | The SOP says | The answer says |
|---|---|---|
| Scale test | the **shift lead** signs the **pre-start checklist** | the **shift supervisor** signs the **First-Bottle Check**: a real rule, but from the **seal-change** procedure |
| Reject rate | a rising reject count is often the first sign of **worn seals** | blames **checkweigher calibration drift**, which is in no document; the whole seal-check path is missing |

## How we measured: three lessons from building it

1. **Read the tool's code before trusting its formula.** RAGAS's "recall" mode also counts the answer's own claims, so a long answer that repeats a fact scores higher. We used RAGAS's own claim-splitting and claim-checking steps, unchanged, but computed the score our way. This was recorded before locking.
2. **The reference has to be written for the judge, not just for word-matching.** Version 1 reused our short fact phrases ("The rails are locked"). The judge read them as statements about the machine *now* and was wrong on 3 of 5 "missing" verdicts in the first-run check. Version 2 wrote each fact as the SOP's own instruction ("Lock the guide rails in position"), and judge errors fell to **0 of 22**. The one truly missing fact stayed missing, so the judge did not just get easier.
3. **The splitting step can merge facts.** In one scenario RAGAS joined neighbouring facts. The code flagged them ("NO CLAIM") and a person decided them by hand.

## Three key findings

1. **The writer is the biggest place facts get lost.** Of the 21 missing facts, **11 had reached the writer** and it left them out. Helpers dropped 7, and search never found 3. Before this metric, the grounding card could only say "answer completeness: not measured yet".
2. **Underfill after new seals: everything arrived, half was used.** All needed facts reached the writer. The answer spent its space on three near-identical "don't change the fill time" lines and then **hit its output limit** (the report ends in "TRUNCATED"). The supply-pressure check and its 1.5–2.0 bar range were in its evidence and never reached the operator.
3. **When the fault isn't recognised, gaps get filled with the wrong thing.** The two lowest scenarios (scale test, reject rate) had no matching fault in the knowledge graph. In both, the answer filled a gap with something wrong: a real rule from the wrong procedure, or a cause from nowhere.

## The full path of the needed facts

```
50 facts the answers needed
 └─ 40 found by search
     └─ 27 kept in the helper summaries
         └─ 31 reached the writer (incl. knowledge graph)
             └─ 29 in the final answer   (+ 2 stated wrongly)
```

Some facts reached the answer by other routes (for example the knowledge graph or the operator's own question), so the steps do not subtract exactly.

## What this result means

**When PlantMind recognises the fault, operators get most of what they need (82–91%). When it doesn't, they get under half, and sometimes the wrong thing.** The writer step loses as many facts as search and the helpers together. These results suggest the writer's template and length should be looked at. That is a design note, not a change made here: PlantMind is never changed based on the held-out questions.

**These figures come from a small test set (5 scenarios, 50 facts).** The corrected number depends on a person's judgement, under rules locked before the results were seen.

**Next:** agent goal accuracy (did the operator end up able to act safely?), then response relevancy, then the task-success card.

---

*Evidence: settings `heldout-v1/factual_correctness_v2.json` (locked 2026-11-17, fingerprint `9ec2c1074bda`; v1 `factual_correctness.json`, `0410d0a85943`, kept with its H2 result) · facts `heldout-v1/retrieval_labels.json` (locked) · evaluator `evals/investigations/factual_correctness_ragas.py` · results `heldout-v1/results/factual_correctness_v2_*_after.json` · human review [review.md](review.md) (confirmed by the user 2026-11-17) · corrections as data `heldout-v1/task_success_corrections.json`*
