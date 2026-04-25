// tests/unit/memoryPanel.test.mjs — pure HTML template builders for memory sidebar.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  memoryFileHtml, memoryStatsHtml, memoryCategoryHtml, memoryCronHtml, memorySidebarHtml,
} from '../../web/src/ui/memoryPanel.js';

const file = (name, path, icon, size) => ({ name, path, icon, size });

const sample = {
  longTerm: [file('MEMORY.md', '/w/MEMORY.md', '📌', 8192)],
  daily: [
    file('2026-04-25.md', '/w/m/2026-04-25.md', '📝', 4096),
    file('2026-04-24.md', '/w/m/2026-04-24.md', '📝', 2048),
  ],
  identity: [
    file('IDENTITY.md', '/w/IDENTITY.md', '🪪'),
    file('SOUL.md', '/w/SOUL.md', '👻'),
  ],
  projects: [
    file('finance.md', '/w/m/p/finance.md', '💰', 1024),
  ],
};

// --- memoryFileHtml ---
test('memoryFileHtml: basic active class', () => {
  const html = memoryFileHtml(sample.longTerm[0], true);
  assert.match(html, /class="memory-file active"/);
  assert.match(html, /onclick="openMemFile\('\/w\/MEMORY\.md'\)"/);
  assert.match(html, /📌 MEMORY\.md/);
});

test('memoryFileHtml: inactive has no active class', () => {
  const html = memoryFileHtml(sample.longTerm[0], false);
  assert.match(html, /class="memory-file"/);
  assert.ok(!html.includes('active'));
});

test('memoryFileHtml: includes size badge in KB when size present', () => {
  const html = memoryFileHtml(sample.longTerm[0], false);
  assert.match(html, /<span class="mem-size">8\.0K<\/span>/);
});

test('memoryFileHtml: omits size badge when no size', () => {
  const html = memoryFileHtml(sample.identity[0], false);
  assert.ok(!html.includes('mem-size'));
});

test('memoryFileHtml: showSize=false disables badge even with size', () => {
  const html = memoryFileHtml(sample.longTerm[0], false, false);
  assert.ok(!html.includes('mem-size'));
});

// --- memoryStatsHtml ---
test('memoryStatsHtml: counts all categories', () => {
  // 1 longTerm + 2 daily + 2 identity + 1 project = 6
  const html = memoryStatsHtml(sample);
  assert.match(html, /<strong>6<\/strong> 个文件/);
});

test('memoryStatsHtml: sums sizes from categories', () => {
  // 8192 + 4096 + 2048 + 1024 = 15360 bytes = 15.0 KB
  const html = memoryStatsHtml(sample);
  assert.match(html, /<strong>15\.0<\/strong> KB/);
});

test('memoryStatsHtml: hides KB row when no size info', () => {
  const html = memoryStatsHtml({ longTerm: [], daily: [], identity: sample.identity, projects: [] });
  assert.match(html, /<strong>2<\/strong> 个文件/);
  assert.ok(!html.includes('KB'));
});

test('memoryStatsHtml: tolerates missing categories', () => {
  const html = memoryStatsHtml({ longTerm: [{ size: 1024 }] });
  assert.match(html, /<strong>1<\/strong> 个文件/);
  assert.match(html, /<strong>1\.0<\/strong> KB/);
});

// --- memoryCategoryHtml ---
test('memoryCategoryHtml: empty list → empty string', () => {
  assert.equal(memoryCategoryHtml('Title', [], null), '');
  assert.equal(memoryCategoryHtml('Title', null, null), '');
});

test('memoryCategoryHtml: includes title and one entry per file', () => {
  const html = memoryCategoryHtml('📝 Daily', sample.daily, null);
  assert.match(html, /memory-category-title">📝 Daily/);
  // 2 file rows
  assert.equal((html.match(/class="memory-file/g) || []).length, 2);
});

test('memoryCategoryHtml: marks active file', () => {
  const html = memoryCategoryHtml('📝 Daily', sample.daily, '/w/m/2026-04-24.md');
  assert.match(html, /class="memory-file active"[^>]*>📝 2026-04-24/);
  // The other should NOT have active class
  assert.ok(!/class="memory-file active"[^>]*>📝 2026-04-25/.test(html));
});

test('memoryCategoryHtml: showSize=false disables size badges in identity', () => {
  // Use longTerm files (which have size) but pass showSize=false
  const html = memoryCategoryHtml('LT', sample.longTerm, null, { showSize: false });
  assert.ok(!html.includes('mem-size'));
});

// --- memoryCronHtml ---
test('memoryCronHtml: includes time value and Save button', () => {
  const html = memoryCronHtml('23:30');
  assert.match(html, /value="23:30"/);
  assert.match(html, /onclick="saveMemoryCronTime\(\)"/);
  assert.match(html, /id="cronTimeInput"/);
  assert.match(html, /id="cronStatus"/);
});

// --- memorySidebarHtml (integration of all pieces) ---
test('memorySidebarHtml: contains header, stats, all 4 categories, cron', () => {
  const html = memorySidebarHtml(sample, '/w/MEMORY.md', '23:00');
  // header
  assert.match(html, /🧠 记忆管理/);
  // stats
  assert.match(html, /6<\/strong> 个文件/);
  // long-term
  assert.match(html, /📌 长期记忆/);
  // projects (with count suffix)
  assert.match(html, /📂 项目记忆 \(1\)/);
  // daily (with count suffix)
  assert.match(html, /📝 每日记录 \(2\)/);
  // identity
  assert.match(html, /🪪 身份文件/);
  // cron
  assert.match(html, /value="23:00"/);
  // current path is marked active in long-term
  assert.match(html, /class="memory-file active"[^>]*>📌 MEMORY\.md/);
});

test('memorySidebarHtml: skips daily section when no daily files', () => {
  const html = memorySidebarHtml({ ...sample, daily: [] }, null, '23:00');
  assert.ok(!html.includes('每日记录'));
});

test('memorySidebarHtml: skips projects section when no projects', () => {
  const html = memorySidebarHtml({ ...sample, projects: [] }, null, '23:00');
  assert.ok(!html.includes('项目记忆'));
});

test('memorySidebarHtml: identity files have NO size badges (matches inline)', () => {
  // Add a size to identity to verify it's still hidden
  const withSize = {
    ...sample,
    identity: [{ name: 'X.md', path: '/w/X.md', icon: '📄', size: 9999 }],
  };
  const html = memorySidebarHtml(withSize, null, '23:00');
  // Identity row should not show its size
  assert.ok(!/X\.md<span class="mem-size"/.test(html));
});
