# Held-out investigation v1 (H1–H5)

## Why

The fixes raised TC1–TC5 a lot, but H1–H5 (questions never used while fixing) barely moved: 12 failed checks before the fixes, 11 after. This investigation finds out why, and maps PlantMind's weak areas from evidence.

**Objective.** For each failure, find out whether it comes from:

1. **missing knowledge**: not in the documents or the graph
2. **failing to retrieve it**: there, but not found
3. **failing to use it**: it reached the AI and was dropped or misread
4. **unreliable checking**: the checker or the answer key was wrong

**We understand, we don't fix.** H1–H5 stay a fair test only while nothing is tuned on them. Findings go on a "found on held-out" list. A later fix round needs new held-out questions.

**One question at a time.** Each case is finished end to end, with a conclusion, before the next one starts. Order: H1 → H5 → H2 (the passing control, compared with H5) → H3 → H4.

## Versions investigated

From the run records, saved in `snapshot/versions.json` on 2026-11-09.

| Item | Before run | After run |
|---|---|---|
| Run label | `heldout-before-1104` | `heldout-after-1108` |
| promptfoo result | `evals/results/heldout-before-1104.json` | `evals/results/heldout-after-1108.json` |
| git commit / code_hash | `ed17260` / `7211bcfb13` | `a3c9155+dirty` / `b8bb09c396`, the same code as the final-v1 runs (the "+dirty" was case-study page files only) |
| Models (fast / deep) | openai/gpt-oss-20b / openai/gpt-oss-120b | same |
| Judge | qwen/qwen3.8-27b | qwen/qwen3.8-27b |
| Eval config | `evals/promptfoo/eval_fl101_heldout.yaml` | same |

## The rules

1. **No stage is marked failed without evidence from that stage. No root cause is marked confirmed without evidence linking the mechanism to the observed failure.**
2. **✅ also needs evidence:** a quote, a rank, or a line number. A stage we didn't check is never shown as passed.
3. **No saved evidence means ⬜ "not observable"**, never passed or failed. Each ⬜ is listed as an observability gap.
4. **Rebuilt evidence is weaker.** For example, the graph text rebuilt from Neo4j today shows what the graph says now, not what the AI saw then. Mark it "reconstructed". A cause that rests only on reconstructed evidence is at most "Likely".
5. **Every stage note keeps three things apart:** evidence (what the data shows), observation (what that means for this fact), interpretation (what might explain it).
6. **"Unresolved" is an acceptable answer.** Say what would settle it.
7. **Say what works as well as what fails.**

### Stage marks

| Mark | Meaning |
|---|---|
| ✅ | present, with evidence |
| ❌ | lost or wrong here, with evidence |
| ⚠️ | doubtful or partly there |
| ⬜ | not observable: no saved evidence |
| — | not relevant at this stage |

### Confidence

| Level | What it requires |
|---|---|
| **Confirmed** | evidence on both sides of the break (present before, absent after) **and** the mechanism visible in the code or prompt |
| **Likely** | the evidence fits, but the mechanism is inferred or rests on reconstructed evidence |
| **Unresolved** | not enough evidence; say what would settle it |
| **Tested** | confirmed by a re-run with one thing changed (Phase 4, costs tokens, asked first) |

## The seven stages

PlantMind hands evidence over twice: search pieces go to the specialists, then the specialists' summaries go to the writer. So "what reached the AI" is split into 4a and 4b.

| # | Stage | Question | Where the evidence is |
|---|---|---|---|
| 1 | Documents | Is the fact in the FL-101 documents? | `demo_data/fl101/` (line numbers) |
| 2 | Search | Did search find it? At what rank? Was it in the top 4 handed on? | run record `pieces`; replay of the saved search questions |
| 3 | Graph | Which fault was matched? What did the graph add (chain, must-show warnings, severity floor)? | run record (`fault_matched`, `graph_warnings`); Neo4j snapshot (reconstructed) |
| 4a | Specialist | Did the specialist's summary keep it? | run record `findings` |
| 4b | Writer input | Was it in the writer's prompt? | LangSmith trace (exported) |
| 5 | Report | What did the answer say? | run record `report` |
| 6 | Checker | Was each verdict right? | promptfoo result + documents + report; **decided by a person** |

## Hypotheses (none accepted in advance)

| | Hypothesis | What would support it |
|---|---|---|
| A | Single-fault matching ("recipe book") | one fault matched, only its chain used, searches only about it |
| B | Retrieval | the fact is in the documents but not in the pieces found (a bad search question or badly cut chunks) |
| C | Graph | the relation is missing in the graph, or present but not used |
| D | Evidence selection | found by search, dropped in the specialist summary or the writer prompt |
| E | Reasoning | the writer had the evidence and used it wrongly or left it out |
| F | Prompt interference | must-show / Do NOT content pushes out the diagnosis |
| G | Checker / answer key | the verdict or the expectation is wrong |

## Steps for each case

| Phase | What | Who |
|---|---|---|
| 0 | Save the evidence: run records, traces, graph snapshot, chunks, settings | script (read-only) → you run and commit |
| 1 | Agree what a right answer needs: facts with document lines, expected rating | I propose → **you confirm** |
| 2 | Follow each fact through the 7 stages; backward trace for anything said that shouldn't be | script gathers, I write |
| 3 | Mark each checker verdict right or wrong | I lay it out → **you decide** |
| 4 | Score hypotheses A–G, write the conclusion and lessons | I draft → you review |
| 5 | Add the findings to `WEAK_AREAS.md` | I draft → you review |

Phases 0–5 use **no Groq tokens**. Re-runs happen only if the saved traces can't settle something, and each one is asked about first with its cost.

## Files

```
heldout-v1/
├── README.md        this file: method, rules, versions
├── TEMPLATE.md      the case template
├── WEAK_AREAS.md    patterns across cases (updated after each case)
├── cases/H1.md …    one per question
└── snapshot/        saved evidence (Phase 0)
```
