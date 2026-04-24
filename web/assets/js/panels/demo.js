// panels/demo.js —— Demo 访问码管理面板
// 依赖全局：$ (document.getElementById), esc (html 转义)
// 对外暴露：loadDemoCodes / createDemoCode / deleteDemoCode

const $ = (id) => document.getElementById(id);
const esc = (t) => { const d = document.createElement('div'); d.textContent = t; return d.innerHTML; };

let demosLoaded = false;

export async function loadDemoCodes() {
  demosLoaded = true;
  try {
    const r = await fetch('/auth/demo-codes');
    if (!r.ok) throw new Error('Failed');
    const codes = await r.json();
    renderDemoCodes(codes);
  } catch (e) {
    $('demoCodes').innerHTML = `<div style="color:var(--danger);padding:12px">❌ 加载失败</div>`;
  }
}

function renderDemoCodes(codes) {
  const now = Date.now();
  if (!codes.length) { $('demoCodes').innerHTML = ''; $('demoEmpty').style.display = 'block'; return; }
  $('demoEmpty').style.display = 'none';
  $('demoCodes').innerHTML = codes.sort((a, b) => b.createdAt - a.createdAt).map(c => {
    const expired = c.expiresAt <= now;
    const expStr = new Date(c.expiresAt).toLocaleString('zh-CN');
    const createdStr = new Date(c.createdAt).toLocaleString('zh-CN');
    const accessH = Math.round((c.accessDurationMs || 0) / 3600000);
    const statusColor = expired ? 'var(--danger)' : 'var(--accent)';
    const statusText = expired ? '已过期' : '有效';
    const usedText = c.usedCount ? `已使用 ${c.usedCount} 次` : '未使用';
    const link = 'https://zhangyangbin.com/demos/village/';
    return `<div style="background:var(--input-bg);border-radius:10px;padding:16px;border-left:3px solid ${statusColor}">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
        <div style="display:flex;align-items:center;gap:10px">
          <span style="font-family:monospace;font-size:22px;font-weight:700;letter-spacing:3px;color:${expired ? 'var(--text-sec)' : 'var(--text)'}">${c.code}</span>
          <span style="font-size:11px;padding:2px 8px;border-radius:6px;background:${expired ? 'rgba(239,68,68,.15)' : 'rgba(16,163,127,.15)'};color:${statusColor}">${statusText}</span>
        </div>
        <button onclick="deleteDemoCode('${c.code}')" style="background:none;border:none;color:var(--text-sec);cursor:pointer;font-size:16px;padding:4px 8px;border-radius:6px;transition:all .15s" onmouseover="this.style.color='var(--danger)'" onmouseout="this.style.color='var(--text-sec)'" title="删除">🗑</button>
      </div>
      <div style="font-size:12px;color:var(--text-sec);display:flex;flex-wrap:wrap;gap:12px">
        ${c.label ? `<span>📝 ${esc(c.label)}</span>` : ''}
        <span>📅 创建: ${createdStr}</span>
        <span>⏰ 过期: ${expStr}</span>
        <span>🕐 访问时长: ${accessH}h</span>
        <span>👤 ${usedText}</span>
      </div>
      ${!expired ? `<div style="margin-top:10px;font-size:12px;color:var(--text-sec)">
        🔗 链接: <span style="color:var(--accent);cursor:pointer" onclick="navigator.clipboard.writeText('${link}');this.textContent='已复制!';setTimeout(()=>this.textContent='${link}',1500)">${link}</span>
        &nbsp;|&nbsp; 码: <span style="color:var(--accent);cursor:pointer;font-family:monospace" onclick="navigator.clipboard.writeText('${c.code}');this.textContent='已复制!';setTimeout(()=>this.textContent='${c.code}',1500)">${c.code}</span>
      </div>` : ''}
    </div>`;
  }).join('');
}

export async function createDemoCode() {
  const label = $('demoLabel').value.trim();
  const durationHours = parseInt($('demoDuration').value);
  const accessDurationHours = parseInt($('demoAccessDuration').value);
  $('demoCreateBtn').disabled = true;
  try {
    const r = await fetch('/auth/demo-codes', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ label, durationHours, accessDurationHours }),
    });
    if (!r.ok) throw new Error('Failed');
    $('demoLabel').value = '';
    loadDemoCodes();
  } catch (e) { alert('创建失败'); }
  $('demoCreateBtn').disabled = false;
}

export async function deleteDemoCode(code) {
  if (!confirm('确定删除此访问码？')) return;
  try {
    await fetch('/auth/demo-codes?code=' + code, { method: 'DELETE' });
    loadDemoCodes();
  } catch (e) { alert('删除失败'); }
}

// Lazy-load when the "demos" tab is clicked.
export function wireDemosTab() {
  document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
      if (tab.dataset.tab === 'demos' && !demosLoaded) loadDemoCodes();
    });
  });
}
