// config/constants.js — Static, immutable configuration data.
//
// These constants used to be top-level `const` declarations inside the inline
// <script> in index.html. After Phase 6.1 promoted that script to type=
// "module", we can finally `import` them as a real ES module instead of
// duplicating data through `window.__oc`.
//
// Rules for additions:
//   - Pure data, no side effects (no localStorage reads, no DOM access)
//   - Never mutated at runtime (use Object.freeze where it makes sense)
//   - If a value is read by HTML attributes (onclick), expose it via the
//     window.__oc namespace in main.js, NOT here

/** Default workspace path on the host. Used by memory panel + file viewer. */
export const WORKSPACE = '/home/nikefd/.openclaw/workspace';

/** Built-in agents shown in the sidebar grid + mention popup. */
export const AGENTS = Object.freeze([
  { id: 'main',     name: '狗蛋',     emoji: '🦞', color: '#10a37f', desc: '你的全能助手' },
  { id: 'climbing', name: '攀岩教练', emoji: '🧗', color: '#f97316', desc: '训练记录、进步分析、训练计划', mention: '@攀岩教练' },
  { id: 'finance',  name: '理财管家', emoji: '🎩', color: '#eab308', desc: 'A股选股、模拟交易、行情分析',  mention: '@理财管家' },
]);

/**
 * Available chat models. The `openclaw` id is a legacy alias (see
 * infra/storage/localStore.js) — leave it as the default for back-compat.
 */
export const MODELS = Object.freeze([
  { id: 'openclaw',                          name: 'Default (Haiku)',   emoji: '🐰', icon: '🐰', cost: '1x',  desc: '快速轻量，日常任务' },
  { id: 'github-copilot/claude-opus-4.7',    name: 'Claude Opus 4.7',   emoji: '🐙', icon: '🐙', cost: '10x', desc: '最强模型，深度思考' },
  { id: 'github-copilot/claude-opus-4.6-fast', name: 'Opus 4.6 (Fast)', emoji: '⚡', icon: '⚡', cost: '5x',  desc: '平衡速度和能力' },
]);

/** Skill id → emoji icon, used by the skills panel. */
export const SK_ICONS = Object.freeze({
  'discord': '💬', 'github': '🐙', 'gh-issues': '🐛', 'weather': '🌤',
  'tmux': '🖥', 'video-frames': '🎬', 'healthcheck': '🛡',
  'skill-creator': '✨', 'node-connect': '🔗', 'coding-agent': '🤖',
  'himalaya': '📧', 'slack': '💼', 'spotify-player': '🎵',
  'voice-call': '📞', 'sag': '🔊', 'camsnap': '📷',
  'notion': '📓', 'obsidian': '💎', 'trello': '📋',
  '1password': '🔐', 'gog': '📬', 'xurl': '🐦',
  'summarize': '📝', 'nano-pdf': '📄', 'oracle': '🔮',
  'sonoscli': '🔈', 'openhue': '💡', 'peekaboo': '👀',
  'gemini': '♊', 'clawhub': '🦞', 'web-dev-rules': '🚧',
  'mermaid-fix': '🧜', 'memory-ops': '🧠',
});

/**
 * Skills currently considered "active" for the user — these get a green dot
 * and float to the top of the panel. Update when enabling/disabling skills.
 */
export const ACTIVE_SKILLS = Object.freeze(new Set([
  'discord', 'gh-issues', 'github', 'healthcheck', 'skill-creator',
  'node-connect', 'tmux', 'video-frames', 'weather',
]));

/** File-extension → emoji icon mapping for the file viewer. */
export const FILE_ICONS = Object.freeze({
  js: '🟨', ts: '🔷', py: '🐍', rb: '💎', go: '🔵', rs: '🦀',
  html: '🌐', css: '🎨', json: '📋', xml: '📰',
  yaml: '⚙️', yml: '⚙️', toml: '⚙️',
  md: '📝', txt: '📄', log: '📜', csv: '📊',
  sh: '⚡', bash: '⚡', zsh: '⚡', fish: '⚡',
  png: '🖼', jpg: '🖼', gif: '🖼', svg: '🖼', webp: '🖼', ico: '🖼',
  pdf: '📕', zip: '📦', tar: '📦', gz: '📦',
  env: '🔒', lock: '🔒', gitignore: '👁', dockerfile: '🐳',
  conf: '⚙️', cfg: '⚙️', ini: '⚙️', service: '⚙️',
});

/** Extension → human-readable language label, used by the file viewer. */
export const LANG_MAP = Object.freeze({
  js: 'JavaScript', ts: 'TypeScript', py: 'Python', rb: 'Ruby',
  go: 'Go', rs: 'Rust',
  html: 'HTML', css: 'CSS', json: 'JSON', xml: 'XML',
  yaml: 'YAML', yml: 'YAML', toml: 'TOML',
  md: 'Markdown', txt: 'Text', log: 'Log', csv: 'CSV',
  sh: 'Shell', bash: 'Shell', zsh: 'Shell',
});
