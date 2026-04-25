// ui/demoCodes.js — pure HTML/data helpers for the Demo Codes admin panel.
//
// No DOM, no fetch, no globals. Just data → HTML strings.
// Caller does $('demoCodes').innerHTML = demoCodesListHtml(codes).

const DEMO_LINK = 'https://zhangyangbin.com/demos/village/';

/**
 * Plain-string HTML escape (no DOM dependency). Equivalent to the inline
 * `esc()` helper for typical text content.
 * @param {*} s
 * @returns {string}
 */
function escHtml(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/**
 * Compute display metadata for a single demo code. Pure: no Date.now() side
 * effect — caller passes `now` for testability.
 *
 * @param {{code:string, label?:string, createdAt:number, expiresAt:number,
 *          accessDurationMs?:number, usedCount?:number}} c
 * @param {number} now ms timestamp (Date.now() at call site)
 * @param {string} [locale='zh-CN'] for toLocaleString formatting
 * @returns {{
 *   expired:boolean, statusText:string, statusColor:string, statusBg:string,
 *   codeColor:string, expStr:string, createdStr:string, accessHours:number,
 *   usedText:string,
 * }}
 */
export function demoCodeMeta(c, now, locale = 'zh-CN') {
  const expired = c.expiresAt <= now;
  return {
    expired,
    statusText: expired ? '已过期' : '有效',
    statusColor: expired ? 'var(--danger)' : 'var(--accent)',
    statusBg:    expired ? 'rgba(239,68,68,.15)' : 'rgba(16,163,127,.15)',
    codeColor:   expired ? 'var(--text-sec)' : 'var(--text)',
    expStr:     new Date(c.expiresAt).toLocaleString(locale),
    createdStr: new Date(c.createdAt).toLocaleString(locale),
    accessHours: Math.round((c.accessDurationMs || 0) / 3600000),
    usedText: c.usedCount ? `已使用 ${c.usedCount} 次` : '未使用',
  };
}

/**
 * HTML for a single demo code card. Caller must already have a wrapper.
 * @param {object} c demo code object (see demoCodeMeta)
 * @param {number} now ms timestamp
 * @returns {string}
 */
export function demoCodeCardHtml(c, now) {
  const m = demoCodeMeta(c, now);
  const codeStr = escHtml(c.code);
  const labelLine = c.label ? `<span>📝 ${escHtml(c.label)}</span>` : '';
  const linkLine = m.expired ? '' : (
    `<div style="margin-top:10px;font-size:12px;color:var(--text-sec)">` +
      `🔗 链接: <span style="color:var(--accent);cursor:pointer" onclick="navigator.clipboard.writeText('${DEMO_LINK}');this.textContent='已复制!';setTimeout(()=>this.textContent='${DEMO_LINK}',1500)">${DEMO_LINK}</span>` +
      `&nbsp;|&nbsp; 码: <span style="color:var(--accent);cursor:pointer;font-family:monospace" onclick="navigator.clipboard.writeText('${codeStr}');this.textContent='已复制!';setTimeout(()=>this.textContent='${codeStr}',1500)">${codeStr}</span>` +
    `</div>`
  );

  return (
    `<div style="background:var(--input-bg);border-radius:10px;padding:16px;border-left:3px solid ${m.statusColor}">` +
      `<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">` +
        `<div style="display:flex;align-items:center;gap:10px">` +
          `<span style="font-family:monospace;font-size:22px;font-weight:700;letter-spacing:3px;color:${m.codeColor}">${codeStr}</span>` +
          `<span style="font-size:11px;padding:2px 8px;border-radius:6px;background:${m.statusBg};color:${m.statusColor}">${m.statusText}</span>` +
        `</div>` +
        `<button onclick="deleteDemoCode('${codeStr}')" style="background:none;border:none;color:var(--text-sec);cursor:pointer;font-size:16px;padding:4px 8px;border-radius:6px;transition:all .15s" onmouseover="this.style.color='var(--danger)'" onmouseout="this.style.color='var(--text-sec)'" title="删除">🗑</button>` +
      `</div>` +
      `<div style="font-size:12px;color:var(--text-sec);display:flex;flex-wrap:wrap;gap:12px">` +
        labelLine +
        `<span>📅 创建: ${m.createdStr}</span>` +
        `<span>⏰ 过期: ${m.expStr}</span>` +
        `<span>🕐 访问时长: ${m.accessHours}h</span>` +
        `<span>👤 ${m.usedText}</span>` +
      `</div>` +
      linkLine +
    `</div>`
  );
}

/**
 * Sort codes (newest first) and return joined HTML for the full list.
 * Returns '' for empty input — caller should toggle the empty-state UI.
 * @param {Array} codes
 * @param {number} now
 * @returns {string}
 */
export function demoCodesListHtml(codes, now) {
  if (!codes || !codes.length) return '';
  return [...codes]
    .sort((a, b) => b.createdAt - a.createdAt)
    .map(c => demoCodeCardHtml(c, now))
    .join('');
}
