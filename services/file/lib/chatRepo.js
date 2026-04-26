// services/file/lib/chatRepo.js
//
// Pure(ish) chat persistence layer: file system access is injected via deps,
// so the same code path can be unit-tested with an in-memory fs mock.
//
// Public API:
//   listChats({since, full})   -> {data: chat[]}
//   bulkSaveChats(chats)       -> {ok: true}
//   getChatRaw(chatId)         -> {data: string}            (raw JSON string for sendJson)
//   saveChat(chatId, chat)     -> {ok:true}
//                              | {ok:false, status, reason, body}   (guarded reject)
//                              | logs ACCEPTED-SHRINK via opts.warn(...) when applicable
//   deleteChat(chatId)         -> {ok: true}
//
// All functions accept `deps` (factory-injected) and either throw on real I/O
// errors or return a structured envelope. The thin server.js handler wraps
// these into HTTP responses.
//
// Design note: stripHeavy + checkChatOverwrite are passed via deps too — keeps
// this module independent and lets tests stub guard outcomes.

'use strict';

const path = require('path');

/**
 * @param {object} deps
 * @param {object} deps.fs                 node:fs (real or mock)
 * @param {string} deps.chatsDir           absolute path to per-chat .json dir
 * @param {string} deps.chatsFile          absolute path to legacy bulk file
 * @param {(c:object)=>object} deps.stripHeavy
 * @param {(existing:object,incoming:object)=>{ok:boolean,status?:number,reason?:string,body?:object}} deps.checkChatOverwrite
 * @param {(...args:any[])=>void} [deps.warn]   optional logger (defaults to console.warn)
 */
function createChatRepo(deps) {
  if (!deps || !deps.fs || !deps.chatsDir || !deps.chatsFile ||
      !deps.stripHeavy || !deps.checkChatOverwrite) {
    throw new TypeError('createChatRepo: missing required deps');
  }
  const { fs, chatsDir, chatsFile, stripHeavy, checkChatOverwrite } = deps;
  const warn = typeof deps.warn === 'function' ? deps.warn : (...a) => console.warn(...a);

  function chatPath(chatId) {
    return path.join(chatsDir, chatId + '.json');
  }

  /**
   * GET /api/chats — list summary or full chats; supports incremental ?since.
   *
   * @param {object} [opts]
   * @param {number} [opts.since]   only return chats with updatedAt > since
   * @param {boolean} [opts.full]   when true, skip stripHeavy
   * @returns {{data: object[]}}
   */
  function listChats(opts) {
    const since = opts && Number.isFinite(opts.since) ? opts.since : 0;
    const wantFull = !!(opts && opts.full);

    fs.mkdirSync(chatsDir, { recursive: true });
    const files = fs.readdirSync(chatsDir).filter((f) => f.endsWith('.json'));
    let all = [];
    if (files.length > 0) {
      all = files
        .map((f) => {
          try { return JSON.parse(fs.readFileSync(path.join(chatsDir, f), 'utf-8')); }
          catch { return null; }
        })
        .filter(Boolean);
    } else if (fs.existsSync(chatsFile)) {
      // Migrate legacy file to individual files
      try {
        const legacy = JSON.parse(fs.readFileSync(chatsFile, 'utf-8'));
        for (const c of legacy) {
          if (c && c.id) {
            try {
              fs.writeFileSync(chatPath(c.id), JSON.stringify(c), 'utf-8');
            } catch { /* migration best-effort */ }
          }
        }
        all = Array.isArray(legacy) ? legacy : [];
      } catch { all = []; }
    }
    if (since) {
      all = all.filter((c) => (c.updatedAt || 0) > since);
    }
    all.sort((a, b) => (b.updatedAt || 0) - (a.updatedAt || 0));
    const out = wantFull ? all : all.map(stripHeavy);
    return { data: out };
  }

  /**
   * POST /api/chats — legacy bulk save. Writes both per-chat files AND legacy file.
   *
   * @param {object[]} chats
   * @returns {{ok: true}}
   */
  function bulkSaveChats(chats) {
    if (!Array.isArray(chats)) throw new TypeError('bulkSaveChats: chats must be array');
    fs.mkdirSync(chatsDir, { recursive: true });
    for (const c of chats) {
      if (c && c.id) {
        fs.writeFileSync(chatPath(c.id), JSON.stringify(c), 'utf-8');
      }
    }
    fs.mkdirSync(path.dirname(chatsFile), { recursive: true });
    fs.writeFileSync(chatsFile, JSON.stringify(chats), 'utf-8');
    return { ok: true };
  }

  /**
   * GET /api/chats/:id — return raw JSON string (for sendJson passthrough).
   *
   * @param {string} chatId
   * @returns {{found:true, data:string} | {found:false}}
   */
  function getChatRaw(chatId) {
    if (!chatId) throw new TypeError('getChatRaw: chatId required');
    const fp = chatPath(chatId);
    if (!fs.existsSync(fp)) return { found: false };
    return { found: true, data: fs.readFileSync(fp, 'utf-8') };
  }

  /**
   * PUT/POST /api/chats/:id — guarded single-chat save.
   *
   * @param {string} chatId
   * @param {object} chat
   * @returns {{ok:true} | {ok:false, status:number, reason:string, body:object}}
   */
  function saveChat(chatId, chat) {
    if (!chatId) throw new TypeError('saveChat: chatId required');
    fs.mkdirSync(chatsDir, { recursive: true });
    const fp = chatPath(chatId);
    let existingMsgCount = null;

    if (fs.existsSync(fp)) {
      try {
        const existing = JSON.parse(fs.readFileSync(fp, 'utf-8'));
        existingMsgCount = Array.isArray(existing.messages) ? existing.messages.length : 0;
        const guard = checkChatOverwrite(existing, chat);
        if (!guard.ok) {
          warn('[chats] REFUSED', guard.reason, 'for', chatId, JSON.stringify(guard.body));
          return { ok: false, status: guard.status, reason: guard.reason, body: guard.body };
        }
      } catch { /* corrupt existing — let write proceed */ }
    }

    fs.writeFileSync(fp, JSON.stringify(chat), 'utf-8');

    // Visibility log: shrinking accepted writes (regression sentinel from 4/24 P0).
    try {
      const incomingCount = Array.isArray(chat.messages) ? chat.messages.length : 0;
      if (existingMsgCount != null && incomingCount < existingMsgCount) {
        warn('[chats] ACCEPTED-SHRINK', chatId,
          'existing=' + existingMsgCount, 'incoming=' + incomingCount);
      }
    } catch { /* logging is best-effort */ }

    return { ok: true };
  }

  /**
   * DELETE /api/chats/:id
   *
   * @param {string} chatId
   * @returns {{ok: true}}
   */
  function deleteChat(chatId) {
    if (!chatId) throw new TypeError('deleteChat: chatId required');
    const fp = chatPath(chatId);
    if (fs.existsSync(fp)) fs.unlinkSync(fp);
    return { ok: true };
  }

  return { listChats, bulkSaveChats, getChatRaw, saveChat, deleteChat };
}

module.exports = { createChatRepo };
