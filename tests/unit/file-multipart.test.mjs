// tests/unit/file-multipart.test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const {
  getBoundary,
  splitParts,
  parsePartHeaders,
  stripTrailingCrlf,
  sanitizeFilename,
  makeUniqueName,
  parseMultipart,
} = require('../../services/file/lib/multipart.js');

// Helper: build a real multipart/form-data body for a single text-file part.
function buildBody(boundary, parts) {
  const chunks = [];
  for (const p of parts) {
    chunks.push(Buffer.from('--' + boundary + '\r\n'));
    chunks.push(Buffer.from('Content-Disposition: form-data; name="' + p.field + '"' +
      (p.filename != null ? '; filename="' + p.filename + '"' : '') + '\r\n'));
    if (p.contentType) chunks.push(Buffer.from('Content-Type: ' + p.contentType + '\r\n'));
    chunks.push(Buffer.from('\r\n'));
    chunks.push(Buffer.isBuffer(p.body) ? p.body : Buffer.from(p.body));
    chunks.push(Buffer.from('\r\n'));
  }
  chunks.push(Buffer.from('--' + boundary + '--\r\n'));
  return Buffer.concat(chunks);
}

// ── getBoundary ────────────────────────────────────────────────────

test('getBoundary: extracts from typical content-type', () => {
  assert.equal(getBoundary('multipart/form-data; boundary=abc123'), 'abc123');
});

test('getBoundary: handles quoted boundary', () => {
  assert.equal(getBoundary('multipart/form-data; boundary="abc-123"'), 'abc-123');
});

test('getBoundary: returns null for missing boundary', () => {
  assert.equal(getBoundary('multipart/form-data'), null);
  assert.equal(getBoundary(''), null);
  assert.equal(getBoundary(null), null);
  assert.equal(getBoundary(undefined), null);
});

test('getBoundary: trims trailing whitespace', () => {
  assert.equal(getBoundary('multipart/form-data; boundary=abc   '), 'abc');
});

// ── splitParts ─────────────────────────────────────────────────────

test('splitParts: empty buffer or no boundary → []', () => {
  assert.deepEqual(splitParts(Buffer.alloc(0), 'x'), []);
  assert.deepEqual(splitParts(Buffer.from('hi'), null), []);
  assert.deepEqual(splitParts('not a buffer', 'x'), []);
});

test('splitParts: splits 2 parts correctly', () => {
  const body = buildBody('B', [
    { field: 'f1', filename: 'a.txt', body: 'hello' },
    { field: 'f2', filename: 'b.txt', body: 'world' },
  ]);
  const parts = splitParts(body, 'B');
  assert.equal(parts.length, 2);
  // Each part should contain the headers + blank line + body bytes
  assert.ok(parts[0].includes(Buffer.from('hello')));
  assert.ok(parts[1].includes(Buffer.from('world')));
});

// ── parsePartHeaders ───────────────────────────────────────────────

test('parsePartHeaders: extracts filename + field', () => {
  const h = 'Content-Disposition: form-data; name="upload"; filename="hi.txt"\r\nContent-Type: text/plain';
  const r = parsePartHeaders(h);
  assert.equal(r.field, 'upload');
  assert.equal(r.filename, 'hi.txt');
  assert.equal(r.contentType, 'text/plain');
});

test('parsePartHeaders: no filename → filename:null (non-file field)', () => {
  const r = parsePartHeaders('Content-Disposition: form-data; name="title"');
  assert.equal(r.filename, null);
  assert.equal(r.field, 'title');
});

test('parsePartHeaders: handles empty filename', () => {
  const r = parsePartHeaders('Content-Disposition: form-data; name="f"; filename=""');
  assert.equal(r.filename, '');
});

test('parsePartHeaders: non-string returns nulls', () => {
  const r = parsePartHeaders(null);
  assert.equal(r.field, null);
  assert.equal(r.filename, null);
});

// ── stripTrailingCrlf ──────────────────────────────────────────────

test('stripTrailingCrlf: removes trailing \\r\\n', () => {
  const out = stripTrailingCrlf(Buffer.from('hello\r\n'));
  assert.equal(out.toString(), 'hello');
});

test('stripTrailingCrlf: leaves body without crlf alone', () => {
  const out = stripTrailingCrlf(Buffer.from('hello'));
  assert.equal(out.toString(), 'hello');
});

test('stripTrailingCrlf: only \\n at end → not stripped (need both)', () => {
  const out = stripTrailingCrlf(Buffer.from('hello\n'));
  assert.equal(out.toString(), 'hello\n');
});

test('stripTrailingCrlf: empty buffer untouched', () => {
  assert.equal(stripTrailingCrlf(Buffer.alloc(0)).length, 0);
});

// ── sanitizeFilename ───────────────────────────────────────────────

test('sanitizeFilename: keeps alphanumerics and dots/dashes/underscores', () => {
  assert.equal(sanitizeFilename('My-File_2026.tar.gz'), 'My-File_2026.tar.gz');
});

test('sanitizeFilename: replaces spaces and special chars with _', () => {
  assert.equal(sanitizeFilename('hello world!.txt'), 'hello_world_.txt');
  assert.equal(sanitizeFilename('a/b\\c.txt'), 'a_b_c.txt');
});

test('sanitizeFilename: keeps CJK chars', () => {
  assert.equal(sanitizeFilename('斌哥.png'), '斌哥.png');
});

test('sanitizeFilename: null/undefined → empty string', () => {
  assert.equal(sanitizeFilename(null), '');
  assert.equal(sanitizeFilename(undefined), '');
});

// ── makeUniqueName ─────────────────────────────────────────────────

test('makeUniqueName: injects timestamp before extension', () => {
  assert.equal(makeUniqueName('hi.txt', 12345), 'hi_12345.txt');
});

test('makeUniqueName: handles tar.gz (only last ext used, by design)', () => {
  // path.extname('a.tar.gz') === '.gz', so we match that
  assert.equal(makeUniqueName('a.tar.gz', 9), 'a.tar_9.gz');
});

test('makeUniqueName: no extension', () => {
  assert.equal(makeUniqueName('README', 7), 'README_7');
});

test('makeUniqueName: dotfile (no extension by convention)', () => {
  // '.bashrc'.lastIndexOf('.') === 0 → not treated as extension
  assert.equal(makeUniqueName('.bashrc', 1), '.bashrc_1');
});

test('makeUniqueName: trailing dot is not an extension', () => {
  // 'a.' has dot at len-1 → no ext
  assert.equal(makeUniqueName('a.', 5), 'a._5');
});

test('makeUniqueName: sanitizes input first', () => {
  assert.equal(makeUniqueName('hello world.png', 1), 'hello_world_1.png');
});

// ── parseMultipart (integration) ───────────────────────────────────

test('parseMultipart: 2 file parts parsed correctly', () => {
  const body = buildBody('B', [
    { field: 'a', filename: 'first.txt', body: 'hello' },
    { field: 'b', filename: 'second.bin', body: Buffer.from([1, 2, 3, 4]), contentType: 'application/octet-stream' },
  ]);
  const r = parseMultipart(body, 'B');
  assert.equal(r.length, 2);
  assert.equal(r[0].field, 'a');
  assert.equal(r[0].filename, 'first.txt');
  assert.equal(r[0].body.toString(), 'hello');
  assert.equal(r[1].field, 'b');
  assert.equal(r[1].filename, 'second.bin');
  assert.equal(r[1].contentType, 'application/octet-stream');
  assert.deepEqual([...r[1].body], [1, 2, 3, 4]);
});

test('parseMultipart: skips non-file fields (no filename)', () => {
  const body = buildBody('B', [
    { field: 'title', body: 'hello' }, // no filename
    { field: 'photo', filename: 'p.png', body: 'IMG' },
  ]);
  const r = parseMultipart(body, 'B');
  assert.equal(r.length, 1);
  assert.equal(r[0].filename, 'p.png');
});

test('parseMultipart: empty boundary → []', () => {
  const body = Buffer.from('whatever');
  assert.deepEqual(parseMultipart(body, null), []);
  assert.deepEqual(parseMultipart(body, ''), []);
});

test('parseMultipart: binary file with embedded \\r\\n preserved', () => {
  const binary = Buffer.from([1, 2, 13, 10, 3, 4]); // \r\n in middle
  const body = buildBody('B', [{ field: 'f', filename: 'b.bin', body: binary }]);
  const r = parseMultipart(body, 'B');
  assert.equal(r.length, 1);
  assert.deepEqual([...r[0].body], [1, 2, 13, 10, 3, 4]);
});
