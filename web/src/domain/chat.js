// domain/chat.js — pure chat-shape logic, no DOM, no fetch, no globals.
//
// These functions operate only on plain data and are safe to unit-test. UI
// code (index.html) calls them through window.__oc.domain.* (or in the future
// imports them directly when we modularize the UI layer).

/**
 * Generate a fresh chat id. Format: chat_<epochMs>_<6charBase36>.
 * @returns {string}
 */
export function genChatId() {
  return 'chat_' + Date.now() + '_' + Math.random().toString(36).slice(2, 8);
}

/**
 * Create a new chat object (does NOT touch storage, sidebar, or globals).
 * Caller is responsible for prepending to the chat list and persisting.
 * @param {{ title?: string, agentId?: string }} [opts]
 * @returns {Object}
 */
export function createChat({ title, agentId } = {}) {
  const now = Date.now();
  return {
    id: genChatId(),
    title: title || '新对话',
    agentId: agentId || 'main',
    messages: [],
    createdAt: now,
    updatedAt: now,
  };
}

/**
 * Merge a local chat list with a remote (server) one.
 *  - Newer updatedAt wins.
 *  - Returned list is sorted by updatedAt desc.
 * @param {Object[]} local
 * @param {Object[]} remote
 * @returns {Object[]}
 */
export function mergeChats(local, remote) {
  const map = new Map();
  (remote || []).forEach(c => { if (c?.id) map.set(c.id, c); });
  (local || []).forEach(c => {
    if (!c?.id) return;
    const existing = map.get(c.id);
    if (!existing || (c.updatedAt || 0) > (existing.updatedAt || 0)) {
      map.set(c.id, c);
    }
  });
  return [...map.values()].sort((a, b) => (b.updatedAt || 0) - (a.updatedAt || 0));
}

/**
 * Find a chat by id within a list. Pure helper (no globals).
 * @param {Object[]} chats
 * @param {string} id
 * @returns {Object|undefined}
 */
export function findChat(chats, id) {
  return (chats || []).find(c => c.id === id);
}

/**
 * Escape HTML-special chars for safe text-content rendering.
 * @param {string} s
 * @returns {string}
 */
export function escapeHtml(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
