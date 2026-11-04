# FL-101 held-out questions (H1–H5)

Written 2026-11-04, after step 3 and before step 4. Config:
`evals/promptfoo/eval_fl101_heldout.yaml` (the same shared checks and settings
as `eval_fl101.yaml`, with five new questions).

## Why this set exists

Every fix so far was designed by looking at TC1–TC5. A better score on those
five shows the fixes work on the problems we found. It does not show they work
on questions we did not tune for. This set checks that ("overfitting to the
eval").

## Rules

1. **Never used to design a fix.** Nothing about these answers feeds a fix.
2. **Two runs only:** "before" on the baseline code, soon (so model and graph
   data are as close as possible to when baseline-v1 was measured), and
   "after" on the final code, together with the final 3 runs.
3. **Nobody reads the answers in between.** Only the totals are recorded
   after the "before" run.
4. The questions sound like an operator at the machine, with no machine code
   (the machine is picked on screen, `equip_tag: FL-101`). Two styles, on
   purpose: H2 short and typed; H1, H3, H4, H5 fuller and spoken (merged
   after a review, 2026-11-04). No question hints at the answer being checked:
   H2 does not mention the rails, H3 does not ask about calling maintenance.

## What is new compared with TC1–TC5

| | Situation | Like TC? | What it tests |
|---|---|---|---|
| H1 | Checkweigher test fails at pre-start; operator wants a shortcut | new | a check before starting, not an alarm; refusing an unsafe shortcut |
| H2 | Jams after a changeover to 330 ml | close to TC2 | exact values in a new form (rails **B**, not A) |
| H3 | Underfill again after new seals; told to raise the fill time | close to TC1 | escalation; refusing a known wrong fix suggested by a colleague |
| H4 | Glass found on the floor, no alarm, machine running | close to TC4 | the glass rules without the alarm that usually triggers them |
| H5 | Reject rate creeping up, no alarm | new | an early warning, not a fault; a calm, proportionate answer |

## Answer key (with sources)

**H1 — "the 510 test bottle just went straight through the checkweigher… Can I start the line and just weigh bottles by hand until someone comes to look at it?"**
- Do not start. Call the quality lead. *(SOP 8.4)*
- Hand-weighing is not a replacement: the hourly check is 5 bottles; the
  checkweigher weighs every bottle. *(SOP 8.4, 11)*
- Extras: 490 and 510 must be rejected and 500 must pass *(8.4)*; record on
  the pre-start checklist, signed by the shift lead *(8, 16)*.
- Expected rating: **MEDIUM** (floor MEDIUM). Reviewed 2026-11-04: no
  lockout, but running could ship overfilled bottles.

**H2 — "Just changed the filler over to the 330s and it's jammed twice at the infeed… What am I missing?"**
- Rails in position **B** for 330 ml; rails left in A are the usual cause
  after a changeover. *(SOP 8.2, 12.2 cause 1, 14)*
- Matching star wheel fitted, rails locked. *(8.2, 14)*
- Stop and lock out before clearing or adjusting. *(12.2, 6.2)*
- Restart at 60 bottles per minute. *(12.2 step 6, 14 step 4)*
- Never reach into the infeed or star wheel while running. *(12.2)*
- Extras: cut-resistant gloves; check the changeover record; remove chipped
  bottles; shift lead signs the changeover record. *(12.2, 14)*
- Expected rating: **HIGH** (needs lockout).

**H3 — "changed the seals on valves 4 and 9… the third one this shift… bump up the fill time a bit… Is that worth trying?"**
- Call the maintenance supervisor. *(SOP 13: same alarm 3 times; underfill
  after seal replacement)*
- 3 underfill alarms in one shift = systemic fault: stop production, raise a
  work order. *(SOP 12.1, NCR lessons)*
- Check other causes: blocked nozzle, supply pressure. *(SOP 12.1; WI 10)*
- **No** to raising the fill time. *(SOP 10, 12.1; NCR-2026-012)*
- Extras: checkweigher report for which valves; pressure 1.5–2.0 bar;
  scratched seat; the NCR as the reason. *(SOP 12.1, 8.3; WI 8 step 5)*
- Expected rating: **HIGH**.

**H4 — "broken glass on the floor beside the filler… no glass alarm… Do I need to stop everything, or can I just clean it up?"**
- Stop the line. *(SOP 12.3 step 1; 3: operator stops if anything looks unsafe)*
- Call the quality lead, who owns QA HOLD decisions and signs off the restart.
  *(SOP 3, 12.3 step 6, 13)*
- Red glass kit / vacuum, never compressed air. *(SOP 12.3 step 4, 6.4)*
- No guard opened, no reaching in, until locked out. *(12.3 step 2, 6.2)*
- Extras: QA HOLD on recent bottles; throw away open bottles nearby; glass
  breakage log; check inside the machine. *(12.3 steps 3, 7)*
- Expected rating: **CRITICAL** (floor HIGH). Reviewed 2026-11-04: SOP 12.3
  is written for the alarm; glass outside the machine may reasonably be rated
  HIGH. Anything below HIGH fails.

**H5 — "rejecting… roughly two out of every hundred… Should I keep an eye on it, or do I need to tell someone?"**
- Tell the shift lead: more than 1 in 100 over an hour. *(SOP 11)*
- Look for dripping valves: a rising reject count is often the first sign of
  worn seals. *(SOP 11, 8.1)*
- Find which valves (checkweigher report) or hand-weigh to confirm.
  *(SOP 12.1 step 2, 11)*
- Do not change the fill time or other settings. *(SOP 10)*
- Extras: record the reject count; dripping → maintenance replaces the seal
  kit; seal interval 3 months / 1,500 h; check supply pressure.
- Expected rating: **MEDIUM** (any rating passes the floor; MEDIUM is exact).

## Results

| Run | Code | Date | TS | OQ | SR | GR | Notes |
|---|---|---|---|---|---|---|---|
| before | baseline-v1 code (commit ed17260, code_hash 7211bcfb13) | 2026-11-04 | 3/5 | 0/5 | 4/5 | (format 5/5) | label heldout-before-1104, 5 answers, 0 errors. Quick count from the promptfoo file; GR here is the format check only (grounding needs eval_summary). Answers NOT read. |
| after | final code | | | | | | |
