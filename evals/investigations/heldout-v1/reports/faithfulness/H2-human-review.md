# H2 faithfulness: human review of the judge's "not supported" verdicts

**Question:** "Just changed the filler over to the 330s and it's jammed twice at the infeed in the last 20 mins. Bottles keep catching going into the star wheel. What am I missing?"

**Judge result (v1, locked rubric):** 28 of 60 statements supported → **0.47**.
**This review:** each of the 32 "not supported" verdicts checked against the evidence the writer actually received (helper summaries + knowledge graph, from the saved trace). Proposed by Claude, **confirmed by the user on 2026-11-15** (all 32 verdicts agreed).

**Verdict codes**
- **J: judge error.** The evidence does support it; the judge rejected it for a wrong reason.
- **U: truly unsupported.** The writer added it; nothing in its input says it.
- **B: borderline.** The content is in the evidence, but the answer states it more strongly (for example a possible cause stated as the cause).

## The 32 verdicts

| # | Statement (shortened) | Judge's reason (short) | Review | Why: evidence the writer had |
|---|---|---|---|---|
| 1 | Root cause: rails not reset to B after the changeover | only a possible cause | **B** | Graph: cause #1 "Guide rails not reset after a bottle size changeover"; "Most infeed jams in the first hour after a changeover come from rails left in the wrong position". The answer states it as certain |
| 6 | A changeover lapse, not a recurring defect | not concluded | **B** | Alarm helper: "first-time occurrence"; graph cause list. Reasonable inference, stated as fact |
| 9 | Safety risk rated HIGH | "criticality" is not "safety risk" | **B** | Graph: "min criticality: HIGH — the machine must be stopped and locked out". Relabelled |
| 14 | Potential scrap from jammed bottles | not stated | **U** | Not in the evidence (harmless) |
| 26 | Step 1: lock out, stop production, isolate power | "Step 1 is…" ordering | **J** | Graph LOTO: "Switch off power at the main isolator. Lock the isolator…" |
| 27 | Step 2: verify rails at B and locked | "no Step 2 that verifies rails" | **J** | SOP helper: "Move the guide rails… (B for 330 ml) and lock them" |
| 28 | Step 2: star wheel matches 330 ml | step number | **J** | "Fit the matching star wheel"; "Star wheel must match bottle size" |
| 29 | Step 2: inspect infeed for jammed or damaged bottles | step number | **J** | "Remove the jammed bottles…", "Remove any chipped or damaged bottles" |
| 30 | Step 3: set rails to B and lock | step number | **J** | as #27 |
| 31 | Step 3: fit the 330 ml star wheel | step number | **J** | as #28 |
| 32 | Step 3: remove jammed or chipped bottles, cut-resistant gloves | combines two steps | **J** | "Remove the jammed bottles wearing cut-resistant gloves"; "Remove any chipped or damaged bottles" |
| 33 | Step 3: remove the lock after the jam is cleared | it's step 6 | **J** | "Remove the lock, restart at 60 bottles per minute…" |
| 34 | Step 4: run 20 test bottles at 60 per minute | jam procedure says 2 minutes | **J** | Changeover: "run 20 bottles at 60 bottles per minute" |
| 35 | Step 4: check no jam and correct fill | step number | **J** | "Check none jam and all fill correctly" |
| 36 | Step 4: back to normal 120 per minute if OK | "neither is Step 4" | **J** | "normal: 120 bottles per minute"; "then return to normal speed" |
| 37 | Step 5: record changeover and jam clearing in the shift log | step number | **J** | "Record the changeover in the shift log" (the jam-clearing part is a small addition) |
| 38 | Step 5: shift lead signs the record | "it's step 6" | **J** | "the shift lead signs the changeover record" |
| 39 | No other quality actions required beyond logging | not stated | **U** | A template phrase; the evidence doesn't say it |
| 40 | Root-cause fix: a mandatory checklist step after every changeover | new, not in context | **U** | Invented corrective action |
| 41 | That checklist step confirms rails at B and locked before removing the lock | "mandatory checklist" not in context | **B** | Content supported (rails B, locked, before removing lock); the "checklist" framing is invented |
| 42 | Preventive: a visual "Rail Position B" indicator | not mentioned | **U** | Invented |
| 43 | Preventive: train operators each shift | not mentioned | **U** | Invented |
| 44 | Preventive: periodic changeover audits | not mentioned | **U** | Invented |
| 45 | Shift lead must be notified | signs, not "notified" | **B** | "the shift lead signs the changeover record" |
| 46 | Maintenance supervisor must be notified | no trigger applies | **U** | Graph triggers: 3+ alarms, electrical fault, rail won't lock, glass. None reported, so it's over-escalation |
| 47 | Quality lead must be notified | only for glass | **U** | "Any glass breakage (also call the quality lead)". No glass, so it's over-escalation |
| 48 | The filler was changed to 330 ml | not stated | **J** | **In the operator's question**, which RAGAS doesn't give the judge |
| 49 | Jammed twice after the change | timing not stated | **J** | Operator's question: "Just changed… jammed twice at the infeed in the last 20 mins" |
| 51 | The rails were not reset to B (as a fact) | possible cause only | **B** | Same as #1: a likely cause stated as fact |
| 54 | Required: set rails to B | only if wrong | **J** | Changeover procedure: "Move the guide rails… (B for 330 ml)", a required step after a changeover |
| 55 | Required: lock the rails | not explicit | **J** | "…and lock them" |
| 56 | Required: fit the correct star wheel | conditional | **J** | "Fit the matching star wheel" |

## Summary

| Review verdict | Count | Statements |
|---|---|---|
| **J: judge error** | **18** | 26–38, 48, 49, 54, 55, 56 |
| **U: truly unsupported** | **8** | 14, 39, 40, 42, 43, 44, 46, 47 |
| **B: borderline** | **6** | 1, 6, 9, 41, 45, 51 |

**Corrected H2 faithfulness (reported as a range, user decision 2026-11-15):**
- Judge (v1): **0.47** (28/60)
- After review, borderline counted **unsupported**: (28 + 18) / 60 = **0.77**
- After review, borderline counted **supported**: (28 + 18 + 6) / 60 = **0.87**

**Reported value: H2 faithfulness 0.77–0.87** (judge v1: 0.47). The range is because "a likely cause stated as fact" is a judgement call.

**The judge was wrong on 18 of its 32 "not supported" verdicts (56%).**

## Causes of the judge's errors

| Cause | Statements | Fix (rubric v2) |
|---|---|---|
| Step numbers: RAGAS wrote "Step 2 of the immediate action is…", and the judge checked the numbering, not the action | 26–38 (13) | Remove "Step N:" labels from the answer before RAGAS splits it |
| Facts from the operator's question: the judge never sees the question | 48, 49 | Add the question to the evidence (the writer had it too) |
| Too strict on "required" when the action is conditional | 54, 55, 56 | Keep (not fixable without changing RAGAS's prompts); note as a judge limit |

## What the truly unsupported statements show about PlantMind

- **Invented corrective and preventive actions** (40, 42, 43, 44): checklist, indicator, training, audits. Harmless, but not from any document. The template's "Root cause fix / Preventive action" slots invite them (the same template pressure as H1).
- **Over-escalation** (46, 47): maintenance supervisor and quality lead "must be notified", though no escalation trigger applies. Not unsafe, but it would send people for nothing.
- **Template phrase** (39): "No additional quality actions are required…".
- **Likely causes stated as facts** (1, 6, 51: borderline). The SOP lists rails as the *most likely* cause; the answer states it as *the* cause.

## Not yet checked

The other direction: are any of the judge's **28 "supported"** verdicts wrong (false support)? On H1 the judge counted the off-topic graph rules as supported, correctly by the rule, but worth a sample check here too.
