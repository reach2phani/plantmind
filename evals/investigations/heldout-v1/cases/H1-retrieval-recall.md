# H1: Retrieval recall

**The one question:** did search bring back the facts the right answer needs?

**Result: 6 of 7 facts found = 86%.** The same in the before and after runs.

---

## 1. The ground truth

### What we wrote before the test (HELDOUT.md, 2026-11-04)

> - Do not start. Call the quality lead. *(SOP 8.4)*
> - Hand-weighing is not a replacement: the hourly check is 5 bottles; the checkweigher weighs every bottle. *(SOP 8.4, 11)*
> - Extras: 490 and 510 must be rejected and 500 must pass *(8.4)*; record on the pre-start checklist, signed by the shift lead *(8, 16)*.

It was written to grade **the answer**, as 3 bullets.

### The same ground truth, split into single facts

| # | Fact | Where in the SOP |
|---|---|---|
| F1 | Do not start the line | 8.4, line 184 |
| F2 | Call the quality lead | 8.4, line 184 |
| F3 | By hand it is only 5 bottles an hour | 11, lines 225–226 |
| F4 | The checkweigher weighs every bottle | 7, line 149 |
| F5 | 490 and 510 ml rejected, 500 ml passes | 8.4, lines 181–184 |
| F6 | Record on the pre-start checklist | 8, line 157 |
| F7 | The shift lead signs it | 8, line 157 |

## 2. The rubric

### What the eval defined for retrieval on H1

**Nothing.** The eval file (`evals/promptfoo/eval_fl101_heldout.yaml`) only grades the final answer. PlantMind's retrieval test (`evals/retrieval_labels.json`) covers other questions, not H1. So until now, H1's retrieval was never measured by a written rule.

### The rubric written now (`heldout-v1/retrieval_labels.json`)

> ⚠️ Written on 2026-11-14, **after** seeing H1's results. Not blind. For H2–H5 it must be written before their search results are opened.

**Words that show each fact is in a piece of text:**

| # | The piece must contain… |
|---|---|
| F1 | "do not start" *or* "don't start" *or* "must not start" |
| F2 | "call the quality lead" |
| F3 | "5 bottles" (or "five bottles") **and** "hour" |
| F4 | "weighs every bottle" |
| F5 | "490 ml and 510 ml bottles must be rejected" **and** "500 ml bottle must pass" |
| F6 | "record every check on the pre-start checklist" |
| F7 | "the shift lead signs it" |

**The rules** (also in `retrieval_labels.json` → `rules`; the script refuses any rule it can't apply):
1. **Found** = the fact is inside at least one piece that search handed to the helpers.
2. Capitals and line breaks are ignored ("must↵pass" counts as "must pass").
3. A fact that isn't in **any** FL-101 document can't be blamed on search. It's marked "not in documents" and left out of the score.
4. **Retrieval recall = facts found ÷ facts that exist in the documents.**

## 3. How the evaluator applied the rules

The evaluator is a small script, `evals/investigations/retrieval_recall.py`. It's code, not an AI, so it gives the same result every time. For each fact it does three things:

**Step 1. Could search have found it?** It checks all 77 pieces of FL-101 documents (`snapshot/chunks_fl101.json`). All 7 facts exist, so the score is out of 7.

**Step 2. Did search find it?** It checks the 16 pieces search actually returned (4 for each of 4 helpers), saved in `snapshot/runs/H1-after.json` → `details.pieces`.

**Step 3. Count.**

What search gave the SOP helper:

| Rank | Piece | What it is | Useful for H1? |
|---|---|---|---|
| 1 | SOP piece 0 | title page | ❌ |
| 2 | SOP piece 1 | purpose of the SOP | ❌ |
| 3 | SOP piece 9 | **8.4 Checkweigher test** | ✅ F1, F2, F5 |
| 4 | SOP piece 7 | **how the machine works + start of pre-start checks** | ✅ F4, F6, F7 |

The other 12 pieces (shift logs, work instruction, NCR) held none of the 7 facts.

## 4. Result

| # | Fact | Result | Where |
|---|---|---|---|
| F1 | Do not start | ✅ FOUND | SOP rank 3 (piece 9) |
| F2 | Call the quality lead | ✅ FOUND | SOP rank 3 (piece 9) |
| F3 | 5 bottles an hour | ❌ **MISSED** | exists in SOP pieces 12 and 20; neither was returned |
| F4 | Weighs every bottle | ✅ FOUND | SOP rank 4 (piece 7) |
| F5 | Test rule | ✅ FOUND | SOP rank 3 (piece 9) |
| F6 | Record on checklist | ✅ FOUND | SOP rank 4 (piece 7) |
| F7 | Shift lead signs | ✅ FOUND | SOP rank 4 (piece 7) |

**Retrieval recall = 6 / 7 = 86%** (before run: also 6/7).
Saved: `heldout-v1/results/retrieval_recall_after.json` and `_before.json`.

## 5. How well did the evaluator do its job?

I checked its work by hand: I opened pieces 9 and 7, and read them against the 7 facts.

| Question | Answer |
|---|---|
| Are the 6 "found" really there? | ✅ Yes, all 6, word for word |
| Is the 1 "missed" really missing? | ✅ Yes. Piece 12 ("every hour, take 5 bottles off the line") was not returned |
| Did it handle line breaks? | ✅ Yes. "The 500 ml bottle must↵pass" was found. My earlier hand count missed it; the script didn't |

**Where it could go wrong:**
- **A false miss.** If a document used different words (for example "don't run the line"), the word list wouldn't catch it. The fix: add the wording to the list, but only before results are seen.
- **A false find.** F3's word "hour" is short and common. A piece with "5 bottles" and an unrelated "hour" would count. It didn't happen here, but the rule is loose.
- **It checks presence, not position.** A fact found at rank 4 counts the same as rank 1. For H1 that matters: F6 and F7 were at the very end of the last piece, and the helper dropped them.

## 6. What this score proves, and what it doesn't

**It proves:** search found 6 of the 7 facts H1's answer needs. So H1's main failures (the lost checklist step, the made-up repair steps) were **not** caused by search.

**It does not prove:**
- that the facts reached the answer (they didn't all: see answer completeness, 3 of 7)
- that search is good in general (1 question, 1 run)
- that search was efficient: 2 of the SOP helper's 4 slots went to the title page and purpose section
