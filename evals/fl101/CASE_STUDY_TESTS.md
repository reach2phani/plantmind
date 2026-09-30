# Case study tests: what to run so every lesson has real proof

This is a plan for the main build chat. It lists the tests behind the case-study page
(`docs/index.html`). The page teaches RAG to someone who has never heard of it, one idea
at a time, and proves each idea with something PlantMind actually did.

Everything uses **one example machine**: FL-101, the bottle filler in the Demo Bottling
Plant (Filling Line 1). Everyone understands a short-filled bottle or broken glass on a
food line, so a beginner can follow along without knowing anything about welding or AI.

Most of the questions already exist in [ANSWER_KEY.md](ANSWER_KEY.md) (cases FL-01 to
FL-06). This file doesn't replace it. It says which test proves which lesson, and exactly
what the page needs back.

---

## The house rules for numbers

1. **Every number on the page comes from a file in this repo.** If it hasn't been run, the
   page says "pending". We don't round up, and we don't estimate.
2. **Every test runs 3 times.** One good run can be luck. We learned that the hard way.
3. **Before and after use the same questions, the same models and the same judge.** Only
   one thing changes at a time.
4. **Say how small the test is.** Six cases × 3 runs shows a direction, not proof. The page
   says so in plain words.
5. **Keep the failures.** A test that didn't improve, or got worse, goes on the page too.
6. **Save results here:** `evals/fl101/results/`, one scorecard per lesson, named after
   the lesson (for example `graph_off_vs_on_scorecard.md`).

---

## The opener: "RAG in 60 seconds"

**What a beginner should get:** a normal AI doesn't know your plant. RAG means *search
the plant's own documents first, then answer only from what you found, and show where it
came from.*

**What the page needs:** one real FL-101 report, start to finish, with its list of sources.

| Question | Use |
|---|---|
| "FL-101 bottles are coming out underfilled. That's the third underfill alarm tonight." (FL-01) | Save the full report text from one graph-ON run, plus the names of the document pieces it used |

No before/after needed. This is just "here's what it looks like when it works".

---

## Lesson 1: Scope. "A right answer about the wrong machine is still wrong."

**The idea in plain words:** search can be filtered by labels, like which machine or which
kind of document, so the answer stays about the thing you asked about.

**Why the obvious fix fails:** "Just ask operators to type the machine tag." They don't,
especially at 2 a.m. They say "the filler on line 1". And "search everything and let the AI
sort it out" is how an answer drifts to the wrong machine's manual. The result still sounds
right, which is the dangerous part.

**What to run**

| Test | How | What the page needs |
|---|---|---|
| Find the machine from plain words | Ask 4 ways without the tag, 3 runs each: "the filler on Filling Line 1 is underfilling", "the bottle filler keeps jamming", "glass broke in the filler", "filler supply pressure is low" | Correct machine: __ / 12 |
| Nothing leaks from other machines | The isolation check already in every FL case: no welding words (wire feed, liner, burn-in, arc...) anywhere in an FL-101 report | Reports with a leak: __ / all FL runs |
| Search finds the right piece | Retrieval check using the FL-101 labels in ANSWER_KEY section 5 | Right piece in top 12: __ / 13, top 3: __ / 13 |

**What surprised us (already real):** FL-101 worked straight away. No welding knowledge
leaked into a bottling report, even though every earlier test was about a welder.

---

## Lesson 2: Evals. "You can't improve what you can't measure, and the test can be wrong too."

**The idea in plain words:** to test an AI, write down what a good answer must contain.
Let code check exact things (a number, a time) and a second AI, the "judge", check
judgement ("did it warn against the trap?"). Run each test more than once.

**Why the obvious fix fails:** "Read a few answers and see if they look good." They always
look good. The AI writes fluently even when it's wrong. And a single run can pass by luck.

**What to run:** nothing new. This lesson uses the scorecards from lessons 4 to 6 and
explains *how* they were made.

| What the page needs | Where it comes from |
|---|---|
| One case shown as a marked "exam paper": each required fact ticked or crossed, and whether code or the judge checked it | FL-01 checks from ANSWER_KEY, marked from one real run |
| How steady the answers are: checks that gave the same result in all 3 runs, graph OFF vs ON | "Checks identical across runs" line of the lesson 4 scorecard |
| One case whose result changed between runs (if any) | Per-run results in the lesson 4 runs file |

**What surprised us (already real, in [LEARNINGS.md](LEARNINGS.md)):** the answer key
itself was wrong. It expected the valve numbers (3, 9, 15, 21) for the night of 10 September,
but that seal change is in the *next morning's* log. The system was right to leave them out.
**A test needs checking too.**

---

## Lesson 3: Context. "The AI only knows what you put in front of it."

**The idea in plain words:** before answering, the AI is handed a bundle of text: the
question, the pieces search found, facts about the machine, and the rules. That bundle
(the "context") is *all it knows*. If something isn't in it, it can't be in the answer.
And if something misleading is in it, that ends up in the answer too.

**Why the obvious fix fails:** "Give it more documents." More text doesn't help if the one
piece that matters isn't there. On FL-101, the 10-minute rinse after a seal change sat just
past a cut in the document, so search never returned it, however many pieces we asked for.

**What to run**

| Test | How | What the page needs |
|---|---|---|
| Show the real bundle | One LangSmith trace of FL-02 (overfill after a seal change), graph ON. Split what the report writer received into layers: question, specialist findings, graph facts, machine, rules | Each layer's text and size in tokens, from the trace |
| Empty section, before vs after | The "graph verified" claim with no FL-101 graph loaded. **Before:** seen once in the first spot check (LEARNINGS #3). **After:** run FL-01 to FL-06 graph OFF, 3 runs each, and count reports that claim the graph confirmed anything | Before: seen in 1 spot check · After: __ / 18 |
| Remove one layer, same question | This *is* graph OFF vs ON (lesson 4). Take FL-02 and show the two answers side by side | The two report texts, plus which checks flipped |

**What surprised us (already real):** an *empty* graph section was worse than none. The AI
saw a heading with nothing under it and filled the gap with "knowledge graph (verified)
confirms the SOP steps".

---

## Lesson 4: Knowledge graph. "Search finds similar text. A graph knows how things connect."

**The idea in plain words:** search finds pieces of text that sound like the question. It
doesn't know that *replacing a seal requires a 10-minute rinse* when those facts sit in
different documents. A knowledge graph stores those links on purpose: fault → cause → fix
→ must-do steps → safety.

**Why the obvious fix fails:** "Use bigger pieces, or return more of them." The link runs
*across* documents (the seal procedure is in the work instruction, and the fill-time lesson
is in the quality report), so no size of piece joins them.

**What to run:** the main graph value test, same method as before.

| Test | How | What the page needs |
|---|---|---|
| Graph OFF vs ON | FL-01 to FL-06, 3 runs each, after loading `fl101_graph.json` (currently the draft file) | Required facts: __% → __% · Made-up specifics per report: __ → __ · Checks identical across runs: __ → __ |
| The link a beginner can see | FL-02 "slightly overfilled after new seals": does it say *this is expected, don't change settings*, and include the 10-minute rinse? | Each check, OFF vs ON: __/3 → __/3 |
| The right documents get searched | Routing check for FL-01 to FL-06, OFF vs ON (same script as `evals/routing/`) | Cases that searched everything required: __ / 6 → __ / 6 |
| Where each fact came from | Already in the graph: every fact carries its document section | Nothing to run. The page draws it from the graph file |

**What to watch for (the likely surprise):** on the earlier machine, the graph didn't make
the AI *invent* less. It stopped it *leaving things out*. Check whether that holds here, and
report it either way.

---

## Lesson 5: Trust. "Not all evidence is equal."

**The idea in plain words:** sources disagree. A procedure someone reviewed should beat a
tip someone mentioned in passing. PlantMind labels every piece of evidence with a trust
level (four tiers, in the code) and follows the higher one when they clash.

**Why the obvious fix fails:** "Tell the AI to trust the operators," or "tell it to ignore
them." The first lets an untested tip into the repair steps. The second throws away real
experience. Some tips are *right*.

**The conflict (all real, from the FL-101 documents):** an operator tip says *"For
underfill, raise the fill time by 0.3 seconds. Fixes it every time."* The SOP says the fill
time is 3.2 seconds and must not be changed. The quality report NCR-2026-012 records what
happened when someone did exactly that: fill time went from 3.2 to 3.9 s, the worn seals
stayed hidden, and **1,200 bottles were rejected**.

**What to run**

| Test | How | What the page needs |
|---|---|---|
| The wrong tip | Capture the WRONG tip (ANSWER_KEY section 7), unreviewed. Run FL-06 and FL-01, 3 runs each | Reports with a fill-time change in the repair steps: __ / 6 |
| The right tip | Capture the RIGHT tip (clean the nozzle), unreviewed. Run FL-01, 3 runs | Mentioned as a lead to check (not a step, not ignored): __ / 3 |
| A "before" number, if possible | Only if the trust labels can be switched off with a setting, without a code change: run the wrong-tip test once with them off | Before: __ / 6, or "not measured" |

**Open decision for you:** if there's no switch for the "before", FL-101 only gets an
"after" number. The page can then say "the before was measured on an earlier test machine
(14 of 18 → 1 of 18)", or leave the before out. Your call, since we agreed not to mention
the second machine.

---

## Lesson 6: Rules. "The AI writes. Code decides the things that must never go wrong."

**The idea in plain words:** a rule in a prompt is a suggestion. A rule in code is a
guarantee. Anything exact or safety-critical (a minimum rating, which documents must be
searched, a cost) is decided by plain code, not by the AI.

**Why the obvious fix fails:** "Add 'be careful about safety' to the prompt." The prompt
already had rules, and glass breakage was still rated HIGH, because those rules were
quietly written for welding (electrical, fire, fumes). Nothing covered glass in a bottle.

**What to run**

| Test | How | What the page needs |
|---|---|---|
| Glass must be CRITICAL | FL-04 (bottle shattered), 3 runs. **Before:** the first spot check (HIGH, 1 run, LEARNINGS scorecard). **After:** with the rule fix | Before: HIGH in 1 spot check · After: CRITICAL in __ / 3 |
| The floor as a safety net | Count how often code had to raise a rating, across all lesson 4 runs | Ratings raised by code: __ / 36 (zero is a fine answer, and we'll say so) |
| Required searches | Same routing result as lesson 4, told from the rules side: the graph says what must be searched, and the AI can add searches but never drop one | __ / 6 → __ / 6 |
| Unreviewed tip warning | From the lesson 5 runs: reports where a tip reached the repair steps and got a visible ⚠ | __ / __ |

**What surprised us (already real):** the rules weren't wrong. They were *narrow*. Rules
written while looking at one machine quietly describe that machine's world.

---

## Lesson 7: Tracing. "When something goes wrong, you need to see which step did it."

**The idea in plain words:** an answer passes through many steps: find the machine, read
the graph, several searches, write the report, check it. Tracing records each step with
its input, its output, how long it took and what it cost. That turns "the answer is wrong"
into "step 4 never received the rinse fact".

**Why the obvious fix fails:** "Just log the final answer." Then all you know is that it's
wrong, not where it went wrong.

**What to run**

| Test | How | What the page needs |
|---|---|---|
| One real timeline | One LangSmith trace of FL-01, graph ON. Export each step's start time, end time and tokens | A row per step: name, start (ms), duration (ms), tokens. This becomes the timeline picture, bar for bar |
| Cost and speed | `evals/ops_report.py` over the time window of the lesson 4 runs | Tokens per investigation, typical (p50) and slow (p95) time per step, answers cut off, errors, share of the daily free quota |

**What surprised us (already real):** the logs themselves were wrong at first. Token counts
were estimated from text length instead of measured, and undercounted by about 3×. Found
and fixed on 18 September.

---

## Lesson 8: People in the loop. "AI can investigate. People stay accountable."

**The idea in plain words:** experienced operators know fixes that aren't in any document.
PlantMind lets them explain a fix by voice. It's searchable straight away, but only as an
unreviewed lead. A person has to approve it before it becomes trusted knowledge.

**Why the obvious fix fails:** "Add every capture to the trusted knowledge straight away."
Then one wrong tip (like "raise the fill time") becomes a verified fact in every future
report. But "never let operators add anything" loses the good tips.

**What to run**

| Test | How | What the page needs |
|---|---|---|
| Good tip, before and after approval | RIGHT tip (clean the nozzle): run FL-01 while unreviewed, then approve it in the Review queue and run FL-01 again. 3 runs each | Before: a lead only, __ / 3 · After: allowed in the action and credited, __ / 3 |
| Wrong tip, rejected | Reject the WRONG tip in the Review queue. Confirm it never enters the graph and stays a lead only | Screenshot of the rejection, plus FL-06 still clean: __ / 3 |
| The review screen | Screenshots of the Review queue showing the raw quotes next to the summary | 1 to 2 screenshots, with no personal names visible |

**What surprised us (already real):** a person approved a bad merge. Two different faults
matched by mistake, the reviewer approved it, and one finding's content was lost. A human
in the loop isn't enough if they can't see what they're approving. The planned fix shows
"this will merge into: …" before approval. Report whether it's fixed by the time the page
ships.

---

## What the page needs back: checklist

| Lesson | Needed | Status |
|---|---|---|
| Opener | One full FL-01 report with sources | to run |
| 1 Scope | Machine found from plain words, isolation count, FL-101 retrieval scores | to run |
| 2 Evals | One marked case, consistency numbers | comes from lesson 4 |
| 3 Context | One trace split into layers, "verified" claim count after the fix | to run |
| 4 Knowledge graph | Graph OFF vs ON scorecard, FL-02 checks, routing | to run (needs the graph loaded) |
| 5 Trust | Wrong tip and right tip results, "before" if possible | to run, plus one decision |
| 6 Rules | Glass CRITICAL after the fix, floor count, tip warning count | to run |
| 7 Tracing | One exported trace, ops report | to run |
| 8 People | Before and after approval, rejection, screenshots | to run |
| Already real | Answer-key mistake, empty-graph claim, welding-only rules, glass HIGH, token undercount, bad merge | in LEARNINGS.md and the project history |

**Budget note:** all of this runs on free tiers. Lesson 4 alone is 36 investigations
(6 cases × 3 runs × OFF and ON). Check `/api/llm-stats` first, and spread the runs over
more than one day if needed.
