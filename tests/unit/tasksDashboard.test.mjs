// tests/unit/tasksDashboard.test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  statusBadge,
  runtimeLabel,
  fmtTime,
  fmtDuration,
  countTasks,
  summaryHtml,
  cardStatusText,
  emptyListHtml,
  taskRowHtml,
} from '../../web/src/ui/tasksDashboard.js';

// --- statusBadge --------------------------------------------------------

test('statusBadge: known status → emoji + label', () => {
  const html = statusBadge('running');
  assert.match(html, /🟢/);
  assert.match(html, /运行中/);
  assert.match(html, /#22c55e/);
});

test('statusBadge: unknown status echoes back, escaped', () => {
  const html = statusBadge('<x>');
  assert.ok(!html.includes('<x>'), 'must escape');
  assert.match(html, /&lt;x&gt;/);
});

test('statusBadge: null → "unknown"', () => {
  const html = statusBadge(null);
  assert.match(html, /unknown/);
});

// --- runtimeLabel -------------------------------------------------------

test('runtimeLabel: known runtimes', () => {
  assert.match(runtimeLabel('subagent'), /子Agent/);
  assert.match(runtimeLabel('cron'), /定时/);
  assert.match(runtimeLabel('acp'), /ACP/);
  assert.match(runtimeLabel('cli'), /CLI/);
});

test('runtimeLabel: unknown is escaped', () => {
  assert.equal(runtimeLabel('<script>'), '&lt;script&gt;');
});

// --- fmtTime ------------------------------------------------------------

test('fmtTime: 0/null → "-"', () => {
  assert.equal(fmtTime(0), '-');
  assert.equal(fmtTime(null), '-');
});

test('fmtTime: <60s → "刚刚"', () => {
  const now = 1_700_000_000_000;
  assert.equal(fmtTime(now - 30_000, now), '刚刚');
});

test('fmtTime: <1h → "X 分钟前"', () => {
  const now = 1_700_000_000_000;
  assert.equal(fmtTime(now - 5 * 60 * 1000, now), '5 分钟前');
});

test('fmtTime: <24h → "X 小时前"', () => {
  const now = 1_700_000_000_000;
  assert.equal(fmtTime(now - 3 * 3600 * 1000, now), '3 小时前');
});

test('fmtTime: ≥24h → locale-formatted date', () => {
  const now = 1_700_000_000_000;
  const out = fmtTime(now - 3 * 86400 * 1000, now);
  // Should NOT be "X 小时前" or "刚刚"
  assert.ok(!out.includes('前'));
  assert.ok(!out.includes('刚刚'));
});

// --- fmtDuration --------------------------------------------------------

test('fmtDuration: missing start → "-"', () => {
  assert.equal(fmtDuration(0), '-');
  assert.equal(fmtDuration(null), '-');
});

test('fmtDuration: <1s → ms', () => {
  assert.equal(fmtDuration(1000, 1500), '500ms');
});

test('fmtDuration: <60s → "X.Ys"', () => {
  assert.equal(fmtDuration(1000, 4500), '3.5s');
});

test('fmtDuration: <1h → "Xm Ys"', () => {
  assert.equal(fmtDuration(1000, 1000 + 5 * 60 * 1000 + 23 * 1000), '5m 23s');
});

test('fmtDuration: ≥1h → "Xh Ym"', () => {
  assert.equal(fmtDuration(1000, 1000 + (3600 + 30 * 60) * 1000), '1h 30m');
});

// --- countTasks ---------------------------------------------------------

test('countTasks: aggregates per-status', () => {
  const tasks = [
    { status: 'running' }, { status: 'running' },
    { status: 'queued' },
    { status: 'succeeded' },
    { status: 'failed' },
    { status: 'timed_out' },
    { status: 'cancelled' },
    { status: 'something-else' },
  ];
  const c = countTasks(tasks);
  assert.equal(c.running, 2);
  assert.equal(c.queued, 1);
  assert.equal(c.succeeded, 1);
  assert.equal(c.failed, 1);
  assert.equal(c.timed_out, 1);
  assert.equal(c.cancelled, 1);
  assert.equal(c.total, 8);
});

test('countTasks: handles non-array input', () => {
  const c = countTasks(null);
  assert.equal(c.total, 0);
  assert.equal(c.running, 0);
});

// --- summaryHtml --------------------------------------------------------

test('summaryHtml: 5 cards rendered', () => {
  const html = summaryHtml({ running: 2, queued: 1, succeeded: 5, failed: 1, timed_out: 1, total: 10 });
  assert.match(html, /运行中.*?>2</);
  assert.match(html, /排队中.*?>1</);
  assert.match(html, /已完成.*?>5</);
  assert.match(html, /失败\/超时.*?>2</); // failed + timed_out merged
  assert.match(html, /总计.*?>10</);
});

test('summaryHtml: missing fields default to 0', () => {
  const html = summaryHtml({});
  // All five "0"s must appear
  const zeros = (html.match(/font-weight:700;color:[^"]+">0</g) || []).length;
  assert.equal(zeros, 5);
});

// --- cardStatusText -----------------------------------------------------

test('cardStatusText: running > 0', () => {
  assert.equal(cardStatusText(3, 10), '● 3 个运行中');
});

test('cardStatusText: running == 0 → total', () => {
  assert.equal(cardStatusText(0, 10), '○ 10 条记录');
});

test('cardStatusText: defaults', () => {
  assert.equal(cardStatusText(), '○ 0 条记录');
});

// --- emptyListHtml ------------------------------------------------------

test('emptyListHtml: 暂无任务', () => {
  assert.match(emptyListHtml(), /暂无任务/);
});

// --- taskRowHtml --------------------------------------------------------

test('taskRowHtml: renders title + runtime + status badge', () => {
  const html = taskRowHtml({
    taskId: 't1', label: '测试任务', runtime: 'subagent', status: 'running',
    createdAt: Date.now() - 10_000,
  }, { nowMs: Date.now() });
  assert.match(html, /测试任务/);
  assert.match(html, /子Agent/);
  assert.match(html, /运行中/);
});

test('taskRowHtml: title fallback chain (label → task → taskId → "-")', () => {
  assert.match(taskRowHtml({ taskId: 'id-only' }), />id-only</);
  assert.match(taskRowHtml({ task: 'just task' }), />just task</);
  assert.match(taskRowHtml({}), />-</);
});

test('taskRowHtml: shows error block when present', () => {
  const html = taskRowHtml({ error: 'boom!' });
  assert.match(html, /boom!/);
  assert.match(html, /border-left:2px solid #ef4444/);
});

test('taskRowHtml: hides error block when absent', () => {
  const html = taskRowHtml({});
  assert.ok(!html.includes('border-left:2px solid #ef4444'));
});

test('taskRowHtml: shows terminalSummary in <details>', () => {
  const html = taskRowHtml({ terminalSummary: 'summary text' });
  assert.match(html, /<details/);
  assert.match(html, /summary text/);
});

test('taskRowHtml: ⏱ duration only when running', () => {
  const start = Date.now() - 5000;
  const r = taskRowHtml({ status: 'running', startedAt: start });
  assert.match(r, /⏱/);
  const f = taskRowHtml({ status: 'succeeded', startedAt: start, endedAt: start + 5000 });
  assert.ok(!f.includes('⏱'));
  assert.match(f, /✔/);
});

test('taskRowHtml: HTML-escapes title (defuse XSS)', () => {
  const html = taskRowHtml({ label: '<script>alert(1)</script>' });
  assert.ok(!html.includes('<script>alert(1)'));
  assert.match(html, /&lt;script&gt;alert\(1\)&lt;\/script&gt;/);
});

test('taskRowHtml: HTML-escapes error + terminalSummary', () => {
  const html = taskRowHtml({
    error: '<img src=x onerror=alert(1)>',
    terminalSummary: '<svg/onload=alert(1)>',
  });
  assert.match(html, /&lt;img src=x onerror=alert\(1\)&gt;/);
  assert.match(html, /&lt;svg\/onload=alert\(1\)&gt;/);
});

test('taskRowHtml: handles null input', () => {
  const html = taskRowHtml(null);
  assert.match(html, />-</);
});
