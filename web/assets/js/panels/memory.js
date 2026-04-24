// panels/memory.js —— Memory 面板（长期记忆、每日记录、项目记忆、身份文件、定时整理）
// 对外暴露（供 HTML inline onclick 使用）：
//   loadMemoryPanel / toggleMemArch / saveMemoryCronTime
//   showMemWelcome / memGoBack / openMemFile
//   startMemEdit / cancelMemEdit / saveMemFile

const WORKSPACE = '/home/nikefd/.openclaw/workspace';
const MEMORY_CRON_ID = '6348b819-41af-43f6-bbcc-8e5bbf70e33f';

const MEMORY_FILES = {
  longTerm: [{ name: 'MEMORY.md', path: WORKSPACE + '/MEMORY.md', icon: '📌' }],
  identity: [
    { name: 'IDENTITY.md', path: WORKSPACE + '/IDENTITY.md', icon: '🪪' },
    { name: 'SOUL.md',     path: WORKSPACE + '/SOUL.md',     icon: '👻' },
    { name: 'USER.md',     path: WORKSPACE + '/USER.md',     icon: '👤' },
    { name: 'TOOLS.md',    path: WORKSPACE + '/TOOLS.md',    icon: '🔧' },
  ],
};

let memoryLoaded = false;
let memoryEditing = false;
let currentMemFile = null;
let memoryCronTime = '23:00';

function escapeHtml(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

export async function loadMemoryPanel() {
  if (memoryLoaded) return;
  memoryLoaded = true;
  try {
    const r = await fetch('/api/files/list?path=' + encodeURIComponent(WORKSPACE + '/memory'));
    const data = await r.json();
    const allFiles = (data.entries || [])
      .filter(e => e.type === 'file' && e.name.endsWith('.md'))
      .sort((a, b) => b.name.localeCompare(a.name));
    MEMORY_FILES.daily = allFiles.map(f => ({ name: f.name, path: f.path, icon: '📝', size: f.size }));
  } catch (e) { MEMORY_FILES.daily = []; }
  try {
    const r2 = await fetch('/api/files/list?path=' + encodeURIComponent(WORKSPACE + '/memory/projects'));
    const data2 = await r2.json();
    const projFiles = (data2.entries || [])
      .filter(e => e.type === 'file' && e.name.endsWith('.md'))
      .sort((a, b) => a.name.localeCompare(b.name));
    const projIcons = { finance: '🚨', climbing: '🧗', interview: '💼', village: '🏘', 'ai-frontier': '🔭' };
    MEMORY_FILES.projects = projFiles.map(f => {
      const base = f.name.replace('.md', '');
      return { name: f.name, path: f.path, icon: projIcons[base] || '📂', size: f.size };
    });
  } catch (e) { MEMORY_FILES.projects = []; }
  renderMemorySidebar();
}

export function toggleMemArch() {
  document.querySelector('.memory-arch')?.classList.toggle('open');
}

export async function saveMemoryCronTime() {
  const input = document.getElementById('cronTimeInput');
  if (!input) return;
  const [hh, mm] = input.value.split(':').map(Number);
  const statusEl = document.getElementById('cronStatus');
  try {
    const r = await fetch('/v1/cron/jobs/' + MEMORY_CRON_ID, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ schedule: { kind: 'cron', expr: `${mm} ${hh} * * *`, tz: 'Asia/Shanghai' } }),
    });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    memoryCronTime = input.value;
    if (statusEl) statusEl.textContent = '✅ 已保存';
    setTimeout(() => { if (statusEl) statusEl.textContent = ''; }, 2000);
  } catch (e) {
    if (statusEl) statusEl.textContent = '❌ 保存失败: ' + e.message;
  }
}

export function showMemWelcome() {
  currentMemFile = null; renderMemorySidebar();
  const panel = document.querySelector('.memory-panel');
  const welcome = document.getElementById('memoryWelcome');
  const editor = document.querySelector('.memory-editor');
  panel.classList.remove('mem-viewing'); panel.classList.add('mem-welcome');
  if (welcome) welcome.style.display = '';
  if (editor) editor.style.display = 'none';
}

export function memGoBack() {
  const panel = document.querySelector('.memory-panel');
  panel.classList.remove('mem-viewing', 'mem-welcome');
  currentMemFile = null; renderMemorySidebar();
  const welcome = document.getElementById('memoryWelcome');
  const editor = document.querySelector('.memory-editor');
  if (welcome) welcome.style.display = 'none';
  if (editor) editor.style.display = 'none';
}

function renderMemorySidebar() {
  const sidebar = document.querySelector('.memory-sidebar');
  if (!sidebar) return;
  const totalFiles = 1 + (MEMORY_FILES.daily || []).length + MEMORY_FILES.identity.length;
  let totalSize = 0;
  [MEMORY_FILES.longTerm, MEMORY_FILES.daily || [], MEMORY_FILES.identity].flat()
    .forEach(f => { if (f.size) totalSize += f.size; });
  const projCount = (MEMORY_FILES.projects || []).length;
  let html = `<h3 style="cursor:pointer" onclick="showMemWelcome()">🧠 记忆管理</h3>`;
  html += `<div class="memory-stats"><strong>${totalFiles + projCount}</strong> 个文件`;
  if (totalSize > 0) html += ` · <strong>${(totalSize / 1024).toFixed(1)}</strong> KB`;
  html += `</div>`;
  html += `<div class="memory-category"><div class="memory-category-title">📌 长期记忆</div>`;
  MEMORY_FILES.longTerm.forEach(f => {
    html += `<div class="memory-file${currentMemFile === f.path ? ' active' : ''}" onclick="openMemFile('${f.path}')">${f.icon} ${f.name}${f.size ? `<span class="mem-size">${(f.size / 1024).toFixed(1)}K</span>` : ''}</div>`;
  });
  html += `</div>`;
  if (MEMORY_FILES.projects && MEMORY_FILES.projects.length) {
    html += `<div class="memory-category"><div class="memory-category-title">📂 项目记忆 (${MEMORY_FILES.projects.length})</div>`;
    MEMORY_FILES.projects.forEach(f => {
      html += `<div class="memory-file${currentMemFile === f.path ? ' active' : ''}" onclick="openMemFile('${f.path}')">${f.icon} ${f.name}${f.size ? `<span class="mem-size">${(f.size / 1024).toFixed(1)}K</span>` : ''}</div>`;
    });
    html += `</div>`;
  }
  if (MEMORY_FILES.daily && MEMORY_FILES.daily.length) {
    html += `<div class="memory-category"><div class="memory-category-title">📝 每日记录 (${MEMORY_FILES.daily.length})</div>`;
    MEMORY_FILES.daily.forEach(f => {
      html += `<div class="memory-file${currentMemFile === f.path ? ' active' : ''}" onclick="openMemFile('${f.path}')">${f.icon} ${f.name}${f.size ? `<span class="mem-size">${(f.size / 1024).toFixed(1)}K</span>` : ''}</div>`;
    });
    html += `</div>`;
  }
  html += `<div class="memory-category"><div class="memory-category-title">🪪 身份文件</div>`;
  MEMORY_FILES.identity.forEach(f => {
    html += `<div class="memory-file${currentMemFile === f.path ? ' active' : ''}" onclick="openMemFile('${f.path}')">${f.icon} ${f.name}</div>`;
  });
  html += `</div>`;
  html += `<div class="memory-cron"><label>⏰ 每日自动整理</label><div class="memory-cron-row"><input type="time" id="cronTimeInput" value="${memoryCronTime}"><button class="cron-save" onclick="saveMemoryCronTime()">保存</button></div><div class="cron-status" id="cronStatus"></div></div>`;
  sidebar.innerHTML = html;
}

export async function openMemFile(fp) {
  currentMemFile = fp; memoryEditing = false; renderMemorySidebar();
  const panel = document.querySelector('.memory-panel');
  const editor = document.querySelector('.memory-editor');
  const welcome = document.getElementById('memoryWelcome');
  if (welcome) welcome.style.display = 'none';
  editor.style.display = 'flex';
  panel.classList.remove('mem-welcome'); panel.classList.add('mem-viewing');
  try {
    const r = await fetch('/api/files/read?path=' + encodeURIComponent(fp));
    const data = await r.json();
    if (data.error) throw new Error(data.error);
    editor.innerHTML = `<div class="memory-editor-header"><button class="mem-back" onclick="memGoBack()">← 返回</button><span class="mem-title">${fp.split('/').pop()}</span><button onclick="startMemEdit()">✏️ 编辑</button></div><div class="memory-content">${escapeHtml(data.content)}</div>`;
    editor.dataset.content = data.content; editor.dataset.path = fp;
  } catch (e) {
    editor.innerHTML = `<div class="memory-empty"><div class="mem-icon">❌</div><div>加载失败: ${e.message}</div></div>`;
  }
}

export function startMemEdit() {
  memoryEditing = true;
  const editor = document.querySelector('.memory-editor');
  const content = editor.dataset.content || '', fp = editor.dataset.path || '';
  editor.innerHTML = `<div class="memory-editor-header"><span class="mem-title">${fp.split('/').pop()}</span><button onclick="cancelMemEdit()">取消</button><button class="save-btn" onclick="saveMemFile()">💾 保存</button></div><textarea class="memory-textarea" id="memTextarea">${escapeHtml(content)}</textarea>`;
}

export function cancelMemEdit() {
  if (currentMemFile) openMemFile(currentMemFile);
}

export async function saveMemFile() {
  const textarea = document.getElementById('memTextarea');
  const editor = document.querySelector('.memory-editor');
  const fp = editor.dataset.path;
  if (!fp || !textarea) return;
  try {
    const r = await fetch('/api/files/write', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: fp, content: textarea.value }),
    });
    const data = await r.json();
    if (data.error) throw new Error(data.error);
    editor.dataset.content = textarea.value; openMemFile(fp);
  } catch (e) {
    alert('保存失败: ' + e.message);
  }
}

// NOTE: 'memory' tab lazy-load is in the legacy tab loop (`if(...!memoryLoaded)
// loadMemoryPanel()`). Since memoryLoaded is now module-scoped, we change that
// call site to be unconditional in index.html (module self-guards via
// internal flag).
