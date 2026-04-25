// tests/unit/fileHelpers.test.mjs — pure helpers for the file panel.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { fileIcon, fileLang, fmtSize, FILE_ICONS, LANG_MAP } from '../../web/src/ui/fileHelpers.js';

test('fileIcon: directory beats extension', () => {
  assert.equal(fileIcon('whatever.js', true), '📁');
});

test('fileIcon: known extensions', () => {
  assert.equal(fileIcon('app.js'), FILE_ICONS.js);
  assert.equal(fileIcon('a.PY'), FILE_ICONS.py);   // case-insensitive
  assert.equal(fileIcon('readme.md'), FILE_ICONS.md);
});

test('fileIcon: unknown extension → default', () => {
  assert.equal(fileIcon('thing.xyzzy'), '📄');
});

test('fileIcon: tolerates null/empty', () => {
  assert.equal(fileIcon(null, false), '📄');
  assert.equal(fileIcon('', false), '📄');
});

test('fileLang: known mappings', () => {
  assert.equal(fileLang('a.js'), LANG_MAP.js);
  assert.equal(fileLang('a.ts'), LANG_MAP.ts);
  assert.equal(fileLang('a.py'), LANG_MAP.py);
});

test('fileLang: unknown ext → uppercased ext', () => {
  assert.equal(fileLang('a.weird'), 'WEIRD');
});

test('fileLang: no extension → Text', () => {
  assert.equal(fileLang('Makefile'), 'MAKEFILE'); // splits on '.', returns whole string upper
  assert.equal(fileLang(''), 'Text');
});

test('fmtSize: bytes / KB / MB thresholds', () => {
  assert.equal(fmtSize(0), '0 B');
  assert.equal(fmtSize(512), '512 B');
  assert.equal(fmtSize(1023), '1023 B');
  assert.equal(fmtSize(1024), '1.0 KB');
  assert.equal(fmtSize(1024 * 100), '100.0 KB');
  assert.equal(fmtSize(1024 * 1024), '1.0 MB');
  assert.equal(fmtSize(1024 * 1024 * 5), '5.0 MB');
});

test('fmtSize: null/undefined → empty string', () => {
  assert.equal(fmtSize(null), '');
  assert.equal(fmtSize(undefined), '');
});
