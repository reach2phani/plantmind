# PlantMind case-study page: handoff (updated 19 Oct 2026 · Evals + Knowledge graph + Trust done · next: Tracing · parallel: Architecture rework)

Paste this into a new chat to continue. This chat is **only** for the interview case-study page.
App/eval work (FL-101, Phase 2a+) happens in the main build chat. Don't mix them.

---

## How we work

- Explain everything in **very simple, plain language**.
- **Discuss first → user approves → build → user checks in the browser.** For each stage: talk through what it should convey, sometimes sketch, then build.
- The user commits and pushes to `main` themselves. Don't commit.
- **Honesty rule:** every number and quote on the page comes from a real file in the repo. Not measured = "pending". Never round up, never invent (no made-up quotes, IDs, percentages or dialogue). Quotes are checked **word for word** against `demo_data/fl101/`.
- Don't touch app code from this chat. If you find an app bug, raise it as a separate task.
- Keep names neutral. **No personal names or job titles** (shift logs contain operator names; never show them).

## The files

| File | What it is |
|---|---|
| `docs/preview.html` | **The page being built.** One self-contained HTML file: inline CSS + JS, Google Fonts only, no framework |
| `docs/index.html` | Old first draft (12 sections). Untouched; will be replaced by preview.html later |
| `docs/draft.html` | Earlier experiments (7 lessons, old visuals). Can be deleted later |
| `evals/fl101/CASE_STUDY_TESTS.md` | Test plan written for the main chat: one test per lesson, plus what the page needs back |
| `evals/fl101/LEARNINGS.md`, `ANSWER_KEY.md` | Real FL-101 findings and the answer key (written by the main chat) |
| `evals/graph_value/fl101_scorecard.md`, `fl101_runs.jsonl` | Real FL-101 graph OFF vs ON results and saved reports |
| `evals/fault_match/*_scorecard.md` | Real fault-matching results (exam 4/7 → 7/7) |
| `evals/fl101/TEACHING_SET.md` | The Evals lesson's test plan (one simple question, 5-line answer key, 7 steps) |
| `evals/fl101/results/teaching_*` | Real Evals results: scorecard, judge-vs-person, checker self-test, component checks, run log |

Patches were applied with small Python scripts (find/replace on `preview.html`). The Architecture scene source is mirrored in the scratchpad as `arch.js`, but **preview.html is the source of truth.**

---

## Page structure (current)

- **Header:** "Inside PlantMind" / *What happens between an operator's question and the answer?* / "An animated walkthrough of the journey from identifying the problem and building context to gathering evidence, validating it, and producing the final answer."
- **Side menu:** `· How it works` → `1 Architecture` → `2 Evals, 3 Context, 4 Knowledge graph, 5 Trust, 6 Rules, 7 Tracing, 8 People in the loop` (all "soon").
- **Player:** one SVG scene per page (viewBox 1000×480), caption box, ← ▶ →, step bar. It auto-plays when opened and stops at the end. The caption box hides when a step has no text.

### Note (2 Oct): two single-view rewrites of "How it works" were tried and REJECTED
1. a bottling line (conveyor, moving bottle, pop-up stations); 2. an "investigation sheet" (facts paired with
document quotes, checked box, answer). The user prefers the original 6-stage version below: "it conveys our
thought clearly", the sheet felt overcrowded. Don't propose a single-view rewrite again without a new reason.

### Page "How it works": 6 stages, one caption each (DONE, kept)
Journey bar across the top (Question → Scope → Context → Evidence → Validate → Answer), with a "TRACE" line and a "question" marker sliding along it. Each stage has its own highlight colour. Inside a stage, the elements appear in sequence with delays.

1. **Question** (4 s): the operator bubble: "We're getting underfill alarms again on Filling Line 1, and the checkweigher is rejecting bottles. Third time tonight. What should I check?" (a tidied version of test FL-01). Caption: "Before answering, PlantMind needs to work out what equipment and operating context matter, find the relevant evidence, and determine which information can be trusted."
2. **Scope** (subtitle "what exactly are we dealing with?", 11 s): the faded question with clue words lighting up, laid out as two lanes, "Which machine is it?" / "What's wrong with it?":
   - "Filling Line 1" → **The bottle filler (FL-101)** on Filling Line 1
   - "underfill alarms" + "checkweigher is rejecting bottles" → **Underfill (fault name)**, bottles filled below 495 ml
   - **NOT THIS** (struck through): the welder, or any other machine · overfilled bottles · a jam · broken glass · low supply pressure
   - Green box: **SO THE PROBLEM IS: The bottle filler on Filling Line 1 is putting too little in each bottle.**
   - Caption: "First, identify what we're dealing with: which machine, and what's wrong with it. If we get either one wrong, everything that follows is built on the wrong foundation."
3. **Context** ("what's happening right now?", 13 s):
   - FROM SCOPE: "FL-101 on Filling Line 1 is underfilling bottles."
   - A timeline with phase labels: **PAST INCIDENT** (Jan 2026, fill time raised 3.2→3.9 s, 1,200 rejected, NCR-2026-012) → **EARLY WARNING** (22:05, valves 9 & 15 dripping, seal change booked for tomorrow) → **RECURRENCE** (01:30 live alarm, restarted and monitored) → **RECURRENCE** (03:20, same valves, request to increase fill time declined) → **SPREADING** (04:45, third alarm, valves 9, 15 and 3) → **QUESTION** (Now).
   - Source icons on each row: 📡 live MQTT alarms, 📋 shift log, 📁 past incident, 🗣 operator's words. Alarm beacons; the third one flashes.
   - Right side, "WHAT WE KNOW SO FAR", with lines linking to rows: Same valves · Same failure pattern · Prior incident: 1,200 rejects · Now spreading to another valve.
   - Bottom: THE SITUATION HAS CHANGED: **Recurring → spreading**.
   - Caption: "Context turns isolated events into a situation. Live alarms, the shift log and a past incident, read together, reveal a recurring problem, and a pattern that's now changing."
4. **Evidence** ("what do the plant's documents say?", 13 s):
   - FROM CONTEXT: "FL-101 is underfilling. The problem is recurring and now spreading."
   - Rows of what we know → what the documents say (with the exact sentence highlighted in yellow) → source tag:
     - Valves 9 & 15 dripping → "Dripping means a worn seal … replace the seal kit" (SOP 12.1)
     - 3 alarms this shift → "Three or more underfill alarms in one shift means a systemic fault." (SOP 12.1)
     - Request to raise fill time → "The fill time must NOT be changed by operators." (SOP 10)
     - Fill time raised, Jan 2026 → It hid worn seals: 1,200 bottles rejected, "Never increase the fill time to fix underfill. It hides worn seals…" (NCR-2026-012 · LESSONS)
     - After seal replacement → "Run the sanitation rinse for 10 minutes … weigh the first 20 bottles." (WORK INSTR. · STEPS 9–10)
   - A dashed **NOT FOUND** card: "Last seal service: no record found" (real, from the FL-01 run's maintenance findings).
   - Caption: "Now we check the story against the plant's own documents: finding the guidance that applies, showing where it came from, and calling out what we couldn't find."
   - No § symbol anywhere (the user asked).
5. **Validate** ("does it hold together?", 15 s): DRAFT (Worn seals → systemic fault → stop production → replace the seals) → "CHECKS APPLIED TO THE DRAFT" → three amber-edged gates:
   - **1 · CONSISTENCY**, "Does this fit what we know?": ✓ Underfill pattern ✓ Same valves ✓ 3 alarms
   - **2 · COMPLETENESS**, "Did we include the required procedure?": + Rinse 10 min + Weigh first 20 bottles + SOP 12.1 ("required by the procedure"; the rinse and weighing come from the work instruction, not the SOP)
   - **3 · AUTHORITY**, "Which source wins when they disagree?": SOP ↑ outranks SHIFT LOG, ✕ Raise fill time
   - → **CHECKS PASSED ✓** (not "validated", which would overclaim): Stop production / Replace the seals / Rinse 10 min / Weigh first 20 bottles / Do not change fill time. Sources line underneath.
   - Caption: "Evidence shows us what the plant's sources say. Validation is where we pressure-test the answer: does it fit what we know, did we include the steps that matter, and what do we do when two sources disagree?"
6. **Answer** ("what does the operator need to know now?", 12 s): a report card from the real FL-01 report, shortened. **HIGH** (amber) · "Systemic fault: 3 underfill alarms this shift"; DO THIS NOW 1–5 with source tags; DON'T ✕ Change the fill time (SOP 10 · NCR-2026-012); TELL Maintenance supervisor · Quality lead; "The operator decides. Every step shows where it came from."
   - Each line has a tiny ● CONTEXT / ● EVIDENCE / ● VALIDATE tag, and the matching journey stage box **pings** as the line lands.
   - Caption: "Only now does PlantMind answer: how serious is the situation, what should the operator check, and where did each recommendation come from? The operator remains in charge."
   - **No 7th closing step** (the user removed it).

### Page "Architecture": animation only, no captions (DONE, still being refined)
- Sections: INPUTS · IDENTIFY · INVESTIGATE · WRITE & CHECK · OUTPUT. Legend: ▣ CODE · ✦ AI · ── FLOW · ── GRAPH (amber) · ┄ STORE.
- **Right-angled routing**; one crossing drawn with a "hop". Line types: solid grey = the live path, amber = graph constraints, dashed grey = storage.
- **Inputs:** 👤→Chat; MQTT alarms → Alerts page → 👤 (the operator clicks Investigate) → joins the path; 👤→🎙 Voice capture (✦).
- **Boxes:** Machine finder ▣ · Router ✦ (GPT-OSS 20B) · Graph ▣ with an inner "Fault match ✦" pill · 5 specialists ✦ labelled by what they read (Shift logs, Operator fixes, Work instructions, SOPs, Quality reports) · Report writer ✦ (GPT-OSS 120B) · Code checks ▣ · Report.
- **Stores:** Supabase (under the Machine finder), Neo4j (under the Graph, with a 👤 review gate), Pinecone with 12 small chunk icons.
- **9 steps:**
  1. Alarm → Alerts → operator (stored in Supabase)
  2. Machine finder (reads the equipment list) + FL-101 tag
  3. Into the Graph: fault match, Underfill stays
  4. Graph → 3 amber required-search markers → Router
  5. Specialists 2 at a time + chunks pulled from Pinecone
  6. Findings + amber must-do steps → writer
  7. Code checks: ⚠ flag, ↑ rating raised, ✓
  8. Report, saved to Supabase
  9. Learning loop: voice → Pinecone (amber chunk) → Operator fixes lights up; review 👤 → Neo4j
- **Trace rail removed** (the Tracing lesson will own it).
- A deep check against the code was done (see "Verified against code" below).

---

## Page 2 "Evals" (DONE, 2 Oct 2026)

**Idea:** teach evals to a newcomer with **one simple question** followed through 7 steps:
*"Bottles aren't full enough. What should I check?"* (FL-101). New test data was designed for this
(`TEACHING_SET.md`) and run by the main chat; every number on the page comes from `evals/fl101/results/`.

**Layout (chosen after trying a step bar, a conveyor line and a wheel, all rejected):**
- LEFT: a ruled notebook page, 7 boxes with the step names only (user's wording): 1 WHAT GOOD LOOKS LIKE ·
  2 REAL-WORLD QUESTIONS · 3 CHECKING THE ANSWER · 4 CHECKING THE CHECKS · 5 RUNNING IT AGAIN ·
  6 COMPARING CHANGES · 7 FINDING THE PROBLEM. Current box lit, pointer to the right. Margin arrow 7 → 1 at the end (the loop).
- RIGHT: "STEP n OF 7", the step's question as heading, then one picture and one closing line.

**What each step shows:**
1. 5 requirement lines (MUST ×4, MUST NOT) with tags CAUSE / TARGET / SAFETY / PROOF / TRAP. "Every requirement comes from the plant's procedures."
2. The 3 wordings (plain / in a rush / with typos). No numbers. "Different wording helps us see if the answer holds up."
3. CODE / AI JUDGE / PERSON icons, each with a tiny example question. "The tricky part is knowing how to check each requirement."
4. THE RULE, then WE KNOW THE ANSWER → RUN THE CHECKER → COMPARE → THEY DISAGREE → THE CHECKER IS WRONG (real: the word check failed "Do NOT raise the fill time…"). "So we test the test before using it to judge."
5. One real line from each of the 5 runs (the 20-bottle check, word for word from `teaching_runs.jsonl`). "Every run came back with the same answer."
6. Two cards: GRAPH OFF (typical answer ✗✗✓✗✓, 48%, 9 runs) → GRAPH ON (all ✓, 100%, 11 runs). "Change one thing. See what happens."
7. One requirement traced: PLANT PROCEDURE ✓ → SEARCH ✓ → SPECIALIST ✗ summary left it out → WRITER — never received → ANSWER ✗. "The search worked. The handoff failed." Last caption: "Evaluation isn't a final score. It's a feedback loop for improving the system."

**Below the player:** nothing. The evidence card and "What surprised us" note were removed by the user (2 Oct): "no one will care". Sources stay in the repo files listed in this handoff.

**User preferences learned on this page:**
- Hates crowding and repetition: one picture + one sentence per step; scene line = what happened, caption = why it matters.
- Numbers only where they add meaning (removed from steps 2, 3 and 5's tags); an example is only worth showing if it adds something new (pass/fail example in step 1 was removed as a repeat).
- Plain words over jargon. Industry terms appear only as a small outlined badge next to "STEP n OF 7": SUCCESS CRITERIA · ROBUSTNESS TESTING · GRADERS · LLM-AS-JUDGE · GRADER VALIDATION · CONSISTENCY TESTING · A/B TEST · ABLATION · COMPONENT-LEVEL EVAL.
- Rejected here: stage bar copy of How it works, conveyor line, wheel/loop, upward trace in step 7 (kept top-down for readability).
- Not backed by a file, so NOT used: machine finder "1/3 → 3/3".

Scene source is mirrored in the scratchpad (`sevals3.js` + `apply_page.py`), but **preview.html is the source of truth.**

## Page 4 "Trust" (DONE, 17 Oct 2026)

**Idea:** *Trust means knowing when an answer is safe to rely on, and when a person needs to step in.
Checks help build trust, and a person controls the decision.* The picture is an **empty shield that is
built block by block**. Each block is one trust question; beside it, a side panel with three parts.
At the end the shield is complete in shape, but every block still has a gap.

**How it is built in `preview.html`:** scene `sTrust()` (CSS prefix `tr-`), lesson entry `name:'Trust'`,
8 steps (opening + 6 blocks + finished shield). It uses the shared engine (`data-f/h/c/d`); captions are
empty strings, so **this page has no caption box** (user's choice). A small operator figure holds the shield
and lights up at block 6. Side panels: `What PlantMind does` → `Where it fell short` → `What I learned`
(labels shared by all blocks; user chose "What I learned" everywhere). On phones the shield stacks above
the text. Menu is now: How it works · 1 Architecture · 2 Evals · 3 Knowledge graph · **4 Trust** ·
5 Tracing (soon) · 6 People in the loop (soon).

**The six blocks (final wording is in `sTrust()`; summary only):**
1. **Can I trace the answer?** 4 of 17 restart steps fully backed by documents, 6 partly, 7 none (`fresh_fix_grounding.md`). The step check runs in testing, not in the app ("A test checks whether the document supports it").
2. **Is that source approved?** Tip "Reset tension from 18 to 22" as a repair step in 14 of 18 reports → 1 of 18 after rules and labels (welder; handover → trust scorecards).
3. **Is it the right machine and the right time?** Seal replacement recommended from the 10 Sept log; 11 Sept log: "Seals replaced on 4 valves. Running well." (`fresh_runs.jsonl` FR-01). Screenshot slot `docs/img/trust-restart-high.png`.
4. **Does its confidence mean it's likely to be right?** Label is based on how much evidence was found, not correctness; 4 HIGH answers were missing more than half their facts.
5. **What catches an error before it reaches me?** The tip-based step that slipped past the rule was flagged; the check for made-up numbers missed all 7 unsupported restart steps (LEARNINGS #14). Lesson: "A check only catches the mistake it was built to look for. A missing warning doesn't mean the step is safe."
6. **When does a person need to decide?** Engineer review when confidence isn't HIGH or a check fires; the operator decides; the flag didn't catch every answer that needed review.
Block 1 also has a screenshot slot `docs/img/trust-restart-after-fix.png`. Both slots show a dashed placeholder until the file exists.

**Still open for Trust (before publishing):**
- **Block 4's "4 answers marked HIGH"** comes from a *scratch* calibration analysis (81 saved FL-101 answers with a confidence label: HIGH 30 → 83% of required facts, 21 complete; MEDIUM 10 → 30%; LOW 41 → 38%; review flag caught 33 of 37 weakest; the 4 missed were all HIGH, all fresh questions FR-01 ×3, FR-05 ×1; only 8 distinct questions; HIGH only possible with the graph). **The main chat must save this check into `evals/` and write a scorecard** so the number has a file. Script used: same code checks + saved judge caches as `graph_value_test.py`, no AI calls.
- **Two screenshots** (names cropped/blurred): the after-fix restart answer (block 1) and the HIGH "replace the seals" answer (block 3).

**What the user taught us on this page (follow these):**
- Write for the **operator**, in plain words. Don't keep naming "PlantMind" in captions. No AI-slop patterns: repeated "X isn't Y. It's Z", fragment triplets, balanced closers, lists of abstract virtues, meta badges. Titles say what happened; only the last line may sound like a lesson.
- Every outside-AI feedback had factual errors: three times it weakened the seal evidence ("replacing", "described work") although the 11 Sept log says "New seals fitted" and "Seals replaced on 4 valves. Running well."; it changed the operator's exact question; it invented a merged single answer across welder + bottle filler tests. **Check every pasted claim.**
- Never merge examples from different tests into one answer. Keep the welder and bottle-filler examples separate.
- Don't overclaim: say when a check runs only in testing; "Engineer review needed" flags, it doesn't block.
- Removed by the user: grade chips ("Tested · not good enough yet"), the caption box, inner/outer layer drawing (confusing).
- Rejected along the way (don't re-propose without a new reason): stamps/lightbox, Swiss-cheese slices, wheel/petals, seal ring, andon light, filter/funnel, autopsy, 2×2 sure/right grid with dots, timeline "when was that", report card, left/centre/right spine, agents→shield→operator player, Cesium (geospatial, too heavy, breaks the self-contained page).

## NEXT: Page 5 "Tracing" (start here in the new chat)

**Working method that worked (keep it):** agree the one sentence the reader should remember first, then the
story, then sketch on a scratch page, then merge into `preview.html`. Keep sketches in the scratch folder,
not in `docs/`. Give the page its own look.

**What Tracing means here (from the code):** `tracing.py` sends each investigation to LangSmith as a timeline
tree: graph lookup → supervisor (router) → specialists (each with its search) → report writer → report
guardrails, with each step's exact input and output and the tokens of every Groq call. It shows what each step
received and produced, not the model's private reasoning (turned off on purpose). Off unless `.env` has
`LANGSMITH_TRACING=true`. Traced functions in `multi_agent.py`: `groq_call`, `search_documents`,
`search_expert_fixes`, the five agents, `report_guardrails`, `orchestrator`, `supervisor`, `investigation`.
Plain idea from `CASE_STUDY_TESTS.md` lesson 7: tracing turns "the answer is wrong" into "step 4 never received
the rinse fact". Obvious fix that fails: "just log the final answer" (you learn that it's wrong, not where).

**Real material already in files (check before quoting):**
- **Where each missed fact got lost** (LEARNINGS #11, `evals/context/attribution.md`, made by
  `evals/context_attribution.py`, no AI calls): 84 facts really lost out of 278 required-fact checks, followed
  along documents → search → specialist → writer → report. Graph OFF: 3 not searched, 24 searched but not in the
  top 4, 24 found but cut (300-character cut, fixed 1 Oct), 21 summarised away by a specialist, 2 left out by the
  writer. Graph ON: all 10 losses were the writer leaving out a fact it was given. Not one fact was missing from
  the documents. Corrected 5 Oct (a word pattern also matched past shift-log lines). LEARNINGS already suggests a
  picture: **a leaky pipe with the count dripping out at each joint.** Note: the Context page was dropped, so
  this material is free for Tracing.
- **The Evals page step 7 already shows one trace** (found ✓ → passed on ✗, "weigh the first 20 bottles"
  dropped by the maintenance specialist's summary). Don't repeat it; Tracing should go wider (all 84) or deeper
  (a real timeline).
- **The logs were wrong at first:** token counts were estimated from text length and undercounted by about 3×;
  found and fixed 18 Sept (`CASE_STUDY_TESTS.md`).
- **Known issue 17** ("first time ever" while citing the earlier event) was planned to be diagnosed with a trace
  first (LEARNINGS #7) — check whether that was done.

**Not in the repo yet (ask the main chat):**
- **One real LangSmith trace export** (CASE_STUDY_TESTS lesson 7): e.g. FL-01, graph ON — each step's name,
  start (ms), duration (ms), tokens. That becomes the timeline picture, bar for bar. No trace exports exist in
  the repo today.
- **Cost and speed:** `evals/ops_report.py` over the time window of a run — tokens per investigation, p50/p95 time
  per step, cut-off answers, errors, share of the daily free quota.

**Open decisions for Tracing:**
1. The one sentence to remember (candidate: "When an answer is wrong, tracing shows where it went wrong").
2. Wide (the 84 lost facts, where they leaked) or deep (one real investigation timeline), or one of each.
3. Whether to wait for the real trace export before building the timeline part.

## Lesson "From Document to Answer" (DONE, 20 Oct 2026 · lesson 1, between How it works and Architecture)

**What it is:** one FL-101 work instruction's journey, as a lesson in `docs/preview.html` (it is the single copy;
`sketches/` was removed). Six stages, each one step of the lesson player: **Upload · Chunking · Searchable ·
Question · Retrieved · Answer**. Each stage shows its own label (`Stage n of 6 · name · term`), title and intro
above the animation. The existing **Architecture** lesson is unchanged and follows it.

**How it is built:** a closure `DJ` just above `const L = [` holds the stage code; each stage has `title`, `lead`
(may contain `<em>`/`<br><br>`), `term`, `dur`, `build()` and `render(t)` (t = 0…1, every frame a pure function of t).
Inside a step the stage runs on its own clock: **7 s reading pause** (countdown shown), then the animation at
`PACE` .7, then a 2 s hold. The player gained three optional hooks used only by this lesson: `onStep`, `onPlay`,
`onStop` (+ `onLeave`). Styles are scoped under `.dj` (own `--paper`, `--plum`, `.m/.mb/.s/.q`). Element ids inside
are prefixed or local, so nothing touches the page's ids.

**Real data in it:** the work instruction's own text and the splitter's real cuts (chunk 1 = 918 characters,
chunk 2 = 939, ~160 shared; 8 chunks in all); the Retrieved stage uses the **real Pinecone and reranker order**
for the question *"What checks are needed after changing the fill valve seals?"*: Pinecone ranks all 8 WI chunks
(filter FL-101 + Work Instruction), the reranker moves "Rinse + first-bottle check" from #3 to #1, Procedure
#7 → #4, Sign-off #4 → #8; the top 4 go on to Answer. Reproduce with `evals/lifecycle/retrieved_ranking.py`
(free tier, no Groq tokens; result in `evals/lifecycle/retrieved_ranking.json`). Illustrative and labelled so:
number values, dot positions, topic labels on the map, the answer wording.

**Why that question (not "Bottles aren't full enough"):** for the underfill question the reranker scored every
WI chunk near zero and ranked Scope and the document header top. The WI is about seal replacement; underfill
troubleshooting lives in the SOP. A real finding for the Context chapter, not for this lesson.

**Verified against the code (19 Oct):**
- Text/PDF documents: ~1,000-character pieces, 200 overlap (`embedder.py` chunk_size/chunk_overlap).
- Shift logs (CSV): grouped by the `equipment` column first, then 5 rows per piece (`embedder.py`, Batch E1).
- Embedding model multilingual-e5-large (via Pinecone inference), 1,024 numbers per piece. Stored in **Pinecone**
  with metadata (machine, plant, line, document type, revision). **Neo4j is NOT built from uploads**: it holds
  each machine's reviewed knowledge graph, loaded from a checked graph file, plus operator tips a person approved.
- Search is **by meaning only**, inside machine (and document-type) filters. No keyword search (a keyword mix was
  only an offline experiment).
- **Docs/Ask mode:** top K = 12 (`app.py` ASK_TOP_K); a match must score at least **0.30** with a machine selected
  (0.35 without). If nothing is strong enough, it answers "no information" **before** the AI writes anything.
- **Investigations:** each specialist searches its own document type, 4 pieces per search. Since 6 Oct the SOP,
  work-instruction and NCR searches fetch 15 and a **reranker** (`pinecone-rerank-v0`) keeps the best 4; if the
  reranker fails it falls back to meaning order and says so. The writer then gets the specialists' summaries
  **plus the graph facts from Neo4j**. After writing: safety checks (rating floor, ⚠ on unreviewed tips) and a
  confidence label; correctness is checked in testing, not by a live verifier.
- FL-101 documents = 40 pieces (SOP 23, WI 8, NCR 9).

**Decisions (keep):** words are **chunks** and **tags** throughout (Chunking teaches "chunk"); **fixed-size
chunking** (recursive splitter, ~1,000 characters, up to 200 overlap) — not "structure-aware"; no measurements on
the slides; the vector database is a **flat 2D meaning map** (a 3D cube distorts "nearest"); dots coloured by
topic only once their embedding exists; no topic circles (the database does not group, the numbers do); the AI is
a chip with input lines (tokens flow in along them); the **verifier is shown dashed** and described as "will
check" — PlantMind has no live verifier yet (task proposed: build one; make the box solid and the text present
tense when it exists); reranking is animated but the Retrieved intro only talks about top K (user's choice).

**Rejected:** a single crowded map with highlight frames; three long scenes; 3D cube; printed real vectors;
"structure-aware" label; a Play overlay; a reading pause based on word count (fixed 7 s instead); the old
"notes dropped Step 10" beat (belongs to the Evals page).

**Open (user chose not to do these yet):** Retrieved intro says "four closest" though reranking changes the
order; the question names no machine (FL-101 is implied); verifier box text is present tense; Searchable shows
12 chunks while the real WI has 8; on phones the act labels under the panel are tight.

## Design system (keep)

- Palette (CSS vars):
  - Light: `--bg #F5F2EA` warm ivory, `--surface #FBF9F4`, `--sunk #ECE8DE`, `--ink #252826`, `--muted #68706B`, `--faint #979B94`, `--line #D9D6CC`, `--pine #557A68` (sage, PlantMind signature), `--steel #6D8490` (evidence/sources), `--brass #C08A3E` (warning/validate), `--rust #B85C50` (critical/don't), each with a `-soft` tint
  - Dark mode: same roles, matching values. A Theme toggle is saved in localStorage.
- **Colour only where it means something.** Stage highlights: Question = charcoal, Scope = sage, Context/Evidence = blue-grey, Validate = amber, Answer = charcoal.
- Fonts: Fraunces (headings), IBM Plex Sans (body), IBM Plex Mono (labels). Thin borders (1px).
- Must work at phone width (no sideways page scroll; the diagram scrolls inside its panel) and respect reduced motion.

## Scene engine (in preview.html) and how to change it

- Helpers: `A(o)` builds data attributes: `f` (step it appears), `h` (step it hides), `c` ({step: class}), `tf` ({step: transform}), `d` (delay in seconds within the step), `flow` (a moving marker along a path). Also `G, R, T, txt, node, edge, bubble, svg`.
- Captions: `[act, text, durationMs]`. Lessons are entries in `L` with `name, lesson, plain, acts, scene, caps, below`, and optionally `model` and `kick:''`.
- Classes: `.ping` (a one-off pulse ring, `.loop` = 3 pulses), `.sink` (fades a chip after it appears), `.hl` (highlighter sweep, width set from the real text), `.store` / `.wire` / `.wire-amber` line styles, `.grow` (scaleX bars).
- **Verification method that works:** inject CSS that disables transitions and animations, then measure the **effective (multiplied) opacity** of each text element at each step, and check for bounding-box overlaps. Checking class names alone missed a real bug once: an inline `opacity` overrode the hidden state. Use `fill-opacity` for fades, never inline `opacity` on animated elements.
- The browser pane is narrow. Use `resize_window` 1100×800 for checks, and reset to desktop afterwards. Local files always render light, so test dark mode with the Theme button.

---

## Decisions made (and rejected ideas, so they aren't proposed again)

- One example machine: **FL-101 bottle filler** (Demo Bottling Plant, Filling Line 1). The welder WM-101 appears only as "the welder / other machine". **No "second machine" story.**
- "How it works" replaced the earlier "RAG in 60 seconds" opener. The **Scope lesson page was replaced by Architecture.**
- **Rejected:**
  - Spotlight/dimming of inactive parts on Architecture (the user preferred everything visible)
  - Stat-tile heroes and card grids (looked like AI slop)
  - A "Mental model" strip under How it works
  - "Validated" (overclaims; use "Checks passed")
  - Invented rule IDs (VAL-03, SOP-17…)
  - "Prevents hallucinations" claims
  - A fork-in-the-road Context design
  - Invented operator dialogue
  - Sage green for every live path
  - The closing 7th step on How it works
- Lesson template for lesson pages: **failure → insight (why the obvious fix fails) → intervention → experiment → result → remaining failure**, plus an evidence card linking to files and one "what surprised us" line. Keep it uncrowded.

## Verified against code (Architecture)

- ✓ The machine finder tries the UI picker → a tag in the text → the plain-words resolver (Supabase `equipment`).
- ✓ Fault matching lives **inside** `get_fault_chain` → `match_faults` (meaning + word count + 20B AI tie-break).
- ✓ The router (`supervisor_route`, 20B) must include the graph's required searches.
- ✓ Specialists run with `ThreadPoolExecutor(max_workers=2)`.
- ✓ The writer is GPT-OSS 120B. ✓ `check_report` **raises the rating to the safety floor and adds a ⚠ for unreviewed tips** (it doesn't block).
- ✓ MQTT alarms → `live_events`; an alert after **3 alarms in 7 days**; the Investigate button pre-fills the chat.
- ✓ Voice: Whisper large-v3 → 120B structuring → Supabase `expert_fixes` → Pinecone straight away → grouped at 0.75 similarity → a person approves → Neo4j Pattern.
- Simplified on purpose: the report is saved by the browser (`/api/history`); `llm_logs`, reflection (off by default) and the Neo4j local backup aren't drawn.
- 🐞 **Real app gap found:** `/investigate` with no identifiable machine still runs and searches **all machines' documents** (`/ask` refuses; `/investigate` doesn't). A separate task was created: "Fail closed when an investigation has no machine". It's a great real example for the **Rules** lesson.

## Real numbers available (all from files)

- Graph OFF vs ON, FL-101: required facts **41/96 (42%) → 88/96 (91%)**; made-up specifics 0.3 per report both ways; consistency 26/32 → 28/32 (`fl101_scorecard.md`).
- Fault matching exam (7 fresh questions): **4/7 → 7/7**, false CRITICAL **1 → 0**; tuning set 14/26 → 33/33 (tuned, so label it); AI tie-break needed on ~40% of everyday wording.
- Welding word leak: **1 of 30** FL-101 reports, from the report **template** ("burn-in if required"), fixed in commit `ed6e5c1`, re-run pending.
- Welder-era numbers: 41→70→90→95%, tip used as a step 14/18 → 1/18, routing 1/6 → 6/6, retrieval 18/18 top 12 / 14/18 top 3. **Note:** made-up specifics were 0.2 in the baseline/handover scorecards and **0.3** in the trust scorecard. Real tip wording: "Reset tension from 18 to 22".
- FL-101 docs split into 40 pieces with the app's rule (SOP 23, WI 8, NCR 9).

## Pending / next

**Status 17 Oct:** Trust is DONE and merged (see "Page 4 Trust"). Next is **Tracing** (see "NEXT: Page 5 Tracing").
Scratch pages were moved out of `docs/` (they live in the chat's scratch folder); `docs/kg_compare.html` was
already committed, so git shows it as deleted — that's intended. `docs/` now holds only `draft.html`,
`index.html`, `preview.html`. Before publishing: save the calibration check into `evals/` (block 4 number) and
add the two Trust screenshots.


1. **Architecture:** the user was still reviewing the latest right-angled version. Get feedback first.
2. **Evals (page 2) is DONE.** **Context and Rules lessons were DROPPED (2 Oct, user's call):** "How it works" already covers them. A Context page (handover-folder look) was built and removed. The side menu is now: How it works · 1 Architecture · 2 Evals · 3 Knowledge graph · 4 Trust · 5 Tracing · 6 People in the loop. **Knowledge graph (page 3): built 6 Oct** (`sGraph`, 6 steps, animated; idea "The answer wasn't missing. The connections were."). Left column = operator + PlantMind's answer (fixed); right column = the action. Steps: 0 third alarm (real 10 Sept shift-log lines; 1st/2nd amber, 3rd red) → 1 WHAT SEMANTIC SEARCH FOUND: real snippets with match 0.87 (shift log, WI) ✓ found; SOP + NCR ✗ never searched, showing the sentences that never reached the answer → 2 the missing facts in the plant's documents, dashed lines to the gaps: ✕ no link → 3 experienced operator's notepad, 1:1 with the graph notes, colour per role (symptom steel, root cause brass, action/check pine, never rust; legend top-right) → 4 the graph in the same colours, real notes/links/source badges → 5 threads fill the answer gaps with sources ("All 5 lines, each with a source"); closing "The graph didn't give PlantMind more documents. It gave it the connections between them." No 48%/2-of-5 numbers on this page (user's call). Rejected along the way: constellation, investigation board, metro map, single-view variants, a 'graph isn't magic' jam step (good opener for Trust), a router-failure + ranking-failure framing (user didn't like it), and a made-up "cosine 0.32" badge. Scratch file docs/kg_compare.html is NOT part of the site — delete before committing. What worked for Evals: design new, simple test data together first, have the main chat run it, then build the page from the results. Give each page its own look; don't reuse the Evals left-list/right-panel structure (the user noticed it straight away on Context).
3. **Tests the main chat should run** (see `CASE_STUDY_TESTS.md`):
   - (a) FL-101 retrieval: add the 13 labels from ANSWER_KEY §5 to `retrieval_labels.json` and run `evals/retrieval_eval.py` (free)
   - (b) machine-from-plain-words + refusal checks (free; needs a tiny script)
   - (c) re-run the leak check after the template fix + a welder regression (paid)
   - Also: FL-06 trust test (needs operator tips), one LangSmith trace export (for Tracing), the promptfoo 4/4 baseline
4. Open decision for the Trust lesson: FL-101 only has an "after" number unless trust labels can be switched off. Either show the welder's 14→1 as "an earlier test machine", or leave out the "before".
5. Later: replace `docs/index.html` with the finished page, add real screenshots, publish (private Artifact preview first; GitHub Pages when the user decides).

## Memory
A memory note `case-study-page-preferences` holds the design preferences and rejected ideas.
