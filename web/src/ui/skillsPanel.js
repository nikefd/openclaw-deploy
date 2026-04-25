// ui/skillsPanel.js — pure helpers for the Skills panel.
// No DOM access, no globals. Caller passes data in, gets HTML / filtered list out.

/**
 * HTML-escape a string for safe interpolation into innerHTML.
 * @param {string} s
 * @returns {string}
 */
export function escH(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

/**
 * Filter a list of skills by the current filter tab and search query.
 * @param {Array<{name:string,description:string,active:boolean,builtin:boolean}>} skills
 * @param {'all'|'active'|'builtin'|'custom'} filter
 * @param {string} query
 * @returns {Array}
 */
export function filterSkills(skills, filter, query) {
  const q = (query || '').toLowerCase();
  return (skills || []).filter(s => {
    if (q && !s.name.includes(q) && !s.description.toLowerCase().includes(q)) return false;
    if (filter === 'active') return s.active;
    if (filter === 'builtin') return s.builtin;
    if (filter === 'custom') return !s.builtin;
    return true;
  });
}

/**
 * Render a single skill card to an HTML string.
 * @param {{name:string,description:string,icon:string,active:boolean,builtin:boolean}} s
 * @returns {string}
 */
export function skillCardHtml(s) {
  const tags =
    (s.active ? '<span class="sk-tag on">✅ 已启用</span>' : '<span class="sk-tag">未启用</span>') +
    (s.builtin ? '<span class="sk-tag">📦 内置</span>' : '<span class="sk-tag custom">🛠 自定义</span>');
  return (
    '<div class="skill-card" onclick="openSkill(\'' + s.name + '\')">' +
    '<div class="sk-icon">' + s.icon + '</div>' +
    '<div class="sk-name">' + escH(s.name) + '</div>' +
    '<div class="sk-desc">' + escH(s.description) + '</div>' +
    '<div class="sk-tags">' + tags + '</div>' +
    '</div>'
  );
}

/**
 * Build the grid HTML for the visible skills (or an empty-state placeholder).
 * @param {Array} visibleSkills
 * @returns {string}
 */
export function skillsGridHtml(visibleSkills) {
  if (!visibleSkills || !visibleSkills.length) {
    return '<div style="grid-column:1/-1;padding:40px;text-align:center;color:var(--text-sec)">🔍 没有匹配的技能</div>';
  }
  return visibleSkills.map(skillCardHtml).join('');
}

/**
 * Build the counts label "N 个技能 · M 已启用 · K 自定义".
 * @param {Array} skills
 * @returns {string}
 */
export function countsLabel(skills) {
  const list = skills || [];
  const active = list.filter(s => s.active).length;
  const custom = list.filter(s => !s.builtin).length;
  return list.length + ' 个技能 · ' + active + ' 已启用 · ' + custom + ' 自定义';
}
