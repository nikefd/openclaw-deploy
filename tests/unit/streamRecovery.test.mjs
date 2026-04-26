// tests/unit/streamRecovery.test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  shouldRecover,
  createStreamRecovery,
} from '../../web/src/ui/streamRecovery.js';

// ── shouldRecover ───────────────────────────────────────────────

test('shouldRecover: nothing → false', () => {
  assert.equal(shouldRecover(null), false);
  assert.equal(shouldRecover(undefined), false);
  assert.equal(shouldRecover({}), false);
});

test('shouldRecover: hidden tab → false', () => {
  assert.equal(shouldRecover({
    isVisible:()=>false,
    isStreaming:()=>true,
    getLastChunkAt:()=>0,
    getNow:()=>999_999,
    staleThresholdMs:60_000,
  }), false);
});

test('shouldRecover: not streaming → false', () => {
  assert.equal(shouldRecover({
    isVisible:()=>true,
    isStreaming:()=>false,
    getLastChunkAt:()=>0,
    getNow:()=>999_999,
    staleThresholdMs:60_000,
  }), false);
});

test('shouldRecover: gap below threshold → false', () => {
  assert.equal(shouldRecover({
    isVisible:()=>true,
    isStreaming:()=>true,
    getLastChunkAt:()=>1000,
    getNow:()=>2000,             // 1s gap
    staleThresholdMs:60_000,
  }), false);
});

test('shouldRecover: gap exactly at threshold → true', () => {
  assert.equal(shouldRecover({
    isVisible:()=>true,
    isStreaming:()=>true,
    getLastChunkAt:()=>0,
    getNow:()=>60_000,
    staleThresholdMs:60_000,
  }), true);
});

test('shouldRecover: gap well above threshold → true', () => {
  assert.equal(shouldRecover({
    isVisible:()=>true,
    isStreaming:()=>true,
    getLastChunkAt:()=>0,
    getNow:()=>120_000,
    staleThresholdMs:60_000,
  }), true);
});

test('shouldRecover: NaN time inputs → false (defensive)', () => {
  assert.equal(shouldRecover({
    isVisible:()=>true,
    isStreaming:()=>true,
    getLastChunkAt:()=>NaN,
    getNow:()=>120_000,
    staleThresholdMs:60_000,
  }), false);
});

test('shouldRecover: negative threshold → false', () => {
  assert.equal(shouldRecover({
    isVisible:()=>true,
    isStreaming:()=>true,
    getLastChunkAt:()=>0,
    getNow:()=>120_000,
    staleThresholdMs:-1,
  }), false);
});

// ── createStreamRecovery ────────────────────────────────────────

test('createStreamRecovery: missing onStale → throws', () => {
  assert.throws(()=>createStreamRecovery({}), /onStale/);
  assert.throws(()=>createStreamRecovery({onStale:'nope'}), /onStale/);
});

test('createStreamRecovery: fires onStale once when conditions met', () => {
  let now = 0;
  let visible = true;
  let streaming = true;
  let lastChunk = 0;
  let fireCount = 0;

  const rec = createStreamRecovery({
    isVisible:()=>visible,
    isStreaming:()=>streaming,
    getLastChunkAt:()=>lastChunk,
    getNow:()=>now,
    staleThresholdMs:60_000,
    onStale:()=>{fireCount++;},
  });

  // gap 30s → no fire
  now = 30_000;
  assert.equal(rec.check(), false);
  assert.equal(fireCount, 0);
  assert.equal(rec.hasFired(), false);

  // gap 70s → fire
  now = 70_000;
  assert.equal(rec.check(), true);
  assert.equal(fireCount, 1);
  assert.equal(rec.hasFired(), true);

  // 再调一次 → 不重复 fire
  now = 200_000;
  assert.equal(rec.check(), false);
  assert.equal(fireCount, 1);
});

test('createStreamRecovery: hidden tab never fires even if stale', () => {
  let now = 0;
  let fireCount = 0;
  const rec = createStreamRecovery({
    isVisible:()=>false,
    isStreaming:()=>true,
    getLastChunkAt:()=>0,
    getNow:()=>now,
    staleThresholdMs:60_000,
    onStale:()=>{fireCount++;},
  });
  now = 999_999;
  assert.equal(rec.check(), false);
  assert.equal(fireCount, 0);
});

test('createStreamRecovery: streaming flips false → no fire', () => {
  let streaming = true;
  let fireCount = 0;
  const rec = createStreamRecovery({
    isVisible:()=>true,
    isStreaming:()=>streaming,
    getLastChunkAt:()=>0,
    getNow:()=>120_000,
    staleThresholdMs:60_000,
    onStale:()=>{fireCount++;},
  });
  streaming = false;
  assert.equal(rec.check(), false);
  assert.equal(fireCount, 0);
});

test('createStreamRecovery: onStale throws → check still returns true, no rethrow', () => {
  const rec = createStreamRecovery({
    isVisible:()=>true,
    isStreaming:()=>true,
    getLastChunkAt:()=>0,
    getNow:()=>120_000,
    staleThresholdMs:60_000,
    onStale:()=>{throw new Error('boom');},
  });
  // 不抛
  assert.equal(rec.check(), true);
  assert.equal(rec.hasFired(), true);
});

test('createStreamRecovery: onVisibilityChange === check', () => {
  let fired = 0;
  const rec = createStreamRecovery({
    isVisible:()=>true,
    isStreaming:()=>true,
    getLastChunkAt:()=>0,
    getNow:()=>120_000,
    staleThresholdMs:60_000,
    onStale:()=>{fired++;},
  });
  rec.onVisibilityChange();
  assert.equal(fired, 1);
});

test('createStreamRecovery: default threshold = 60_000', () => {
  let fired = 0;
  const rec = createStreamRecovery({
    isVisible:()=>true,
    isStreaming:()=>true,
    getLastChunkAt:()=>0,
    getNow:()=>59_999,
    onStale:()=>{fired++;},
  });
  assert.equal(rec.check(), false);
  assert.equal(fired, 0);
});
