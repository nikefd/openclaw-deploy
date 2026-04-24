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
});

// Marker so we can verify module loaded in devtools.
window.__ocRefactor = { step: '3c', loadedAt: Date.now() };
console.info('[oc-refactor] modules loaded', APP_VERSION, '(step 3c: demo + skills + memory panels)');
