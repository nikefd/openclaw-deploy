// services/file/lib/chatGuards.js
// Pure guards for PUT /api/chats/:id — decide whether an incoming chat snapshot
// should be allowed to overwrite the on-disk version, or rejected with 409.
//
// All three guards exist because of real production bugs we hit, captured in
// MEMORY.md (2026-04-24, 2026-04-25):
//
//   1. emptyOverwrite     — buggy clients sent stripped (no-message) snapshots
//                           that wiped the on-disk full chat.
//   2. streamingOverFinal — sendBeacon on `beforeunload` raced after the stream
//                           finalized, sending a stale `_streaming:true` snapshot
//                           on top of the now-finalized assistant message.
//   3. shrinkFinalized    — the 4/24 P0: a stale snapshot carried a much shorter
//                           assistant message that was clobbering the longer
//                           finalized one. Threshold is 20 chars (allow normal
//                           edits; block "long answer disappeared" regressions).
//
// Pure functions: (existing, incoming) -> {ok:true} | {ok:false, status, body}.

'use strict';

function lastMsg(chat) {
  if (!chat || !Array.isArray(chat.messages)) return null;
  return chat.messages[chat.messages.length - 1] || null;
}

function checkEmptyOverwrite(existing, incoming) {
  const existingLen = Array.isArray(existing?.messages) ? existing.messages.length : 0;
  const incomingLen = Array.isArray(incoming?.messages) ? incoming.messages.length : 0;
  if (existingLen > 0 && incomingLen === 0) {
    return {
      ok: false,
      status: 409,
      reason: 'empty-overwrite',
      body: { error: 'refusing to overwrite non-empty chat with empty', existingMessages: existingLen },
    };
  }
  return { ok: true };
}

function checkStreamingOverFinal(existing, incoming) {
  const prev = lastMsg(existing);
  const inc = lastMsg(incoming);
  if (
    prev && prev.role === 'assistant' && !prev._streaming &&
    inc && inc.role === 'assistant' && inc._streaming
  ) {
    return {
      ok: false,
      status: 409,
      reason: 'streaming-over-final',
      body: { error: 'refusing to overwrite finalized assistant with in-flight streaming snapshot' },
    };
  }
  return { ok: true };
}

function checkShrinkFinalized(existing, incoming, threshold = 20) {
  const prev = lastMsg(existing);
  const inc = lastMsg(incoming);
  if (
    prev && prev.role === 'assistant' && !prev._streaming &&
    inc && inc.role === 'assistant' &&
    typeof prev.content === 'string' && typeof inc.content === 'string' &&
    prev.content.length > inc.content.length + threshold
  ) {
    return {
      ok: false,
      status: 409,
      reason: 'shrink-finalized',
      body: {
        error: 'refusing to shrink finalized assistant message',
        prevLen: prev.content.length,
        incLen: inc.content.length,
      },
    };
  }
  return { ok: true };
}

// Run all guards in order; first failure wins.
function checkChatOverwrite(existing, incoming, opts = {}) {
  const guards = [checkEmptyOverwrite, checkStreamingOverFinal, checkShrinkFinalized];
  for (const g of guards) {
    const r = g === checkShrinkFinalized
      ? g(existing, incoming, opts.shrinkThreshold)
      : g(existing, incoming);
    if (!r.ok) return r;
  }
  return { ok: true };
}

module.exports = {
  checkChatOverwrite,
  checkEmptyOverwrite,
  checkStreamingOverFinal,
  checkShrinkFinalized,
};
