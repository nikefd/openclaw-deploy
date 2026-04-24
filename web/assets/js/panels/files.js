// panels/files.js —— 本地文件浏览 + 多标签查看 + 上传
// 依赖全局：window.esc (legacy), window.$
// 对外暴露（供 HTML inline onclick / 其他遗留代码使用）：
//   loadFiles / viewFile / switchTab / closeTab / uploadFiles / downloadCurrentFile
// 暴露的 state getters/setters（供 panels/remote 等共享）：
//   getCurrentDir / resetFilesLoaded / getFilesLoaded

import { fileIcon, fileLang, fmtSize } from '../utils/format.js';

const $ = (id) => document.getElementById(id);
const esc = (t) => { const d = document.createElement('div'); d.textContent = t; return d.innerHTML; };

let filesLoaded = false;
let currentDir = '';
let openTabs = [];
let activeTab = null;

export function getCurrentDir() { return currentDir; }
export function getFilesLoaded() { return filesLoaded; }
export function resetFilesLoaded() { filesLoaded = false; }

export async function loadFiles(dir) {
  filesLoaded = true;
  const url = dir ? `/api/files/list?path=${encodeURIComponent(dir)}` : '/api/files/list';
  try {
    const r = await fetch(url);
    const d = await r.json();
    currentDir = d.path;
    // Breadcrumb
    const parts = d.path.split('/').filter(Boolean);
    let bc = ''; let accum = '';
    parts.forEach((p, i) => {
      accum += '/' + p;
      if (i > 0) bc += '<span class="bc-sep">›</span>';
      bc += `<span class="bc-part" onclick="loadFiles('${accum}')">${p}</span>`;
    });
    $('fileBreadcrumb').innerHTML = bc;
    // Entries
    let html = '';
    if (d.parent && d.parent !== d.path) {
      html += `<div class="file-entry" onclick="loadFiles('${d.parent}')"><span class="f-icon">⬆️</span><span class="f-name dir">..</span><span class="f-size"></span></div>`;
    }
    d.entries.forEach(e => {
      const icon = fileIcon(e.name, e.type === 'dir');
      const size = e.type === 'file' ? fmtSize(e.size) : '';
      const cls = e.type === 'dir' ? 'dir' : '';
      const click = e.type === 'dir' ? `loadFiles('${e.path}')` : `viewFile('${e.path}','${e.name}')`;
      html += `<div class="file-entry" data-path="${e.path}" onclick="${click}"><span class="f-icon">${icon}</span><span class="f-name ${cls}">${esc(e.name)}</span><span class="f-size">${size}</span></div>`;
    });
    $('fileEntries').innerHTML = html || '<div style="padding:20px;text-align:center;color:var(--text-sec);font-size:13px">📂 空目录</div>';
    highlightActiveFile();
  } catch (e) {
    $('fileEntries').innerHTML = `<div style="padding:16px;color:var(--danger)">❌ 加载失败: ${e.message}</div>`;
  }
}

// Internal helpers — exported only so panels/remote can share the tab pool.
// Will be folded into a shared tabs module in a later refactor step.
export function _getOpenTabs() { return openTabs; }
export function _pushOpenTab(tab) { openTabs.push(tab); }
export function _setActiveTab(fp) { activeTab = fp; }
export function _getActiveTab() { return activeTab; }

function renderFileTabs() {
  let html = '';
  openTabs.forEach(t => {
    const icon = fileIcon(t.name, false);
    const isActive = activeTab === t.path;
    html += `<div class="file-tab ${isActive ? 'active' : ''}" data-path="${t.path}" onclick="switchTab('${t.path}')">
      <span class="tab-icon">${icon}</span><span class="tab-name">${esc(t.name)}</span>
      <button class="tab-close" onclick="event.stopPropagation();closeTab('${t.path}')">✕</button>
    </div>`;
  });
  $('fileTabs').innerHTML = html;
}

export function switchTab(fp) {
  activeTab = fp;
  renderFileTabs();
  const tab = openTabs.find(t => t.path === fp);
  if (tab && tab.content != null) renderFileContent(tab);
  highlightActiveFile();
}

export function closeTab(fp) {
  openTabs = openTabs.filter(t => t.path !== fp);
  if (activeTab === fp) { activeTab = openTabs.length ? openTabs[openTabs.length - 1].path : null; }
  renderFileTabs();
  if (activeTab) {
    const t = openTabs.find(x => x.path === activeTab);
    if (t) renderFileContent(t);
  } else {
    $('fileViewerBody').innerHTML = `<div class="file-viewer-empty"><div class="empty-icon">📄</div><div>选择文件查看内容</div><div style="font-size:12px;opacity:.6">从左侧目录中点击文件</div></div>`;
    $('fileInfoBar').style.display = 'none';
  }
  highlightActiveFile();
}

export function downloadCurrentFile() {
  const tab = openTabs.find(t => t.path === activeTab);
  if (!tab) return;
  const a = document.createElement('a');
  a.href = '/api/files/download?path=' + encodeURIComponent(tab.path);
  a.download = tab.name;
  a.click();
}

function renderFileContent(tab) {
  const lines = tab.content.split('\n');
  const lineNums = lines.map((_, i) => i + 1).join('\n');
  $('fileViewerBody').innerHTML = `<div class="line-numbers">${lineNums}</div><div class="file-content">${esc(tab.content)}</div>`;
  $('fileInfoBar').style.display = 'flex';
  $('fileInfoLang').textContent = '📝 ' + fileLang(tab.name);
  $('fileInfoLines').textContent = '📏 ' + lines.length + ' 行';
  $('fileInfoSize').textContent = '💾 ' + fmtSize(tab.size);
  $('fileInfoPath').textContent = tab.path;
  // Sync scroll between line numbers and content
  const body = $('fileViewerBody');
  body.onscroll = () => { body.querySelector('.line-numbers').style.transform = `translateY(0)`; };
}

export async function viewFile(fp, name) {
  // Check if already open
  let tab = openTabs.find(t => t.path === fp);
  if (!tab) {
    tab = { path: fp, name: name, content: null, size: 0 };
    openTabs.push(tab);
  }
  activeTab = fp;
  renderFileTabs();
  if (tab.content != null) { renderFileContent(tab); highlightActiveFile(); return; }
  // Loading state
  $('fileViewerBody').innerHTML = `<div class="file-viewer-empty"><div class="empty-icon">⏳</div><div>加载中...</div></div>`;
  try {
    const r = await fetch(`/api/files/read?path=${encodeURIComponent(fp)}`);
    const d = await r.json();
    if (d.error) throw new Error(d.error);
    tab.content = d.content; tab.size = d.size;
    if (activeTab === fp) renderFileContent(tab);
  } catch (e) {
    $('fileViewerBody').innerHTML = `<div class="file-viewer-empty"><div class="empty-icon">❌</div><div>${e.message}</div></div>`;
  }
  highlightActiveFile();
}

export function _renderFileTabs() { renderFileTabs(); }
export function _renderFileContent(tab) { renderFileContent(tab); }

function highlightActiveFile() {
  document.querySelectorAll('.file-entry').forEach(el => {
    el.classList.toggle('active', el.dataset.path === activeTab);
  });
}

export function uploadFiles() {
  $('uploadInput').click();
}

async function handleUploadChange(e) {
  const files = e.target.files;
  if (!files.length) return;
  const fd = new FormData();
  for (const f of files) fd.append('file', f);
  try {
    const targetDir = currentDir || '';
    const url = targetDir ? '/api/files/upload?dir=' + encodeURIComponent(targetDir) : '/api/files/upload';
    const r = await fetch(url, { method: 'POST', body: fd });
    const d = await r.json();
    if (d.ok) {
      const names = d.files.map(f => f.name).join(', ');
      alert('✅ 上传成功: ' + names);
      loadFiles(currentDir);
    } else {
      alert('❌ 上传失败: ' + (d.error || 'unknown'));
    }
  } catch (err) {
    alert('❌ 上传失败: ' + err.message);
  }
  $('uploadInput').value = '';
}

export function wireUploadInput() {
  const el = $('uploadInput');
  if (el) el.addEventListener('change', handleUploadChange);
}
