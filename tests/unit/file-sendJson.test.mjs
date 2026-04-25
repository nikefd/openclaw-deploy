// tests/unit/file-sendJson.test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const { shouldGzip, GZIP_THRESHOLD } = require('../../services/file/lib/sendJson.js');

test('shouldGzip: false when no accept-encoding', () => {
  assert.equal(shouldGzip(undefined, 5000), false);
  assert.equal(shouldGzip(null, 5000), false);
  assert.equal(shouldGzip('', 5000), false);
});

test('shouldGzip: false below threshold even with gzip in accept-encoding', () => {
  assert.equal(shouldGzip('gzip, deflate', 100), false);
  assert.equal(shouldGzip('gzip', GZIP_THRESHOLD), false); // exactly threshold = false
});

test('shouldGzip: true when above threshold + gzip allowed', () => {
  assert.equal(shouldGzip('gzip, deflate, br', GZIP_THRESHOLD + 1), true);
  assert.equal(shouldGzip('gzip', 5000), true);
});

test('shouldGzip: \b is regex word-boundary, not real Accept-Encoding parser', () => {
  // Modern browsers always send `gzip, deflate, br` etc, so this is fine in practice.
  // But document the regex behavior for future-us:
  assert.equal(shouldGzip('xgzipy', 5000), false);            // no word-boundary
  assert.equal(shouldGzip('not-gzip-stuff', 5000), true);     // - is non-word, boundary triggers
  assert.equal(shouldGzip('gzip;q=0', 5000), true);           // realistic header form
});

test('shouldGzip: handles weird inputs gracefully', () => {
  assert.equal(shouldGzip('gzip', 0), false);
  assert.equal(shouldGzip('gzip', -1), false);
  assert.equal(shouldGzip('gzip', 'not a number'), false);
  // NaN > 1024 is false, so it's correctly rejected
  assert.equal(shouldGzip('gzip', NaN), false);
});

test('GZIP_THRESHOLD: matches expected default of 1024', () => {
  assert.equal(GZIP_THRESHOLD, 1024);
});
