// CHECK 5 — the answer must not just stop mid-sentence.
//
// WHY THIS EXISTS
//   The looping Shift answer found in step 1.2 hit the 800-token output cap and
//   ended mid-word, with NO notice to the operator. app.py captures the model's
//   finish_reason and logs it (around line 1174), but /ask never surfaces it —
//   Phase 0's truncation flag covers the investigation path only.
//
//   An operator reading a cut-off answer has no way to know a step is missing.
//   On a plant floor that is the difference between "and then isolate the
//   machine" being read and not being read.
//
// HOW (deliberately conservative)
//   Fail only when BOTH are true:
//     (a) the answer is long — over 1200 characters, so it is plausibly at the
//         output cap rather than simply a short answer, AND
//     (b) the last line does not end in sentence-ending punctuation.
//
//   Short answers, one-line refusals and clean bullet lists are never failed.
//   This check is here to catch a cliff edge, not to police writing style.
//
// EXPECTED TO BE RED FOR NOW
//   This test is meant to fail while the gap exists. The fix is two changes,
//   both later phases: surface truncation to the operator on /ask, and stop the
//   repetition loop that eats the budget in the first place.

const ENDS_CLEANLY = /[.!?:;)"'\]]\s*$/;

module.exports = (output) => {
  const text = (output || '').trimEnd();

  if (text.length <= 1200) {
    return { pass: true, score: 1, reason: 'Answer is short — not near the output cap' };
  }

  if (ENDS_CLEANLY.test(text)) {
    return { pass: true, score: 1, reason: 'Answer ends on a complete sentence' };
  }

  const tail = text.slice(-70).replace(/\n/g, ' ');
  return {
    pass: false,
    score: 0,
    reason: `Answer appears cut off with no notice to the operator — ends: "...${tail}"`,
  };
};
