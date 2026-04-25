// ui/fileHelpers.js — pure helpers for the file panel.
//
// No DOM, no fetch — just file-name → icon/label/size formatting.

export const FILE_ICONS = {
  js: '🟨', ts: '🔷', py: '🐍', rb: '💎', go: '🔵', rs: '🦀',
  html: '🌐', css: '🎨', json: '📋', xml: '📰', yaml: '⚙️', yml: '⚙️', toml: '⚙️',
  md: '📝', txt: '📄', log: '📜', csv: '📊',
  sh: '⚡', bash: '⚡', zsh: '⚡', fish: '⚡',
  png: '🖼', jpg: '🖼', gif: '🖼', svg: '🖼', webp: '🖼', ico: '🖼',
  pdf: '📕', zip: '📦', tar: '📦', gz: '📦',
  env: '🔒', lock: '🔒', gitignore: '👁', dockerfile: '🐳',
  conf: '⚙️', cfg: '⚙️', ini: '⚙️', service: '⚙️',
};

export const LANG_MAP = {
  js: 'JavaScript', ts: 'TypeScript', py: 'Python', rb: 'Ruby', go: 'Go', rs: 'Rust',
  html: 'HTML', css: 'CSS', json: 'JSON', xml: 'XML', yaml: 'YAML', yml: 'YAML', toml: 'TOML',
  md: 'Markdown', txt: 'Text', log: 'Log', csv: 'CSV',
  sh: 'Shell', bash: 'Shell', zsh: 'Shell',
};

/** @param {string} name file name @param {boolean} [isDir] */
export function fileIcon(name, isDir) {
  if (isDir) return '📁';
  const ext = String(name || '').split('.').pop().toLowerCase();
  return FILE_ICONS[ext] || '📄';
}

/** @param {string} name file name */
export function fileLang(name) {
  const ext = String(name || '').split('.').pop().toLowerCase();
  return LANG_MAP[ext] || ext.toUpperCase() || 'Text';
}

/** @param {number} b bytes */
export function fmtSize(b) {
  if (b == null) return '';
  if (b < 1024) return b + ' B';
  if (b < 1024 * 1024) return (b / 1024).toFixed(1) + ' KB';
  return (b / 1024 / 1024).toFixed(1) + ' MB';
}
