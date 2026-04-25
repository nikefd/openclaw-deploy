// ui/fileBreadcrumb.js — pure HTML builder for the file panel breadcrumb.
//
// Used by both the local file viewer (loadFiles) and the remote node file
// browser (loadRemoteFiles), with a different click handler. Caller passes
// the handler name as `clickFn`.
//
// breadcrumbHtml(path, { clickFn = 'loadFiles', escapeHtml? })
//   Splits an absolute path on '/', emits a chain of clickable segments
//   joined by '›'. Empty string for empty/falsy paths.

const PLAIN_HTML = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

function safePath(p) {
  // strip quotes/backslashes — paths shouldn't contain them, but if they do
  // we don't want to break out of the onclick string.
  return String(p || '').replace(/['"\\]/g, '');
}

/**
 * Build breadcrumb HTML for a path.
 * @param {string} dirPath e.g. "/home/nikefd/proj"
 * @param {{clickFn?:string, escapeHtml?:Function}} deps
 * @returns {string}
 */
export function breadcrumbHtml(dirPath, deps = {}) {
  const clickFn = deps.clickFn || 'loadFiles';
  const escapeHtml = deps.escapeHtml || PLAIN_HTML;
  const p = String(dirPath || '');
  if (!p) return '';
  const parts = p.split('/').filter(Boolean);
  let html = '';
  let acc = '';
  parts.forEach((seg, i) => {
    acc += '/' + seg;
    if (i > 0) html += '<span class="bc-sep">›</span>';
    html +=
      '<span class="bc-part" onclick="' + clickFn + '(\'' + safePath(acc) + '\')">' +
      escapeHtml(seg) +
      '</span>';
  });
  return html;
}
