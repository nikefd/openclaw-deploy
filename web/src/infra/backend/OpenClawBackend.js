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

  async *stream({ chatId, modelId, agentId, messages, signal }) {
    const payload = JSON.stringify({
      chatId,
      model: resolveWireModel(modelId),
      messages,
      agentId: agentId || 'main',
    });

    const res = await fetch(config.api.copilotStream, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: payload,
      signal,
    });

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

  async saveChat(chat) {
    const r = await fetch(urls.chatOne(chat.id), {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(chat),
    });
    return r.ok;
  }

  async loadAllChats() {
    const r = await fetch(config.api.chats);
    if (!r.ok) return [];
    return r.json();
  }

  async deleteChat(chatId) {
    return fetch(urls.chatOne(chatId), { method: 'DELETE' })
      .then(r => r.ok).catch(() => false);
  }
}
