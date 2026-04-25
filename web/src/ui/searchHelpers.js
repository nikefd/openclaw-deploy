// ui/searchHelpers.js — pure helpers for the chat-list search bar.
//
// No DOM, no globals. UI side calls these via window.__oc.ui.searchHelpers.*

/**
 * Escape regex meta-characters so a user's query can be embedded in a RegExp
 * literally (no accidental wildcards / capture groups).
 * @param {string} s
 * @returns {string}
 */
export function escReg(s) {
  return String(s).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/**
 * Plain-string HTML escape (no DOM dependency). Equivalent to the inline
 * `esc()` helper for our uses.
 * @param {string} s
 * @returns {string}
 */
function escHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/**
 * Wrap every case-insensitive occurrence of `q` in `<mark>...</mark>`.
 * Returns escaped HTML (safe to drop into innerHTML).
 * If `q` is empty, returns the escaped text unchanged.
 * @param {string} text
 * @param {string} q
 * @returns {string}
 */
export function highlightText(text, q) {
  if (!q) return escHtml(text);
  const re = new RegExp('(' + escReg(q) + ')', 'gi');
  return escHtml(text).replace(re, '<mark>$1</mark>');
}

/**
 * Extract a context snippet around the first match of `q` in `text`.
 * Adds ellipses on truncated sides. Returns '' if no match.
 * @param {string} text
 * @param {string} q
 * @param {number} [radius=30]
 * @returns {string}
 */
export function findSnippet(text, q, radius = 30) {
  if (!text || !q) return '';
  const lower = String(text).toLowerCase();
  const idx = lower.indexOf(String(q).toLowerCase());
  if (idx < 0) return '';
  const start = Math.max(0, idx - radius);
  const end   = Math.min(text.length, idx + q.length + radius);
  return (start > 0 ? '…' : '') + text.substring(start, end) + (end < text.length ? '…' : '');
}

/**
 * Decide whether a chat matches the search query, and if so return a snippet
 * + the message index that matched (or -1 if matched on title only).
 *
 * Empty query → always matches.
 * Title match takes precedence over message match.
 *
 * @param {{title?:string, messages?:Array<{content:any}>}} chat
 * @param {string} q
 * @returns {{match:boolean, snippet?:string, msgIdx?:number}}
 */
export function chatMatches(chat, q) {
  if (!q) return { match: true, snippet: '', msgIdx: -1 };
  const lq = String(q).toLowerCase();
  const title = chat?.title || '';
  if (title.toLowerCase().includes(lq)) return { match: true, snippet: '', msgIdx: -1 };
  const msgs = chat?.messages || [];
  for (let i = 0; i < msgs.length; i++) {
    const m = msgs[i];
    const txt = typeof m?.content === 'string' ? m.content : '';
    if (txt.toLowerCase().includes(lq)) {
      return { match: true, snippet: findSnippet(txt, q), msgIdx: i };
    }
  }
  return { match: false };
}
