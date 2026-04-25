// localStore.js — thin typed wrapper over localStorage.
// Keeps all string keys in one place (via config.storage).

import { config } from '../config.js';

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
  getChats:   () => localStore.get(config.storage.chats, []),
  setChats:   (v) => localStore.set(config.storage.chats, v),
  getAgent:   () => localStore.get(config.storage.agent) || 'main',
  setAgent:   (v) => localStore.set(config.storage.agent, v),
  getTheme:   () => localStore.get(config.storage.theme) || 'dark',
  setTheme:   (v) => localStore.set(config.storage.theme, v),
  getModel:   () => localStore.get(config.storage.model) || 'github-copilot/claude-opus-4.7',
  setModel:   (v) => localStore.set(config.storage.model, v),
};
