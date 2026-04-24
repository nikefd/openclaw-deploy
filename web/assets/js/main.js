// main.js —— ES module 入口
// 当前阶段：把 config 常量挂到 window，保持与遗留脚本兼容。
// 后续会逐步把业务模块搬进来，最终去掉 window.* 全局。

import {
  APP_VERSION, API, TOKEN,
  STORAGE_KEY, AGENT_KEY, THEME_KEY, MODEL_KEY,
  AGENTS, MODELS,
} from './config.js';

// Expose to legacy inline script (which still lives in index.html for now).
Object.assign(window, {
  APP_VERSION, API, TOKEN,
  STORAGE_KEY, AGENT_KEY, THEME_KEY, MODEL_KEY,
  AGENTS, MODELS,
});

// Marker so we can verify module loaded in devtools.
window.__ocRefactor = { step: 2, loadedAt: Date.now() };
console.info('[oc-refactor] config module loaded', APP_VERSION);
