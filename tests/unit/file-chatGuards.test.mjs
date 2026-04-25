// tests/unit/file-chatGuards.test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const {
  checkChatOverwrite,
  checkEmptyOverwrite,
  checkStreamingOverFinal,
  checkShrinkFinalized,
} = require('../../services/file/lib/chatGuards.js');

// helpers ────────────────────────────────────────────────────────────
const u = (txt) => ({ role: 'user', content: txt });
const a = (txt, opts = {}) => ({ role: 'assistant', content: txt, ...opts });
const aStream = (txt) => a(txt, { _streaming: true });
const chat = (...msgs) => ({ id: 'x', messages: msgs });

// ── checkEmptyOverwrite ────────────────────────────────────────────

test('emptyOverwrite: existing has msgs + incoming empty → reject 409', () => {
  const r = checkEmptyOverwrite(chat(u('hi'), a('hello')), chat());
  assert.equal(r.ok, false);
  assert.equal(r.status, 409);
  assert.equal(r.reason, 'empty-overwrite');
  assert.equal(r.body.existingMessages, 2);
});

test('emptyOverwrite: both empty → ok (allow first save)', () => {
  assert.equal(checkEmptyOverwrite(chat(), chat()).ok, true);
});

test('emptyOverwrite: existing empty + incoming has msgs → ok (legit save)', () => {
  assert.equal(checkEmptyOverwrite(chat(), chat(u('hi'))).ok, true);
});

test('emptyOverwrite: both have msgs → ok', () => {
  assert.equal(checkEmptyOverwrite(chat(u('a'), a('b')), chat(u('a'), a('c'))).ok, true);
});

test('emptyOverwrite: missing messages array treated as empty', () => {
  assert.equal(checkEmptyOverwrite({}, {}).ok, true);
  assert.equal(checkEmptyOverwrite(chat(u('a')), {}).ok, false); // existing > 0, incoming = 0
});

// ── checkStreamingOverFinal ────────────────────────────────────────

test('streamingOverFinal: existing finalized assistant + incoming _streaming → reject', () => {
  const r = checkStreamingOverFinal(
    chat(u('hi'), a('done')),
    chat(u('hi'), aStream('partia'))
  );
  assert.equal(r.ok, false);
  assert.equal(r.status, 409);
  assert.equal(r.reason, 'streaming-over-final');
});

test('streamingOverFinal: existing _streaming + incoming finalized → ok (normal flow)', () => {
  const r = checkStreamingOverFinal(
    chat(u('hi'), aStream('partial')),
    chat(u('hi'), a('done'))
  );
  assert.equal(r.ok, true);
});

test('streamingOverFinal: both finalized → ok', () => {
  const r = checkStreamingOverFinal(
    chat(u('hi'), a('first')),
    chat(u('hi'), a('first edited'))
  );
  assert.equal(r.ok, true);
});

test('streamingOverFinal: both _streaming → ok (mid-stream debounce save)', () => {
  const r = checkStreamingOverFinal(
    chat(u('hi'), aStream('par')),
    chat(u('hi'), aStream('partial'))
  );
  assert.equal(r.ok, true);
});

test('streamingOverFinal: last role is user → ok (not an assistant turn)', () => {
  const r = checkStreamingOverFinal(chat(u('hi')), chat(u('hi'), u('hey')));
  assert.equal(r.ok, true);
});

// ── checkShrinkFinalized ───────────────────────────────────────────

test('shrinkFinalized: long finalized -> short incoming (>20 chars) → reject', () => {
  const long = 'x'.repeat(100);
  const short = 'x'.repeat(50);
  const r = checkShrinkFinalized(chat(u('hi'), a(long)), chat(u('hi'), a(short)));
  assert.equal(r.ok, false);
  assert.equal(r.status, 409);
  assert.equal(r.reason, 'shrink-finalized');
  assert.equal(r.body.prevLen, 100);
  assert.equal(r.body.incLen, 50);
});

test('shrinkFinalized: shrink within 20 chars threshold → ok (normal edit)', () => {
  // 100 vs 85 = 15 char shrink → allowed
  const r = checkShrinkFinalized(chat(a('x'.repeat(100))), chat(a('x'.repeat(85))));
  assert.equal(r.ok, true);
});

test('shrinkFinalized: existing _streaming → ok (mid-stream is allowed to be replaced)', () => {
  const r = checkShrinkFinalized(
    chat(aStream('long content here is a lot')),
    chat(a('short'))
  );
  assert.equal(r.ok, true);
});

test('shrinkFinalized: incoming longer → ok', () => {
  const r = checkShrinkFinalized(chat(a('short')), chat(a('much longer content now')));
  assert.equal(r.ok, true);
});

test('shrinkFinalized: array content (not string) → ok (skip check)', () => {
  // Array content not covered by this guard — defensive
  const r = checkShrinkFinalized(
    chat(a([{ type: 'text', text: 'long string '.repeat(20) }])),
    chat(a('short'))
  );
  assert.equal(r.ok, true);
});

test('shrinkFinalized: custom threshold honored', () => {
  // 100 vs 90 = 10 char shrink → with threshold=5, should reject
  const r = checkShrinkFinalized(
    chat(a('x'.repeat(100))),
    chat(a('x'.repeat(90))),
    5
  );
  assert.equal(r.ok, false);
});

// ── checkChatOverwrite (composition) ───────────────────────────────

test('checkChatOverwrite: empty overwrite wins over streaming check', () => {
  // Even if other conditions could match, empty fires first
  const r = checkChatOverwrite(
    chat(u('hi'), a('done')),
    chat() // empty
  );
  assert.equal(r.reason, 'empty-overwrite');
});

test('checkChatOverwrite: streaming-over-final beats shrink', () => {
  // Both could match, but streaming check is earlier
  const long = 'x'.repeat(100);
  const r = checkChatOverwrite(
    chat(u('hi'), a(long)), // finalized + long
    chat(u('hi'), aStream('x')) // streaming + much shorter
  );
  assert.equal(r.reason, 'streaming-over-final');
});

test('checkChatOverwrite: all-clear case → ok', () => {
  const r = checkChatOverwrite(
    chat(u('hi'), a('first')),
    chat(u('hi'), a('first edited a bit'))
  );
  assert.equal(r.ok, true);
});

test('checkChatOverwrite: real bug pattern from 4/24 (finalized long → stale short)', () => {
  // The exact incident this guard was added for
  const finalized = a('A long, well-finalized assistant reply with details and code blocks.');
  const stale = a('A long, well-fina'); // truncated stale snapshot
  const r = checkChatOverwrite(chat(u('q'), finalized), chat(u('q'), stale));
  assert.equal(r.ok, false);
  assert.equal(r.reason, 'shrink-finalized');
});

test('checkChatOverwrite: opts.shrinkThreshold passes through', () => {
  // 100 vs 90 = 10 chars shrink — default threshold 20 → ok, custom 5 → reject
  const r1 = checkChatOverwrite(chat(a('x'.repeat(100))), chat(a('x'.repeat(90))));
  assert.equal(r1.ok, true);
  const r2 = checkChatOverwrite(chat(a('x'.repeat(100))), chat(a('x'.repeat(90))), { shrinkThreshold: 5 });
  assert.equal(r2.ok, false);
});

test('checkChatOverwrite: defensive — null inputs do not crash', () => {
  // Guards should treat null safely (existing not-yet-existing, incoming malformed)
  // If we ever pass null existing, all guards should pass (no on-disk version to protect)
  const r = checkChatOverwrite({ messages: null }, { messages: null });
  assert.equal(r.ok, true);
});
