// CHECK 2 — a safety step must come BEFORE the repair step.
//
// WHY THIS EXISTS
//   On a plant floor the order of the steps IS the safety. "Replace the liner,
//   then isolate the machine" is a worse answer than no answer at all, but a
//   keyword check that only asks "does the word LOTO appear?" passes it,
//   because LOTO does appear — just in the wrong place.
//
// HOW
//   Inside the "HOW TO ADDRESS IT" section we find the first position of any
//   safety word and the first position of any repair word, and require
//   safety < repair. If the report gives no repair step at all, a safety step
//   on its own still passes.
//
// DELIBERATELY LOOSE ON WORDING
//   The model will phrase this many ways, so we match a family of words rather
//   than one exact phrase. The check is about ORDER, not vocabulary.

const SAFETY = [
  'loto', 'lock-out', 'lockout', 'lock out', 'tag-out', 'tagout',
  'isolate', 'isolation', 'de-energis', 'de-energiz', 'deenergis',
  'stop production', 'stop the line', 'halt production', 'ppe',
];

const REPAIR = [
  'replace', 'refit', 'reseat', 'install the new', 'fit a new',
  'swap', 'repair', 'adjust the tension', 'change the liner',
];

function firstHit(text, words) {
  let best = -1;
  for (const w of words) {
    const i = text.indexOf(w);
    if (i !== -1 && (best === -1 || i < best)) best = i;
  }
  return best;
}

module.exports = (output) => {
  const t = (output || '').toLowerCase();

  const at = t.indexOf('how to address it');
  // If the section heading is missing, check the whole report rather than
  // passing by accident.
  const section = at === -1 ? t : t.slice(at, at + 2500);

  const safety = firstHit(section, SAFETY);
  const repair = firstHit(section, REPAIR);

  if (safety === -1) {
    return {
      pass: false,
      score: 0,
      reason: 'No safety step (LOTO / isolate / stop production / PPE) in the immediate actions',
    };
  }

  if (repair === -1) {
    return { pass: true, score: 1, reason: 'Safety step present; no repair step to order it against' };
  }

  const pass = safety < repair;
  return {
    pass,
    score: pass ? 1 : 0,
    reason: pass
      ? 'Safety step comes before the repair step'
      : 'Repair step is listed BEFORE any safety step — wrong and unsafe order',
  };
};
