// tests/unit/mentionPopup.test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  filterMentionAgents, mentionItemsHtml,
} from '../../web/src/ui/mentionPopup.js';

const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

const AGENTS = [
  { id: 'climbing', name: '攀岩教练', mention: '@攀岩教练', emoji: '🧗', desc: '训练规划' },
  { id: 'finance',  name: '金融Agent', mention: '@金融Agent', emoji: '📊', desc: '股票' },
  { id: 'writer',   name: '写手',     mention: '@写手',     emoji: '✍️', desc: '文案' },
];

// ── filterMentionAgents ────────────────────────────────────────────

test('filterMentionAgents: empty filter → all (copy)', () => {
  const r = filterMentionAgents(AGENTS, '');
  assert.equal(r.length, 3);
  assert.notEqual(r, AGENTS, 'should be a fresh array');
});

test('filterMentionAgents: matches name substring', () => {
  const r = filterMentionAgents(AGENTS, '攀岩');
  assert.equal(r.length, 1);
  assert.equal(r[0].id, 'climbing');
});

test('filterMentionAgents: matches mention substring', () => {
  const r = filterMentionAgents(AGENTS, '@金融');
  assert.equal(r.length, 1);
  assert.equal(r[0].id, 'finance');
});

test('filterMentionAgents: matches id substring', () => {
  const r = filterMentionAgents(AGENTS, 'writ');
  assert.equal(r.length, 1);
  assert.equal(r[0].id, 'writer');
});

test('filterMentionAgents: no match → empty array', () => {
  const r = filterMentionAgents(AGENTS, 'nonexistent');
  assert.deepEqual(r, []);
});

test('filterMentionAgents: defensive — null inputs', () => {
  assert.deepEqual(filterMentionAgents(null, 'x'), []);
  assert.deepEqual(filterMentionAgents(undefined, 'x'), []);
  assert.equal(filterMentionAgents(AGENTS, null).length, 3);
});

test('filterMentionAgents: skips agents missing fields', () => {
  const r = filterMentionAgents([null, { mention: '@x' }, { name: 'y', mention: '@y' }], 'y');
  assert.equal(r.length, 1);
  assert.equal(r[0].name, 'y');
});

// ── mentionItemsHtml ───────────────────────────────────────────────

test('mentionItemsHtml: empty list → empty string', () => {
  assert.equal(mentionItemsHtml([], { escapeHtml: esc }), '');
  assert.equal(mentionItemsHtml(null, { escapeHtml: esc }), '');
});

test('mentionItemsHtml: first item gets .selected; others do not', () => {
  const html = mentionItemsHtml(AGENTS, { escapeHtml: esc });
  const sel = html.match(/mention-item selected/g) || [];
  assert.equal(sel.length, 1);
  // The .selected one must be the first (climbing)
  assert.match(html, /mention-item selected[\s\S]*?攀岩教练/);
});

test('mentionItemsHtml: each item has emoji + mention + desc', () => {
  const html = mentionItemsHtml(AGENTS, { escapeHtml: esc });
  assert.match(html, /🧗.*?@攀岩教练.*?训练规划/s);
  assert.match(html, /📊.*?@金融Agent.*?股票/s);
  assert.match(html, /✍️.*?@写手.*?文案/s);
});

test('mentionItemsHtml: data-mention attribute set', () => {
  const html = mentionItemsHtml(AGENTS, { escapeHtml: esc });
  assert.match(html, /data-mention="@攀岩教练"/);
});

test('mentionItemsHtml: skips entries without mention; preserves index-based selection', () => {
  const html = mentionItemsHtml(
    [{ name: 'no-mention' }, null, { name: 'ok', mention: '@ok', emoji: 'O', desc: 'd' }],
    { escapeHtml: esc },
  );
  // Only one item rendered (the third)
  assert.equal((html.match(/mention-item/g) || []).length, 1);
  // Index-2 origin → not 'selected' (caller is expected to pre-filter; this
  // matches the inline behavior we're replacing).
  assert.doesNotMatch(html, /mention-item selected/);
  assert.match(html, /data-mention="@ok"/);
});

test('mentionItemsHtml: XSS — desc/name escaped', () => {
  const html = mentionItemsHtml(
    [{ mention: '@x', name: 'X', emoji: '!', desc: '<script>alert(1)</script>' }],
    { escapeHtml: esc },
  );
  assert.doesNotMatch(html, /<script>alert/);
  assert.match(html, /&lt;script&gt;/);
});

test('mentionItemsHtml: XSS — quote in mention escaped in data attr', () => {
  const html = mentionItemsHtml(
    [{ mention: '@x" onerror="alert(1)', name: 'X', emoji: '!', desc: 'd' }],
    { escapeHtml: esc },
  );
  // raw double-quote must not break out of data-mention
  assert.doesNotMatch(html, /data-mention="@x" onerror/);
  assert.match(html, /&quot;/);
});
