// services/file/lib/parseChatJsonl.js
// Parse the tail of an OpenClaw agent JSONL session file and extract the
// last assistant message's text + streaming status.
//
// The file mixes two formats over time:
//   A) old:  {role:'assistant', content: '...'  | [{type:'text',text}...]}
//   B) new:  {type:'message', message:{role, content:[...]}, timestamp, stopReason}
//
// Both are tolerated; malformed lines are silently dropped.
// Pure: input string → {messages, lastAssistant, text, stopReason, isStreaming, ts}.

'use strict';

function parseLine(line) {
  let o;
  try { o = JSON.parse(line); } catch { return null; }
  if (!o || typeof o !== 'object') return null;
  // Format B: openclaw envelope
  if (o.type === 'message' && o.message && typeof o.message === 'object') {
    const role = o.message.role;
    if (role === 'assistant' || role === 'user') {
      return {
        role,
        content: o.message.content,
        stopReason: o.stopReason ?? o.message.stopReason ?? null,
        timestamp: o.timestamp ?? null,
      };
    }
    return null;
  }
  // Format A: bare role/content
  if (o.role === 'assistant' || o.role === 'user') {
    return {
      role: o.role,
      content: o.content,
      stopReason: o.stopReason ?? null,
      timestamp: o.timestamp ?? null,
    };
  }
  return null;
}

function extractText(content) {
  if (Array.isArray(content)) {
    return content
      .filter((c) => c && c.type === 'text' && typeof c.text === 'string')
      .map((c) => c.text)
      .join('');
  }
  if (typeof content === 'string') return content;
  return '';
}

function isStreamingStop(stopReason) {
  if (!stopReason) return true;                 // null/empty = still streaming
  if (stopReason === 'inFlight') return true;
  if (stopReason === 'streaming') return true;
  return false;
}

// Main entry. `bufText` is the decoded tail of the JSONL file.
function parseChatJsonl(bufText) {
  const lines = String(bufText || '').split('\n').filter(Boolean);
  const messages = [];
  for (const ln of lines) {
    const m = parseLine(ln);
    if (m) messages.push(m);
  }
  // Find last assistant
  let lastAssistant = null;
  for (let i = messages.length - 1; i >= 0; i--) {
    if (messages[i].role === 'assistant') { lastAssistant = messages[i]; break; }
  }
  let text = '';
  let stopReason = null;
  let isStreaming = false;
  let ts = null;
  if (lastAssistant) {
    stopReason = lastAssistant.stopReason || null;
    isStreaming = isStreamingStop(stopReason);
    text = extractText(lastAssistant.content);
    ts = lastAssistant.timestamp || null;
  }
  return { messages, lastAssistant, text, stopReason, isStreaming, ts };
}

module.exports = { parseChatJsonl, parseLine, extractText, isStreamingStop };
