// Turns PlantMind's /investigate streamed reply into the report text the
// checks read.
//
// /investigate streams progress lines while it works, then the report:
//   "🔍 Multi-agent investigation started..."
//   "⚠️ Knowledge graph unavailable — ..."        (only in degraded mode)
//   "→ alarm agent ... "                           (specialist progress)
//   "📝 All specialists complete. Orchestrator synthesizing report..."
//   "════════...\nINVESTIGATION REPORT\n════════...\n\n<the report>"
//
// We keep everything from the INVESTIGATION REPORT banner onwards. The progress
// lines must be dropped, or a check looking for "isolate" could match a
// specialist's progress chatter instead of the actual recommended steps.
//
// The degraded-mode warning is captured separately and re-attached at the TOP
// as a plain marker line, because Phase 1 has a graph-on / graph-off case pair
// and losing that signal would hide which mode produced the report.

const normalise = require('../lib/normalise');

module.exports = (json, text) => {
  const body = normalise(text);

  const degraded = body.includes('Knowledge graph unavailable')
    ? 'GRAPH_UNAVAILABLE\n\n'
    : '';

  const at = body.indexOf('INVESTIGATION REPORT');
  if (at === -1) {
    // No report banner: the run failed (rate limit, error, empty). Return the
    // raw text so the failure reason is visible in the results screen rather
    // than showing up as a mysterious empty answer.
    return degraded + body.trim();
  }

  // Skip the banner line and the "════" rule that follows it.
  const afterBanner = body.slice(at + 'INVESTIGATION REPORT'.length);
  const start = afterBanner.search(/\n\s*\n/);
  const report = start === -1 ? afterBanner : afterBanner.slice(start);

  return degraded + report.trim();
};
