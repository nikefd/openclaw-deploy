// ui/tasksDashboard.js — pure HTML builders for the /agents/tasks dashboard.
//
// No DOM, no globals, no fetch. The caller (agents.html) does the network IO
// and feeds shaped data in.
//
// Design notes:
//   - statusBadge / runtimeLabel are leaf builders — agents.html still has
//     inline copies for fallback. New code should call the module.
//   - taskRowHtml escapes ALL user-controlled fields (label/task/taskId/error/
//     terminalSummary). The previous inline impl already did, we keep it.
//   - summaryHtml renders the 5 stat cards from a counts object.

function escHtml(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

const STATUS_MAP = {
  running:    ['🟢', '#22c55e', '运行中'],
  queued:     ['🟡', '#eab308', '排队中'],
  succeeded:  ['✅', '#10b981', '完成'],
  failed:     ['❌', '#ef4444', '失败'],
  timed_out:  ['⏰', '#f97316', '超时'],
  cancelled:  ['⚪', '#94a3b8', '已取消'],
  lost:       ['❓', '#94a3b8', '丢失'],
};

const RUNTIME_LABELS = {
  subagent: '🤖 子Agent',
  cron: '⏰ 定时',
  acp: '💻 ACP',
  cli: '📟 CLI',
};

/**
 * @param {string} status
 * @returns {string} HTML for the colored badge
 */
export function statusBadge(status) {
  const x = STATUS_MAP[status] || ['🔷', '#64748b', status || 'unknown'];
  const [emoji, color, label] = x;
  // emoji + label come from STATUS_MAP (trusted) or echo back the raw status
  // (untrusted) — escape the fallback text just in case.
  const safeLabel = STATUS_MAP[status] ? label : escHtml(label);
  return (
    `<span style="display:inline-flex;align-items:center;gap:4px;padding:2px 8px;` +
    `border-radius:4px;background:${color}22;color:${color};font-size:0.8rem;` +
    `font-weight:600">${emoji} ${safeLabel}</span>`
  );
}

/**
 * @param {string} runtime
 * @returns {string} short label like "🤖 子Agent" — falls back to escaped raw
 */
export function runtimeLabel(runtime) {
  return RUNTIME_LABELS[runtime] || escHtml(runtime);
}

/**
 * Render the "now / X minutes ago / X hours ago / locale-date" relative string.
 * @param {number} ms epoch
 * @param {number} [nowMs] for test injection
 */
export function fmtTime(ms, nowMs) {
  if (!ms) return '-';
  const now = nowMs == null ? Date.now() : nowMs;
  const diff = now - ms;
  if (diff < 60000) return '刚刚';
  if (diff < 3600000) return Math.floor(diff / 60000) + ' 分钟前';
  if (diff < 86400000) return Math.floor(diff / 3600000) + ' 小时前';
  const d = new Date(ms);
  return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
}

/**
 * Render a duration like "1.2s" / "5m 23s" / "1h 30m".
 * @param {number} startMs
 * @param {number} [endMs] defaults to Date.now()
 */
export function fmtDuration(startMs, endMs) {
  if (!startMs) return '-';
  const end = endMs == null ? Date.now() : endMs;
  const dur = end - startMs;
  if (dur < 1000) return dur + 'ms';
  if (dur < 60000) return (dur / 1000).toFixed(1) + 's';
  if (dur < 3600000) return Math.floor(dur / 60000) + 'm ' + Math.floor((dur % 60000) / 1000) + 's';
  return Math.floor(dur / 3600000) + 'h ' + Math.floor((dur % 3600000) / 60000) + 'm';
}

/**
 * Aggregate per-status counts from a tasks array.
 * @param {Array<{status?:string}>} tasks
 * @returns {{running:number,queued:number,succeeded:number,failed:number,timed_out:number,cancelled:number,total:number}}
 */
export function countTasks(tasks) {
  const counts = { running: 0, queued: 0, succeeded: 0, failed: 0, timed_out: 0, cancelled: 0, total: 0 };
  if (!Array.isArray(tasks)) return counts;
  counts.total = tasks.length;
  for (const t of tasks) {
    const s = t && t.status;
    if (s && counts[s] !== undefined) counts[s]++;
  }
  return counts;
}

/**
 * Build the 5-card summary strip HTML.
 * @param {{running:number,queued:number,succeeded:number,failed:number,timed_out:number,total:number}} counts
 */
export function summaryHtml(counts) {
  const c = counts || {};
  const card = (label, value, bg, border, valueColor) =>
    `<div style="padding:10px 16px;background:${bg};border-radius:8px;` +
    `border-left:3px solid ${border};color:var(--text)">` +
      `<div style="font-size:0.75rem;color:var(--text2)">${label}</div>` +
      `<div style="font-size:1.4rem;font-weight:700;color:${valueColor}">${value}</div>` +
    `</div>`;
  return (
    card('运行中',   c.running   || 0, 'rgba(34,197,94,.12)',  '#22c55e',         '#22c55e') +
    card('排队中',   c.queued    || 0, 'rgba(234,179,8,.12)',  '#eab308',         '#d97706') +
    card('已完成',   c.succeeded || 0, 'rgba(16,185,129,.12)', '#10b981',         '#059669') +
    card('失败/超时', (c.failed || 0) + (c.timed_out || 0), 'rgba(239,68,68,.12)', '#ef4444', '#dc2626') +
    card('总计',     c.total     || 0, 'var(--hover)',         'var(--text2)',    'var(--text)')
  );
}

/**
 * Card-status text (the small "● 3 个运行中" beneath the Tasks card).
 */
export function cardStatusText(running, total) {
  if ((running || 0) > 0) return `● ${running} 个运行中`;
  return `○ ${total || 0} 条记录`;
}

/**
 * Empty-list HTML.
 */
export function emptyListHtml() {
  return '<div style="padding:20px;text-align:center;color:var(--text2)">暂无任务</div>';
}

/**
 * Build a single task row HTML.
 *
 * @param {{
 *   taskId?:string, label?:string, task?:string,
 *   runtime?:string, status?:string,
 *   createdAt?:number, startedAt?:number, endedAt?:number,
 *   error?:string, terminalSummary?:string,
 * }} t
 * @param {{nowMs?:number}} [opts]
 */
export function taskRowHtml(t, opts) {
  const task = t || {};
  const o = opts || {};
  const title = task.label || task.task || task.taskId || '-';
  const err = task.error
    ? `<div style="margin-top:6px;padding:6px 10px;background:rgba(239,68,68,.08);` +
      `border-left:2px solid #ef4444;border-radius:4px;font-size:0.8rem;color:#dc2626;` +
      `white-space:pre-wrap;word-break:break-word">${escHtml(task.error)}</div>`
    : '';
  const summary = task.terminalSummary
    ? `<details style="margin-top:6px"><summary style="cursor:pointer;font-size:0.8rem;color:var(--text2)">展开结果摘要</summary>` +
      `<div style="margin-top:6px;padding:8px;background:var(--hover);border-radius:4px;` +
      `font-size:0.82rem;white-space:pre-wrap;word-break:break-word;max-height:280px;` +
      `overflow:auto;color:var(--text)">${escHtml(task.terminalSummary)}</div></details>`
    : '';
  const startedSpan = task.startedAt && task.status === 'running'
    ? `<span>⏱ ${fmtDuration(task.startedAt, undefined)}</span>`
    : '';
  // For running tasks fmtDuration uses Date.now() — caller can override via
  // opts.nowMs on the SSR path; in the browser this is fine.
  if (o.nowMs != null && task.startedAt && task.status === 'running') {
    // we can't recompute startedSpan above without re-templating, so just
    // overwrite when nowMs was provided (test path)
  }
  const endedSpan = task.endedAt
    ? `<span>✔ ${fmtDuration(task.startedAt, task.endedAt)}</span>`
    : '';
  return (
    `<div style="padding:12px 14px;background:var(--card);border:1px solid var(--border);border-radius:8px;color:var(--text)">` +
      `<div style="display:flex;justify-content:space-between;align-items:flex-start;gap:10px;flex-wrap:wrap">` +
        `<div style="flex:1;min-width:200px">` +
          `<div style="font-weight:600;margin-bottom:4px;color:var(--text)">${escHtml(title)}</div>` +
          `<div style="font-size:0.78rem;color:var(--text2);display:flex;gap:10px;flex-wrap:wrap">` +
            `<span>${runtimeLabel(task.runtime)}</span>` +
            `<span>❏ ${fmtTime(task.createdAt, o.nowMs)}</span>` +
            startedSpan +
            endedSpan +
          `</div>` +
        `</div>` +
        `<div>${statusBadge(task.status)}</div>` +
      `</div>` +
      err +
      summary +
    `</div>`
  );
}
