// tests/unit/chatSidebar.test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  groupLabel,
  groupHeaderHtml,
  chatItemHtml,
  emptyStateHtml,
} from '../../web/src/ui/chatSidebar.js';

// --- groupLabel ---------------------------------------------------------

test('groupLabel: search query overrides everything', () => {
  // Even if updatedAt is "today", a search context wins.
  const now = Date.parse('2026-04-25T12:00:00');
  assert.equal(groupLabel(now, now, true), '搜索结果');
});

test('groupLabel: same calendar day → "今天"', () => {
  const now = Date.parse('2026-04-25T12:00:00');
  const earlier = Date.parse('2026-04-25T01:30:00');
  assert.equal(groupLabel(earlier, now, false), '今天');
});

test('groupLabel: previous calendar day → "昨天"', () => {
  const now = Date.parse('2026-04-25T12:00:00');
  const y = Date.parse('2026-04-24T22:00:00');
  assert.equal(groupLabel(y, now, false), '昨天');
});

test('groupLabel: older date → locale month/day string', () => {
  const now = Date.parse('2026-04-25T12:00:00');
  const old = Date.parse('2026-03-01T12:00:00');
  const out = groupLabel(old, now, false, 'en-US');
  // "Mar 1" or "Mar 01" depending on engine — both acceptable.
  assert.match(out, /Mar/);
});

// --- groupHeaderHtml ----------------------------------------------------

test('groupHeaderHtml: renders label + escapes injection', () => {
  assert.match(groupHeaderHtml('今天'), /font-weight:600">今天</);
  const evil = groupHeaderHtml('<script>x</script>');
  assert.ok(!evil.includes('<script>x'));
  assert.match(evil, /&lt;script&gt;/);
});

// --- chatItemHtml -------------------------------------------------------

const AGENT = { emoji: '🐶', name: '狗蛋', color: '#fa0' };
const CHAT = { id: 'abc-123' };

test('chatItemHtml: renders core attrs', () => {
  const html = chatItemHtml(CHAT, AGENT, {
    isActive: false,
    isStreaming: false,
    titleHtml: 'Hello',
  });
  assert.match(html, /data-id="abc-123"/);
  assert.match(html, /background:#fa0/);
  assert.match(html, /🐶/);
  assert.match(html, /狗蛋/);
  assert.match(html, /class="title">Hello</);
  assert.match(html, /data-edit="abc-123"/);
  assert.match(html, /data-del="abc-123"/);
  assert.ok(!html.includes('data-jump-msg'));
  assert.ok(!html.includes('class="snippet"'));
});

test('chatItemHtml: active flag toggles "active" class', () => {
  const off = chatItemHtml(CHAT, AGENT, { isActive: false, titleHtml: 't' });
  assert.match(off, /class="chat-item "/);
  const on = chatItemHtml(CHAT, AGENT, { isActive: true, titleHtml: 't' });
  assert.match(on, /class="chat-item active"/);
});

test('chatItemHtml: streaming flag adds ⏳', () => {
  const html = chatItemHtml(CHAT, AGENT, { isStreaming: true, titleHtml: 'x' });
  assert.match(html, /class="title">x ⏳</);
});

test('chatItemHtml: snippet block only when provided', () => {
  const without = chatItemHtml(CHAT, AGENT, { titleHtml: 't', snippetHtml: '' });
  assert.ok(!without.includes('class="snippet"'));
  const withSnip = chatItemHtml(CHAT, AGENT, {
    titleHtml: 't',
    snippetHtml: 'hello <mark>world</mark>',
  });
  assert.match(withSnip, /class="snippet">hello <mark>world<\/mark></);
});

test('chatItemHtml: jumpMsgIdx adds data-jump-msg only when ≥ 0', () => {
  assert.ok(!chatItemHtml(CHAT, AGENT, { titleHtml: 't' }).includes('data-jump-msg'));
  assert.ok(!chatItemHtml(CHAT, AGENT, { titleHtml: 't', jumpMsgIdx: -1 }).includes('data-jump-msg'));
  const ok = chatItemHtml(CHAT, AGENT, { titleHtml: 't', jumpMsgIdx: 7 });
  assert.match(ok, /data-jump-msg="7"/);
});

test('chatItemHtml: titleHtml passes through (allows <mark> from highlight)', () => {
  const html = chatItemHtml(CHAT, AGENT, {
    titleHtml: 'foo <mark>bar</mark> baz',
  });
  assert.match(html, /foo <mark>bar<\/mark> baz/);
});

test('chatItemHtml: HTML-escapes chat.id (defuse attr injection)', () => {
  const evilChat = { id: 'a" onload="alert(1)' };
  const html = chatItemHtml(evilChat, AGENT, { titleHtml: 't' });
  assert.ok(!/data-id="a" onload="alert\(1\)/.test(html), 'raw quote must not break out');
  assert.match(html, /data-id="a&quot; onload=&quot;alert\(1\)"/);
});

test('chatItemHtml: HTML-escapes agent.color (defuse style injection)', () => {
  const evilAgent = { emoji: 'e', name: 'n', color: 'red"></div><script>alert(1)' };
  const html = chatItemHtml(CHAT, evilAgent, { titleHtml: 't' });
  assert.ok(!html.includes('<script>alert(1)'));
  assert.match(html, /background:red&quot;&gt;/);
});

test('chatItemHtml: HTML-escapes agent.emoji + name', () => {
  const evilAgent = { emoji: '<x>', name: '<y>', color: '#000' };
  const html = chatItemHtml(CHAT, evilAgent, { titleHtml: 't' });
  assert.match(html, /&lt;x&gt;/);
  assert.match(html, /&lt;y&gt;/);
});

test('chatItemHtml: handles missing chat / agent / ctx gracefully', () => {
  const html = chatItemHtml(null, null, null);
  assert.match(html, /class="chat-item "/);
  assert.match(html, /data-id=""/);
});

// --- emptyStateHtml -----------------------------------------------------

test('emptyStateHtml: no query → "暂无对话"', () => {
  assert.match(emptyStateHtml(''), /暂无对话/);
});

test('emptyStateHtml: with query → 未找到 + 引号包查询词', () => {
  const html = emptyStateHtml('foo');
  assert.match(html, /未找到匹配「foo」/);
});

test('emptyStateHtml: HTML-escapes the query (defuse injection)', () => {
  const html = emptyStateHtml('<script>x</script>');
  assert.ok(!html.includes('<script>x'));
  assert.match(html, /&lt;script&gt;/);
});
