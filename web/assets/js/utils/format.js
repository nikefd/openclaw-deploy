// utils/format.js —— 文件/字节尺寸等通用格式化工具
// 供 panels/files + panels/remote (and potentially others) 共用

const FILE_ICONS = {
  js: '🟨', ts: '🔷', py: '🐍', rb: '💎', go: '🔵', rs: '🦀',
  html: '🌐', css: '🎨', json: '📋', xml: '📰', yaml: '⚙️', yml: '⚙️', toml: '⚙️',
  md: '📝', txt: '📄', log: '📜', csv: '📊',
  sh: '⚡', bash: '⚡', zsh: '⚡', fish: '⚡',
  png: '🖼', jpg: '🖼', gif: '🖼', svg: '🖼', webp: '🖼', ico: '🖼',
  pdf: '📕', zip: '📦', tar: '📦', gz: '📦',
  env: '🔒', lock: '🔒', gitignore: '👁', dockerfile: '🐳',
  conf: '⚙️', cfg: '⚙️', ini: '⚙️', service: '⚙️',
};

const LANG_MAP = {
  js: 'JavaScript', ts: 'TypeScript', py: 'Python', rb: 'Ruby', go: 'Go', rs: 'Rust',
  html: 'HTML', css: 'CSS', json: 'JSON', xml: 'XML', yaml: 'YAML', yml: 'YAML', toml: 'TOML',
  md: 'Markdown', txt: 'Text', log: 'Log', csv: 'CSV',
  sh: 'Shell', bash: 'Shell', zsh: 'Shell',
};

export function fileIcon(name, isDir) {
  if (isDir) return '📁';
  const ext = name.split('.').pop().toLowerCase();
  return FILE_ICONS[ext] || '📄';
}

export function fileLang(name) {
  const ext = name.split('.').pop().toLowerCase();
  return LANG_MAP[ext] || ext.toUpperCase() || 'Text';
}

export function fmtSize(b) {
  if (b == null) return '';
  if (b < 1024) return b + ' B';
  if (b < 1048576) return (b / 1024).toFixed(1) + ' KB';
  return (b / 1048576).toFixed(1) + ' MB';
}
