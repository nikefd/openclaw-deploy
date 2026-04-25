// tests/unit/file-dispatchStore.test.mjs
import { test, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const dispatch = require('../../services/file/lib/dispatchStore.js');

beforeEach(() => dispatch._reset());

test('markPending sets status=pending with startedAt + null error/httpStatus', () => {
  const rec = dispatch.markPending('chat-A', { startedAt: 1000 });
  assert.equal(rec.status, 'pending');
  assert.equal(rec.startedAt, 1000);
  assert.equal(rec.error, null);
  assert.equal(rec.httpStatus, null);
  assert.deepEqual(dispatch.get('chat-A'), rec);
});

test('markPending defaults startedAt to now', () => {
  const before = Date.now();
  const rec = dispatch.markPending('chat-A');
  assert.ok(rec.startedAt >= before);
  assert.ok(rec.startedAt <= Date.now() + 5);
});

test('markDone after pending → status=done, preserves startedAt, sets httpStatus + endedAt', () => {
  dispatch.markPending('chat-A', { startedAt: 100 });
  const rec = dispatch.markDone('chat-A', { httpStatus: 200, endedAt: 500 });
  assert.equal(rec.status, 'done');
  assert.equal(rec.startedAt, 100);
  assert.equal(rec.httpStatus, 200);
  assert.equal(rec.endedAt, 500);
});

test('markDone on unknown chatId still creates record (defensive)', () => {
  const rec = dispatch.markDone('ghost', { httpStatus: 200, endedAt: 1 });
  assert.equal(rec.status, 'done');
  assert.equal(rec.httpStatus, 200);
  assert.equal(dispatch.get('ghost').status, 'done');
});

test('markError sets status=error + error + endedAt', () => {
  dispatch.markPending('chat-A');
  const rec = dispatch.markError('chat-A', { error: 'boom', endedAt: 9 });
  assert.equal(rec.status, 'error');
  assert.equal(rec.error, 'boom');
  assert.equal(rec.endedAt, 9);
});

test('markError can carry httpStatus (HTTP 4xx/5xx case)', () => {
  dispatch.markPending('chat-A');
  const rec = dispatch.markError('chat-A', { error: 'HTTP 500: oops', httpStatus: 500 });
  assert.equal(rec.status, 'error');
  assert.equal(rec.httpStatus, 500);
  assert.equal(rec.error, 'HTTP 500: oops');
});

test('markError without httpStatus does not nuke a previously-set httpStatus', () => {
  dispatch.markPending('chat-A');
  dispatch.markDone('chat-A', { httpStatus: 200 });
  // weird sequence but defensive: if a later error fires (e.g. timeout after done),
  // we shouldn't blow away the httpStatus we already recorded.
  const rec = dispatch.markError('chat-A', { error: 'late timeout' });
  assert.equal(rec.status, 'error');
  assert.equal(rec.httpStatus, 200);
});

test('get returns null for unknown chatId', () => {
  assert.equal(dispatch.get('nope'), null);
});

test('get / mark return null for falsy chatId', () => {
  assert.equal(dispatch.markPending(''), null);
  assert.equal(dispatch.markDone(null), null);
  assert.equal(dispatch.markError(undefined, { error: 'x' }), null);
  assert.equal(dispatch.get(''), null);
});

test('multiple chatIds tracked independently', () => {
  dispatch.markPending('A');
  dispatch.markPending('B');
  dispatch.markDone('A', { httpStatus: 200 });
  dispatch.markError('B', { error: 'boom' });
  assert.equal(dispatch.get('A').status, 'done');
  assert.equal(dispatch.get('B').status, 'error');
});

test('writes go through global.__chatDispatch (history handler reads this)', () => {
  dispatch.markPending('chat-X', { startedAt: 42 });
  assert.equal(global.__chatDispatch['chat-X'].status, 'pending');
  assert.equal(global.__chatDispatch['chat-X'].startedAt, 42);
});

test('_reset clears the global store', () => {
  dispatch.markPending('A');
  dispatch._reset();
  assert.equal(dispatch.get('A'), null);
  assert.deepEqual(global.__chatDispatch, {});
});
