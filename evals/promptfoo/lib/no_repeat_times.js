// CHECK 3 — the same EVENT must not be listed twice.
//
// WHY THIS EXISTS
//   Step 1.2 caught a Shift answer that listed one alarm 46 times:
//     "- 2025-01-21 at 03:18 - Wire feed motor overload (third this shift)"
//     "- 2025-01-21 at 03:18 - Wire feed motor overload (third this shift, repeated entry)"
//     ...
//   To an operator that reads as 46 alarms: a pattern that did not happen.
//
// WHAT COUNTS AS "THE SAME EVENT" (rewritten after step 1.7)
//   An event is a list line that STARTS with a time (optionally a date first),
//   followed by a description. Two lines are the same event when date, time
//   AND description match. Notes in brackets are ignored, so
//   "(third this shift)" and "(third this shift, repeated entry)" still match.
//
// WHY IT WAS REWRITTEN
//   The first version flagged ANY clock time that appeared twice anywhere in
//   the answer. The consistency run (3 runs of the same question) showed that
//   was too strict. Two of the three answers were GOOD — they found the real
//   pattern of three alarm clusters — and were failed for:
//     - a handover note mentioning an earlier time: "...liner replaced at 03:45"
//       (a reference, not a second event)
//     - different events that happened in the same minute
//   A check that fails good answers teaches you to ignore it. The real bug —
//   the 46x loop — still fails under the new rule.

function eventKey(line) {
  const m = line.match(
    /^\s*(?:[-*•]|\d+[.)])?\s*(?:\*\*)?\s*(\d{4}-\d{2}-\d{2})?\s*(?:at\s+)?(\d{1,2}:\d{2})\b\s*(?:\*\*)?\s*[-–:|]?\s*(.*)$/i
  );
  if (!m) return null;
  const [, date = '', time, rest] = m;

  // Description without bracketed notes; if the description IS only a
  // bracketed note, keep that note as the description.
  let desc = rest.replace(/\([^)]*\)/g, ' ').trim();
  if (!desc) desc = rest.trim();
  desc = desc.toLowerCase().replace(/[^a-z0-9 ]+/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 50);

  return `${date}|${time}|${desc}`;
}

module.exports = (output) => {
  const counts = new Map();
  let events = 0;

  for (const line of (output || '').split('\n')) {
    const key = eventKey(line);
    if (!key) continue;
    events++;
    counts.set(key, (counts.get(key) || 0) + 1);
  }

  const repeated = [...counts.entries()]
    .filter(([, n]) => n > 1)
    .map(([k, n]) => {
      const [date, time, desc] = k.split('|');
      return `${date ? date + ' ' : ''}${time} "${desc.slice(0, 30)}" x${n}`;
    });

  if (repeated.length === 0) {
    return {
      pass: true,
      score: 1,
      reason: events ? `${events} event line(s), none listed twice` : 'No event lines in the answer',
    };
  }

  return {
    pass: false,
    score: 0,
    reason: `Same event listed more than once: ${repeated.join('; ')}`,
  };
};
