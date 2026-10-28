// GR (instruction following) — the report follows the format it was told to use.
//
// WHY THIS EXISTS
//   multi_agent.py tells the writer EXACTLY how to lay out a report: fixed
//   section headings, plain text (no Markdown), a criticality word from a fixed
//   list. Instruction following = did it obey? Code can check this exactly, so
//   no judge is needed (rule: code for anything exact, AI for judgement).
//
// FAILS WHEN
//   - a required section heading is missing, or
//   - Markdown slipped in: **bold**, # headings, or `backticks`.
//   The reason lists every problem found, not just the first.

const SECTIONS = [
  'SOURCE DATA',
  'WHAT IS THE ISSUE',
  'WHAT IS THE IMPACT',
  'HOW CRITICAL IS IT',
  'HOW TO ADDRESS IT',
  'PLANT MANAGER SUMMARY',
];

module.exports = (output) => {
  const text = output || '';
  const upper = text.toUpperCase();
  const problems = [];

  const missing = SECTIONS.filter((s) => !upper.includes(s));
  if (missing.length) problems.push(`missing section(s): ${missing.join(', ')}`);

  if (text.includes('**')) problems.push('Markdown bold (**)');
  if (/^\s*#{1,6}\s/m.test(text)) problems.push('Markdown heading (#)');
  if (text.includes('`')) problems.push('Markdown backticks');

  return problems.length
    ? { pass: false, score: 0, reason: `Format not followed: ${problems.join('; ')}` }
    : { pass: true, score: 1, reason: 'All 6 sections present, plain text' };
};
