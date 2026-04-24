// main.js —— ES module 入口
// 当前阶段：把 config 常量挂到 window，保持与遗留脚本兼容。
// 后续会逐步把业务模块搬进来，最终去掉 window.* 全局。

import {
  APP_VERSION, API, TOKEN,
  STORAGE_KEY, AGENT_KEY, THEME_KEY, MODEL_KEY,
  AGENTS, MODELS,
} from './config.js';

import { loadDemoCodes, createDemoCode, deleteDemoCode, wireDemosTab } from './panels/demo.js';
import { loadSkillsPanel, setSkillFilter, filterSkills, openSkill, closeSkillDetail } from './panels/skills.js';
import {
  loadMemoryPanel, toggleMemArch, saveMemoryCronTime,
  showMemWelcome, memGoBack, openMemFile,
  startMemEdit, cancelMemEdit, saveMemFile,
} from './panels/memory.js';
import {
  toggleExpertPanel, selectExpertTeam, queryExperts, cancelExpertRequests,
  wireExpertToggle,
} from './panels/experts.js';
import {
  loadFiles, viewFile, switchTab, closeTab,
  uploadFiles, downloadCurrentFile,
  getCurrentDir, getFilesLoaded, resetFilesLoaded,
  wireUploadInput,
} from './panels/files.js';
import { fileIcon, fileLang, fmtSize } from './utils/format.js';
import {
  loadRemoteFiles, viewRemoteFile, runRemoteCmd, resetRemoteFileCwd,
} from './panels/remote.js';
import {
  loadNodes, approveDevice, rejectDevice, copyConnectCmd,
  toggleToken, copyToken,
  startNodesAutoRefresh, stopNodesAutoRefresh,
  getKnownNodes, getNodesLoaded,
} from './panels/nodes.js';

// Expose to legacy inline script (which still lives in index.html for now).
Object.assign(window, {
  APP_VERSION, API, TOKEN,
  STORAGE_KEY, AGENT_KEY, THEME_KEY, MODEL_KEY,
  AGENTS, MODELS,
  // panels/demo
  loadDemoCodes, createDemoCode, deleteDemoCode,
  // panels/skills
  loadSkillsPanel, setSkillFilter, filterSkills, openSkill, closeSkillDetail,
  // panels/memory
  loadMemoryPanel, toggleMemArch, saveMemoryCronTime,
  showMemWelcome, memGoBack, openMemFile,
  startMemEdit, cancelMemEdit, saveMemFile,
  // panels/experts
  toggleExpertPanel, selectExpertTeam, queryExperts, cancelExpertRequests,
  // panels/files
  loadFiles, viewFile, switchTab, closeTab,
  uploadFiles, downloadCurrentFile,
  getCurrentDir, getFilesLoaded, resetFilesLoaded,
  // utils/format (shared by files + remote + etc.)
  fileIcon, fileLang, fmtSize,
  // panels/remote
  loadRemoteFiles, viewRemoteFile, runRemoteCmd, resetRemoteFileCwd,
  // panels/nodes
  loadNodes, approveDevice, rejectDevice, copyConnectCmd,
  toggleToken, copyToken,
  startNodesAutoRefresh, stopNodesAutoRefresh,
  getKnownNodes, getNodesLoaded,
});

// Wire lazy-load hooks once DOM is ready. <script type="module"> is deferred,
// so parsing is done by the time this runs — but tabs are defined in the
// legacy inline script which also runs deferred; use DOMContentLoaded to be safe.
function onReady(fn) {
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', fn, { once: true });
  else fn();
}
onReady(() => {
  wireDemosTab();
  wireExpertToggle();
  wireUploadInput();
});

// Marker so we can verify module loaded in devtools.
window.__ocRefactor = { step: '4d', loadedAt: Date.now() };
console.info('[oc-refactor] modules loaded', APP_VERSION, '(step 4d: + nodes panel — all panels done!)');
