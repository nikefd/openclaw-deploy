// ui/chatSidebar.js — pure HTML builders for the chat list sidebar.
//
// No DOM, no globals. Caller pre-resolves agent, streaming flag, and any
// already-escaped strings (title HTML, snippet HTML) so this module stays
// trivially testable.

function escHtml(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/**
 * Compute the section label for a chat row.
 *
 * @param {number} updatedAtMs  chat.updatedAt epoch ms
 * @param {number} nowMs        current time epoch ms (for testability)
 * @param {boolean} isSearch    true when a search query is active
 * @param {string} [locale]     locale for the date fallback (default 'zh-CN')
 * @returns {string}
 */
export function groupLabel(updatedAtMs, nowMs, isSearch, locale) {
  if (isSearch) return '搜索结果';
  const today = new Date(nowMs).toDateString();
  const yesterday = new Date(nowMs - 86400000).toDateString();
  const d = new Date(updatedAtMs).toDateString();
  if (d === today) return '今天';
  if (d === yesterday) return '昨天';
  return new Date(updatedAtMs).toLocaleDateString(locale || 'zh-CN', {
    month: 'short',
    day: 'numeric',
  });
}

/**
 * Render the small group-header label that goes between chat rows.
 * (Visible separator: "今天" / "昨天" / "搜索结果" / "Apr 25" etc.)
 *
 * @param {string} label  already-decided group label (use groupLabel())
 * @returns {string}
 */
export function groupHeaderHtml(label) {
  return `<div style="padding:6px 12px 3px;font-size:11px;color:var(--text-sec);font-weight:600">${escHtml(label)}</div>`;
}

/**
 * Build a single chat-item row.
 *
 * The caller is responsible for:
 *   - filtering / sorting / grouping
 *   - producing `titleHtml` and `snippetHtml` (these may legitimately contain
 *     <mark> tags from search highlighting and so are NOT re-escaped here —
 *     pass through `escHtml(c.title)` for the no-search case)
 *
 * Anything that lands in HTML attributes (chat id, agent.color) IS escaped
 * here to defuse injection.
 *
 * @param {{id:string}} chat
 * @param {{emoji?:string, name?:string, color?:string}} agent
 * @param {{
 *   isActive: boolean,
 *   isStreaming: boolean,
 *   titleHtml: string,        // already escaped + optionally highlighted
 *   snippetHtml?: string,     // already escaped + optionally highlighted, or ''
 *   jumpMsgIdx?: number,      // -1 / undefined → no data-jump-msg attr
 * }} ctx
 * @returns {string}
 */
export function chatItemHtml(chat, agent, ctx) {
  const c = chat || {};
  const a = agent || {};
  const o = ctx || {};
  const id = escHtml(c.id);
  const color = escHtml(a.color);
  const emoji = escHtml(a.emoji);
  const name = escHtml(a.name);
  const titleHtml = o.titleHtml == null ? '' : String(o.titleHtml);
  const snippetHtml = o.snippetHtml ? String(o.snippetHtml) : '';
  const activeCls = o.isActive ? 'active' : '';
  const streamMark = o.isStreaming ? ' ⏳' : '';
  const jumpAttr =
    typeof o.jumpMsgIdx === 'number' && o.jumpMsgIdx >= 0
      ? ` data-jump-msg="${escHtml(String(o.jumpMsgIdx))}"`
      : '';
  const snippetBlock = snippetHtml
    ? `<span class="snippet">${snippetHtml}</span>`
    : '';

  return (
    `<div class="chat-item ${activeCls}" data-id="${id}"${jumpAttr}>` +
      `<div class="agent-dot" style="background:${color}"></div>` +
      `<div class="info">` +
        `<span class="title">${titleHtml}${streamMark}</span>` +
        `<span class="meta">${emoji} ${name}</span>` +
        snippetBlock +
      `</div>` +
      `<div class="actions">` +
        `<button class="edit-btn" data-edit="${id}" title="编辑标题">✏️</button>` +
        `<button class="delete" data-del="${id}">✕</button>` +
      `</div>` +
    `</div>`
  );
}

/**
 * Empty-state HTML for the chat list (used when no rows match).
 *
 * @param {string} query  current search query (empty string when not searching)
 * @returns {string}
 */
export function emptyStateHtml(query) {
  if (query) {
    return `<div style="padding:20px;text-align:center;color:var(--text-sec);font-size:13px">未找到匹配「${escHtml(query)}」的对话</div>`;
  }
  return `<div style="padding:20px;text-align:center;color:var(--text-sec);font-size:13px">暂无对话</div>`;
}
