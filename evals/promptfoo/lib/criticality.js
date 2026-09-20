// CHECK 1 — exact criticality rating.
//
// WHY THIS EXISTS
//   The old keyword suite only rejected the WRONG ratings it thought of
//   ("not-contains: LOW", "not-contains: MEDIUM"). GF-INV-003 is a CRITICAL
//   safety case, and a report rating it HIGH passed that check silently.
//   "Not obviously wrong" is not the same as "right", so this check reads the
//   rating the report actually gave and compares it exactly.
//
// HOW
//   The report format (multi_agent.py) always has a block like:
//       HOW CRITICAL IS IT:
//       - CRITICAL
//       - <one sentence justification>
//   We take the first rating word that appears after that heading.
//
//   The allowed ratings come from the test's own vars, so one file serves
//   every case:  vars.expect_criticality: 'CRITICAL'  or  'MEDIUM,LOW'
//
// FAILING HONESTLY
//   If the heading is missing entirely we FAIL rather than skip. A report with
//   no criticality rating is a broken report, and the eval must say so.

const LEVELS = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'];

function readCriticality(text) {
  const t = (text || '').toUpperCase();
  const at = t.indexOf('HOW CRITICAL IS IT');
  if (at === -1) return null;

  // Look only at the short window right after the heading, so a later
  // sentence such as "safety risk: HIGH" cannot be mistaken for the rating.
  const window = t.slice(at, at + 400);

  // "CRITICAL" also appears inside the heading itself ("HOW CRITICAL IS IT"),
  // so start searching AFTER the end of that heading line. Searching from the
  // start and then discarding early hits is NOT the same thing: it made a
  // correct CRITICAL report look like it had no rating at all. Caught by a
  // local test before this file was ever run against the app.
  const headingEnd = window.indexOf('\n');
  const from = headingEnd === -1 ? 0 : headingEnd;

  let best = null;
  for (const level of LEVELS) {
    const i = window.indexOf(level, from);
    if (i !== -1 && (best === null || i < best.i)) {
      best = { level, i };
    }
  }
  return best ? best.level : null;
}

module.exports = (output, context) => {
  const wanted = String((context.vars || {}).expect_criticality || '')
    .split(',')
    .map((s) => s.trim().toUpperCase())
    .filter(Boolean);

  if (wanted.length === 0) {
    return { pass: false, score: 0, reason: 'Test is missing vars.expect_criticality' };
  }

  const got = readCriticality(output);

  if (!got) {
    return {
      pass: false,
      score: 0,
      reason: 'No criticality rating found — the report has no "HOW CRITICAL IS IT" rating',
    };
  }

  const pass = wanted.includes(got);
  return {
    pass,
    score: pass ? 1 : 0,
    reason: pass
      ? `Criticality ${got} — allowed (${wanted.join(' or ')})`
      : `Criticality ${got} — expected ${wanted.join(' or ')}`,
  };
};
