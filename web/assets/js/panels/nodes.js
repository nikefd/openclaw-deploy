// panels/nodes.js —— 节点管理（配对审批 + 已知节点 + 连接指引 + 自动刷新）
// 依赖全局：window.esc / window.updateNodeSelectors (legacy)
// 对外暴露（供 HTML inline onclick 和 tab loop 使用）：
//   loadNodes / approveDevice / rejectDevice / copyConnectCmd
//   toggleToken / copyToken
//   startNodesAutoRefresh / stopNodesAutoRefresh
//   getKnownNodes (供其他模块只读访问)

const $ = (id) => document.getElementById(id);
const esc = (t) => { const d = document.createElement('div'); d.textContent = t; return d.innerHTML; };

let nodesLoaded = false;
let knownNodes = [];
let tokenVisible = false;
let nodesAutoRefresh = null;

export function getKnownNodes() { return knownNodes; }
export function getNodesLoaded() { return nodesLoaded; }

export async function loadNodes() {
  nodesLoaded = true;
  try {
    const [statusRes, devicesRes, infoRes] = await Promise.all([
      fetch('/api/nodes/status'),
      fetch('/api/devices/list'),
      fetch('/api/gateway/info'),
    ]);
    const status = await statusRes.json();
    const devices = await devicesRes.json();
    const info = await infoRes.json();

    knownNodes = status.nodes || [];

    // Render connect command (auto-fill token)
    const cmdEl = $('connectCmd');
    if (cmdEl) {
      cmdEl.textContent = 'export OPENCLAW_GATEWAY_TOKEN=<点击下方显示Token>\nopenclaw node run --host ' + info.host + ' --port 443 --tls';
      fetch('/api/gateway/token').then(r => r.json()).then(d => {
        if (d.token && cmdEl) {
          cmdEl.textContent = 'export OPENCLAW_GATEWAY_TOKEN=' + d.token + '\nopenclaw node run --host ' + info.host + ' --port 443 --tls';
        }
      }).catch(() => {});
    }

    // Render pending
    const pendingEl = $('nodesPending');
    const allPending = devices.pending || [];
    if (allPending.length) {
      pendingEl.innerHTML = '<h3 style="font-size:14px;color:#f59e0b;margin-bottom:10px">⏳ 待审批的配对请求</h3>' +
        allPending.map(d => '<div class="node-card pending"><div class="node-card-header"><div class="node-status pending"></div><span class="node-name">' + esc(d.displayName || d.deviceId?.slice(0, 12) || 'Unknown') + '</span><span class="node-platform">' + (d.platform || 'unknown') + '</span></div><div class="node-meta"><span>🔑 ' + (d.deviceId?.slice(0, 16) || 'N/A') + '...</span><span>📋 角色: ' + ((d.roles || [d.role]).join(', ')) + '</span></div><div class="node-actions"><button class="approve-btn" onclick="approveDevice(\'' + (d.requestId || d.deviceId) + '\')">✅ 批准</button><button class="reject-btn" onclick="rejectDevice(\'' + (d.requestId || d.deviceId) + '\')">❌ 拒绝</button></div></div>').join('');
    } else {
      pendingEl.innerHTML = '';
    }

    // Render known nodes
    const nodesEl = $('nodesConnected');
    const nodes = status.nodes || [];
    if (nodes.length) {
      nodesEl.innerHTML = '<h3 style="font-size:14px;color:var(--text-sec);margin-bottom:10px">📡 已知节点</h3>' +
        nodes.map(n => {
          const online = n.connected || n.status === 'connected';
          const caps = (n.capabilities || n.caps || []).join(', ') || 'N/A';
          const lastSeen = n.lastConnectMs ? new Date(n.lastConnectMs).toLocaleString('zh-CN') : '从未';
          return '<div class="node-card ' + (online ? 'connected' : '') + '"><div class="node-card-header"><div class="node-status ' + (online ? 'online' : 'offline') + '"></div><span class="node-name">' + esc(n.displayName || n.name || n.nodeId?.slice(0, 12) || 'Node') + '</span><span class="node-platform">' + (n.platform || 'unknown') + '</span></div><div class="node-meta"><span>' + (online ? '🟢 在线' : '🔴 离线') + '</span><span>🕐 最后连接: ' + lastSeen + '</span><span>🔧 能力: ' + caps + '</span></div></div>';
        }).join('');
    } else {
      nodesEl.innerHTML = '<div style="text-align:center;padding:20px;color:var(--text-sec);font-size:13px">暂无已连接节点，按照下方指引接入新机器</div>';
    }

    // Update selectors (legacy function still in index.html)
    if (typeof window.updateNodeSelectors === 'function') {
      window.updateNodeSelectors(nodes);
    }
  } catch (e) {
    $('nodesConnected').innerHTML = '<div style="color:var(--danger);padding:12px">❌ 加载失败: ' + e.message + '</div>';
  }
}

export async function approveDevice(id) {
  try {
    const r = await fetch('/api/devices/approve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ requestId: id }),
    });
    const d = await r.json();
    if (d.ok) { alert('✅ 已批准'); loadNodes(); }
    else alert('❌ 失败: ' + (d.error || JSON.stringify(d)));
  } catch (e) { alert('❌ ' + e.message); }
}

export async function rejectDevice(id) {
  if (!confirm('确定拒绝此配对请求？')) return;
  try {
    const r = await fetch('/api/devices/reject', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ requestId: id }),
    });
    const d = await r.json();
    if (d.ok) { alert('已拒绝'); loadNodes(); }
    else alert('❌ 失败: ' + (d.error || JSON.stringify(d)));
  } catch (e) { alert('❌ ' + e.message); }
}

export function copyConnectCmd() {
  const el = $('connectCmd');
  if (el) navigator.clipboard.writeText(el.textContent).then(() => {
    const btn = el.nextElementSibling?.querySelector('.copy-cmd') || el.parentElement.querySelector('.copy-cmd');
    if (btn) { btn.textContent = '✅ 已复制'; setTimeout(() => btn.textContent = '📋 复制命令', 1500); }
  });
}

export async function toggleToken() {
  const display = $('tokenDisplay');
  const val = $('tokenValue');
  const btn = $('tokenToggleBtn');
  if (tokenVisible) { display.style.display = 'none'; btn.textContent = '🔑 显示 Token'; tokenVisible = false; return; }
  btn.textContent = '⏳ 加载中...';
  try {
    const r = await fetch('/api/gateway/token');
    const d = await r.json();
    if (d.token) { val.textContent = d.token; display.style.display = 'block'; btn.textContent = '🔒 隐藏 Token'; tokenVisible = true; }
    else { alert('❌ 获取失败: ' + (d.error || 'unknown')); btn.textContent = '🔑 显示 Token'; }
  } catch (e) { alert('❌ ' + e.message); btn.textContent = '🔑 显示 Token'; }
}

export function copyToken() {
  const val = $('tokenValue');
  if (val) navigator.clipboard.writeText(val.textContent).then(() => {
    const btn = val.nextElementSibling;
    if (btn) { btn.textContent = '✅'; setTimeout(() => btn.textContent = '📋', 1500); }
  });
}

export function startNodesAutoRefresh() {
  if (nodesAutoRefresh) return;
  nodesAutoRefresh = setInterval(() => {
    const panel = $('panel-nodes');
    if (panel && panel.classList.contains('active')) loadNodes();
  }, 5000);
}

export function stopNodesAutoRefresh() {
  if (nodesAutoRefresh) { clearInterval(nodesAutoRefresh); nodesAutoRefresh = null; }
}
