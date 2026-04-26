// ui/fileHelpers.js — pure helpers for the file panel.
//
// No DOM, no fetch — just file-name → icon/label/size formatting.
//
// Phase 6.3 (2026-04-26): FILE_ICONS / LANG_MAP moved to config/constants.js
// to keep a single source of truth (also imported by inline). Re-exported
// here so existing call sites (and unit tests) keep working.

import { FILE_ICONS, LANG_MAP } from '../config/constants.js';

export { FILE_ICONS, LANG_MAP };

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
