// ui/escape.js — HTML-escape a string for safe interpolation.
//
// Extracted from inline as part of Phase 6.3.
//
// IMPORTANT: this matches the original `document.createElement('div').textContent`
// → `innerHTML` round-trip behaviour exactly. The browser only escapes
// `&`, `<`, `>` for textContent — quotes are NOT escaped, because text
// nodes don't need them. Several call sites interpolate esc() into HTML
// attributes (e.g. `data-foo="${esc(...)}"`), which is technically a pre-
// existing XSS vector, but tightening that here would change observable
// output. Done in a focused security pass instead.
//
// A pure-string implementation also lets us unit-test esc() in Node,
// which the DOM-based original could not.

const ESC_MAP = {
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
};

/**
 * Escape arbitrary text for safe interpolation into HTML text content.
 * Behaviour-equivalent to the legacy DOM-based esc() helper.
 * @param {unknown} t
 * @returns {string}
 */
export function esc(t) {
  if (t == null) return '';
  return String(t).replace(/[&<>]/g, c => ESC_MAP[c]);
}
