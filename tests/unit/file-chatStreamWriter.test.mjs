// tests/unit/file-chatStreamWriter.test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const {
  extractTextFromContent,
  makeChatTitle,
  ensureChatShape,
  isSameUserMessage,
  updateAssistantInChat,
} = require('../../services/file/lib/chatStreamWriter.js');

// ── extractTextFromContent ─────────────────────────────────────────

test('extractTextFromContent: string passes through', () => {
  assert.equal(extractTextFromContent('hi'), 'hi');
  assert.equal(extractTextFromContent(''), '');
});

test('extractTextFromContent: array of text parts joined', () => {
  assert.equal(
    extractTextFromContent([{ type: 'text', text: 'a' }, { type: 'text', text: 'b' }]),
    'ab'
  );
});

test('extractTextFromContent: filters non-text and missing types', () => {
  assert.equal(
    extractTextFromContent([
      { type: 'text', text: 'A' },
      { type: 'tool_use', name: 'foo' },
      { type: 'image' },
      { text: 'no type' },
      null,
      { type: 'text', text: 'B' },
    ]),
    'AB'
  );
});

test('extractTextFromContent: non-string non-array → empty', () => {
  assert.equal(extractTextFromContent(null), '');
  assert.equal(extractTextFromContent(undefined), '');
  assert.equal(extractTextFromContent({}), '');
  assert.equal(extractTextFromContent(42), '');
});

// ── makeChatTitle ──────────────────────────────────────────────────

test('makeChatTitle: short text passes through', () => {
  assert.equal(makeChatTitle('hello'), 'hello');
});

test('makeChatTitle: truncates at 30 chars + ellipsis', () => {
  const t = makeChatTitle('a'.repeat(50));
  assert.equal(t, 'a'.repeat(30) + '...');
});

test('makeChatTitle: exactly 30 chars → no ellipsis', () => {
  assert.equal(makeChatTitle('a'.repeat(30)), 'a'.repeat(30));
});

test('makeChatTitle: empty/whitespace falls back to 新对话', () => {
  assert.equal(makeChatTitle(''), '新对话');
  assert.equal(makeChatTitle('   '), '新对话');
  assert.equal(makeChatTitle(null), '新对话');
  assert.equal(makeChatTitle(undefined), '新对话');
});

test('makeChatTitle: custom max', () => {
  assert.equal(makeChatTitle('a'.repeat(20), 10), 'a'.repeat(10) + '...');
});

// ── ensureChatShape ────────────────────────────────────────────────

test('ensureChatShape: null → fresh chat with userText title', () => {
  const c = ensureChatShape(null, { id: 'x', userText: 'hello world' });
  assert.equal(c.id, 'x');
  assert.equal(c.title, 'hello world');
  assert.equal(c.agentId, 'main');
  assert.deepEqual(c.messages, []);
  assert.ok(c.createdAt > 0);
});

test('ensureChatShape: null + custom agentId', () => {
  const c = ensureChatShape(null, { id: 'x', agentId: 'climbing', userText: '' });
  assert.equal(c.agentId, 'climbing');
  assert.equal(c.title, '新对话');
});

test('ensureChatShape: existing chat returned as-is (mutated)', () => {
  const orig = { id: 'x', title: 't', agentId: 'main', messages: [{ role: 'user', content: 'hi' }] };
  const c = ensureChatShape(orig, { id: 'x', userText: 'newer' });
  assert.equal(c, orig); // same ref
  assert.equal(c.title, 't'); // not overwritten
});

test('ensureChatShape: missing messages array filled', () => {
  const orig = { id: 'x', title: 't' };
  const c = ensureChatShape(orig, { id: 'x' });
  assert.deepEqual(c.messages, []);
});

test('ensureChatShape: title backfilled when empty + no msgs + has userText', () => {
  const c = ensureChatShape({ id: 'x', title: '', messages: [] }, { id: 'x', userText: 'first q' });
  assert.equal(c.title, 'first q');
});

test('ensureChatShape: title NOT backfilled when chat already has messages', () => {
  const c = ensureChatShape(
    { id: 'x', title: '', messages: [{ role: 'user', content: 'old' }] },
    { id: 'x', userText: 'new' }
  );
  assert.equal(c.title, ''); // preserved as-is
});

// ── isSameUserMessage ──────────────────────────────────────────────

test('isSameUserMessage: same string content → true', () => {
  assert.equal(
    isSameUserMessage({ role: 'user', content: 'hi' }, { role: 'user', content: 'hi' }),
    true
  );
});

test('isSameUserMessage: different string → false', () => {
  assert.equal(
    isSameUserMessage({ role: 'user', content: 'hi' }, { role: 'user', content: 'hello' }),
    false
  );
});

test('isSameUserMessage: same array content → true', () => {
  const arr = [{ type: 'text', text: 'hi' }];
  assert.equal(
    isSameUserMessage({ role: 'user', content: [...arr] }, { role: 'user', content: [...arr] }),
    true
  );
});

test('isSameUserMessage: last is assistant → false', () => {
  assert.equal(
    isSameUserMessage({ role: 'assistant', content: 'hi' }, { role: 'user', content: 'hi' }),
    false
  );
});

test('isSameUserMessage: null/undefined → false', () => {
  assert.equal(isSameUserMessage(null, { role: 'user', content: 'hi' }), false);
  assert.equal(isSameUserMessage({ role: 'user', content: 'hi' }, null), false);
});

// ── updateAssistantInChat ──────────────────────────────────────────

test('updateAssistantInChat: empty messages → push streaming msg', () => {
  const chat = { id: 'x', messages: [] };
  updateAssistantInChat(chat, 'partial');
  assert.equal(chat.messages.length, 1);
  assert.equal(chat.messages[0].role, 'assistant');
  assert.equal(chat.messages[0].content, 'partial');
  assert.equal(chat.messages[0]._streaming, true);
  assert.ok(chat.updatedAt > 0);
});

test('updateAssistantInChat: existing _streaming → update in place', () => {
  const chat = {
    id: 'x',
    messages: [
      { role: 'user', content: 'q' },
      { role: 'assistant', content: 'par', _streaming: true },
    ],
  };
  updateAssistantInChat(chat, 'partial');
  assert.equal(chat.messages.length, 2);
  assert.equal(chat.messages[1].content, 'partial');
  assert.equal(chat.messages[1]._streaming, true);
});

test('updateAssistantInChat: done=true clears _streaming flag', () => {
  const chat = {
    id: 'x',
    messages: [
      { role: 'user', content: 'q' },
      { role: 'assistant', content: 'par', _streaming: true },
    ],
  };
  updateAssistantInChat(chat, 'final', { done: true });
  assert.equal(chat.messages[1].content, 'final');
  assert.equal(chat.messages[1]._streaming, undefined);
});

test('updateAssistantInChat: last is finalized assistant → push NEW (not overwrite)', () => {
  const chat = {
    id: 'x',
    messages: [
      { role: 'user', content: 'q' },
      { role: 'assistant', content: 'old reply' }, // finalized, no _streaming
    ],
  };
  updateAssistantInChat(chat, 'new partial');
  assert.equal(chat.messages.length, 3);
  assert.equal(chat.messages[1].content, 'old reply'); // untouched
  assert.equal(chat.messages[2].content, 'new partial');
  assert.equal(chat.messages[2]._streaming, true);
});

test('updateAssistantInChat: last is user → push new assistant', () => {
  const chat = { id: 'x', messages: [{ role: 'user', content: 'q' }] };
  updateAssistantInChat(chat, 'reply', { done: true });
  assert.equal(chat.messages.length, 2);
  assert.equal(chat.messages[1].role, 'assistant');
  assert.equal(chat.messages[1]._streaming, undefined);
});

test('updateAssistantInChat: missing messages array fixed', () => {
  const chat = { id: 'x' };
  updateAssistantInChat(chat, 'r');
  assert.equal(chat.messages.length, 1);
});

test('updateAssistantInChat: returns same chat ref', () => {
  const chat = { id: 'x', messages: [] };
  const r = updateAssistantInChat(chat, 'r');
  assert.equal(r, chat);
});

test('updateAssistantInChat: throws on null chat (caller bug)', () => {
  assert.throws(() => updateAssistantInChat(null, 'r'));
});
