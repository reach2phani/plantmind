// OQ — the "what to do now" list is short enough to use at the machine.
//
// WHY THIS EXISTS
//   An operator standing at a stopped filler needs a short numbered list, not
//   an essay. Agreed limit (2026-10-28): at most 10 immediate-action steps.
//   Code counts them, so the limit is applied exactly the same way every time.
//
// HOW
//   Inside "HOW TO ADDRESS IT", from "Immediate action" up to "Root cause fix",
//   count lines that start with "Step <number>" (the format multi_agent.py asks
//   for). Zero steps also fails: a report with no numbered steps cannot be
//   followed like a checklist.
//   The limit comes from vars.max_steps (default 10).

module.exports = (output, context) => {
  const max = Number((context && context.vars && context.vars.max_steps) || 10);
  const text = output || '';
  const lower = text.toLowerCase();

  const start = lower.indexOf('immediate action');
  if (start === -1) {
    return { pass: false, score: 0, reason: 'No "Immediate action" part found' };
  }
  let end = lower.indexOf('root cause fix', start);
  if (end === -1) end = lower.indexOf('preventive action', start);
  if (end === -1) end = text.length;

  const block = text.slice(start, end);
  const steps = block.split('\n').filter((ln) => /^\s*-?\s*step\s+\d+/i.test(ln)).length;

  if (steps === 0) {
    return { pass: false, score: 0, reason: 'Immediate action has no numbered steps' };
  }
  return steps <= max
    ? { pass: true, score: 1, reason: `${steps} immediate-action steps (limit ${max})` }
    : { pass: false, score: 0, reason: `${steps} immediate-action steps — over the limit of ${max}` };
};
