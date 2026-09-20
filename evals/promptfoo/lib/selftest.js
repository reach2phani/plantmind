// Tests the CHECKS, not the app.
//
// WHY THIS EXISTS
//   A check you have not tested is just an opinion. Two of the five checks in
//   this folder had real bugs on their first write, and both were caught here
//   rather than by a wrong eval score:
//     - criticality.js read the word "CRITICAL" inside the heading "HOW
//       CRITICAL IS IT" and reported a correct CRITICAL report as unrated.
//     - no_repeat_lines.js failed two CORRECT reports on the "═══════" section
//       dividers the report format draws four times by design.
//
//   A broken check is worse than no check: it sends you hunting a bug in the
//   app that was never there.
//
// THE FIXTURE
//   __fixtures__real_answers.json holds the 16 REAL answers from the step-1.2
//   run — 15 good-or-bad-in-known-ways, plus the genuinely broken GF-SI-001
//   (a 45x repetition loop that stopped mid-word). Real output, not invented
//   samples, so a check is proved against the shapes the app actually produces.
//
// RUN (no app needed, no tokens spent, takes a second)
//   node evals/promptfoo/lib/selftest.js

const answers = require('./__fixtures__real_answers.json');
const criticality = require('./criticality.js');
const safetyOrder = require('./safety_order.js');
const noRepeatTimes = require('./no_repeat_times.js');
const noRepeatLines = require('./no_repeat_lines.js');
const notTruncated = require('./not_truncated.js');

let failures = 0;

function expect(name, got, want) {
  const ok = got === want;
  if (!ok) failures++;
  console.log(`${ok ? 'ok  ' : 'FAIL'}  ${name}${ok ? '' : `  (got ${got}, want ${want})`}`);
}

// ── criticality: the rating must be read exactly ───────────────────────────
const rating = (level) =>
  ['WHAT IS THE IMPACT:', '- Safety risk: HIGH', 'HOW CRITICAL IS IT:', `- ${level}`, '- because'].join('\n');

expect('criticality: CRITICAL report, CRITICAL wanted',
  criticality(rating('CRITICAL'), { vars: { expect_criticality: 'CRITICAL' } }).pass, true);
expect('criticality: HIGH report, CRITICAL wanted -> fail',
  criticality(rating('HIGH'), { vars: { expect_criticality: 'CRITICAL' } }).pass, false);
expect('criticality: MEDIUM report, MEDIUM or LOW wanted',
  criticality(rating('MEDIUM'), { vars: { expect_criticality: 'MEDIUM,LOW' } }).pass, true);
expect('criticality: "Safety risk: HIGH" above the block is not the rating',
  criticality(rating('LOW'), { vars: { expect_criticality: 'LOW' } }).pass, true);
expect('criticality: no rating block at all -> fail',
  criticality('no rating anywhere', { vars: { expect_criticality: 'CRITICAL' } }).pass, false);

// ── safety order: safety step before repair step ──────────────────────────
const steps = (a, b) => `HOW TO ADDRESS IT:\nStep 1: ${a}\nStep 2: ${b}`;

expect('safety order: LOTO then replace',
  safetyOrder(steps('LOTO and isolate the machine', 'Replace the liner')).pass, true);
expect('safety order: replace then LOTO -> fail',
  safetyOrder(steps('Replace the liner', 'LOTO and isolate the machine')).pass, false);
expect('safety order: no safety step at all -> fail',
  safetyOrder(steps('Replace the liner', 'Run a test bead')).pass, false);

// ── duplicate events (rule rewritten after the step-1.7 consistency run) ──
expect('repeat events: same event listed twice -> fail',
  noRepeatTimes('- 2025-01-21 at 03:18 - Overload alarm (third)\n- 2025-01-21 at 03:18 - Overload alarm (third, repeated entry)').pass, false);
expect('repeat events: distinct events',
  noRepeatTimes('- 03:18 - Overload alarm\n- 04:20 - Overload alarm').pass, true);
expect('repeat events: different events in the same minute are fine',
  noRepeatTimes('- 04:30 - Burn-in completed\n- 04:30 - Test weld passed').pass, true);
expect('repeat events: a later note MENTIONING an earlier time is fine',
  noRepeatTimes('- 03:45 - Rolls replaced\n- 06:15 - Handover: rolls replaced at 03:45').pass, true);

// Two GOOD Shift answers from the consistency run that the first version of
// the check wrongly failed. Kept as fixtures so it can never regress.
for (const id of ['SI-GOOD-RUN2', 'SI-GOOD-RUN3']) {
  if (answers[id]) expect(`real ${id}: duplicate-event check`, noRepeatTimes(answers[id]).pass, true);
}
expect('real GF-SI-001 (46x loop): duplicate-event check', noRepeatTimes(answers['GF-SI-001']).pass, false);

// ── against the real answers from the step-1.2 run ────────────────────────
// Only GF-SI-001 is genuinely broken. Every other real answer must pass these
// two sanity checks, whatever its quality problems were.
for (const [id, text] of Object.entries(answers)) {
  const broken = id === 'GF-SI-001';
  expect(`real ${id}: repetition check`, noRepeatLines(text).pass, !broken);
  expect(`real ${id}: truncation check`, notTruncated(text).pass, !broken);
}

console.log(failures === 0 ? '\nAll checks behave as intended.' : `\n${failures} check(s) misbehaving.`);
process.exit(failures === 0 ? 0 : 1);
