// tests/unit/file-appendAssistantReply.test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
const require = createRequire(import.meta.url);
const { appendAssistantReply } = require('../../services/file/lib/appendAssistantReply.js');

function tmpChatPath() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'oc-aar-'));
  return path.join(dir, 'chats', 'chat-X.json');
}

test('creates a fresh chat doc when file does not exist', () => {
  const p = tmpChatPath();
  const r = appendAssistantReply({ chatPath: p, chatId: 'chat-X', reply: 'hi there', now: 1000 });
  assert.equal(r.persisted, true);
  assert.equal(r.len, 'hi there'.length);
  const doc = JSON.parse(fs.readFileSync(p, 'utf-8'));
  assert.equal(doc.id, 'chat-X');
  assert.equal(doc.messages.length, 1);
  assert.deepEqual(doc.messages[0], { role: 'assistant', content: 'hi there' });
  assert.equal(doc.updatedAt, 1000);
});

test('appends to existing chat preserving prior messages', () => {
  const p = tmpChatPath();
  fs.mkdirSync(path.dirname(p), { recursive: true });
  fs.writeFileSync(p, JSON.stringify({
    id: 'chat-X', title: 't', messages: [{ role: 'user', content: 'q' }],
    createdAt: 50, updatedAt: 60,
  }));
  const r = appendAssistantReply({ chatPath: p, chatId: 'chat-X', reply: 'a', now: 999 });
  assert.equal(r.persisted, true);
  const doc = JSON.parse(fs.readFileSync(p, 'utf-8'));
  assert.equal(doc.messages.length, 2);
  assert.equal(doc.messages[1].content, 'a');
  assert.equal(doc.createdAt, 50, 'createdAt preserved');
  assert.equal(doc.updatedAt, 999);
});

test('dedup: skip when last message is same assistant content', () => {
  const p = tmpChatPath();
  fs.mkdirSync(path.dirname(p), { recursive: true });
  fs.writeFileSync(p, JSON.stringify({
    id: 'chat-X', messages: [
      { role: 'user', content: 'q' },
      { role: 'assistant', content: 'same' },
    ], createdAt: 1, updatedAt: 2,
  }));
  const r = appendAssistantReply({ chatPath: p, chatId: 'chat-X', reply: 'same', now: 7777 });
  assert.equal(r.persisted, false);
  assert.equal(r.len, 'same'.length);
  const doc = JSON.parse(fs.readFileSync(p, 'utf-8'));
  assert.equal(doc.messages.length, 2, 'no extra append');
  assert.equal(doc.updatedAt, 2, 'updatedAt unchanged on dedup');
});

test('different content from last assistant → still appends', () => {
  const p = tmpChatPath();
  fs.mkdirSync(path.dirname(p), { recursive: true });
  fs.writeFileSync(p, JSON.stringify({
    id: 'chat-X', messages: [{ role: 'assistant', content: 'old' }], updatedAt: 1,
  }));
  const r = appendAssistantReply({ chatPath: p, chatId: 'chat-X', reply: 'new', now: 5 });
  assert.equal(r.persisted, true);
  const doc = JSON.parse(fs.readFileSync(p, 'utf-8'));
  assert.equal(doc.messages.length, 2);
});

test('empty reply → no-op', () => {
  const p = tmpChatPath();
  const r = appendAssistantReply({ chatPath: p, chatId: 'chat-X', reply: '', now: 1 });
  assert.equal(r.persisted, false);
  assert.equal(r.len, 0);
  assert.equal(fs.existsSync(p), false);
});

test('non-string reply → no-op', () => {
  const p = tmpChatPath();
  const r = appendAssistantReply({ chatPath: p, chatId: 'chat-X', reply: null, now: 1 });
  assert.equal(r.persisted, false);
});

test('corrupt existing file → recovers by treating as fresh', () => {
  const p = tmpChatPath();
  fs.mkdirSync(path.dirname(p), { recursive: true });
  fs.writeFileSync(p, '{not valid json');
  const r = appendAssistantReply({ chatPath: p, chatId: 'chat-X', reply: 'ok', now: 100 });
  assert.equal(r.persisted, true);
  const doc = JSON.parse(fs.readFileSync(p, 'utf-8'));
  assert.equal(doc.id, 'chat-X');
  assert.equal(doc.messages.length, 1);
});

test('atomic write: no .tmp file lingers after success', () => {
  const p = tmpChatPath();
  appendAssistantReply({ chatPath: p, chatId: 'chat-X', reply: 'ok', now: 1 });
  assert.equal(fs.existsSync(p + '.tmp'), false);
});

test('throws on missing chatPath / chatId', () => {
  assert.throws(() => appendAssistantReply({ chatId: 'x', reply: 'y' }), /chatPath/);
  assert.throws(() => appendAssistantReply({ chatPath: '/tmp/x.json', reply: 'y' }), /chatId/);
});

test('default now uses real Date.now (smoke)', () => {
  const p = tmpChatPath();
  const before = Date.now();
  appendAssistantReply({ chatPath: p, chatId: 'chat-X', reply: 'hi' });
  const doc = JSON.parse(fs.readFileSync(p, 'utf-8'));
  assert.ok(doc.updatedAt >= before);
  assert.ok(doc.updatedAt <= Date.now() + 5);
});
