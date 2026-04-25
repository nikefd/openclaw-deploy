// services/file/lib/stripHeavy.js
// Strip large base64 payloads (images/attachments) from a chat for the
// summary list. Keeps message text for client-side search; marks messages
// so UI can lazy-load full content via the per-chat endpoint.
//
// Pure function — no I/O, no req/res. Safe to unit-test.

'use strict';

function stripHeavy(chat) {
  if (!chat || !Array.isArray(chat.messages)) return chat;
  let hadHeavy = false;
  const messages = chat.messages.map((m) => {
    if (!m || typeof m !== 'object') return m;
    const out = { ...m };
    let touched = false;

    if (Array.isArray(out.images) && out.images.length) {
      const n = out.images.length;
      out.images = Array(n).fill('[image]');
      touched = true;
    }
    if (Array.isArray(out.attachments) && out.attachments.length) {
      out.attachments = out.attachments.map((a) => {
        if (!a || typeof a !== 'object') return a;
        const { data, content, base64, ...rest } = a;
        if (data || content || base64) touched = true;
        return rest;
      });
    }
    if (typeof out.image === 'string' && out.image.length > 200) {
      out.image = '[image]';
      touched = true;
    }
    if (touched) {
      out._stripped = true;
      hadHeavy = true;
    }
    return out;
  });
  return hadHeavy ? { ...chat, messages, _stripped: true } : chat;
}

module.exports = { stripHeavy };
