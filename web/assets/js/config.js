// config.js —— 纯常量配置，无副作用
// 通过挂载到 window 暴露给遗留脚本；后续会逐步改为 ES module import。

export const APP_VERSION = '2026-04-24-refactor-step2';

export const API = '/v1/chat/completions';
export const TOKEN = '17043bad6b19491dfa222d681d43584fbc3e8dd3781edfbc';

export const STORAGE_KEY = 'oc_chats_v2';
export const AGENT_KEY = 'oc_selected_agent';
export const THEME_KEY = 'oc_theme';
export const MODEL_KEY = 'oc_model';

export const AGENTS = [
  { id: 'main',     name: '狗蛋',     emoji: '🦞', color: '#10a37f', desc: '你的全能助手' },
  { id: 'climbing', name: '攀岩教练', emoji: '🧗', color: '#f97316', desc: '训练记录、进步分析、训练计划', mention: '@攀岩教练' },
  { id: 'finance',  name: '理财管家', emoji: '🎩', color: '#eab308', desc: 'A股选股、模拟交易、行情分析', mention: '@理财管家' },
];

export const MODELS = [
  { id: 'openclaw',                              name: 'Default (Haiku)', emoji: '🐰', icon: '🐰', cost: '1x',  desc: '快速轻量，日常任务' },
  { id: 'github-copilot/claude-opus-4.7',        name: 'Claude Opus 4.7', emoji: '🐙', icon: '🐙', cost: '10x', desc: '最强模型，深度思考' },
  { id: 'github-copilot/claude-opus-4.6-fast',   name: 'Opus 4.6 (Fast)', emoji: '⚡', icon: '⚡', cost: '5x',  desc: '平衡速度和能力' },
];
