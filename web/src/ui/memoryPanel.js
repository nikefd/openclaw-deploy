// ui/memoryPanel.js — pure HTML template builders for the Memory sidebar.
//
// No DOM, no fetch, no globals. Just data → HTML strings.
// Caller does sidebar.innerHTML = memorySidebarHtml(...).

/**
 * One file row in the memory sidebar.
 * @param {{name:string, path:string, icon:string, size?:number}} file
 * @param {boolean} isActive whether this file is currently open
 * @param {boolean} [showSize=true]
 * @returns {string}
 */
export function memoryFileHtml(file, isActive, showSize = true) {
  const cls = 'memory-file' + (isActive ? ' active' : '');
  const sizeBadge = (showSize && file.size)
    ? `<span class="mem-size">${(file.size / 1024).toFixed(1)}K</span>`
    : '';
  return `<div class="${cls}" onclick="openMemFile('${file.path}')">${file.icon} ${file.name}${sizeBadge}</div>`;
}

/**
 * Stats line: "<N> 个文件 · <K.K> KB".
 * @param {{longTerm?:Array, daily?:Array, identity?:Array, projects?:Array}} memoryFiles
 * @returns {string}
 */
export function memoryStatsHtml(memoryFiles) {
  const longTerm = memoryFiles.longTerm || [];
  const daily = memoryFiles.daily || [];
  const identity = memoryFiles.identity || [];
  const projects = memoryFiles.projects || [];
  const total = longTerm.length + daily.length + identity.length + projects.length;
  let totalSize = 0;
  [...longTerm, ...daily, ...identity, ...projects].forEach(f => {
    if (f && f.size) totalSize += f.size;
  });
  let html = `<div class="memory-stats"><strong>${total}</strong> 个文件`;
  if (totalSize > 0) html += ` · <strong>${(totalSize / 1024).toFixed(1)}</strong> KB`;
  html += `</div>`;
  return html;
}

/**
 * One category block. Returns '' if files is empty (so callers don't have
 * to re-check). Title may include a count suffix in (...).
 * @param {string} title e.g. "📌 长期记忆" or "📂 项目记忆 (3)"
 * @param {Array} files
 * @param {string|null} currentPath
 * @param {{showSize?:boolean}} [opts]
 * @returns {string}
 */
export function memoryCategoryHtml(title, files, currentPath, opts = {}) {
  const list = files || [];
  if (!list.length) return '';
  const showSize = opts.showSize !== false;
  let html = `<div class="memory-category"><div class="memory-category-title">${title}</div>`;
  list.forEach(f => {
    html += memoryFileHtml(f, currentPath === f.path, showSize);
  });
  html += `</div>`;
  return html;
}

/**
 * Cron settings block.
 * @param {string} time HH:MM
 * @returns {string}
 */
export function memoryCronHtml(time) {
  return (
    `<div class="memory-cron"><label>⏰ 每日自动整理</label>` +
    `<div class="memory-cron-row">` +
    `<input type="time" id="cronTimeInput" value="${time}">` +
    `<button class="cron-save" onclick="saveMemoryCronTime()">保存</button>` +
    `</div>` +
    `<div class="cron-status" id="cronStatus"></div>` +
    `</div>`
  );
}

/**
 * Full memory sidebar HTML.
 * @param {{longTerm:Array, daily?:Array, identity:Array, projects?:Array}} memoryFiles
 * @param {string|null} currentPath
 * @param {string} cronTime
 * @returns {string}
 */
export function memorySidebarHtml(memoryFiles, currentPath, cronTime) {
  let html = `<h3 style="cursor:pointer" onclick="showMemWelcome()">🧠 记忆管理</h3>`;
  html += memoryStatsHtml(memoryFiles);
  html += memoryCategoryHtml('📌 长期记忆', memoryFiles.longTerm, currentPath);
  const projects = memoryFiles.projects || [];
  if (projects.length) {
    html += memoryCategoryHtml(`📂 项目记忆 (${projects.length})`, projects, currentPath);
  }
  const daily = memoryFiles.daily || [];
  if (daily.length) {
    html += memoryCategoryHtml(`📝 每日记录 (${daily.length})`, daily, currentPath);
  }
  // Identity files don't get size badges (intentional — matches inline behavior).
  html += memoryCategoryHtml('🪪 身份文件', memoryFiles.identity, currentPath, { showSize: false });
  html += memoryCronHtml(cronTime);
  return html;
}
