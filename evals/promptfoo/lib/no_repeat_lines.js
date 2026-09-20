// CHECK 4 — the answer must not degenerate into a repeated line.
//
// WHY THIS EXISTS
//   Step 1.2 caught a Shift answer that printed the SAME line 48 times:
//     "2025-01-21 at 03:18 - Wire feed motor overload (third this shift,
//      repeated)"
//   ...until it ran out of output budget and stopped mid-sentence. The old
//   keyword suite scored it a PASS, because the words it looked for ("wire
//   feed") were present — 48 times over.
//
//   no_repeat_times.js catches the timestamp version of this. This check is the
//   general one: ANY line repeating three or more times means the model got
//   stuck in a loop, whatever the words are.
//
// WHY THREE, NOT TWO
//   Two identical short lines can be legitimate ("- None", "- N/A" under two
//   headings). Three or more is not a coincidence. Chosen to avoid failing
//   correct answers, since a false failure costs as much trust as a false pass.
//
// STRUCTURAL LINES ARE IGNORED
//   Only lines with real words count. The investigation report draws "═══════"
//   section rules and repeats them four times by design — the first version of
//   this check failed two CORRECT reports on those dividers. Caught against the
//   real step-1.2 answers before this file was ever used in a run.

module.exports = (output) => {
  const lines = (output || '')
    .split('\n')
    .map((l) => l.trim())
    // Needs real content: long enough, and at least 8 letters or digits, so
    // rules, bullets, blanks and box-drawing are never counted.
    .filter((l) => l.length >= 15 && (l.match(/[a-z0-9]/gi) || []).length >= 8);

  const counts = new Map();
  for (const l of lines) counts.set(l, (counts.get(l) || 0) + 1);

  const worst = [...counts.entries()].sort((a, b) => b[1] - a[1])[0];

  if (!worst || worst[1] < 3) {
    return {
      pass: true,
      score: 1,
      reason: worst ? `No line repeated more than ${worst[1]}x` : 'No repeated lines',
    };
  }

  return {
    pass: false,
    score: 0,
    reason: `Repetition loop: a line is repeated ${worst[1]} times — "${worst[0].slice(0, 70)}..."`,
  };
};
