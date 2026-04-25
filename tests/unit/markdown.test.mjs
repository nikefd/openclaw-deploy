// tests/unit/markdown.test.mjs — DOM-touching helpers, smoke level only.
//
// renderMd uses document/window.marked. We stub the bare minimum so the
// no-marked fallback path runs and produces escaped output.
import { test } from 'node:test';
import assert from 'node:assert/strict';

// --- minimal DOM stub for escDom() ---
class StubEl {
  constructor() { this._tc = ''; }
  set textContent(v) { this._tc = v == null ? '' : String(v); }
  get textContent() { return this._tc; }
  // mimic browser innerHTML escape for textContent
  get innerHTML() {
    return this._tc
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }
}
globalThis.document = { createElement: () => new StubEl() };
globalThis.window = {}; // no marked → triggers fallback path

const { escDom, renderMd } = await import('../../web/src/ui/markdown.js');

test('escDom: tags are escaped', () => {
  assert.equal(escDom('<a>'), '&lt;a&gt;');
});

test('escDom: null → empty string', () => {
  assert.equal(escDom(null), '');
});

test('escDom: numbers coerced', () => {
  assert.equal(escDom(42), '42');
});

test('renderMd: empty input → empty', () => {
  assert.equal(renderMd(''), '');
  assert.equal(renderMd(null), '');
});

test('renderMd: no marked → escapes as plain text (fallback path)', () => {
  // window.marked undefined → renderMd should return escDom(text)
  const out = renderMd('<script>x</script>');
  assert.match(out, /&lt;script&gt;/);
});

test('renderMd: with marked → uses it and adds copy button to <pre><code>', () => {
  globalThis.window.marked = {
    parse: (s) => `<pre><code>${s}</code></pre>`,
  };
  const out = renderMd('hello');
  assert.match(out, /<pre><button class="copy-code-btn"/);
  assert.match(out, /onclick="copyCodeBlock\(this\)"/);
  assert.match(out, /hello/);
  delete globalThis.window.marked;
});

test('renderMd: marked throws → falls back to escDom', () => {
  globalThis.window.marked = { parse: () => { throw new Error('boom'); } };
  const out = renderMd('<x>');
  assert.match(out, /&lt;x&gt;/);
  delete globalThis.window.marked;
});
