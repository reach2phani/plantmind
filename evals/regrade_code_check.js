// regrade_code_check.js - re-mark ONE code check in saved promptfoo result files.
//
// Why: a code checker (not the AI judge) was found to be wrong and was fixed.
// The answers are already saved, so we re-mark them with the fixed checker
// instead of re-running the eval. 0 tokens. Each changed mark keeps a note in
// its reason so the file shows it was re-marked, and when.
//
// First used 2026-11-03: safety_order.js counted "Do NOT attempt electrical
// repairs" (a warning) as a repair step, so after-fix-1 r1 failed
// "lockout before repair" three times although Step 1 was lockout every time.
//
// Usage (from C:\plantmind):
//   node evals\regrade_code_check.js SR:safe-lockout-before-repair evals\promptfoo\lib\safety_order.js evals\results\after-fix-1-1102-r1.json
//   add --dry to only show what would change

const fs = require('fs');
const path = require('path');

const args = process.argv.slice(2);
const dry = args.includes('--dry');
const [metric, checkerFile, ...files] = args.filter((a) => a !== '--dry');
if (!metric || !checkerFile || !files.length) {
  console.log('usage: node evals\\regrade_code_check.js <metric> <checker.js> <results.json>... [--dry]');
  process.exit(1);
}
const checker = require(path.resolve(checkerFile));
const today = new Date().toISOString().slice(0, 10);

for (const f of files) {
  const data = JSON.parse(fs.readFileSync(f, 'utf8'));
  let changed = 0;
  for (const r of data.results.results) {
    const c = ((r.gradingResult || {}).componentResults || []).find((x) => (x.assertion || {}).metric === metric);
    if (!c) continue;
    const now = checker((r.response || {}).output || '');
    const tc = (r.vars || {}).tc;
    if (now.pass === c.pass) {
      console.log(`${f}  ${tc}: unchanged (${c.pass ? 'pass' : 'FAIL'})`);
      continue;
    }
    console.log(`${f}  ${tc}: ${c.pass ? 'pass' : 'FAIL'} -> ${now.pass ? 'pass' : 'FAIL'}  (${now.reason})`);
    changed++;
    c.pass = now.pass;
    c.score = now.score;
    c.reason = `${now.reason} [re-marked ${today} with fixed ${path.basename(checkerFile)}; was: ${c.reason}]`;
  }
  if (changed && !dry) {
    fs.writeFileSync(f, JSON.stringify(data, null, 2));
    console.log(`${f}: ${changed} mark(s) updated`);
  }
}
