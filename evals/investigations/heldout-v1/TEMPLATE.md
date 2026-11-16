# Hx: <short title of the situation>

| | |
|---|---|
| Question asked | "<operator's words>" |
| Run | `heldout-after-1108` · run_id `<id>` · trace `<langsmith id>` |
| Code | commit `<sha>` · code_hash `<hash>` |
| Compared with | `heldout-before-1104` · run_id `<id>` |
| Status | In progress / Concluded (date) |

**In one sentence:** written last.

---

## Part A. The case (once)

### 1. Industrial context
What was happening in the plant? What was the operator trying to do? 3–5 plain lines.

### 2. Expected behaviour
What the approved documents require. Agreed with the user on `<date>`.

| # | The answer should… | Source (document, line) | Check that tests it |
|---|---|---|---|
| F1 | … | `FL-101-SOP.txt` line nn | TS:… |
| R | Rating: … | … | OQ:criticality-exact |

**Should NOT say:**

| # | … | Why (source) |
|---|---|---|
| N1 | … | … |

## Part B. Findings at a glance

| ID | Finding type | What went wrong (one line) | Cause(s) | Severity | Checker |
|---|---|---|---|---|---|
| Hx-01 | (from the fixed list) | … | (from the fixed list) | High / Medium / Low | right pass / right fail / false pass / false fail / not tested |

**Cause count** (what we compare across cases):

| Cause | Findings |
|---|---|
| … | … |

## Part C. Findings

Full card for High and Medium findings; short card (stages 3–7 and 10) for Low ones.
Finding types, causes and checker results come from the fixed lists in `README.md`.

### Hx-01 · <finding type>: <one-line detail>

**3. What actually happened?**
…

**4. Why does it matter?** *(consequence + severity)*
… **Severity: …**

**5. Evidence trace** *(missing information: where it disappeared. Added content: where it first appeared.)*

| Step | There? | Exact place to check |
|---|---|---|
| Document | ✅ / ❌ | file + line |
| Search | | trace step n |
| Helper input | | trace step n |
| Helper summary | | trace step n → `findings` |
| Writer input | | trace step 19 → input |
| Writer output | | trace step 19 → output |
| Final answer | | run record → report |

✅ there · ❌ not there · ⬜ not saved (an observability gap)

**6. Failure mechanism** *(cause)*
How it happened. **Cause: …**

**7. Evidence strength**
- **Proven:** …
- **Likely:** …
- **Unknown:** …

**8. Competing explanations** *(full card only)*
| Explanation | For | Against |
|---|---|---|

**9. Verification** *(full card only)*
Which test would tell the explanations apart, and what it costs.

**10. Evaluator assessment**
Which check covered it, what it said, whether that was right.

---

## Part D. Lessons (once)

### 11. Learning takeaway
The general principle this case shows, in plain words.

### 12. Independent exercise
A new, short situation for the reader to diagnose, with the answer below it.

### What worked
What the system got right, with evidence.

### Open questions and observability gaps
| Open question | Why we can't tell | What would settle it (and cost) |
|---|---|---|

## Appendix

- A. Fact journey (each required fact through every stage)
- B. Evidence files
