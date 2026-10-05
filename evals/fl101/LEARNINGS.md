# What a second machine taught us (FL-101 generalisation test)

PlantMind was built and tuned on one machine: WM-101, a welder.
To check it really works for *any* machine, we added a completely different one:
FL-101, a bottle filler in a bottling plant. **No code changes were allowed for FL-101.**
Anything that only worked for WM-101 had to be fixed for every machine.

This log records what broke, why, and what we did about it. Newest last.
Numbers are filled in as the before/after runs happen.

---

## First spot check (29 Sep 2026): documents uploaded, no FL-101 fault graph yet

What worked straight away:
- FL-101 was recognised automatically and searches stayed on FL-101's documents only.
- **No welding knowledge leaked** into a bottling report (no wire, torch, burn-in or tension).
- Simple look-ups worked ("fill range: 495 to 505 ml").
- It refused honestly when the answer was not in the documents (motor temperature).

What broke:

### 1. Shift mode assumed every question was about 2025
- **Symptom:** "underfill alarms on the night of 10 September" came back as "no events on 2025-09-10". The logs are from 2026.
- **Cause:** when no year was typed, the code filled in **2025**, because every WM-101 log happened to be from 2025. A hidden assumption.
- **Fix (generic):** the year is taken from the logs themselves by an exact lookup of the date labels. If several years have that day, it shows the most recent one and **tells the operator** the other years exist. If none do, it says so. A typed year always wins.
- **Lesson:** test data from a single year hides date bugs. *Code for anything exact; never guess silently.*

- **Result after the fix:** the same question now returns the 3 alarms (01:30, 03:20, 04:45), the refused fill-time change and the production stop, all from the 10 Sept night log only.
- **The fix also exposed a mistake in our own answer key:** it expected the valve numbers (3, 9, 15, 21), but that seal change is in the **next morning's** log (11 Sept). The system was right to leave it out. The answer key was corrected. **Lesson: answer keys need checking too. A test can be wrong.**

### 2. The criticality rules were written for welding
- **Symptom:** glass breakage in the filler was rated HIGH. The FL-101 SOP itself says **CRITICAL** (glass can end up in bottles).
- **Cause:** the CRITICAL rule listed only "electrical, fire, fumes", which are welding hazards. No rule said "trust the document's own rating".
- **Fix (generic):** CRITICAL now also covers injury and foreign material (glass, metal) that could reach the product. New rule: *if a document states a criticality, never rate below it.*
- **Lesson:** rules written while looking at one machine quietly encode that machine's world.

### 3. An almost-empty graph was presented as "verified"
- **Symptom:** the report said "Knowledge graph (verified) confirms SOP steps", but FL-101 has no fault graph yet.
- **Cause:** adding FL-101 in Plant Setup creates one node (the machine itself). The code treated "at least 1 node" as "graph available", so the AI got a graph section with nothing in it and filled the gap with a claim.
- **Fix (generic):** the graph only counts as available when it holds real knowledge (a fault, procedure, pattern and so on), not just the machine's own node.
- **Lesson:** an empty context section invites the model to invent. Only show a section when it has content.

### 4. The most important step sat just past a cut in the document (not fixed yet, Phase 3)
- **Symptom:** "What must be done after replacing a fill valve seal?" answered "count tools, refill the bowl" and missed the **mandatory 10-minute rinse and weighing 20 bottles**. In an investigation, normal overfill after a seal change was called a fault and rated HIGH, because the note "this is expected, don't change settings" was also missed.
- **Cause:** documents are cut into pieces of about 1,000 characters. The procedure was split, and the piece with steps 9 and 10 and the "expected behaviour" note was not among the 12 pieces the search returned.
- **This is the same failure as WM-101's burn-in** (known eval case INV-004). A second machine proves it's a general weakness, not a one-off.
- **Plan:** Phase 3, cutting documents by section instead of every 1,000 characters, and adding keyword search. The FL-101 fault graph should also carry these facts. Measure both.

### 5. Without a graph, the right documents were not always searched (expected; the graph fixes it)
- **Symptom:** for the jams after the 330 ml changeover, the SOP (which has the changeover steps) was not searched. The report guessed "guide plates" but hedged, and said "no history", although the 7 Sept shift log records the exact same problem.
- **Cause:** without a fault graph, only the AI supervisor picks the searches, based on wording.
- **Plan:** build the FL-101 graph. On WM-101 the graph-required searches took routing from 1/6 to 6/6.

### 6. Loading a machine's graph would have erased its place on the plant map (fixed before it happened)
- **Found by reading the loader before using it**, not by a failure. The loader first deletes every note tagged with the machine, then writes the new ones. That included the machine's own node, and with it the links "FL-101 is a Filler" and "is located at Filling Line 1" created in Plant Setup. A read-only check confirmed the old code would have deleted that node.
- Two more one-machine assumptions sat in the same place: on startup the app only looked for `wm101_graph.json`, and it treated "has any node" as "graph already loaded". A machine added in Plant Setup already has one node, so its graph would never have loaded.
- Also found: notes are matched by id alone, so two machines both using an id like `loto_procedure` would have merged into one note.
- **Fixes (generic):** the machine's node is updated in place, never deleted. The loader refuses a file whose ids belong to another machine. Links only join notes of the same machine. Startup loads every `<tag>_graph.json` for any machine with no knowledge yet.
- **Lesson:** read the code path before the first run on new data. The cheapest bug is the one that never runs.

### 8. Everyday words confuse the fault matching (FIXED: Phase 2a step A, 30 Sep 2026)

**Result** (evals/fault_match/*_scorecard.md; free check, no report writing):

| Matcher | Right | Unsure (flagged) | Wrong | False CRITICAL |
|---|---|---|---|---|
| Before: word counting, 26 tuning questions | 14/26 | 5/26 | 7/26 | 0 |
| After: meaning + AI tie-break, all 33 questions | **33/33** | 0 | **0** | **0** |
| **Exam** (7 fresh questions written by the user after tuning, never tuned on): word counting | 4/7 | 1/7 | 2/7 | **1** |
| **Exam**: meaning + AI tie-break | **7/7** | 0 | **0** | **0** |

- On the exam, the old matcher read "another low-fill alarm… reject table's starting to pile up" as **Glass Breakage**. That's a false CRITICAL, which would have pushed an underfill report to CRITICAL.
- The new matcher got all 7 right, including words found nowhere in the documents ("stack height", "turret", "worm screw", "HMI"). Meaning settled 4; the AI tie-breaker settled the 3 close calls.
- WM-101 everyday wording: 4/8 → 8/8. WM-101 alarm wording stayed 6/6.
- **How it works:** each fault gets a short description card. The card and the question are turned into meaning vectors (the same embedding model as document search), and the closest fault wins if it's clearly closest (gap ≥ 0.03). A close call gets a word-count second opinion, then one short AI multiple-choice question. Still unsure → the close candidates go to the report marked "fault not confirmed", and the safety floor is **not** applied from a guess.
- **Tuning found a data gap:** the Underfill card lacked "checkweigher rejects", because that fact was stored as `alarm_trigger`, which the card didn't read. The fix was generic: cards read every "how it shows up" field.
- **Honesty:** the 26 tuning questions were used to set the threshold, so the exam is the real number.
- **Cost trade-off:** across the 33 questions, meaning alone decided 19, meaning plus word count 1, and the AI tie-breaker 13. Alarm-style wording rarely needs the AI (WM-101 alarm set: 0/6); everyday wording needs it about 40% of the time, at one extra small call (a few hundred tokens, about a second). Richer fault cards with real operator words would move more decisions to the free path.

The original finding:
- **Found by a free check (no AI calls):** the 6 FL-101 test questions were reworded the way an operator talks ("the checkweigher keeps kicking out short bottles", "bottles keep falling over since we swapped to the 330s"). The graph then picked exactly the right fault for only **1 of 6**.
  - Four picked two faults at once (a tie).
  - One picked the wrong fault: "someone says bump the fill time up" matched **Overfill** instead of Underfill, because "fill time" is a word on the overfill path.
- **Why it matters:** with a tie, the AI gets both faults' facts. Worse, "pressure dropped to 1.2 bar" tied with Glass Breakage. Glass is CRITICAL, so the safety floor would push a pressure drop to CRITICAL.
- **Cause:** the matcher counts shared words (label, alarm text, cause names). Operators don't use alarm words.
- **A second, independently written set of wordings** (from the user) scored **3/6**. Its sharpest miss: "getting underfill alarms again for the third time tonight and checkweigher is rejecting them" matched **Overfill**, although the word *underfill* is in the question. The overfill notes share more small words ("checkweigher", "reject", "fill", "time").
- **Plan (Phase 2a A, already planned):** match by meaning (embeddings plus a threshold), keywords as backup, and ask the AI only when unsure. **Before: 1/6 and 3/6 exact matches** on two sets of everyday wording. Test on both machines.
- **Lesson:** test with the words users actually use. Alarm-style test questions hid this on WM-101.

### 9. The graph value test on the second machine (30 Sep 2026): it generalises
Source: evals/graph_value/fl101_scorecard.md. Five cases × 3 runs per arm, everyday wording, fault matching by meaning in place. FL-06 waits for the operator tips.

| Machine | Required facts, graph OFF | Graph ON |
|---|---|---|
| WM-101 welder (built on) | 41% | 95% |
| **FL-101 bottle filler (new industry, no special code)** | **41/96 (42%)** | **88/96 (91%)** |

- Made-up specifics: 0.3 per report in both arms. Consistency across runs: 26/32 → 28/32. Unreviewed tip used as an instruction: 0/15.
- Glass breakage was rated CRITICAL in both arms, but only the graph brought the actual steps: emergency stop, hold 30 minutes of bottles, vacuum only, quality lead sign-off (0/3 → 3/3 each).
- Overfill after a seal change: "expected, don't touch the settings" went from 0/3 → 3/3.

**Misses with the graph ON, and what was done:**
1. **A welding word in a bottling report**: "Step 4: Verify: post-fix checks, burn-in if required". It came from the **report template**, a welder leftover that every report copies. **Fixed:** the line now reads "…and any run-in or first-product check the procedure requires" (WM-101 still gets burn-in from its graph). To be confirmed by the WM-101 regression run.
2. **The 10-minute rinse is missing in the overfill case (0/3):** the FL-101 graph's overfill path leads to the first-bottle check but not to the rinse before it. Small graph data fix, **deferred**.
3. **One invented number:** "set an alarm if pressure drops below 1.4 bar" (SOP: 1.3) in the preventive ideas, not the repair steps. **Noted.**
4. Position B 2/3 and restart speed 1/3 in the jam case: the report sometimes skips details it was handed. Orchestrator habit, **Phase 2b**.

### 10. The evals teaching set: one simple question, all 7 steps (1–2 Oct 2026)
Plan: evals/fl101/TEACHING_SET.md. Results: evals/fl101/results/teaching_*. Question: "Bottles aren't full enough. What should I check?", asked three ways (plain, rushed, typos), with a 5-line answer key.

| Step | Result | File |
|---|---|---|
| 1 Define good | Key checked word for word against the documents: 5/5 lines right, 1 wrong section number fixed | TEACHING_SET.md |
| 2 Real questions (graph ON) | T-1 25/25, T-2 15/15, T-3 15/15 lines | teaching_scorecard.md |
| 3 Judge vs person | **29/30 marks agree**; 1 borderline disagreement (A3, L1) | teaching_step3_agreement.md |
| 4 Test the tests | 15/15 whole-answer marks and 7/7 variants as expected; 1 weak spot written down; a lazy word-check failed 2 of 3 correct answers | teaching_step4_selftest.md |
| 5 Repeatability (T-1 × 5, graph ON) | 5/5 lines in 5/5 runs; rating HIGH 5/5; confidence HIGH 5/5 | teaching_runs.jsonl, teaching_scorecard.md |
| 6 Graph OFF vs ON | **22/45 (48%) → 55/55 (100%)**; identical across runs 12/15 → 15/15; made-up specifics 0.0 both | teaching_scorecard.md |
| 7a Each part alone | Machine finder 1/3 → 3/3 after the fix; fault Underfill 3/3; "20 bottles" shown to the specialist 0/4 → 4/4 after the fix | teaching_step7a_components(_before).md |
| 7b Trace a missing line | Found by search → handed over whole → **dropped by the specialist's summary** | below |

**Per line, graph OFF (9 runs):** L1 drips 4/9 · L2 495–505 ml 0/9 · L3 stop and make safe 9/9 · L4 weigh 20 bottles 0/9 · L5 don't touch the fill time 9/9.

**Step 7b, the trace (T-1, graph OFF):** 1) in the documents? Yes (WI Step 10: "weigh the first 20 bottles. All 20 must be between 495 and 505 ml"). 2) Found by search? **Yes**: the maintenance search returned that passage, whole. 3) Passed on by the specialist? **No.** The maintenance specialist is asked for maintenance *history*; the passage is a *procedure*, so it wrote "no maintenance records found, Data confidence: NO DATA" and dropped it. 4) Used by the writer? Never received. **Broken part: the specialist summary.** The same summary hid L2. Without the graph, the SOP (where L1 and L2 also live) was never searched in any of the 9 runs: the AI router picked Alarm, Expert Fix and Maintenance every time.

**Why the graph fixed it:** the graph hands the facts straight to the writer, skipping the summary step, and its routing rule makes the SOP search required.

**App issues found, noted (not fixed inside the test task):**
- Specialists summarise, and a summary can drop the exact fact needed. That's evidence for Phase 2b "specialists fetch, they don't summarise".
- The maintenance specialist's question (history) misses procedures in the work instruction.
- "Dripping means a worn seal" ranks 7th and 10th for T-1 and T-3; only the top 4 are used. Ranking → Phase 3 (search wide, then rerank).
- The fault matcher needed the AI tie-breaker for all 3 short wordings (Underfill vs Overfill): correct, at one extra small call each.

**Fixed because of this test:** the machine finder (plurals/typos; never search every machine) and whole search pieces instead of the first 300 characters.

**Honest limits:** 3 wordings × 3–5 runs, 5 lines: a direction, not proof. The graph was built from the same documents as the key; the graph-OFF version could search those documents too, so the comparison is fair, but it measures delivery of known facts, not new knowledge. One person marked the judge. The L1 judge question has a grey zone ("inspect the seals" vs "check for drips"): next time, sharpen it rather than re-score.

### 11. Context chapter C1: where did each missed fact get lost? (2 Oct 2026)
Source: evals/context/attribution.md (made by evals/context_attribution.py; no AI calls). Hand decisions: evals/context/hand_review.json.

Every required fact a saved report missed was followed along the relay race (documents → search → specialist → writer → report) and counted at the **first** hand-off where it went missing. Runs: the teaching set (20), the FL-101 graph value test (30) and the WM-101 trust run (18).

| Where it got lost | Graph OFF | Graph ON | All |
|---|---|---|---|
| Not in the documents | 0 | 0 | 0 |
| Not searched (the router skipped the right search) | 3 | 0 | 3 |
| Searched, not found (not in the top 4 pieces) | 24 | 0 | 24 |
| Found but cut (piece cut at 300 characters; fixed 1 Oct) | 24 | 0 | 24 |
| Found, summarised away by the specialist | 21 | 0 | 21 |
| Reached the writer, left out | 2 | 10 | 12 |
| **Really lost** | **74** | **10** | **84** |
| Not lost: the check was wrong (read by hand) | 1 | 1 | 2 |

84 facts were really lost, out of 278 required-fact checks.

> **Corrected 5 Oct.** The first version of this table said 77% were found and then lost (30 cut, 27 summarised, 12 not found). Reading the C2 runs by hand showed that the pattern for "weigh the first 20 bottles" also matched past shift-log lines ("First 20 bottles 499-502 ml"). Those are a reading, not the instruction. With the pattern limited to the instruction, 12 more facts turn out to have been **never found by search**. The table above is the corrected one. Lesson: a word check can be fooled by the same words used for a different purpose. Read the matches, not just the counts.

- **Without the graph, most lost facts were found and then lost on the way.** 45 of the 74 lost facts (61%) were found by search and lost before the writer: 24 cut off, 21 dropped by a specialist's summary. 27 were never found or never searched. None was missing from the documents.
- **After the 1 Oct fix (whole pieces), two leaks remain about equal.** In the teaching set, which ran after the fix: 12 of 23 losses were never found (search ranking), 9 were summarised away, 2 were left out by the writer, and 0 were cut.
- **With the graph, everything reached the writer.** All 10 remaining losses are the writer leaving out a detail it was given: the 10-minute rinse (4), position B and restart speed (3), the 10–15 mm stickout (2), "stop welding" (1).
- Two examples: FL-04 glass breakage (graph OFF) — the SOP search found section 12.3, but the specialist saw only its first 300 characters, so "Step 1: emergency stop" was cut off and it wrote "stop the line immediately". FL-03 jams (graph OFF) — the 7 Sept shift log said "rails still in position A… should be position B for 330 ml"; the alarm specialist was handed that line and left it out. That is likely also why the report said "first recorded instance" (finding 7).
- **The checks were wrong twice out of 86** (read by hand): the judge marked "Apply LOTO, stop the line" as a NO, and the word check didn't accept "tighten by hand then a quarter-turn".

**Lesson:** finding a fact is not the same as delivering it. With no graph, 6 in 10 lost facts were found and then dropped by the app's own hand-offs. **Next, C2:** let specialists pass on what they found, not only their summary, and measure on the graph-OFF arm.

**Honest limits:** runs before 1 Oct saved only what the writer received. What each specialist received was re-created by repeating the same search today with the old 300-character cut. That's not a recording from the day, but repeating the teaching set's searches gave the same pieces as on the day in 82/82 searches. Facts are found by short word patterns: every "reached the writer" and "marked missed" row was read by hand (rows changed are listed in hand_review.json), and one pattern was corrected (see above). Older WM-101 graph-OFF runs were not included, because they're from before the hand-over fix.

**Picture idea:** a leaky pipe from "documents" to "report", with the count of facts dripping out at each joint. Graph OFF leaks mostly at the specialist joint. Graph ON leaks only at the last joint.

### 12. Context chapter C2: give the writer the pieces, not only the summaries (3–5 Oct 2026)
Sources: evals/fl101/results/teaching_c2_before_scorecard.md, teaching_c2_after_scorecard.md, evals/context/attribution.md, tokens from llm_logs (the app's own call log).

**The change:** a switch (`PM_WRITER_GETS_EVIDENCE`, off by default). When it's on, the report writer gets the specialists' summaries **plus the document pieces they read**: strongest match first, each piece whole, operator tips left out, at most 6,000 characters. Tested on the teaching set, graph OFF, 3 wordings × 3 runs. Before ran on 2 Oct and after on 3 Oct, with the same code except the switch.

| Graph OFF, 9 reports each | Before (summaries only) | After (+ pieces) |
|---|---|---|
| Required facts in the report | 23/45 (51%) | **26/45 (57%)** |
| L1 check the valves for drips | 3/9 | **7/9** |
| L2 a good bottle is 495–505 ml | 1/9 | 0/9 |
| L4 weigh the first 20 bottles | 1/9 | 1/9 |
| L3 make safe / L5 don't touch the fill time | 9/9 · 9/9 | 9/9 · 9/9 |
| Made-up specifics per report | 0.1 | **0.0** |
| Checks identical across runs | 11/15 | 13/15 |
| Lost to "summarised away" | 7 | **0** |
| Tokens per investigation (all calls) | 8,164 | 9,869 (**+21%**) |

**What the after runs show (C1 run again on them):**
- **The summary leak is closed.** 0 facts were summarised away (7 before). Most of the gain is L1: the shift log's "valves 9 and 15 dripping" and the work instruction's "drip between fills" now reach the writer.
- **But the cap dropped the piece we needed most (5 losses).** For T-1, the search did find the work-instruction piece with "weigh the first 20 bottles; all must be 495–505 ml". The evidence is sorted by match score, and shift logs score higher than procedures. So that piece was the one of 8 that didn't fit under 6,000 characters. That's why L2 and L4 didn't improve.
- **Search ranking is now the biggest leak:** 12 of 19 losses. For the rushed and messy wordings (T-2, T-3), the search never finds the procedure step at all. No hand-over change can fix that. Phase 3: search wide, then rerank.
- **With the graph ON there is no room.** A graph-ON writer request is already ~7,400 of the ~7,600 tokens allowed per minute. The first try with the pieces added was rejected by Groq ("413 request too large"; waiting never helps), and the same error had already happened once on 2 Oct without the change. Fix: the pieces only fill the **spare** room under the per-minute limit. Graph ON now gets none, and its request is unchanged (1 check run: 5/5 facts).

**Lesson:** delivering more context helps only if the **right** context makes the cut. Fixing one leak (the summary) moved the loss to the next one (a cap that sorted by similarity, not by usefulness). Every hand-off needs to be measured, including the ones we add ourselves.

**Next (C2b, proposed):** order the pieces so procedures (SOP, work instruction, NCR) come before shift logs, then re-run T-1 × 3. Expected: L2 and L4 reach the writer for T-1.

**Honest limits:** 9 reports per arm, one question family, one machine. Before and after ran a day apart. +3 facts is a direction, not proof. The token numbers come from the app's own log, matched by time.

### 13. Knowledge graph chapter: first free checks (5 Oct 2026)
Sources: evals/graph_health/graph_health_FL-101_2026-10-05_0839.json, evals/graph_chapter/graph_facts_teaching.md (made by evals/graph_facts_table.py; no AI calls).

- **Graph health, FL-101: 8/8 rules pass.** But the database is one link behind the file: "first-bottle check REQUIRES sanitation rinse" (added to fl101_graph.json on 2 Oct) is not loaded yet. Reload before any new FL-101 graph-ON run.
- **Which facts appear only with the graph?** (teaching set: 18 reports graph OFF, 11 graph ON)

| Fact | Graph OFF | Graph ON | Where the graph-ON writer got it |
|---|---|---|---|
| L1 check the valves for drips | 7/18 | 11/11 | graph and specialists 10, graph only 1 |
| L2 a good bottle is 495–505 ml | 1/18 | 11/11 | graph and specialists 11 |
| L4 weigh the first 20 bottles | 1/18 | 11/11 | graph and specialists 11 |
| L3 make it safe first | 18/18 | 11/11 | (no difference) |

- **No fact is "graph only" here, and that's the finding.** With the graph ON, two things change at once: the graph hands its facts to the writer, **and** it forces the SOP and NCR searches (graph OFF: never run). The SOP specialist then also carries 495–505 ml and the 20 bottles (11/11). From this data we can't tell which of the two did the work.
- This refines finding 10 ("the graph hands the facts straight to the writer"). It does that, but the same facts also arrive by the search the graph forced.
- **Next:** the separation run (graph facts on, forced searches off) splits the two effects. It's now the key run of this chapter.

**Bug found by looking at the page, not by an eval (5 Oct):** the Graph Explorer showed FL-101 as empty (0 notes), and the fault-chain diagram under FL-101 reports was missing too. Cause: Plant Setup stamps a new machine's note with a Neo4j date (`created_at`). Python can't turn that date into JSON for the page, so both endpoints failed, and their fallback returned an **empty graph instead of an error**. WM-101 was older and had no date, so it never showed up there.
- Fixed generically: dates become plain text when graph data leaves Neo4j (`_plain()` in knowledge_graph.py). The endpoints now return the error, and the page shows it instead of "0 nodes".
- Also fixed: the "has graph ✓" list counted every machine's own note, so 10 machines got a ✓ and only 2 have knowledge. Same mistake as finding 3.
- **Reports were not affected:** the writer gets the graph as plain text. Checked against the old code: identical text for FL-101 (20,747 characters) and WM-101 (13,999). No eval needs re-running.
- **Lessons:** an error dressed up as "empty" is the hardest failure to notice. And evals only test what they look at: every eval read the report, none opened the page. Looking at the product yourself still matters.

### Side note: one empty answer
One Docs answer came back blank the first time and correct on retry. No AI call was logged, so it failed before the model was reached. Watching it; investigate if it repeats.

---

## Scorecard: first investigation spot check (graph OFF, before fixes)

| Test | Given | Expected | Result |
|---|---|---|---|
| Glass breakage | HIGH | CRITICAL | ❌ |
| Overfill 2 min after seal change | HIGH, "seals fitted wrong" | LOW/MEDIUM, "expected, don't touch" | ❌ |
| 3 jams after 330 ml changeover | HIGH, cause hedged | HIGH, rails left at 500 ml position | 🟡 |

After fixes 1 to 3, graph still OFF: _not run separately; the graph was loaded first. Recover later with the graph-off switch in the graph value test._

## Spot check with the FL-101 graph loaded (30 Sep 2026, one run each)

| Test | Before (no graph) | With graph + fixes | Result |
|---|---|---|---|
| Glass breakage | HIGH | **CRITICAL**; all 7 SOP steps in order; LOTO before opening guards; QA HOLD 30 min; no compressed air; rinse; quality lead signs off | ✅ |
| Overfill 2 min after seal change | HIGH, "seals fitted wrong, re-seat them" | **MEDIUM, "expected settling, up to 510 ml for 2 to 3 min"**; do NOT change the fill time; first-bottle check; refit the valve only if still overfilling after 5 min | ✅ |
| 3 jams after 330 ml changeover | cause hedged, SOP not searched | **Rails left in the wrong position → move to position B**; LOTO first; SOP now required by the graph | ✅ |

Routing: the graph now makes the SOP search mandatory (it was skipped for the jam before).

Still wrong in these reports:
- **"First recorded instance"**: the jam and glass reports both said there was no history, while citing the very shift logs that record the same event (7 Sept jams, 17 Sept glass breakage). The report can't tell a past log entry from the current incident. This happens on both machines' reports, so it's a general issue (finding 7, below).
- Small invented details outside the documented steps: "inspect the first 100 bottles", "torque check of star wheel fasteners", "guide-rail sensor warning". They appear in preventive or verify steps, not in the documented procedure.
- The glass report says "Safety risk: HIGH" inside a CRITICAL report.
- The overfill report didn't mention the 10-minute sanitation rinse (step 9, which comes before the first-bottle check).

**Caveat:** one run per case, scored by eye. The real number comes from the graph value test (3 runs, code checks plus judge) once the FL-101 cases are added.

### 7. "First time ever", while citing the earlier event (open)
- **Symptom:** "This is the first recorded infeed jam after a changeover", with the 7 Sept shift log (3 jams, same cause) listed in the sources.
- **Likely cause:** the history comparison doesn't separate "past events in the logs" from "the incident being reported now", and a similar past event gets read as the current one.
- **Plan:** investigate with the trace (LangSmith) before fixing. Candidate: hand the orchestrator past events as a dated list and ask "has this happened before?" explicitly.
