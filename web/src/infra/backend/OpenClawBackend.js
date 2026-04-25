// OpenClawBackend — concrete implementation of ChatBackend for OpenClaw.
//
// Streaming strategy: we use /api/copilot/stream (server-authoritative) — the
// Node proxy reads upstream SSE, writes chats/<id>.json to disk in real time,
// AND streams the same bytes back to us. If the browser disconnects mid-stream,
// the server keeps writing, so reload still works.
//
// This is the ONLY place that knows about SSE / OpenClaw URL shapes / the
// copilot stream proxy. Everything above calls `.stream()` and iterates.

import { ChatBackend } from './ChatBackend.js';
import { config, urls, resolveWireModel } from '../config.js';

export class OpenClawBackend extends ChatBackend {
  get name() { return 'openclaw'; }

  /**
   * Build the HTTP request to start a streaming completion. The UI does the
   * actual fetch + reader.read() because it needs to interleave perf timing,
   * visibility handling, and tool-pause detection. This method only owns the
   * URL/body shape — a Hermes backend would override only this.
   *
   * @param {Object} opts
   * @param {string} opts.chatId
   * @param {string} opts.modelId
   * @param {string} [opts.agentId]
   * @param {ChatMessage[]} opts.messages
   * @param {boolean} [opts.useKeepalive]
   * @returns {{ url: string, init: RequestInit }}
   */
  buildStreamRequest({ chatId, modelId, agentId, messages, useKeepalive }) {
    const body = JSON.stringify({
      chatId,
      model: resolveWireModel(modelId),
      messages,
      agentId: agentId || 'main',
    });
    return {
      url: config.api.copilotStream,
      init: {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body,
        ...(useKeepalive ? { keepalive: true } : {}),
      },
    };
  }

  // Convenience wrapper: build the request, iterate SSE, yield deltas.
  // Most call sites won't use this directly — they want fine control over
  // the reader loop. See buildStreamRequest for the lower-level path.
  async *stream({ chatId, modelId, agentId, messages, signal }) {
    const { url, init } = this.buildStreamRequest({ chatId, modelId, agentId, messages });
    const res = await fetch(url, { ...init, signal });

    if (!res.ok || !res.body) {
      yield { type: 'error', error: `HTTP ${res.status}` };
      return;
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buf = '';

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });

      // SSE: events separated by blank line; each event has "data: ..." lines.
      let idx;
      while ((idx = buf.indexOf('\n\n')) !== -1) {
        const raw = buf.slice(0, idx);
        buf = buf.slice(idx + 2);
        const data = raw.split('\n')
          .filter(l => l.startsWith('data:'))
          .map(l => l.slice(5).trim())
          .join('');
        if (!data) continue;
        if (data === '[DONE]') { yield { type: 'done' }; return; }
        try {
          const evt = JSON.parse(data);
          const text = evt?.choices?.[0]?.delta?.content;
          if (text) yield { type: 'text', text };
        } catch { /* skip malformed */ }
      }
    }
    yield { type: 'done' };
  }

  async loadHistory(chatId) {
    const r = await fetch(urls.chatOne(chatId));
    if (!r.ok) return [];
    const chat = await r.json();
    return chat?.messages || [];
  }

  // Like loadHistory but returns the full chat object (id, title, messages, ...).
  async getChat(chatId) {
    const r = await fetch(urls.chatOne(chatId));
    if (!r.ok) return null;
    return r.json();
  }

  async saveChat(chat) {
    const r = await fetch(urls.chatOne(chat.id), {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(chat),
    });
    return r.ok;
  }

  // Best-effort beacon save (used in beforeunload / streaming flush).
  // Falls back to a keepalive fetch if sendBeacon is not available.
  saveChatBeacon(chat) {
    try {
      const blob = new Blob([JSON.stringify(chat)], { type: 'application/json' });
      if (navigator.sendBeacon && navigator.sendBeacon(urls.chatOne(chat.id), blob)) return true;
    } catch {}
    try {
      fetch(urls.chatOne(chat.id), {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(chat),
        keepalive: true,
      }).catch(() => {});
      return true;
    } catch { return false; }
  }

  async loadAllChats() {
    const r = await fetch(config.api.chats);
    if (!r.ok) return [];
    return r.json();
  }

  // Incremental sync: fetch only chats updated since `sinceTs` (epoch ms).
  // Returns { chats, serverTime } so caller can use server's clock to avoid drift.
  async loadChatsSince(sinceTs) {
    const r = await fetch(`${config.api.chats}?since=${encodeURIComponent(sinceTs)}`, { cache: 'no-store' });
    if (!r.ok) return { chats: [], serverTime: null };
    const serverTime = r.headers.get('X-Server-Time');
    const chats = await r.json();
    return { chats: Array.isArray(chats) ? chats : [], serverTime };
  }

  async deleteChat(chatId) {
    return fetch(urls.chatOne(chatId), { method: 'DELETE' })
      .then(r => r.ok).catch(() => false);
  }

  // Server-side bulk reset (with backup). `chatsBackup` is sent so server can
  // archive before clearing.
  async clearAllChats(chatsBackup) {
    return fetch(config.api.chats, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Backup': 'true' },
      body: JSON.stringify(chatsBackup || []),
    }).then(r => r.ok).catch(() => false);
  }
}
