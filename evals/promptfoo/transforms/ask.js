// Turns PlantMind's /ask plain-text reply into the answer promptfoo checks.
//
// /ask replies in one of these shapes:
//   "SOURCES:[{...}]\n\n<answer text>"          normal answer
//   "FALLBACK:SOURCES:[{...}]\n\n<answer text>"  answer after relaxing filters
//   "NOANSWER:<message>"                         honest refusal
//
// promptfoo calls this with (json, text, context). The body isn't JSON, so we
// use `text`. Step 1.5 will also return the sources, for retrieval scores.

// Text is normalised first (see lib/normalise.js for why).
const normalise = require('../lib/normalise');

module.exports = (json, text) => {
  let body = normalise(text).replace(/^FALLBACK:/, '');

  if (body.startsWith('NOANSWER:')) {
    return body.slice('NOANSWER:'.length).trim();
  }

  if (body.startsWith('SOURCES:')) {
    const split = body.indexOf('\n\n');
    return split === -1 ? '' : body.slice(split + 2).trim();
  }

  return body.trim();
};
