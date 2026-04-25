// tests/unit/file-parseChatJsonl.test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const {
  parseChatJsonl,
  parseLine,
  extractText,
  isStreamingStop,
} = require('../../services/file/lib/parseChatJsonl.js');

// ────── parseLine ──────

test('parseLine: format A (bare role/content) — assistant', () => {
  const m = parseLine('{"role":"assistant","content":"hello","stopReason":"endTurn","timestamp":123}');
  assert.equal(m.role, 'assistant');
  assert.equal(m.content, 'hello');
  assert.equal(m.stopReason, 'endTurn');
  assert.equal(m.timestamp, 123);
});

test('parseLine: format B (openclaw envelope) — assistant array content', () => {
  const m = parseLine(JSON.stringify({
    type: 'message',
    timestamp: 999,
    stopReason: 'endTurn',
    message: { role: 'assistant', content: [{ type: 'text', text: 'hi' }] },
  }));
  assert.equal(m.role, 'assistant');
  assert.deepEqual(m.content, [{ type: 'text', text: 'hi' }]);
  assert.equal(m.stopReason, 'endTurn');
  assert.equal(m.timestamp, 999);
});

test('parseLine: format B falls back to message.stopReason if envelope has none', () => {
  const m = parseLine(JSON.stringify({
    type: 'message',
    message: { role: 'assistant', content: 'x', stopReason: 'inFlight' },
  }));
  assert.equal(m.stopReason, 'inFlight');
});

test('parseLine: ignores tool/system/unknown roles', () => {
  assert.equal(parseLine('{"role":"tool","content":"x"}'), null);
  assert.equal(parseLine('{"role":"system","content":"x"}'), null);
  assert.equal(parseLine(JSON.stringify({
    type: 'message',
    message: { role: 'tool', content: 'x' },
  })), null);
});

test('parseLine: malformed JSON returns null (no throw)', () => {
  assert.equal(parseLine('{not json'), null);
  assert.equal(parseLine(''), null);
  assert.equal(parseLine('null'), null);
  assert.equal(parseLine('42'), null);
});

test('parseLine: type=message but no message field → null', () => {
  assert.equal(parseLine('{"type":"message"}'), null);
});

// ────── extractText ──────

test('extractText: string content passes through', () => {
  assert.equal(extractText('hello'), 'hello');
});

test('extractText: array of text parts joined', () => {
  assert.equal(
    extractText([{ type: 'text', text: 'a' }, { type: 'text', text: 'b' }]),
    'ab'
  );
});

test('extractText: filters non-text parts (tool_use, image, etc)', () => {
  assert.equal(
    extractText([
      { type: 'text', text: 'before ' },
      { type: 'tool_use', name: 'foo' },
      { type: 'image' },
      { type: 'text', text: 'after' },
    ]),
    'before after'
  );
});

test('extractText: handles missing/wrong types safely', () => {
  assert.equal(extractText(null), '');
  assert.equal(extractText(undefined), '');
  assert.equal(extractText({}), '');
  assert.equal(extractText(42), '');
  assert.equal(extractText([null, { text: 'no type' }]), '');
});

// ────── isStreamingStop ──────

test('isStreamingStop: null/empty/undefined → still streaming', () => {
  assert.equal(isStreamingStop(null), true);
  assert.equal(isStreamingStop(undefined), true);
  assert.equal(isStreamingStop(''), true);
});

test('isStreamingStop: inFlight/streaming → still streaming', () => {
  assert.equal(isStreamingStop('inFlight'), true);
  assert.equal(isStreamingStop('streaming'), true);
});

test('isStreamingStop: any final reason → done', () => {
  assert.equal(isStreamingStop('endTurn'), false);
  assert.equal(isStreamingStop('stopSequence'), false);
  assert.equal(isStreamingStop('maxTokens'), false);
  assert.equal(isStreamingStop('error'), false);
});

// ────── parseChatJsonl integration ──────

test('parseChatJsonl: empty buffer returns empty result', () => {
  const r = parseChatJsonl('');
  assert.deepEqual(r.messages, []);
  assert.equal(r.lastAssistant, null);
  assert.equal(r.text, '');
  assert.equal(r.stopReason, null);
  assert.equal(r.isStreaming, false);
  assert.equal(r.ts, null);
});

test('parseChatJsonl: mixed format A + B, picks last assistant', () => {
  const lines = [
    '{"role":"user","content":"hi"}',
    '{"type":"message","timestamp":1,"message":{"role":"assistant","content":[{"type":"text","text":"first"}]},"stopReason":"endTurn"}',
    '{"role":"user","content":"again"}',
    '{"type":"message","timestamp":2,"message":{"role":"assistant","content":[{"type":"text","text":"second"}]},"stopReason":"inFlight"}',
  ].join('\n');
  const r = parseChatJsonl(lines);
  assert.equal(r.text, 'second');
  assert.equal(r.stopReason, 'inFlight');
  assert.equal(r.isStreaming, true);
  assert.equal(r.ts, 2);
  assert.equal(r.messages.length, 4);
});

test('parseChatJsonl: tolerates a torn line at the start (tail-read scenario)', () => {
  // Simulating reading from stat.size-65536: first line might be truncated mid-JSON.
  const lines = [
    '{"role":"assistant","content":"trunca',
    '{"type":"message","timestamp":5,"message":{"role":"assistant","content":"good"},"stopReason":"endTurn"}',
  ].join('\n');
  const r = parseChatJsonl(lines);
  assert.equal(r.text, 'good');
  assert.equal(r.stopReason, 'endTurn');
  assert.equal(r.isStreaming, false);
});

test('parseChatJsonl: only user messages → no assistant', () => {
  const lines = [
    '{"role":"user","content":"a"}',
    '{"role":"user","content":"b"}',
  ].join('\n');
  const r = parseChatJsonl(lines);
  assert.equal(r.lastAssistant, null);
  assert.equal(r.text, '');
  assert.equal(r.isStreaming, false);
  assert.equal(r.messages.length, 2);
});

test('parseChatJsonl: skips blank lines and noise', () => {
  const lines = [
    '',
    'garbage',
    '{"role":"assistant","content":"clean","stopReason":"endTurn"}',
    '',
    '{not json}',
  ].join('\n');
  const r = parseChatJsonl(lines);
  assert.equal(r.text, 'clean');
  assert.equal(r.messages.length, 1);
});

test('parseChatJsonl: format-B with string content (real openclaw legacy data)', () => {
  const r = parseChatJsonl(JSON.stringify({
    type: 'message',
    message: { role: 'assistant', content: 'plain string' },
    stopReason: 'endTurn',
  }));
  assert.equal(r.text, 'plain string');
});

test('parseChatJsonl: handles non-string input gracefully', () => {
  assert.deepEqual(parseChatJsonl(null).messages, []);
  assert.deepEqual(parseChatJsonl(undefined).messages, []);
});
