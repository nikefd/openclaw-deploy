// localStore.js — thin typed wrapper over localStorage.
// Keeps all string keys in one place (via config.storage).

import { config } from '../config.js';

// Strip large base64 image data before saving to avoid localStorage quota.
// Server-side storage keeps full images; localStorage is just a quick cache.
function stripImages(chats) {
  if (!Array.isArray(chats)) return chats;
  return chats.map(c => ({
    ...c,
    messages: (c.messages || []).map(m => {
      if (!m?.images || !m.images.length) return m;
      return { ...m, images: m.images.map(img => (img && img.length > 200) ? '[image]' : img) };
    }),
  }));
}

export const localStore = {
  get(key, fallback = null) {
    try {
      const v = localStorage.getItem(key);
      if (v == null) return fallback;
      try { return JSON.parse(v); } catch { return v; }  // plain strings work too
    } catch { return fallback; }
  },

  set(key, value) {
    try {
      const v = typeof value === 'string' ? value : JSON.stringify(value);
      localStorage.setItem(key, v);
      return true;
    } catch { return false; }
  },

  remove(key) { try { localStorage.removeItem(key); } catch {} },
};

// Typed accessors for the well-known keys — prefer these at call sites.
export const prefs = {
  // chats: stripImages on write to avoid localStorage quota errors.
  // Server-side storage keeps full images; localStorage is just a fast cache.
  getChats:   () => localStore.get(config.storage.chats, []),
  setChats:   (v) => localStore.set(config.storage.chats, stripImages(v)),

  // Per-node chat caches: oc_chats_v2_<nodeId>
  // The multi-node feature stores a separate cache per node so switching
  // nodes doesn't lose context. Pass node='local' for the default node.
  getChatsForNode: (node) => localStore.get(`${config.storage.chats}_${node}`, []),
  setChatsForNode: (node, v) => localStore.set(`${config.storage.chats}_${node}`, stripImages(v)),

  getAgent:   () => localStore.get(config.storage.agent) || 'main',
  setAgent:   (v) => localStore.set(config.storage.agent, v),
  getTheme:   () => localStore.get(config.storage.theme) || 'dark',
  setTheme:   (v) => localStore.set(config.storage.theme, v),
  // Default 'openclaw' is a legacy alias — NOT a real model id. Used in URL
  // building when no model has been explicitly chosen. Don't change without
  // also updating index.html resolution code.
  getModel:   () => localStore.get(config.storage.model) || 'openclaw',
  setModel:   (v) => localStore.set(config.storage.model, v),
};
