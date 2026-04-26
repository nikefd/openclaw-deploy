// tests/unit/streamHandler.test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  parseStreamLine,
  extractDelta,
  appendDelta,
  splitBuffer,
} from '../../web/src/ui/streamHandler.js';

// ── parseStreamLine ──────────────────────────────────────────────

test('parseStreamLine: empty string → skip', () => {
  assert.deepEqual(parseStreamLine(''), { kind: 'skip' });
});

test('parseStreamLine: non-string input → skip', () => {
  assert.deepEqual(parseStreamLine(null), { kind: 'skip' });
  assert.deepEqual(parseStreamLine(undefined), { kind: 'skip' });
  assert.deepEqual(parseStreamLine(42), { kind: 'skip' });
});

test('parseStreamLine: line not starting with "data: " → skip', () => {
  assert.deepEqual(parseStreamLine('event: ping'), { kind: 'skip' });
  assert.deepEqual(parseStreamLine(': keepalive'), { kind: 'skip' });
  assert.deepEqual(parseStreamLine('id: 42'), { kind: 'skip' });
});

test('parseStreamLine: "data: [DONE]" → done', () => {
  assert.deepEqual(parseStreamLine('data: [DONE]'), { kind: 'done' });
});

test('parseStreamLine: valid JSON frame → frame', () => {
  const r = parseStreamLine('data: {"choices":[{"delta":{"content":"hi"}}]}');
  assert.equal(r.kind, 'frame');
  assert.equal(r.frame.choices[0].delta.content, 'hi');
});

test('parseStreamLine: role-only first frame (real-world example) → frame, no error', () => {
  // Captured from production stream 2026-04-26
  const line = 'data: {"id":"chatcmpl_abc","object":"chat.completion.chunk","created":1777194717,"model":"openclaw/opus","choices":[{"index":0,"delta":{"role":"assistant"}}]}';
  const r = parseStreamLine(line);
  assert.equal(r.kind, 'frame');
  // extractDelta will return null for this (no content), tested separately
});

test('parseStreamLine: invalid JSON → error', () => {
  const r = parseStreamLine('data: {not valid json');
  assert.equal(r.kind, 'error');
  assert.match(r.error.message, /invalid SSE frame JSON/);
});

test('parseStreamLine: server-proxy error frame → error', () => {
  // Real example from 2026-04-26 production: backend's idle-timeout finalizer
  const line = 'data: {"error":{"message":"upstream idle timeout (no data >30s)"}}';
  const r = parseStreamLine(line);
  assert.equal(r.kind, 'error');
  assert.equal(r.error.message, 'upstream idle timeout (no data >30s)');
});

test('parseStreamLine: error frame without message → falls back to "stream error"', () => {
  const r = parseStreamLine('data: {"error":{}}');
  assert.equal(r.kind, 'error');
  assert.equal(r.error.message, 'stream error');
});

test('parseStreamLine: data with extra spaces is preserved', () => {
  // 'data: ' (single space) is the SSE standard prefix; we treat it strictly
  const r = parseStreamLine('data:{"x":1}'); // no space → not matched
  assert.equal(r.kind, 'skip');
});

// ── extractDelta ─────────────────────────────────────────────────

test('extractDelta: standard content delta → string', () => {
  assert.equal(extractDelta({ choices: [{ delta: { content: 'hello' } }] }), 'hello');
});

test('extractDelta: role-only first frame → null (no content)', () => {
  // This is the key real-world case from 2026-04-26
  assert.equal(extractDelta({ choices: [{ delta: { role: 'assistant' } }] }), null);
});

test('extractDelta: empty content string → null', () => {
  assert.equal(extractDelta({ choices: [{ delta: { content: '' } }] }), null);
});

test('extractDelta: missing choices → null', () => {
  assert.equal(extractDelta({}), null);
  assert.equal(extractDelta({ choices: [] }), null);
  assert.equal(extractDelta({ choices: null }), null);
});

test('extractDelta: missing delta → null', () => {
  assert.equal(extractDelta({ choices: [{ finish_reason: 'stop' }] }), null);
});

test('extractDelta: non-string content (tool call delta) → null', () => {
  assert.equal(extractDelta({ choices: [{ delta: { tool_calls: [{}] } }] }), null);
});

test('extractDelta: garbage input → null, never throws', () => {
  assert.equal(extractDelta(null), null);
  assert.equal(extractDelta(undefined), null);
  assert.equal(extractDelta('not an object'), null);
  assert.equal(extractDelta(42), null);
});

test('extractDelta: extracts only choices[0] (matches existing send() behaviour)', () => {
  const frame = {
    choices: [
      { delta: { content: 'first' } },
      { delta: { content: 'second' } },
    ],
  };
  assert.equal(extractDelta(frame), 'first');
});

// ── appendDelta ──────────────────────────────────────────────────

test('appendDelta: first delta → isFirstDelta:true', () => {
  const r = appendDelta({ full: '', typingRemoved: false }, 'hi');
  assert.equal(r.state.full, 'hi');
  assert.equal(r.state.typingRemoved, true);
  assert.equal(r.isFirstDelta, true);
});

test('appendDelta: subsequent delta → isFirstDelta:false', () => {
  const r = appendDelta({ full: 'hi', typingRemoved: true }, ' there');
  assert.equal(r.state.full, 'hi there');
  assert.equal(r.state.typingRemoved, true);
  assert.equal(r.isFirstDelta, false);
});

test('appendDelta: handles missing state defensively', () => {
  const r = appendDelta(undefined, 'hi');
  assert.equal(r.state.full, 'hi');
  assert.equal(r.isFirstDelta, true);
});

test('appendDelta: handles non-string delta as empty', () => {
  const r = appendDelta({ full: 'hi', typingRemoved: true }, null);
  assert.equal(r.state.full, 'hi');
  assert.equal(r.isFirstDelta, false);
});

test('appendDelta: never mutates input state', () => {
  const before = { full: 'hi', typingRemoved: false };
  appendDelta(before, ' world');
  assert.deepEqual(before, { full: 'hi', typingRemoved: false });
});

// ── splitBuffer ──────────────────────────────────────────────────

test('splitBuffer: complete lines + trailing partial', () => {
  const r = splitBuffer('data: a\ndata: b\ndata: ');
  assert.deepEqual(r.lines, ['data: a', 'data: b']);
  assert.equal(r.remaining, 'data: ');
});

test('splitBuffer: ends with newline → empty remaining', () => {
  const r = splitBuffer('data: a\ndata: b\n');
  assert.deepEqual(r.lines, ['data: a', 'data: b']);
  assert.equal(r.remaining, '');
});

test('splitBuffer: no newline → all goes into remaining', () => {
  const r = splitBuffer('partial chunk');
  assert.deepEqual(r.lines, []);
  assert.equal(r.remaining, 'partial chunk');
});

test('splitBuffer: empty / non-string input', () => {
  assert.deepEqual(splitBuffer(''), { lines: [], remaining: '' });
  assert.deepEqual(splitBuffer(null), { lines: [], remaining: '' });
  assert.deepEqual(splitBuffer(undefined), { lines: [], remaining: '' });
});

// ── integration: full pipeline using real production trace ──────

test('integration: real production stream (2026-04-26 trace)', () => {
  // The exact 4-line trace 斌哥 pasted: role-only first, content, error, done
  const stream = [
    'data: {"id":"chatcmpl_abc","object":"chat.completion.chunk","created":1777194717,"model":"openclaw/opus","choices":[{"index":0,"delta":{"role":"assistant"}}]}',
    'data: {"id":"chatcmpl_abc","object":"chat.completion.chunk","created":1777194717,"model":"openclaw/opus","choices":[{"index":0,"delta":{"content":"继续推，先写测试："},"finish_reason":null}]}',
    'data: {"error":{"message":"upstream idle timeout (no data >30s)"}}',
    'data: [DONE]',
  ];

  let state = { full: '', typingRemoved: false };
  let firstDeltaSeen = false;
  let doneSeen = false;
  let errorSeen = null;

  for (const line of stream) {
    const parsed = parseStreamLine(line);
    if (parsed.kind === 'skip') continue;
    if (parsed.kind === 'done') { doneSeen = true; break; }
    if (parsed.kind === 'error') { errorSeen = parsed.error; break; }
    // kind === 'frame'
    const delta = extractDelta(parsed.frame);
    if (delta == null) continue;        // role-only first frame
    const r = appendDelta(state, delta);
    state = r.state;
    if (r.isFirstDelta) firstDeltaSeen = true;
  }

  // The error frame breaks the loop before [DONE], matching the real client experience
  assert.equal(state.full, '继续推，先写测试：');
  assert.equal(firstDeltaSeen, true);
  assert.equal(state.typingRemoved, true);
  assert.equal(doneSeen, false);
  assert.ok(errorSeen);
  assert.match(errorSeen.message, /upstream idle timeout/);
});

test('integration: clean stream without errors', () => {
  const stream = [
    'data: {"choices":[{"delta":{"role":"assistant"}}]}',
    'data: {"choices":[{"delta":{"content":"Hel"}}]}',
    'data: {"choices":[{"delta":{"content":"lo"}}]}',
    'data: {"choices":[{"delta":{"content":"!"},"finish_reason":"stop"}]}',
    'data: [DONE]',
  ];

  let state = { full: '', typingRemoved: false };
  let doneSeen = false;
  for (const line of stream) {
    const parsed = parseStreamLine(line);
    if (parsed.kind === 'done') { doneSeen = true; break; }
    if (parsed.kind !== 'frame') continue;
    const delta = extractDelta(parsed.frame);
    if (delta == null) continue;
    state = appendDelta(state, delta).state;
  }

  assert.equal(state.full, 'Hello!');
  assert.equal(doneSeen, true);
});
