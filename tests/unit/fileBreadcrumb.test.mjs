// tests/unit/fileBreadcrumb.test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { breadcrumbHtml } from '../../web/src/ui/fileBreadcrumb.js';

const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

test('breadcrumbHtml: empty path → empty string', () => {
  assert.equal(breadcrumbHtml('', { escapeHtml: esc }), '');
  assert.equal(breadcrumbHtml(null, { escapeHtml: esc }), '');
  assert.equal(breadcrumbHtml(undefined, { escapeHtml: esc }), '');
});

test('breadcrumbHtml: root "/" has no segments → empty', () => {
  assert.equal(breadcrumbHtml('/', { escapeHtml: esc }), '');
});

test('breadcrumbHtml: single segment, no leading separator', () => {
  const h = breadcrumbHtml('/home', { escapeHtml: esc });
  assert.match(h, /<span class="bc-part" onclick="loadFiles\('\/home'\)">home<\/span>/);
  assert.doesNotMatch(h, /bc-sep/);
});

test('breadcrumbHtml: multi-segment chain joined by ›', () => {
  const h = breadcrumbHtml('/a/b/c', { escapeHtml: esc });
  const seps = h.match(/bc-sep/g) || [];
  const parts = h.match(/bc-part/g) || [];
  assert.equal(parts.length, 3);
  assert.equal(seps.length, 2);
});

test('breadcrumbHtml: cumulative paths in onclick', () => {
  const h = breadcrumbHtml('/a/b/c', { escapeHtml: esc });
  assert.match(h, /loadFiles\('\/a'\)/);
  assert.match(h, /loadFiles\('\/a\/b'\)/);
  assert.match(h, /loadFiles\('\/a\/b\/c'\)/);
});

test('breadcrumbHtml: clickFn is configurable', () => {
  const h = breadcrumbHtml('/x', { clickFn: 'loadRemoteFiles', escapeHtml: esc });
  assert.match(h, /loadRemoteFiles\('\/x'\)/);
  assert.doesNotMatch(h, /loadFiles\(/);
});

test('breadcrumbHtml: defaults clickFn to loadFiles', () => {
  const h = breadcrumbHtml('/x', { escapeHtml: esc });
  assert.match(h, /loadFiles\('\/x'\)/);
});

test('breadcrumbHtml: XSS — segment text escaped', () => {
  const h = breadcrumbHtml('/<script>', { escapeHtml: esc });
  assert.doesNotMatch(h, /<span [^>]*><script>/);
  assert.match(h, /&lt;script&gt;/);
});

test('breadcrumbHtml: XSS — quotes stripped from onclick path', () => {
  const h = breadcrumbHtml("/x'/y", { escapeHtml: esc });
  // path with single quote in segment: quote must be stripped from onclick
  assert.doesNotMatch(h, /loadFiles\('[^']*'\); /);
  assert.match(h, /loadFiles\(/);
});

test('breadcrumbHtml: trailing slashes collapsed', () => {
  const h = breadcrumbHtml('/a//b/', { escapeHtml: esc });
  const parts = h.match(/bc-part/g) || [];
  assert.equal(parts.length, 2);
});
