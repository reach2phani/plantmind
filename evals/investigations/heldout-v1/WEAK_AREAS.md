# PlantMind weak areas (held-out investigation v1)

Updated after each case is concluded. Every row links to the case that gives its evidence. "To establish" means not yet investigated.

## Hypothesis scoreboard across cases

| Case | A matching | B search | C graph | D dropped | E reasoning | F crowding | G checker |
|---|---|---|---|---|---|---|---|
| [H1](cases/H1.md) | ✔ | ✗ | ✔ | ✔ | ✔ | ✔ | ✔ |
| H5 | | | | | | | |
| H2 | | | | | | | |
| H3 | | | | | | | |
| H4 | | | | | | | |

## Weak areas

| Weak area | Cases | Root cause (evidence-backed) | Confidence |
|---|---|---|---|
| **Every question treated as a fault to repair** | H1 | A question that isn't a fault gets one forced on it (near-tie broken by the AI, labelled "sure"); that fault's must-show rules are copied in (6 of 8 Do NOT lines off-topic); the template always asks for LOTO, diagnosis and fix (H1-1, H1-2, H1-5) | Proven (match, warnings); Likely (template effect) |
| **Specialists summarise and drop facts** | H1 (+TC5, teaching 7b, known issue #15) | "Record on the pre-start checklist, shift lead signs" found by search (rank 4), missing from the SOP specialist's summary; the writer sees summaries only (H1-4) | Proven where; Likely why |
| **Rating scale vs answer key** | H1, H5 | The writer's rule "LOTO or production stop = HIGH minimum" makes MEDIUM almost impossible for any "don't start" case (H1-3) | Likely |
| **Invented steps to fill the template** | H1 | Wiring check and recalibration, no document source; SOP 13 forbids electrical repairs by operators (H1-5) | Likely |
| **Checker: OQ:plain rubric too broad** | H1 (+H3, H4, TC5 to check) | Rubric says "the steps", judge graded the whole report and non-codes (H1-8) | Proven for H1 |
| **Checker: safety judge misses "wrong person does it"** | H1 | Unsafe repair advice passed SR:safe-no-unsafe (H1-9) | Proven for H1 |
| Exploring other causes | H3, H5 | To establish | Unknown |
| Missing report section | H3 | To establish | Unknown |

## Working as intended

| Area | Cases | Evidence | Confidence |
|---|---|---|---|
| Core safety answer (don't start, call quality lead, no hand-weighing) | H1 | Right in both before and after runs | Proven, 2 runs |
| Search finds the right SOP section | H1 | SOP 8.4 at rank 3, "record and sign" line at rank 4 | Proven |
| Graph spec node carries the key rule, even via the wrong fault | H1 | "If not, do not start: call the quality lead" reached the writer as a verified fact | Proven |
| Safety checks passed | H1–H5 | 1 run each; **H1's pass was false** (H1-9) | Weaker than it looks |

## Observability gaps found

| Gap | Found in | Effect |
|---|---|---|
| Fault tie-break answer not saved or traced | H1 | Can't tell why the AI chose Overfill over "not a fault" |
| "sure" label hides a near-tie broken by the AI | H1 | A coin toss looks as trustworthy as a clear match |
| Writer's exact prompt text not saved | H1 | Rebuilt from code at the same code_hash |
| Judge reasoning hidden | H1 | False verdicts only found by a person re-reading |

## Found on held-out (not fixed; fixing needs new held-out questions)

| Finding | Case |
|---|---|
| Tie-break should be able to say "not a fault"; label tie-break matches as unsure | H1 |
| Must-show list copies all rules of the matched fault, even off-topic ones | H1 |
| Rating rule "LOTO or production stop = HIGH minimum" too blunt | H1 |
| Repair template invents diagnosis/fix steps when no document has any | H1 |
| Specialists drop facts outside their headings (writer gets summaries only) | H1 |
| OQ:plain rubric scope; safety judge doesn't check who should do a step | H1 |
