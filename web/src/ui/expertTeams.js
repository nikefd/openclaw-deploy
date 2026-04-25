// ui/expertTeams.js — pure HTML builders for the Expert Teams panel.
//
// No DOM, no fetch, no globals. The handlers in index.html
// (toggleExpertPanel / selectExpertTeam / queryExperts) still own the
// imperative side; this lib just turns plain data into safe HTML.
//
// Shape contract:
//   team   = { id, name, icon, experts: [{id,name,icon,prompt}] }
//
// All user-visible fields (name / icon) are escaped; ids go into onclick
// attribute strings so they're additionally guarded against quote injection
// (replace single-quote with empty — ids are app-controlled and slug-shaped,
// but defense in depth never hurts).
//
// Two builders + one finder:
//   expertTeamsHtml(teams, selectedTeam, deps?)   → chip strip
//   expertTeamReadyHtml(team, deps?)              → "team ready" placeholder
//   findExpertTeam(teams, id)                     → team or null

const PLAIN_HTML = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

function safeId(id) {
  return String(id || '').replace(/['"\\]/g, '');
}

/**
 * Render the row of clickable team chips.
 * @param {Array} teams
 * @param {string|null} selectedTeam
 * @param {{escapeHtml?:Function}} deps
 * @returns {string}
 */
export function expertTeamsHtml(teams, selectedTeam, deps = {}) {
  const escapeHtml = deps.escapeHtml || PLAIN_HTML;
  const list = Array.isArray(teams) ? teams : [];
  let html = '';
  for (const t of list) {
    if (!t || !t.id) continue;
    const isActive = selectedTeam === t.id;
    html +=
      '<button class="expert-team-chip' + (isActive ? ' active' : '') + '" ' +
      'onclick="selectExpertTeam(\'' + safeId(t.id) + '\')">' +
      escapeHtml(t.icon || '') + ' ' + escapeHtml(t.name || '') +
      '</button>';
  }
  return html;
}

/**
 * Render the "team is ready" placeholder shown after selection.
 * @param {Object} team
 * @param {{escapeHtml?:Function}} deps
 * @returns {string}
 */
export function expertTeamReadyHtml(team, deps = {}) {
  const escapeHtml = deps.escapeHtml || PLAIN_HTML;
  if (!team) return '';
  const experts = Array.isArray(team.experts) ? team.experts : [];
  const expertsHtml = experts
    .filter((e) => e)
    .map((e) =>
      '<span style="margin:0 4px">' +
      escapeHtml(e.icon || '') + ' ' + escapeHtml(e.name || '') +
      '</span>'
    )
    .join('');
  return (
    '<div class="expert-empty">' +
      '<div class="expert-empty-icon">' + escapeHtml(team.icon || '') + '</div>' +
      '<div><strong>' + escapeHtml(team.name || '') + '</strong> 团队已就绪</div>' +
      '<div style="margin-top:8px">' + expertsHtml + '</div>' +
      '<div style="margin-top:12px;font-size:12px">发送消息后，专家会同时分析</div>' +
    '</div>'
  );
}

/**
 * Find an expert team by id.
 * @param {Array} teams
 * @param {string} id
 * @returns {Object|null}
 */
export function findExpertTeam(teams, id) {
  if (!Array.isArray(teams) || !id) return null;
  for (const t of teams) {
    if (t && t.id === id) return t;
  }
  return null;
}
