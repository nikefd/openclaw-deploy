// panels/remote.js —— 远程节点：文件浏览 + 终端命令执行
// 依赖全局：window.currentNode / window.esc / window.$
// 从模块 import：files 的 tab 池 helper、utils/format
// 对外暴露（供 HTML inline onclick + 遗留 switchGlobalNode 使用）：
//   loadRemoteFiles / viewRemoteFile / runRemoteCmd

import { fileIcon, fmtSize } from '../utils/format.js';
import {
  _getOpenTabs, _pushOpenTab, _setActiveTab, _getActiveTab,
  _renderFileTabs, _renderFileContent,
  loadFiles,
} from './files.js';

const $ = (id) => document.getElementById(id);
const esc = (t) => { const d = document.createElement('div'); d.textContent = t; return d.innerHTML; };

let remoteTermCwd = '~';
let remoteFileCwd = '~';

export function resetRemoteFileCwd() { remoteFileCwd = '~'; }

export async function runRemoteCmd(cmd) {
  const output = $('remoteTermOutput');
  const cwdEl = $('remoteTermCwd');
  if (!output) return;
  output.innerHTML += `<span style="color:#10a37f">$ </span><span style="color:#e5e5e5">${esc(cmd)}</span>\n`;
  output.innerHTML += `<span style="color:#888">执行中...</span>`;
  output.scrollTop = output.scrollHeight;
  // Handle cd
  let execCmd = cmd;
  if (cmd.startsWith('cd ')) {
    execCmd = cmd + ' && pwd';
  } else {
    execCmd = 'cd ' + remoteTermCwd + ' 2>/dev/null; ' + cmd;
  }
  try {
    const r = await fetch('/api/nodes/exec', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ node: window.currentNode, command: execCmd }),
    });
    const d = await r.json();
    // Remove "执行中..."
    output.innerHTML = output.innerHTML.replace(/<span style="color:#888">执行中...<\/span>$/, '');
    if (d.ok !== false) {
      if (d.stdout) output.innerHTML += esc(d.stdout);
      if (d.stderr) output.innerHTML += `<span style="color:#f59e0b">${esc(d.stderr)}</span>`;
      if (d.exitCode && d.exitCode !== 0) output.innerHTML += `<span style="color:#ef4444">[exit ${d.exitCode}]</span>\n`;
      // Update cwd if cd command
      if (cmd.startsWith('cd ') && d.stdout) {
        remoteTermCwd = d.stdout.trim().split('\n').pop();
        if (cwdEl) cwdEl.textContent = remoteTermCwd;
      }
    } else {
      output.innerHTML += `<span style="color:#ef4444">${esc(d.error || '执行失败')}</span>\n`;
    }
    output.innerHTML += '\n';
  } catch (e) {
    output.innerHTML = output.innerHTML.replace(/<span style="color:#888">执行中...<\/span>$/, '');
    output.innerHTML += `<span style="color:#ef4444">❌ ${esc(e.message)}</span>\n\n`;
  }
  output.scrollTop = output.scrollHeight;
  $('remoteTermInput')?.focus();
}

export async function loadRemoteFiles(dir) {
  if (window.currentNode === 'local') { loadFiles(dir); return; }
  const target = dir || remoteFileCwd;
  const entries = $('fileEntries');
  const breadcrumb = $('fileBreadcrumb');
  entries.innerHTML = '<div style="padding:16px;text-align:center;color:var(--text-sec)">加载中...</div>';
  try {
    const r = await fetch('/api/nodes/exec', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        node: window.currentNode,
        command: `cd ${target} 2>/dev/null && pwd && echo "---SPLIT---" && ls -laF --color=never`,
      }),
    });
    const d = await r.json();
    if (d.ok === false) throw new Error(d.error || 'failed');
    const parts = (d.stdout || '').split('---SPLIT---');
    const pwd = (parts[0] || '').trim();
    const listing = (parts[1] || '').trim();
    if (pwd) remoteFileCwd = pwd;
    // Breadcrumb
    const bParts = pwd.split('/').filter(Boolean);
    let bc = '', acc = '';
    bParts.forEach((p, i) => {
      acc += '/' + p;
      if (i > 0) bc += '<span class="bc-sep">›</span>';
      bc += `<span class="bc-part" onclick="loadRemoteFiles('${acc}')">${p}</span>`;
    });
    breadcrumb.innerHTML = bc;
    // Parse ls output
    const lines = listing.split('\n').filter(l => l && !l.startsWith('total'));
    let html = '';
    const parent = pwd.split('/').slice(0, -1).join('/') || '/';
    if (pwd !== '/') {
      html += '<div class="file-entry" onclick="loadRemoteFiles(\'' + parent + '\')"><span class="f-icon">⬆️</span><span class="f-name dir">..</span><span class="f-size"></span></div>';
    }
    lines.forEach(line => {
      const m = line.match(/\S+\s+\S+\s+\S+\s+\S+\s+(\S+)\s+\S+\s+\S+\s+\S+\s+(.+)/);
      if (!m) return;
      const size = parseInt(m[1]) || 0;
      let name = m[2].trim();
      const isDir = name.endsWith('/');
      const isLink = name.includes(' -> ');
      if (isDir) name = name.replace(/\/$/, '');
      const linkTarget = isLink ? name.split(' -> ')[1] : '';
      const baseName = isLink ? name.split(' -> ')[0] : name;
      if (baseName === '.' || baseName === '..') return;
      const icon = isDir ? '📁' : fileIcon(baseName, false);
      const fmtSz = isDir ? '' : fmtSize(size);
      const fp = pwd + (pwd.endsWith('/') ? '' : '/') + baseName;
      const click = isDir ? `loadRemoteFiles('${fp}')` : `viewRemoteFile('${fp}','${esc(baseName)}')`;
      html += `<div class="file-entry" onclick="${click}"><span class="f-icon">${icon}</span><span class="f-name ${isDir ? 'dir' : ''}">${esc(baseName)}${isLink ? ' → ' + esc(linkTarget) : ''}</span><span class="f-size">${fmtSz}</span></div>`;
    });
    entries.innerHTML = html || '<div style="padding:20px;text-align:center;color:var(--text-sec)">📂 空目录</div>';
  } catch (e) {
    entries.innerHTML = `<div style="padding:16px;color:var(--danger)">❌ ${esc(e.message)}</div>`;
  }
}

export async function viewRemoteFile(fp, name) {
  let tab = _getOpenTabs().find(t => t.path === fp);
  if (!tab) { tab = { path: fp, name: name, content: null, size: 0 }; _pushOpenTab(tab); }
  _setActiveTab(fp); _renderFileTabs();
  if (tab.content != null) { _renderFileContent(tab); return; }
  $('fileViewerBody').innerHTML = '<div class="file-viewer-empty"><div class="empty-icon">⏳</div><div>加载中...</div></div>';
  try {
    const r = await fetch('/api/nodes/exec', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        node: window.currentNode,
        command: `cat ${JSON.stringify(fp)} 2>&1 | head -5000`,
      }),
    });
    const d = await r.json();
    if (d.ok === false) throw new Error(d.error || 'failed');
    tab.content = d.stdout || ''; tab.size = (d.stdout || '').length;
    if (_getActiveTab() === fp) _renderFileContent(tab);
  } catch (e) {
    $('fileViewerBody').innerHTML = `<div class="file-viewer-empty"><div class="empty-icon">❌</div><div>${esc(e.message)}</div></div>`;
  }
}
