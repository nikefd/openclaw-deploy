// tests/unit/chat.test.mjs — domain/chat.js pure-function tests.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  genChatId, createChat, mergeChats, findChat, escapeHtml,
} from '../../web/src/domain/chat.js';

test('genChatId returns chat_<digits>_<6chars>', () => {
  const id = genChatId();
  assert.match(id, /^chat_\d+_[a-z0-9]{1,6}$/);
});

test('genChatId is unique across rapid calls', () => {
  const seen = new Set();
  for (let i = 0; i < 100; i++) seen.add(genChatId());
  assert.equal(seen.size, 100);
});

test('createChat defaults: 新对话 / main / empty messages', () => {
  const c = createChat();
  assert.equal(c.title, '新对话');
  assert.equal(c.agentId, 'main');
  assert.deepEqual(c.messages, []);
  assert.ok(c.createdAt > 0);
  assert.equal(c.createdAt, c.updatedAt);
  assert.match(c.id, /^chat_/);
});

test('createChat respects overrides', () => {
  const c = createChat({ title: 'hi', agentId: 'finance' });
  assert.equal(c.title, 'hi');
  assert.equal(c.agentId, 'finance');
});

test('mergeChats: newer updatedAt wins', () => {
  const local  = [{ id: 'a', updatedAt: 200, messages: ['LOCAL'] }];
  const remote = [{ id: 'a', updatedAt: 100, messages: ['REMOTE'] }];
  const out = mergeChats(local, remote);
  assert.equal(out.length, 1);
  assert.deepEqual(out[0].messages, ['LOCAL']);
});

test('mergeChats: remote wins when newer', () => {
  const local  = [{ id: 'a', updatedAt: 100, messages: ['LOCAL'] }];
  const remote = [{ id: 'a', updatedAt: 200, messages: ['REMOTE'] }];
  const out = mergeChats(local, remote);
  assert.deepEqual(out[0].messages, ['REMOTE']);
});

test('mergeChats: union and sort by updatedAt desc', () => {
  const local  = [{ id: 'a', updatedAt: 100 }, { id: 'b', updatedAt: 300 }];
  const remote = [{ id: 'c', updatedAt: 200 }];
  const out = mergeChats(local, remote);
  assert.deepEqual(out.map(c => c.id), ['b', 'c', 'a']);
});

test('mergeChats: tolerates null/undefined inputs', () => {
  assert.deepEqual(mergeChats(null, null), []);
  assert.deepEqual(mergeChats(undefined, []), []);
  assert.deepEqual(mergeChats([{ id: 'x', updatedAt: 1 }], null).length, 1);
});

test('mergeChats: skips items without id', () => {
  const out = mergeChats([{ id: 'a', updatedAt: 1 }, { updatedAt: 2 }], []);
  assert.equal(out.length, 1);
  assert.equal(out[0].id, 'a');
});

test('findChat: finds by id', () => {
  const list = [{ id: 'a' }, { id: 'b' }];
  assert.equal(findChat(list, 'b').id, 'b');
});

test('findChat: missing returns undefined; null list ok', () => {
  assert.equal(findChat([{ id: 'a' }], 'x'), undefined);
  assert.equal(findChat(null, 'a'), undefined);
});

test('escapeHtml: amps, lt, gt', () => {
  assert.equal(escapeHtml('<a>&"'), '&lt;a&gt;&amp;"');
});

test('escapeHtml: coerces non-strings', () => {
  assert.equal(escapeHtml(42), '42');
  assert.equal(escapeHtml(null), 'null');
});
