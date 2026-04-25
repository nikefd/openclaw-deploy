// tests/unit/welcome.test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { welcomeHtml } from '../../web/src/ui/welcome.js';

const MAIN = { emoji: '🐶', name: '狗蛋', desc: '随和、直接、偶尔贱兮兮' };
const MENTIONS = [
  { emoji: '🧗', mention: '@攀岩教练' },
  { emoji: '💰', mention: '@金融Agent' },
];

test('welcomeHtml: empty/missing agent → still renders shell', () => {
  const html = welcomeHtml(null, []);
  assert.match(html, /class="welcome"/);
  assert.match(html, /<h2><\/h2>/);
});

test('welcomeHtml: renders agent emoji / name / desc', () => {
  const html = welcomeHtml(MAIN, []);
  assert.match(html, /🐶/);
  assert.match(html, /狗蛋/);
  assert.match(html, /随和、直接、偶尔贱兮兮/);
});

test('welcomeHtml: no mentions → no agents-hint block', () => {
  const html = welcomeHtml(MAIN, []);
  assert.ok(!html.includes('agents-hint'));
  assert.ok(!html.includes('输入 @ 切换角色'));
});

test('welcomeHtml: with mentions → renders hint + chips', () => {
  const html = welcomeHtml(MAIN, MENTIONS);
  assert.match(html, /agents-hint/);
  assert.match(html, /输入 @ 切换角色/);
  assert.match(html, /@攀岩教练/);
  assert.match(html, /@金融Agent/);
  // 2 chips
  const chips = (html.match(/<span onclick="insertMention/g) || []).length;
  assert.equal(chips, 2);
});

test('welcomeHtml: filters out agents missing .mention', () => {
  const mixed = [
    { emoji: '🧗', mention: '@攀岩教练' },
    { emoji: '🐶', mention: '' },
    { emoji: '🐱' }, // no mention key
  ];
  const html = welcomeHtml(MAIN, mixed);
  const chips = (html.match(/<span onclick="insertMention/g) || []).length;
  assert.equal(chips, 1);
});

test('welcomeHtml: HTML-escapes agent fields (defuse injection)', () => {
  const evil = { emoji: '<x>', name: '<script>alert(1)</script>', desc: '"&<>' };
  const html = welcomeHtml(evil, []);
  assert.ok(!html.includes('<script>alert(1)'));
  assert.match(html, /&lt;script&gt;alert\(1\)&lt;\/script&gt;/);
  assert.match(html, /&lt;x&gt;/);
});

test('welcomeHtml: HTML-escapes mention text (visible chip label)', () => {
  const evil = [{ emoji: '?', mention: '<img src=x>' }];
  const html = welcomeHtml(MAIN, evil);
  assert.match(html, /&lt;img src=x&gt;/);
  assert.ok(!html.includes('<img src=x>'));
});

test('welcomeHtml: defuses single-quote in mention (would break onclick)', () => {
  const evil = [{ emoji: '?', mention: "'); alert(1); ('" }];
  const html = welcomeHtml(MAIN, evil);
  // The raw closing quote must NOT appear unescaped right after insertMention('
  assert.ok(!/insertMention\('\); alert\(1\)/.test(html), 'raw quote must not break out');
});

test('welcomeHtml: returns single root .welcome div', () => {
  const html = welcomeHtml(MAIN, MENTIONS);
  const opens = (html.match(/<div class="welcome">/g) || []).length;
  assert.equal(opens, 1);
});

test('welcomeHtml: handles non-array mentionable input', () => {
  const html = welcomeHtml(MAIN, null);
  assert.ok(!html.includes('agents-hint'));
  const html2 = welcomeHtml(MAIN, undefined);
  assert.ok(!html2.includes('agents-hint'));
  const html3 = welcomeHtml(MAIN, 'nope');
  assert.ok(!html3.includes('agents-hint'));
});
