// services/file/lib/chatStreamWriter.js
// Pure helpers for the /api/copilot/stream and /api/chat/send handlers.
// All side effects (fs, http) stay in server.js; this module just shapes data.
//
// Functions:
//   extractTextFromContent(content)   — string | text-part array → joined string
//   makeChatTitle(userText, max=30)   — truncate + ellipsis, fallback "新对话"
//   ensureChatShape(chat, opts)       — null | partial → valid chat object
//   updateAssistantInChat(chat, full, {done})
//                                     — append/update last assistant message
//                                       in-place (returns same chat ref)
//   isSameUserMessage(last, incoming) — dedup check before re-appending user msg
//
// All pure: same input → same output, no I/O.

'use strict';

function extractTextFromContent(content) {
  if (typeof content === 'string') return content;
  if (Array.isArray(content)) {
    return content
      .filter((c) => c && c.type === 'text' && typeof c.text === 'string')
      .map((c) => c.text)
      .join('');
  }
  return '';
}

function makeChatTitle(userText, max = 30) {
  const t = String(userText || '').trim();
  if (!t) return '新对话';
  return t.length > max ? t.slice(0, max) + '...' : t;
}

// Make sure a chat has all required fields. Returns the same object (mutated)
// if it was already a valid object; otherwise returns a fresh one.
function ensureChatShape(chat, { id, agentId = 'main', userText = '' } = {}) {
  if (!chat || typeof chat !== 'object') {
    return {
      id,
      title: makeChatTitle(userText),
      agentId,
      messages: [],
      createdAt: Date.now(),
    };
  }
  if (!Array.isArray(chat.messages)) chat.messages = [];
  // If existing chat has no title and is empty, backfill from userText.
  if (!chat.title && chat.messages.length === 0 && userText) {
    chat.title = makeChatTitle(userText);
  }
  return chat;
}

// Decide if `incoming` user message duplicates `last` (the last message in chat).
// Used to skip persisting the user msg when the previous push already wrote it.
function isSameUserMessage(last, incoming) {
  if (!last || !incoming) return false;
  if (last.role !== 'user' || incoming.role !== 'user') return false;
  // String content fast path
  if (typeof last.content === 'string' && typeof incoming.content === 'string') {
    return last.content === incoming.content;
  }
  // Fallback: structural equality via JSON
  try {
    return JSON.stringify(last.content) === JSON.stringify(incoming.content);
  } catch {
    return false;
  }
}

// Mutate chat in place to reflect the latest streamed assistant content.
// If the last message is an in-flight assistant (`_streaming`), update it.
// Otherwise push a new assistant message. When `done` is true, clear the
// _streaming flag.
//
// Returns the chat (same ref).
function updateAssistantInChat(chat, full, { done = false } = {}) {
  if (!chat || typeof chat !== 'object') {
    throw new Error('updateAssistantInChat: chat must be a non-null object');
  }
  if (!Array.isArray(chat.messages)) chat.messages = [];
  const last = chat.messages[chat.messages.length - 1];
  if (last && last.role === 'assistant' && last._streaming) {
    last.content = full;
    if (done) delete last._streaming;
  } else {
    const newMsg = { role: 'assistant', content: full };
    if (!done) newMsg._streaming = true;
    chat.messages.push(newMsg);
  }
  chat.updatedAt = Date.now();
  return chat;
}

module.exports = {
  extractTextFromContent,
  makeChatTitle,
  ensureChatShape,
  isSameUserMessage,
  updateAssistantInChat,
};
