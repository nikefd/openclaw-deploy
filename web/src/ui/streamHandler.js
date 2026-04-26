// ui/streamHandler.js — pure logic for SSE stream frame parsing.
//
// Why this exists:
//   The send() function in index.html owned the full SSE pipeline:
//     - HTTP request + reader
//     - decode/buffer/split lines
//     - parse 'data: ...' frames
//     - dispatch deltas to DOM (removeTyping / appendMsg / textContent)
//     - performance logging
//     - error / recovery / typing animation
//   That single function grew to ~7 levels of nested try/catch on one
//   600-character line and produced 3 brace-counting bugs in 24h
//   (2026-04-26: SyntaxError twice + ReferenceError for undeclared `el`).
//
// The minimum-invasion fix: pull the *pure* parts out so they can be unit
// tested. DOM/network/recovery still live in index.html, but every branch
// that decides "is this a delta? a done marker? an error? skip?" goes
// through these functions.
//
// Contract:
//   - No DOM access, no fetch, no setTimeout, no globals.
//   - All inputs strings or plain objects; all outputs plain data.
//   - Errors are returned as values (kind:'error'), never thrown
//     (except parseStreamLine: synchronous JSON.parse can throw, we wrap it).

/**
 * Parse a single line of an SSE response body.
 *
 * Lines we expect to handle:
 *   - 'data: {...json...}'  → kind:'frame', frame:{...}
 *   - 'data: [DONE]'        → kind:'done'
 *   - ''                    → kind:'skip'  (blank between events)
 *   - 'event: ...'          → kind:'skip'  (we only consume 'data:' lines)
 *   - any line not starting 'data: ' → kind:'skip'
 *   - 'data: <invalid json>'→ kind:'error', error:Error
 *   - 'data: {error:{message:...}}' → kind:'error', error:Error  (server
 *     proxy can downstream {error:{...}} frames)
 *
 * @param {string} line
 * @returns {{kind:'skip'} | {kind:'done'} | {kind:'frame', frame:object} | {kind:'error', error:Error}}
 */
export function parseStreamLine(line) {
  if (typeof line !== 'string') return { kind: 'skip' };
  if (!line.startsWith('data: ')) return { kind: 'skip' };
  const data = line.slice(6);
  if (data === '[DONE]') return { kind: 'done' };
  let parsed;
  try {
    parsed = JSON.parse(data);
  } catch (e) {
    return { kind: 'error', error: new Error('invalid SSE frame JSON: ' + (e?.message || e)) };
  }
  if (parsed && typeof parsed === 'object' && parsed.error) {
    const msg = parsed.error?.message || 'stream error';
    return { kind: 'error', error: new Error(msg) };
  }
  return { kind: 'frame', frame: parsed };
}

/**
 * Extract the OpenAI-style delta text from a parsed frame.
 *
 * Frames look like: { choices:[{ delta:{ content:'...' }, finish_reason:null }] }
 * Returns null when there's no content (tool call only / first chunk role-only / etc).
 *
 * @param {any} frame
 * @returns {string|null}
 */
export function extractDelta(frame) {
  if (!frame || typeof frame !== 'object') return null;
  const choices = frame.choices;
  if (!Array.isArray(choices) || choices.length === 0) return null;
  const choice = choices[0];
  if (!choice || typeof choice !== 'object') return null;
  const delta = choice.delta;
  if (!delta || typeof delta !== 'object') return null;
  const content = delta.content;
  if (typeof content !== 'string' || content.length === 0) return null;
  return content;
}

/**
 * Reduce a delta string into the running stream state.
 *
 * Returns the new state plus an `isFirstDelta` flag; the caller uses that
 * to fire one-shot side effects (remove typing indicator, mount the
 * assistant bubble, log TTFT) without having to track the boolean itself.
 *
 * @param {{full:string, typingRemoved:boolean}} state
 * @param {string} delta
 * @returns {{state:{full:string, typingRemoved:boolean}, isFirstDelta:boolean}}
 */
export function appendDelta(state, delta) {
  const prevFull = (state && typeof state.full === 'string') ? state.full : '';
  const prevTypingRemoved = !!(state && state.typingRemoved);
  const safeDelta = typeof delta === 'string' ? delta : '';
  return {
    state: {
      full: prevFull + safeDelta,
      typingRemoved: true,
    },
    isFirstDelta: !prevTypingRemoved,
  };
}

/**
 * Split a decoder buffer on newlines and return {lines, remaining}.
 *
 * Mirrors the existing `buf.split('\\n'); buf=lines.pop();` pattern used in
 * send() — we keep the trailing partial line in `remaining` so the caller
 * can prepend it to the next decoded chunk.
 *
 * @param {string} buf
 * @returns {{lines:string[], remaining:string}}
 */
export function splitBuffer(buf) {
  const safe = typeof buf === 'string' ? buf : '';
  const parts = safe.split('\n');
  const remaining = parts.pop() ?? '';
  return { lines: parts, remaining };
}
