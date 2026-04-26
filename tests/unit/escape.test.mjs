// tests/unit/escape.test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { esc } from '../../web/src/ui/escape.js';

test('esc: nullish → empty string', () => {
  assert.equal(esc(null), '');
  assert.equal(esc(undefined), '');
});

test('esc: empty input', () => {
  assert.equal(esc(''), '');
});

test('esc: plain text passes through', () => {
  assert.equal(esc('hello world'), 'hello world');
  assert.equal(esc('斌哥 是 北京 程序员'), '斌哥 是 北京 程序员');
});

test('esc: escapes < > &', () => {
  assert.equal(esc('<script>'), '&lt;script&gt;');
  assert.equal(esc('a & b'), 'a &amp; b');
  assert.equal(esc('<a href="x">'), '&lt;a href="x"&gt;');
});

test('esc: matches legacy DOM behaviour — quotes NOT escaped', () => {
  // The original helper used `div.textContent = ...; div.innerHTML`,
  // which leaves single/double quotes alone (text-node context).
  assert.equal(esc(`'`), `'`);
  assert.equal(esc(`"`), `"`);
  assert.equal(esc(`a'b"c`), `a'b"c`);
});

test('esc: ampersand is escaped only once', () => {
  // Important property: escaping is idempotent on already-encoded entities
  // only at the literal character level — we should never double-escape
  // an unrelated `&` again.
  assert.equal(esc('&amp;'), '&amp;amp;'); // legacy behaviour
});

test('esc: numeric / boolean inputs coerced to string', () => {
  assert.equal(esc(123), '123');
  assert.equal(esc(true), 'true');
  assert.equal(esc(false), 'false');
});

test('esc: combined edge cases', () => {
  assert.equal(esc('5 < 6 && 7 > 4'), '5 &lt; 6 &amp;&amp; 7 &gt; 4');
});
