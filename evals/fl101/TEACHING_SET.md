# Teaching set: one simple question, all 7 steps of evals

This is a test plan for the main build chat. It makes the real numbers for the
**Evals lesson** on the case-study page (`docs/preview.html`).

The page teaches evals to someone new, using **one simple question** followed
through 7 steps. Every number on the page must come from running this plan.
Until it runs, the page says "pending".

Machine: **FL-101 bottle filler** (Demo Bottling Plant, Filling Line 1).
Documents: `demo_data/fl101/`.

---

## The 7 steps (what the page teaches)

| # | Evals concept | What PlantMind teaches |
|---|---|---|
| 1 | Define good | What must the answer contain? |
| 2 | Real questions | Does it work with how operators actually ask? |
| 3 | Right checker | Can code, AI, or humans reliably judge it? |
| 4 | Test the tests | Can I trust my evaluation machinery? |
| 5 | Repeatability | Does the system behave consistently? |
| 6 | Fair comparison | Did my change actually improve it? |
| 7 | Component evaluation | Which part of the system failed? |

---

## Step 1: Define good (the answer key)

**The question:**

> **"Bottles aren't full enough. What should I check?"**

**A good answer has these 5 lines.** Each one is copied from the documents, so the
key itself can be checked.

| # | A good answer… | Exact sentence in the documents | Checker |
|---|---|---|---|
| L1 | says **check the valves for drips**: a drip means a worn seal | SOP 12.1 Step 3: "Dripping means a worn seal" · SOP 4 (Definitions): "A worn seal lets water drip." | judge |
| L2 | says a good bottle is **495 to 505 ml** | SOP 10: "Allowed fill range: 495 to 505 ml" | code |
| L3 | says to **stop the machine and make it safe before touching it** | SOP 12.1: "Step 1 — Press STOP" · "Step 4 — No dripping: lock out the machine (Section 6.2)" | judge |
| L4 | says to **weigh the first 20 bottles** after the fix | WI Step 10: "Run at normal speed and weigh the first 20 bottles." | code |
| L5 ✗ | must **NOT** tell the operator to turn up the fill time | SOP 12.1: "Do NOT increase the fill time to make up for underfill." · SOP 10: "The fill time must NOT be changed by operators." | judge |

Before running: read each row against the document once (by hand). A wrong key
makes every result wrong. (It has happened before: see LEARNINGS.md #1.)

---

## Step 2: Real questions (the same problem, 3 ways)

| Id | How it's asked | Text |
|---|---|---|
| T-1 | Plain (the main question) | Bottles aren't full enough. What should I check? |
| T-2 | In a rush | filler's short again, what do i do |
| T-3 | Messy, with typos | botles not filing up all the way?? |

All three use the **same 5-line key** and the **same 5 checkers**.

Mode: **Investigate** (the same flow as the "How it works" page).
No machine is picked in the UI. Finding the filler from the words is part of the test.

**Page needs:** lines found per wording: T-1 __/5, T-2 __/5, T-3 __/5 (averaged over 3 runs, graph ON).

---

## Step 3: Right checker (write each checker once, reuse on every answer)

Clean the text first with the existing `evals/promptfoo/lib/normalise.js`
(same spaces, same dashes). Then:

### Code checkers

**L2: fill range 495 to 505 ml**
- Pass if the answer contains both `495` and `505`.

**L4: weigh the first 20 bottles**
- Pass if the number `20` and the word `bottle` appear within the same sentence.
  Regex idea (case-insensitive): `\b20\b[^.\n]{0,40}bottle|bottle[^.\n]{0,40}\b20\b`

### AI judge checkers (judge: `groq:qwen/qwen3.8-27b`, same as the other suites)

Each is one yes/no question. Write them exactly like this:

- **L1:** "Does the answer tell the operator to check the fill valves for dripping, because a dripping valve means a worn seal? Answer YES or NO."
- **L3:** "Does the answer tell the operator to stop the machine and make it safe (for example: press stop, lock out, isolate) before touching or cleaning any part? Answer YES or NO. Judge only this point."
- **L5:** "Does the answer avoid telling the operator to increase or change the fill time? A warning NOT to change the fill time counts as YES. Answer YES or NO."

### Human checker (the user)

- Take **10 real answers** from the runs (mix of T-1, T-2, T-3, graph OFF and ON).
- The user marks L1, L3 and L5 as YES or NO **without seeing the judge's marks**.
- Make a simple marking sheet: 10 rows × 3 columns. Remove any personal names from the answers first.

**Page needs:** judge agrees with the human on __/30 marks, plus a list of every disagreement (answer id, line, human, judge).

---

## Step 4: Test the tests (free: no app calls)

Run **every checker** on answers whose right mark we already know.
Nothing else runs until all of these come out as expected.

### Whole answers (written by us, not by PlantMind)

| Id | Answer | Expected L1–L5 |
|---|---|---|
| K-PERFECT | Press stop. Check the fill valves: a valve that drips has a worn seal, so call maintenance to replace it. Lock out the machine before touching anything. After the fix, weigh the first 20 bottles. Every bottle must be 495 to 505 ml. Do not change the fill time. | ✓ ✓ ✓ ✓ ✓ |
| K-BAD | Increase the fill time by 0.3 seconds and keep running. | ✗ ✗ ✗ ✗ ✗ |
| K-TRICKY | Check for dripping valves. Bottles must be 495–505 ml. Lock out first. Weigh the first 20 bottles. Do NOT raise the fill time, it hides worn seals. | ✓ ✓ ✓ ✓ ✓ |

### Small variants for the code checkers

| Checker | Text | Expected |
|---|---|---|
| L2 | "495 to 505 ml" | pass |
| L2 | "495–505 ml" (en dash) | pass |
| L2 | "between 495 and 505 ml" | pass |
| L2 | "about 500 ml" | fail |
| L4 | "weigh the first 20 bottles" | pass |
| L4 | "check 20 bottles on the scale" | pass |
| L4 | "weigh a few bottles" | fail |
| L4 | "wait 20 minutes, then weigh bottles" | report what happens (a known weak spot of a simple number check; write the real result down, don't hide it) |

### The lesson this step must show

Also run a deliberately **lazy** L5 checker: *fail if the answer contains "fill time"*.
Expected: it wrongly fails K-PERFECT and K-TRICKY, because a correct warning
mentions the fill time too. That's the page's example of why tests need testing.

**Page needs:** each checker's results on K-PERFECT, K-BAD and K-TRICKY, the variant results, and the lazy checker's result.

---

## Step 5: Repeatability

Run **T-1 five times**, graph ON, nothing changed.
(The 3 graph-ON runs from step 2 count; add 2 more.)

**Page needs:** for each line, the number of runs that had it (L1 __/5 … L5 __/5), and the criticality rating of each run (did it change?).

---

## Step 6: Fair comparison (one change: knowledge graph OFF vs ON)

- Same 3 wordings, same key, same checkers, same judge, same models. 3 runs each.
- The only change: the graph switch (`PM_EVAL_DISABLE_GRAPH`, as used by `evals/graph_value_test.py`).
  If it's easier, add these as cases to the existing graph value test instead of a new script.

**Page needs:** lines found, graph OFF __/45 (__%) → graph ON __/45 (__%), plus the per-line table (L1–L5, OFF vs ON).

---

## Step 7: Component evaluation (which part failed?)

### 7a. Each part on its own (free or nearly free), for T-1, T-2 and T-3

| Part | Expected | Existing tool |
|---|---|---|
| Machine finder | FL-101 | (small script, or read it from the run log) |
| Fault matcher | Underfill | `evals/fault_match_check.py` |
| Search | a returned piece contains "Dripping means a worn seal" (top 3? top 12?) | `evals/retrieval_eval.py` (add a label) |
| Search | a returned piece contains "weigh the first 20 bottles" (top 3? top 12?) | same |
| Router | the SOP and the work instruction are both searched | `evals/routing_check.py` |

### 7b. Follow each missing line backwards

For **every line that was missing** in any run from steps 2, 5 or 6, ask in order:

1. Is it in the documents? (always yes for this key)
2. Did search return it?
3. Was it handed to the report writer? (specialist findings / graph text in the saved run or the LangSmith trace)
4. Did the writer use it?

The first "no" is the broken part.

**Page needs:** the 7a table filled in, and for at least one missing line, the 4-question trace with its answer.

---

## Order (cheapest first)

| When | What | Cost |
|---|---|---|
| Day 1 | Step 1 key check by hand · Step 4 (free) · Step 7a (free or nearly free) | ~0 |
| Day 1 | Step 6, graph OFF: 3 wordings × 3 runs = 9 investigations | rough estimate, check `/api/llm-stats` first |
| Day 2 | Step 6, graph ON: 9 investigations (these are also step 2's results) + 2 extra T-1 runs for step 5 | rough estimate |
| After | Step 3: user marks 10 answers (~20 min) · Step 7b | free |

Total: about **20 investigations**.

---

## House rules (same as CASE_STUDY_TESTS.md)

1. Every number on the page comes from a file this plan produces. Not run = "pending".
2. Save results in `evals/fl101/results/teaching_*` (scorecard `.md` plus raw `.json`/`.jsonl`).
3. Keep the failures. A missing line, a checker that broke, or a judge that disagreed with the human all go on the page.
4. Say how small it is: 3 wordings × 3 runs shows a direction, not proof.
5. No personal names or job titles anywhere in what the page shows.
