// chatStore.js — single source of truth for chat persistence.
//
// Rules learned the hard way (see MEMORY.md 2026-04-24):
//   1. Server is authoritative while streaming. Do NOT PUT a front-end snapshot
//      that overwrites mid-stream content — the backend is already writing.
//   2. localStorage is a cache + offline fallback only.
//   3. On unload, ONLY flush non-streaming chats via sendBeacon.
//
// The UI layer should only call: loadAll / save / remove / bulkBackup.
// Never touch fetch() for chats directly.

import { getBackend } from '../backend/backendFactory.js';
import { prefs } from './localStore.js';
import { config } from '../config.js';

const streamingChats = new Set();

export const chatStore = {
  /** Mark a chat as streaming; skip server writes while flagged. */
  markStreaming(chatId)   { streamingChats.add(chatId); },
  markIdle(chatId)        { streamingChats.delete(chatId); },
  isStreaming(chatId)     { return streamingChats.has(chatId); },

  /** Read cached chats from localStorage (sync, instant). */
  cached() { return prefs.getChats(); },

  /** Load chats from server and merge with local cache. */
  async loadAll() {
    const local = prefs.getChats();
    try {
      const remote = await getBackend().loadAllChats();
      const merged = mergeChats(local, remote);
      prefs.setChats(merged);
      return merged;
    } catch {
      return local;
    }
  },

  /** Persist a chat to the server — NOT during streaming. */
  async save(chat) {
    if (!chat?.id) return false;
    if (streamingChats.has(chat.id)) return false;   // server is authoritative
    return getBackend().saveChat(chat);
  },

  async remove(chatId) { return getBackend().deleteChat(chatId); },

  /** Bulk backup (used by "clear all" to keep a server-side trash copy). */
  async bulkBackup(chats) {
    return fetch(config.api.chats, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Backup': 'true' },
      body: JSON.stringify(chats),
    }).then(r => r.ok).catch(() => false);
  },

  /** Beacon-based flush on page unload. Skips streaming chats. */
  beaconFlush(chats) {
    if (!navigator.sendBeacon) return;
    for (const c of chats) {
      if (!c?.id || streamingChats.has(c.id)) continue;
      const blob = new Blob([JSON.stringify(c)], { type: 'application/json' });
      navigator.sendBeacon(`${config.api.chatOne}${encodeURIComponent(c.id)}`, blob);
    }
  },
};

// -- helpers ---------------------------------------------------------------

function mergeChats(local, remote) {
  const map = new Map();
  for (const c of local)  if (c?.id) map.set(c.id, c);
  for (const c of remote) if (c?.id) {
    const prev = map.get(c.id);
    if (!prev || (c.updatedAt || 0) >= (prev.updatedAt || 0)) map.set(c.id, c);
  }
  return Array.from(map.values()).sort((a, b) => (b.updatedAt || 0) - (a.updatedAt || 0));
}
