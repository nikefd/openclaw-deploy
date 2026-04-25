// tests/unit/demoCodes.test.mjs — pure helpers for the Demo Codes admin panel.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  demoCodeMeta, demoCodeCardHtml, demoCodesListHtml,
} from '../../web/src/ui/demoCodes.js';

const HOUR = 3600 * 1000;
const NOW = 1700000000000; // fixed reference

const validCode = {
  code: 'ABC123',
  label: 'guest',
  createdAt: NOW - 2 * HOUR,
  expiresAt: NOW + 24 * HOUR,
  accessDurationMs: 4 * HOUR,
  usedCount: 0,
};

const expiredCode = {
  code: 'OLD999',
  createdAt: NOW - 100 * HOUR,
  expiresAt: NOW - HOUR,
  accessDurationMs: 2 * HOUR,
  usedCount: 5,
};

// --- demoCodeMeta ---
test('demoCodeMeta: valid code', () => {
  const m = demoCodeMeta(validCode, NOW);
  assert.equal(m.expired, false);
  assert.equal(m.statusText, '有效');
  assert.equal(m.statusColor, 'var(--accent)');
  assert.equal(m.accessHours, 4);
  assert.equal(m.usedText, '未使用');
  assert.equal(m.codeColor, 'var(--text)');
});

test('demoCodeMeta: expired code', () => {
  const m = demoCodeMeta(expiredCode, NOW);
  assert.equal(m.expired, true);
  assert.equal(m.statusText, '已过期');
  assert.equal(m.statusColor, 'var(--danger)');
  assert.equal(m.usedText, '已使用 5 次');
  assert.equal(m.codeColor, 'var(--text-sec)');
});

test('demoCodeMeta: boundary expiresAt === now → expired', () => {
  // matches inline behavior: c.expiresAt <= now
  const m = demoCodeMeta({ ...validCode, expiresAt: NOW }, NOW);
  assert.equal(m.expired, true);
});

test('demoCodeMeta: missing accessDurationMs → 0 hours', () => {
  const m = demoCodeMeta({ ...validCode, accessDurationMs: undefined }, NOW);
  assert.equal(m.accessHours, 0);
});

test('demoCodeMeta: usedCount missing/zero/positive', () => {
  assert.equal(demoCodeMeta({ ...validCode, usedCount: 0 }, NOW).usedText, '未使用');
  assert.equal(demoCodeMeta({ ...validCode, usedCount: undefined }, NOW).usedText, '未使用');
  assert.equal(demoCodeMeta({ ...validCode, usedCount: 1 }, NOW).usedText, '已使用 1 次');
});

test('demoCodeMeta: rounds accessHours', () => {
  // 1.4h → rounds to 1
  assert.equal(demoCodeMeta({ ...validCode, accessDurationMs: 1.4 * HOUR }, NOW).accessHours, 1);
  // 1.6h → rounds to 2
  assert.equal(demoCodeMeta({ ...validCode, accessDurationMs: 1.6 * HOUR }, NOW).accessHours, 2);
});

// --- demoCodeCardHtml ---
test('demoCodeCardHtml: includes code, label, status', () => {
  const html = demoCodeCardHtml(validCode, NOW);
  assert.match(html, />ABC123</);
  assert.match(html, /📝 guest/);
  assert.match(html, /有效/);
  assert.match(html, /var\(--accent\)/);
});

test('demoCodeCardHtml: omits label line when no label', () => {
  const html = demoCodeCardHtml({ ...validCode, label: '' }, NOW);
  assert.ok(!html.includes('📝'));
});

test('demoCodeCardHtml: includes link section ONLY for valid (not expired)', () => {
  const valid = demoCodeCardHtml(validCode, NOW);
  const expired = demoCodeCardHtml(expiredCode, NOW);
  assert.match(valid, /🔗 链接/);
  assert.ok(!expired.includes('🔗 链接'));
});

test('demoCodeCardHtml: delete button references the code', () => {
  const html = demoCodeCardHtml(validCode, NOW);
  assert.match(html, /onclick="deleteDemoCode\('ABC123'\)"/);
});

test('demoCodeCardHtml: escapes label HTML', () => {
  const html = demoCodeCardHtml({ ...validCode, label: '<script>x</script>' }, NOW);
  assert.ok(!html.includes('<script>x</script>'));
  assert.match(html, /&lt;script&gt;/);
});

test('demoCodeCardHtml: escapes < and > in code field', () => {
  // Code shouldn't realistically contain HTML, but guard anyway.
  const html = demoCodeCardHtml({ ...validCode, code: 'A<B>' }, NOW);
  assert.ok(!html.includes('A<B>'));
  assert.match(html, /A&lt;B&gt;/);
});

test('demoCodeCardHtml: includes access hours and usedText', () => {
  const html = demoCodeCardHtml(validCode, NOW);
  assert.match(html, /🕐 访问时长: 4h/);
  assert.match(html, /👤 未使用/);
});

// --- demoCodesListHtml ---
test('demoCodesListHtml: empty input → empty string', () => {
  assert.equal(demoCodesListHtml([], NOW), '');
  assert.equal(demoCodesListHtml(null, NOW), '');
  assert.equal(demoCodesListHtml(undefined, NOW), '');
});

test('demoCodesListHtml: sorts newest first', () => {
  const old = { ...validCode, code: 'OLD', createdAt: NOW - 10 * HOUR };
  const newer = { ...validCode, code: 'NEW', createdAt: NOW - 1 * HOUR };
  const html = demoCodesListHtml([old, newer], NOW);
  const idxOld = html.indexOf('>OLD<');
  const idxNew = html.indexOf('>NEW<');
  assert.ok(idxNew >= 0 && idxOld >= 0);
  assert.ok(idxNew < idxOld, 'newer code should come first');
});

test('demoCodesListHtml: does not mutate input array', () => {
  const a = { ...validCode, code: 'A', createdAt: NOW - 1 * HOUR };
  const b = { ...validCode, code: 'B', createdAt: NOW - 2 * HOUR };
  const arr = [a, b];
  const before = arr.slice();
  demoCodesListHtml(arr, NOW);
  assert.deepEqual(arr, before);
});

test('demoCodesListHtml: renders one card per item', () => {
  const html = demoCodesListHtml([validCode, expiredCode], NOW);
  // Each card starts with `<div style="background:var(--input-bg);` — count those.
  const cardCount = (html.match(/<div style="background:var\(--input-bg\);/g) || []).length;
  assert.equal(cardCount, 2);
});
