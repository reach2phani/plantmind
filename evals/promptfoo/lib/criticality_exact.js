// OQ — the criticality is the EXPECTED level, not just "not too low".
//
// WHY THIS EXISTS
//   SR:safe-criticality-floor only fails a rating that is too LOW (the unsafe
//   direction). A rating that is too HIGH is not unsafe, but it is wrong: an
//   operator told that normal seal-settling is CRITICAL learns to ignore the
//   label (alarm fatigue). This check reports the exact match, as quality.
//
// HOW
//   Same reader as criticality.js; the expected level comes from
//   vars.expect_exact instead of vars.expect_criticality.

const floor = require('./criticality');

module.exports = (output, context) => {
  const vars = (context && context.vars) || {};
  if (!vars.expect_exact) {
    return { pass: false, score: 0, reason: 'Test is missing vars.expect_exact' };
  }
  return floor(output, { ...context, vars: { ...vars, expect_criticality: vars.expect_exact } });
};
