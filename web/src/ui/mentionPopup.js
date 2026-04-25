// ui/mentionPopup.js — pure helpers for the @mention autocomplete popup.
//
// Two functions, both pure (no DOM, no globals):
//
//   filterMentionAgents(agents, filter)
//     Filter agents by name/mention/id substring. Used to live inline in
//     renderMentionPopup; extracting makes the matching rules testable.
//
//   mentionItemsHtml(items, { escapeHtml })
//     Render the popup body. The first item is auto-selected (matches the
//     existing keyboard-navigation contract). All user-visible fields
//     (emoji/name/desc) are escaped; data-mention attribute is escaped too
//     so quotes in mention strings can't break out of the attribute.

const PLAIN_HTML = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const ESC_ATTR = (s) => String(s).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;');

/**
 * Filter mention-eligible agents by a free-text query.
 * Match is substring on name OR mention OR id (case-sensitive, matches the
 * existing inline behavior).
 * @param {Array<{id:string,name:string,mention:string,emoji?:string,desc?:string}>} agents
 * @param {string} filter
 * @returns {Array}
 */
export function filterMentionAgents(agents, filter) {
  const list = Array.isArray(agents) ? agents : [];
  const q = String(filter || '');
  if (!q) return list.slice();
  return list.filter((a) =>
    !!a && (
      (a.name && a.name.includes(q)) ||
      (a.mention && a.mention.includes(q)) ||
      (a.id && a.id.includes(q))
    )
  );
}

/**
 * Render the mention popup item list.
 * @param {Array} items
 * @param {{escapeHtml?:Function}} deps
 * @returns {string} HTML; empty string for an empty item list.
 */
export function mentionItemsHtml(items, deps = {}) {
  const escapeHtml = deps.escapeHtml || PLAIN_HTML;
  const list = Array.isArray(items) ? items : [];
  let html = '';
  for (let i = 0; i < list.length; i++) {
    const a = list[i];
    if (!a || !a.mention) continue;
    html +=
      '<div class="mention-item' + (i === 0 ? ' selected' : '') + '" ' +
      'data-mention="' + ESC_ATTR(a.mention) + '">' +
        '<span class="m-emoji">' + escapeHtml(a.emoji || '') + '</span>' +
        '<span class="m-name">' + escapeHtml(a.mention) + '</span>' +
        '<span class="m-desc">' + escapeHtml(a.desc || '') + '</span>' +
      '</div>';
  }
  return html;
}
