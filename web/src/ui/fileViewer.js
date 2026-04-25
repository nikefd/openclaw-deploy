// ui/fileViewer.js — pure HTML builders for the file viewer panel.
//
// No DOM access, no fetch, no globals. The handlers in index.html
// (switchTab / closeTab / viewFile) still own the imperative side
// (click → load → mutate openTabs → call these to (re)render).
//
// Two builders:
//
//   fileTabsHtml(openTabs, activeTab, { fileIcon, escapeHtml })
//     → string of <div class="file-tab">…</div> for each open tab.
//
//   fileViewerContent(tab, { fileIcon, fileLang, fmtSize, escapeHtml })
//     → { bodyHtml, infoBar: { lang, lines, size, path } }
//     bodyHtml is the line-numbers + file-content block. infoBar is the
//     pre-formatted text the caller stamps into the four <span>s.
//
// Helpers (fileIcon/fileLang/fmtSize/escapeHtml) are injected so this lib
// has zero coupling. Caller passes window.__oc.ui.fileHelpers + escapeHtml.
//
// Empty / placeholder bodies (loading, empty-tab, error) live as exported
// constants so callers can stamp them directly without duplicating markup.

const PLAIN_HTML = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

export const FILE_VIEWER_EMPTY_HTML =
  '<div class="file-viewer-empty">' +
  '<div class="empty-icon">📄</div>' +
  '<div>选择文件查看内容</div>' +
  '<div style="font-size:12px;opacity:.6">从左侧目录中点击文件</div>' +
  '</div>';

export const FILE_VIEWER_LOADING_HTML =
  '<div class="file-viewer-empty">' +
  '<div class="empty-icon">⏳</div>' +
  '<div>加载中...</div>' +
  '</div>';

export function fileViewerErrorHtml(msg, { escapeHtml = PLAIN_HTML } = {}) {
  return (
    '<div class="file-viewer-empty">' +
    '<div class="empty-icon">❌</div>' +
    '<div>' + escapeHtml(String(msg || '加载失败')) + '</div>' +
    '</div>'
  );
}

/**
 * Render the open-tabs strip.
 * @param {Array<{path:string,name:string}>} openTabs
 * @param {string|null} activeTab path of the currently active tab
 * @param {{fileIcon:Function, escapeHtml:Function}} deps
 * @returns {string} HTML
 */
export function fileTabsHtml(openTabs, activeTab, deps = {}) {
  const fileIcon = deps.fileIcon || (() => '📄');
  const escapeHtml = deps.escapeHtml || PLAIN_HTML;
  const tabs = Array.isArray(openTabs) ? openTabs : [];
  let html = '';
  for (const t of tabs) {
    if (!t || !t.path) continue;
    const icon = fileIcon(t.name, false);
    const isActive = activeTab === t.path;
    const safePath = escapeHtml(t.path);
    const safeName = escapeHtml(t.name || '');
    html +=
      '<div class="file-tab' + (isActive ? ' active' : '') + '" data-path="' + safePath + '" onclick="switchTab(\'' + safePath + '\')">' +
        '<span class="tab-icon">' + icon + '</span>' +
        '<span class="tab-name">' + safeName + '</span>' +
        '<button class="tab-close" onclick="event.stopPropagation();closeTab(\'' + safePath + '\')">✕</button>' +
      '</div>';
  }
  return html;
}

/**
 * Render the file body (line numbers + content) and prepare info-bar text.
 * Body still relies on the caller to insert into #fileViewerBody and to
 * toggle #fileInfoBar visibility; this lib only produces strings.
 *
 * @param {{name:string, path:string, content:string, size:number}} tab
 * @param {{fileLang:Function, fmtSize:Function, escapeHtml:Function}} deps
 * @returns {{bodyHtml:string, infoBar:{lang:string,lines:string,size:string,path:string}}}
 */
export function fileViewerContent(tab, deps = {}) {
  const fileLang = deps.fileLang || ((n) => String(n || '').split('.').pop().toUpperCase() || 'Text');
  const fmtSize = deps.fmtSize || ((b) => b == null ? '' : (b + ' B'));
  const escapeHtml = deps.escapeHtml || PLAIN_HTML;

  const safe = tab && typeof tab === 'object' ? tab : { name: '', path: '', content: '', size: 0 };
  const content = typeof safe.content === 'string' ? safe.content : '';
  const lines = content.split('\n');
  const lineNums = lines.map((_, i) => i + 1).join('\n');

  const bodyHtml =
    '<div class="line-numbers">' + lineNums + '</div>' +
    '<div class="file-content">' + escapeHtml(content) + '</div>';

  return {
    bodyHtml,
    infoBar: {
      lang: '📝 ' + fileLang(safe.name || ''),
      lines: '📏 ' + lines.length + ' 行',
      size: '💾 ' + fmtSize(safe.size),
      path: safe.path || '',
    },
  };
}
