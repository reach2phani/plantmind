# Hx: <question title>

| | |
|---|---|
| Question asked | "<operator's words>" |
| Run | `heldout-after-1108` · run_id `<id>` · trace `<langsmith id>` |
| Code | commit `<sha>` · code_hash `<hash>` |
| Compared with | `heldout-before-1104` · run_id `<id>` |
| Status | In progress / Concluded (date) |

## 1. Observed result

Facts only, quoted from the report and the checker. No explanations here.

- Rating given: … (expected …)
- Checks failed: …
- Notable things said: "…"

## 2. Conclusion

Written last.

**Root cause:** … **Confidence:** Confirmed / Likely / Unresolved

**In one sentence:** …

## 3. What a right answer needs

Proposed by Claude, confirmed by the user on `<date>`.

| # | Fact | Source (document, line) | Required by check |
|---|---|---|---|
| F1 | … | `FL101-SOP…` line nn | TS:… |
| R | Expected rating: … | … | OQ:criticality-exact |

Answer-key problems found: …

## 4. Fact journey

One row per fact. ✗ rows are the backward trace: things said that shouldn't have been.

| Fact | 1 Docs | 2 Search | 3 Graph | 4a Specialist | 4b Writer input | 5 Report | 6 Checker |
|---|---|---|---|---|---|---|---|
| F1 … | | | | | | | |
| ✗ … | | | | | | | |

✅ present · ❌ lost/wrong here · ⚠️ doubtful · ⬜ not observable · — not relevant

## 5. Stage notes

For each stage: **Evidence** (what the data shows) / **Observation** (what that means for the facts) / **Interpretation** (what might explain it, with the hypothesis letter).

### Stage 1: Documents
- Evidence:
- Observation:
- Interpretation:

### Stage 2: Search
Search questions sent, pieces found (rank, document), top 4 handed on.
- Evidence:
- Observation:
- Interpretation:

### Stage 3: Graph
Fault matched (and how sure), chain, must-show warnings, severity floor.
- Evidence:
- Observation:
- Interpretation:

### Stage 4a: Specialist summaries
- Evidence:
- Observation:
- Interpretation:

### Stage 4b: Writer input
- Evidence:
- Observation:
- Interpretation:

### Stage 5: Report
- Evidence:
- Observation:
- Interpretation:

### Stage 6: Checker

| Check | Checker said | Verdict was | Why (document line + report quote) |
|---|---|---|---|
| … | pass / fail | right pass / right fail / false pass / false fail | … |

Decided by the user on `<date>`.

## 6. Issues

One card per problem.

> **Hx-1: <short name>**
> - Observed:
> - First visible at: stage …
> - Evidence:
> - Likely cause: hypothesis …
> - Confidence:
> - Other explanation:
> - Matches elsewhere: (other cases, TC runs, known issues)

## 7. Hypothesis scoreboard

| A matching | B search | C graph | D dropped | E reasoning | F crowding | G checker |
|---|---|---|---|---|---|---|
| | | | | | | |

✔ supports · ✗ against · ? unresolved · ➖ not involved

## 8. What works here

…

## 9. What this case teaches about PlantMind

A finding about how the system behaves, not just a description of this answer.

…

## 10. Unresolved, and observability gaps

| Open question | Why we can't tell | What would settle it (and cost) |
|---|---|---|
| … | … | … |

## 11. Evidence links

- Run record: `snapshot/…`
- Trace: `snapshot/…`
- Documents: …
