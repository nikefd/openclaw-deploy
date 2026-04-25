// tests/unit/fileViewer.test.mjs — pure HTML builders for the file viewer.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  fileTabsHtml,
  fileViewerContent,
  fileViewerErrorHtml,
  FILE_VIEWER_EMPTY_HTML,
  FILE_VIEWER_LOADING_HTML,
} from '../../web/src/ui/fileViewer.js';

const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const fileIcon = (n, isDir) => isDir ? '📁' : (n.endsWith('.js') ? '🟨' : '📄');
const fileLang = (n) => n.endsWith('.js') ? 'JavaScript' : 'Text';
const fmtSize = (b) => b == null ? '' : (b < 1024 ? b + ' B' : (b / 1024).toFixed(1) + ' KB');

// ── fileTabsHtml ──────────────────────────────────────────────────

test('fileTabsHtml: empty tabs → empty string', () => {
  assert.equal(fileTabsHtml([], null, { fileIcon, escapeHtml: esc }), '');
  assert.equal(fileTabsHtml(null, null, { fileIcon, escapeHtml: esc }), '');
  assert.equal(fileTabsHtml(undefined, null, { fileIcon, escapeHtml: esc }), '');
});

test('fileTabsHtml: single tab renders icon + name + close button', () => {
  const html = fileTabsHtml(
    [{ path: '/a/b.js', name: 'b.js' }],
    '/a/b.js',
    { fileIcon, escapeHtml: esc },
  );
  assert.match(html, /class="file-tab active"/);
  assert.match(html, /data-path="\/a\/b\.js"/);
  assert.match(html, /🟨/);
  assert.match(html, />b\.js</);
  assert.match(html, /tab-close/);
});

test('fileTabsHtml: non-active tab has no .active class', () => {
  const html = fileTabsHtml(
    [{ path: '/x.js', name: 'x.js' }],
    '/other.js',
    { fileIcon, escapeHtml: esc },
  );
  assert.match(html, /class="file-tab"/);
  assert.doesNotMatch(html, /\bactive\b/);
});

test('fileTabsHtml: multiple tabs, only matching one is active', () => {
  const html = fileTabsHtml(
    [
      { path: '/a.js', name: 'a.js' },
      { path: '/b.js', name: 'b.js' },
      { path: '/c.js', name: 'c.js' },
    ],
    '/b.js',
    { fileIcon, escapeHtml: esc },
  );
  const active = html.match(/file-tab active/g) || [];
  assert.equal(active.length, 1);
  assert.match(html, /data-path="\/b\.js"/);
});

test('fileTabsHtml: XSS-safe — name escaped', () => {
  const html = fileTabsHtml(
    [{ path: '/x', name: '<script>alert(1)</script>' }],
    null,
    { fileIcon, escapeHtml: esc },
  );
  assert.doesNotMatch(html, /<script>alert/);
  assert.match(html, /&lt;script&gt;/);
});

test('fileTabsHtml: skips entries without path', () => {
  const html = fileTabsHtml(
    [{ name: 'no-path' }, null, { path: '/ok', name: 'ok' }],
    null,
    { fileIcon, escapeHtml: esc },
  );
  assert.match(html, /data-path="\/ok"/);
  assert.equal((html.match(/file-tab/g) || []).length, 1);
});

test('fileTabsHtml: dir flag is false (file viewer never shows dirs)', () => {
  let captured;
  const spy = (n, d) => { captured = d; return '📄'; };
  fileTabsHtml(
    [{ path: '/x', name: 'x' }],
    null,
    { fileIcon: spy, escapeHtml: esc },
  );
  assert.equal(captured, false);
});

// ── fileViewerContent ─────────────────────────────────────────────

test('fileViewerContent: line numbers match content lines', () => {
  const tab = { name: 'x.js', path: '/x.js', content: 'a\nb\nc', size: 5 };
  const r = fileViewerContent(tab, { fileLang, fmtSize, escapeHtml: esc });
  assert.match(r.bodyHtml, /<div class="line-numbers">1\n2\n3<\/div>/);
  assert.equal(r.infoBar.lines, '📏 3 行');
});

test('fileViewerContent: single-line content → 1 line', () => {
  const tab = { name: 'x.txt', path: '/x.txt', content: 'hello', size: 5 };
  const r = fileViewerContent(tab, { fileLang, fmtSize, escapeHtml: esc });
  assert.equal(r.infoBar.lines, '📏 1 行');
  assert.match(r.bodyHtml, /<div class="line-numbers">1<\/div>/);
});

test('fileViewerContent: empty content → 1 line, body still rendered', () => {
  const tab = { name: '', path: '', content: '', size: 0 };
  const r = fileViewerContent(tab, { fileLang, fmtSize, escapeHtml: esc });
  assert.match(r.bodyHtml, /line-numbers/);
  assert.equal(r.infoBar.lines, '📏 1 行');
});

test('fileViewerContent: infoBar uses injected fileLang/fmtSize', () => {
  const tab = { name: 'x.js', path: '/x.js', content: '', size: 2048 };
  const r = fileViewerContent(tab, { fileLang, fmtSize, escapeHtml: esc });
  assert.equal(r.infoBar.lang, '📝 JavaScript');
  assert.equal(r.infoBar.size, '💾 2.0 KB');
  assert.equal(r.infoBar.path, '/x.js');
});

test('fileViewerContent: XSS-safe — content escaped in body', () => {
  const tab = { name: 'x', path: '/x', content: '<script>boom</script>', size: 1 };
  const r = fileViewerContent(tab, { fileLang, fmtSize, escapeHtml: esc });
  assert.doesNotMatch(r.bodyHtml, /<script>boom/);
  assert.match(r.bodyHtml, /&lt;script&gt;boom/);
});

test('fileViewerContent: defensive — null tab → safe placeholder', () => {
  const r = fileViewerContent(null, { fileLang, fmtSize, escapeHtml: esc });
  assert.match(r.bodyHtml, /line-numbers/);
  assert.equal(r.infoBar.path, '');
});

test('fileViewerContent: non-string content does not crash', () => {
  const tab = { name: 'x', path: '/x', content: null, size: 0 };
  const r = fileViewerContent(tab, { fileLang, fmtSize, escapeHtml: esc });
  assert.equal(r.infoBar.lines, '📏 1 行');
});

// ── error / placeholder constants ─────────────────────────────────

test('fileViewerErrorHtml: escapes message', () => {
  const html = fileViewerErrorHtml('<bad>', { escapeHtml: esc });
  assert.doesNotMatch(html, /<bad>/);
  assert.match(html, /&lt;bad&gt;/);
  assert.match(html, /file-viewer-empty/);
  assert.match(html, /❌/);
});

test('fileViewerErrorHtml: defaults to "加载失败" on empty', () => {
  const html = fileViewerErrorHtml('', { escapeHtml: esc });
  assert.match(html, /加载失败/);
});

test('FILE_VIEWER_EMPTY_HTML / FILE_VIEWER_LOADING_HTML are non-empty placeholders', () => {
  assert.match(FILE_VIEWER_EMPTY_HTML, /file-viewer-empty/);
  assert.match(FILE_VIEWER_EMPTY_HTML, /选择文件查看内容/);
  assert.match(FILE_VIEWER_LOADING_HTML, /加载中/);
  assert.match(FILE_VIEWER_LOADING_HTML, /⏳/);
});
