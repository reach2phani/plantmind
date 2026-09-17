// Turns PlantMind's /ask plain-text reply into the answer promptfoo checks.
//
// /ask replies in one of these shapes:
//   "SOURCES:[{...}]\n\n<answer text>"          normal answer
//   "FALLBACK:SOURCES:[{...}]\n\n<answer text>"  answer after relaxing filters
//   "NOANSWER:<message>"                         honest refusal
//
// promptfoo calls this with (json, text, context). The body isn't JSON, so we
// use `text`. Step 1.5 will also return the sources, for retrieval scores.

// Why normalise: the models write typographic characters that LOOK like plain
// ones but aren't. Our first run failed a correct answer because it said
// "burn‑in" with a non-breaking hyphen (U+2011) while the check looked for
// "burn-in". A false failure costs as much trust as a false pass, so text is
// flattened to plain characters before any check sees it.
function normalise(s) {
  return (s || '')
    .replace(/[‐-―−]/g, '-')   // hyphens, dashes, minus sign
    .replace(/[‘’‛]/g, "'")    // curly single quotes
    .replace(/[“”]/g, '"')          // curly double quotes
    .replace(/[    ]/g, ' ') // non-breaking / thin spaces
    .replace(/…/g, '...');               // ellipsis
}

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
