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

### Side note: one empty answer
One Docs answer came back blank the first time and correct on retry. No AI call was logged, so it failed before the model was reached. Watching it; investigate if it repeats.

---

## Scorecard: first investigation spot check (graph OFF, before fixes)

| Test | Given | Expected | Result |
|---|---|---|---|
| Glass breakage | HIGH | CRITICAL | ❌ |
| Overfill 2 min after seal change | HIGH, "seals fitted wrong" | LOW/MEDIUM, "expected, don't touch" | ❌ |
| 3 jams after 330 ml changeover | HIGH, cause hedged | HIGH, rails left at 500 ml position | 🟡 |

After fixes 1 to 3: _to be run_. After the FL-101 graph: _to be run_.
