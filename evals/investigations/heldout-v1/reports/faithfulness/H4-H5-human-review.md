# H4 and H5 faithfulness: human review of the judge's "not supported" verdicts (rubric v2)

**Method:** same as the H2 review. Each "not supported" verdict is checked against the evidence the writer actually received (operator's question + helper summaries + knowledge graph, from the saved trace). **Proposed by Claude, confirmed by the user on 2026-11-16** (all verdicts agreed; the "verify / confirm" statements H4 #24 and #30, and H5 #19 and #21, are kept as B).

**Verdict codes**
- **J: judge error.** The evidence does support it.
- **U: truly unsupported.** The writer added it; nothing in its input says it.
- **B: borderline.** The content is in the evidence, but the answer reframes it or states it more strongly.

---

## H4: broken glass on the floor, no alarm, machine still running

**Judge (v2):** 34 of 47 supported → **0.72**

| # | Statement (shortened) | Review | Why: evidence the writer had |
|---|---|---|---|
| 10 | Financial impact: product lost to QA HOLD and thrown-away open bottles | **B** | QA HOLD and "throw away open bottles within 2 m" are in the graph; "financial impact" is a relabel |
| 11 | Financial impact may include re-work or scrap costs | **U** | Not in the evidence (harmless) |
| 12 | No exact dollar amount is available | **B** | True (no dollar figure anywhere), but a statement about missing data can't be "supported" |
| 24 | Inspect the area for more glass fragments | **B** | "Clean up the broken glass" is there; a separate inspection step is added |
| 30 | Confirm the guard is locked out | **B** | "Do not open any guard until… locked out" is there; "guard locked out" is muddled wording |
| 31 | Confirm the area is free of glass | **J** | Same requirement as "clean up the glass before restart", which the judge accepted in #19 |
| 32 | Confirm the sanitation rinse is completed | **J** | "Run the sanitation rinse (10 minutes)" before restart; the judge accepted the same thing in #19 |
| 36 | Review and repair the glass-breakage sensor | **U** | A sensible idea, but invented. The evidence only notes that no alarm went off |
| 37 | Add a quarterly inspection of the detection system | **U** | Invented |
| 38 | Update operator training | **U** | Invented |
| 41 | Notify the shift supervisor | **U** | The graph names only the quality lead and the maintenance supervisor |
| 42 | Notify the plant manager | **U** | Not in the evidence (over-escalation) |
| 47 | Could cause recalls, safety incidents, significant financial loss | **B** | "Glass can end up inside filled bottles… product safety event" is there; recalls and money are added |

| Review verdict | Count | Statements |
|---|---|---|
| J: judge error | **2** | 31, 32 |
| U: truly unsupported | **6** | 11, 36, 37, 38, 41, 42 |
| B: borderline | **5** | 10, 12, 24, 30, 47 |

**H4 corrected range:** borderline unsupported (34 + 2) / 47 = **0.77**; borderline supported (34 + 2 + 5) / 47 = **0.87**.

**One possible lenient "supported":** #6 "Product safety is compromised because the line continues running". This is a reasonable conclusion, but the evidence doesn't say it.

**Note:** "the maintenance supervisor must be notified" was correctly **supported** here (glass breakage is escalation trigger 5). In H2 it was correctly **not supported** (no trigger applied). The judge followed the triggers both times.

---

## H5: reject rate about 2%, no alarm, "should I tell someone?"

**Judge (v2):** 19 of 44 supported → **0.43**

The evidence is thin, and on purpose. The SOP says **"If the checkweigher rejects more than 1 bottle in 100 over an hour, tell the shift lead"**, and the SOP helper adds "no further escalation or shutdown is required". The graph says **"no machine fault reported"**.

| # | Statement (shortened) | Review | Why: evidence the writer had |
|---|---|---|---|
| 6 | Production impact: minor quality loss | **B** | 2% rejects, no shutdown; "minor" is a label |
| 8 | Safety risk low: no hazard identified | **B** | SOP helper: no safety requirements for this issue; graph: no fault |
| 9 | Financial impact: about 2% product waste | **B** | 2% rejects is in the question; "waste" and "financial" are a relabel |
| 10 | No major cost | **U** | Not in the evidence (template slot) |
| 11 | Criticality is low | **B** | "Notification only, no escalation" supports it; the label isn't stated |
| 19 | Verify PPE is worn | **B** | "PPE Required" is listed; "verify" is added (and not relevant to the question) |
| 20 | Verify all guard doors are closed | **U** | The evidence describes the machine (guard switches), not an operator check |
| 21 | Watch the reject count for an hour to confirm it's above 1% | **B** | The SOP rule is "over an hour"; a fair reading, but the instruction is added |
| 23 | Maintenance schedules a checkweigher calibration | **U** | Calibration is not in the evidence at all |
| 24 | Re-measure for one hour after calibration | **U** | Invented |
| 25 | Reject rate must be ≤ 1% after calibration | **U** | Invented |
| 26 | Put the affected batch on QA HOLD | **U** | QA HOLD belongs to glass breakage, not this |
| 27 | Record the reject count "per the SOP" | **U** | Not in the evidence, **and it cites the SOP as its source** |
| 28 | Record the note "None required by the documents" | **U** | **Template text leaked into the answer**: an instruction to the writer became an instruction to the operator |
| 29 | Recalibrate per the manufacturer's schedule | **U** | Invented |
| 30 | Investigate possible drift | **U** | Invented |
| 31 | Add a daily pre-shift checkweigher check | **U** | Invented |
| 32 | Record that daily check's results | **U** | Invented |
| 33 | Trigger early maintenance if rejects approach 1% | **U** | Invented |
| 35 | Notify the maintenance supervisor for calibration | **U** | Over-escalation; the SOP helper says no further escalation is needed |
| 38 | Likely root cause: calibration drift | **U** | No evidence names calibration. The history links high rejects to underfill and valve drips instead |
| 40 | A quality hold is placed | **U** | Invented |
| 42 | A calibration must be scheduled | **U** | Invented |
| 43 | Risk if not actioned: continued product waste | **B** | 2% rejects continuing is waste; a logical step |
| 44 | Risk if not actioned: downstream quality complaints | **U** | Not in the evidence (harmless) |

| Review verdict | Count | Statements |
|---|---|---|
| J: judge error | **0** | none |
| U: truly unsupported | **18** | 10, 20, 23–33, 35, 38, 40, 42, 44 |
| B: borderline | **7** | 6, 8, 9, 11, 19, 21, 43 |

**H5 corrected range:** borderline unsupported 19 / 44 = **0.43**; borderline supported (19 + 7) / 44 = **0.59**.

No lenient "supported" verdicts were found in a read-through. Statements 14–18 (LOTO and guard rules) are supported but off-topic for a reject-rate question. Faithfulness doesn't measure relevance (known limit).

---

## What this review shows

**About the judge (v2):**

| Case | "Not supported" verdicts | Judge errors |
|---|---|---|
| H2 (v1, before the fix) | 32 | 18 (56%) |
| H4 (v2) | 13 | 2 (15%) |
| H5 (v2) | 25 | 0 (0%) |

The v2 prep fixes worked outside the case they were designed on. The remaining errors are the known "confirm / verify" strictness.

**About PlantMind:**
- **The thinner the evidence, the more the writer invents.** H5's correct answer is one line ("tell the shift lead"). The writer filled the rest of the template with a calibration plan, a QA hold, a root cause and extra notifications: 18 invented statements, the most of any case.
- **The same template pressure in every case:** root-cause fix / preventive action / who to notify / financial impact slots get filled whether or not the evidence covers them (H1, H2, H4, H5).
- **New, in H5:** a statement that **cites the SOP for something the SOP doesn't say** (#27), and **template text leaking into the answer** (#28).

## Faithfulness so far (judge v2, with human-reviewed range)

| Case | Judge v2 | Human-reviewed range |
|---|---|---|
| H1 | 0.54 | not reviewed under v2 (calibration passed) |
| H2 | 0.82 | 0.77–0.87 (v1 review) |
| H4 | 0.72 | 0.77–0.87 |
| H5 | 0.43 | 0.43–0.59 |
| H3 | not run | too large for one call on the free tier |
