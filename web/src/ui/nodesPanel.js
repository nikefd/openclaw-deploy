// ui/nodesPanel.js — pure HTML/data helpers for the Nodes admin panel.
//
// Side-effect free: no fetch, no DOM, no globals. Pure string output.
// Caller does $('nodesPending').innerHTML = pendingNodesListHtml(devices).

/** Plain-string HTML escape (no DOM dependency). */
function escHtml(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/**
 * Format a single pending device as a card.
 *
 * @param {{requestId?:string, deviceId?:string, displayName?:string,
 *          platform?:string, role?:string, roles?:string[]}} d
 * @returns {string}
 */
export function pendingNodeCardHtml(d) {
  const id = d.requestId || d.deviceId || '';
  const name = escHtml(d.displayName || (d.deviceId ? d.deviceId.slice(0, 12) : 'Unknown'));
  const platform = escHtml(d.platform || 'unknown');
  const idShort = (d.deviceId ? d.deviceId.slice(0, 16) : 'N/A') + '...';
  const roles = (d.roles || (d.role ? [d.role] : [])).join(', ');

  return (
    `<div class="node-card pending">` +
      `<div class="node-card-header">` +
        `<div class="node-status pending"></div>` +
        `<span class="node-name">${name}</span>` +
        `<span class="node-platform">${platform}</span>` +
      `</div>` +
      `<div class="node-meta">` +
        `<span>🔑 ${escHtml(idShort)}</span>` +
        `<span>📋 角色: ${escHtml(roles)}</span>` +
      `</div>` +
      `<div class="node-actions">` +
        `<button class="approve-btn" onclick="approveDevice('${id}')">✅ 批准</button>` +
        `<button class="reject-btn" onclick="rejectDevice('${id}')">❌ 拒绝</button>` +
      `</div>` +
    `</div>`
  );
}

/**
 * Format the full pending-devices block (header + cards), or empty string
 * when there are no pending devices. Caller can assign result directly to
 * innerHTML.
 *
 * @param {Array} devices
 * @returns {string}
 */
export function pendingNodesListHtml(devices) {
  if (!devices || !devices.length) return '';
  return (
    `<h3 style="font-size:14px;color:#f59e0b;margin-bottom:10px">⏳ 待审批的配对请求</h3>` +
    devices.map(pendingNodeCardHtml).join('')
  );
}

/**
 * Compute display metadata for a known node. Pure: caller passes locale.
 * Default locale 'zh-CN' for parity with the inline implementation.
 *
 * @param {object} n raw node entry
 * @param {string} [locale='zh-CN']
 * @returns {{
 *   online:boolean, name:string, platform:string, caps:string,
 *   lastSeen:string, statusEmoji:string, statusText:string,
 * }}
 */
export function nodeMeta(n, locale = 'zh-CN') {
  const online = !!(n.connected || n.status === 'connected');
  const caps = (n.capabilities || n.caps || []).join(', ') || 'N/A';
  const lastSeen = n.lastConnectMs
    ? new Date(n.lastConnectMs).toLocaleString(locale)
    : '从未';
  return {
    online,
    name:        n.displayName || n.name || (n.nodeId ? n.nodeId.slice(0, 12) : 'Node'),
    platform:    n.platform || 'unknown',
    caps,
    lastSeen,
    statusEmoji: online ? '🟢 在线' : '🔴 离线',
    statusText:  online ? 'online' : 'offline',
  };
}

/**
 * Format a single connected/known node as a card.
 *
 * @param {object} n raw node entry
 * @param {string} [locale='zh-CN']
 * @returns {string}
 */
export function connectedNodeCardHtml(n, locale = 'zh-CN') {
  const m = nodeMeta(n, locale);
  return (
    `<div class="node-card ${m.online ? 'connected' : ''}">` +
      `<div class="node-card-header">` +
        `<div class="node-status ${m.statusText}"></div>` +
        `<span class="node-name">${escHtml(m.name)}</span>` +
        `<span class="node-platform">${escHtml(m.platform)}</span>` +
      `</div>` +
      `<div class="node-meta">` +
        `<span>${m.statusEmoji}</span>` +
        `<span>🕐 最后连接: ${escHtml(m.lastSeen)}</span>` +
        `<span>🔧 能力: ${escHtml(m.caps)}</span>` +
      `</div>` +
    `</div>`
  );
}

/**
 * Format the full known-nodes block (header + cards) or an empty-state
 * message. Caller assigns result to innerHTML.
 *
 * @param {Array} nodes
 * @param {string} [locale='zh-CN']
 * @returns {string}
 */
export function connectedNodesListHtml(nodes, locale = 'zh-CN') {
  if (!nodes || !nodes.length) {
    return (
      `<div style="text-align:center;padding:20px;color:var(--text-sec);font-size:13px">` +
        `暂无已连接节点，按照下方指引接入新机器` +
      `</div>`
    );
  }
  return (
    `<h3 style="font-size:14px;color:var(--text-sec);margin-bottom:10px">📡 已知节点</h3>` +
    nodes.map(n => connectedNodeCardHtml(n, locale)).join('')
  );
}
