// Flattens typographic characters to plain ones before any check sees the text.
//
// WHY: models write characters that LOOK plain but aren't. Our first run failed
// a CORRECT answer because it wrote "burn-in" with a non-breaking hyphen
// (U+2011) while the check looked for a plain "-". A false failure costs as
// much trust as a false pass.
module.exports = function normalise(s) {
  return (s || '')
    .replace(/[\u2010-\u2015\u2212]/g, '-')        // hyphens, dashes, minus
    .replace(/[\u2018\u2019\u201B]/g, "'")          // curly single quotes
    .replace(/[\u201C\u201D]/g, '"')                // curly double quotes
    .replace(/[\u00A0\u2007\u2009\u202F]/g, ' ')    // non-breaking / thin spaces
    .replace(/\u2026/g, '...');                     // ellipsis
};
