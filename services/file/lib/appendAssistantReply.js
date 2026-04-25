// services/file/lib/appendAssistantReply.js
// Persist a non-streaming assistant reply to a chat file.
//
// Used by /api/chat/send after the gateway round-trip finishes. Unlike the
// streaming path (which updates an in-flight assistant message in place via
// chatStreamWriter.updateAssistantInChat), this path appends a fresh, complete
// assistant message in one shot.
//
// Behavior:
//   - Reads existing chat doc (if any); falls back to a fresh empty doc.
//   - ensureChatShape via chatStreamWriter so missing fields are filled in.
//   - Dedup: if the last message is already an assistant with the same content,
//     do nothing (returns persisted:false). Prevents double-writes if the
//     handler is somehow invoked twice for the same response.
//   - Appends {role:'assistant', content:reply}, bumps updatedAt.
//   - Atomic write: tmp file + rename.
//
// Returns: { persisted: boolean, len: number }
//   persisted=false means the dedup branch hit — caller can skip log noise.
//
// I/O happens inside (fs read + atomic write). This is the only "impure"
// extracted helper, but isolating it lets us unit-test against tmp dirs.

'use strict';

const fs = require('fs');
const path = require('path');
const { ensureChatShape } = require('./chatStreamWriter');

function appendAssistantReply({ chatPath, chatId, reply, now = Date.now() }) {
  if (!chatPath || !chatId) throw new Error('chatPath and chatId are required');
  if (typeof reply !== 'string' || reply.length === 0) {
    return { persisted: false, len: 0 };
  }

  fs.mkdirSync(path.dirname(chatPath), { recursive: true });

  let chatDoc = null;
  try {
    chatDoc = JSON.parse(fs.readFileSync(chatPath, 'utf-8'));
  } catch {
    chatDoc = null;
  }

  chatDoc = ensureChatShape(chatDoc, { id: chatId });
  if (!chatDoc.createdAt) chatDoc.createdAt = now;

  const last = chatDoc.messages[chatDoc.messages.length - 1];
  if (last && last.role === 'assistant' && last.content === reply) {
    return { persisted: false, len: reply.length };
  }

  chatDoc.messages.push({ role: 'assistant', content: reply });
  chatDoc.updatedAt = now;

  const tmp = chatPath + '.tmp';
  fs.writeFileSync(tmp, JSON.stringify(chatDoc), 'utf-8');
  fs.renameSync(tmp, chatPath);

  return { persisted: true, len: reply.length };
}

module.exports = { appendAssistantReply };
