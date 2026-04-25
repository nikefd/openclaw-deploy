// tests/unit/expertTeams.test.mjs — pure HTML builders for the Expert Teams panel.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  expertTeamsHtml, expertTeamReadyHtml, findExpertTeam,
} from '../../web/src/ui/expertTeams.js';

const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

const TEAMS = [
  { id: 'cr', name: '代码审查', icon: '🔍', experts: [
    { id: 'arch', name: '架构师', icon: '🏗️' },
    { id: 'sec', name: '安全', icon: '🔒' },
  ]},
  { id: 'wr', name: '写作', icon: '✍️', experts: [
    { id: 'ed', name: '编辑', icon: '📝' },
  ]},
];

// ── expertTeamsHtml ─────────────────────────────────────────────────

test('expertTeamsHtml: empty teams → empty string', () => {
  assert.equal(expertTeamsHtml([], null, { escapeHtml: esc }), '');
  assert.equal(expertTeamsHtml(null, null, { escapeHtml: esc }), '');
  assert.equal(expertTeamsHtml(undefined, null, { escapeHtml: esc }), '');
});

test('expertTeamsHtml: each team gets a chip with icon + name', () => {
  const html = expertTeamsHtml(TEAMS, null, { escapeHtml: esc });
  assert.match(html, /🔍 代码审查/);
  assert.match(html, /✍️ 写作/);
  const chips = html.match(/expert-team-chip/g) || [];
  assert.equal(chips.length, 2);
});

test('expertTeamsHtml: selected team gets .active class; others do not', () => {
  const html = expertTeamsHtml(TEAMS, 'wr', { escapeHtml: esc });
  const active = html.match(/expert-team-chip active/g) || [];
  assert.equal(active.length, 1);
  assert.match(html, /expert-team-chip active[\s\S]*?写作/);
});

test('expertTeamsHtml: no selection → no .active', () => {
  const html = expertTeamsHtml(TEAMS, null, { escapeHtml: esc });
  assert.doesNotMatch(html, /expert-team-chip active/);
});

test('expertTeamsHtml: onclick wired with team id', () => {
  const html = expertTeamsHtml(TEAMS, null, { escapeHtml: esc });
  assert.match(html, /selectExpertTeam\('cr'\)/);
  assert.match(html, /selectExpertTeam\('wr'\)/);
});

test('expertTeamsHtml: skips entries without id', () => {
  const html = expertTeamsHtml(
    [{ id: 'ok', name: 'Ok', icon: '✅' }, null, { name: 'no-id' }],
    null,
    { escapeHtml: esc },
  );
  assert.equal((html.match(/expert-team-chip/g) || []).length, 1);
});

test('expertTeamsHtml: XSS — name escaped', () => {
  const html = expertTeamsHtml(
    [{ id: 'x', name: '<script>x</script>', icon: '!' }],
    null,
    { escapeHtml: esc },
  );
  assert.doesNotMatch(html, /<script>x/);
  assert.match(html, /&lt;script&gt;x/);
});

test('expertTeamsHtml: XSS — id quote/backslash stripped from onclick', () => {
  const html = expertTeamsHtml(
    [{ id: "x'); alert(1);//", name: 'Bad', icon: '!' }],
    null,
    { escapeHtml: esc },
  );
  // Single quote must be gone so the onclick string stays well-formed.
  assert.doesNotMatch(html, /selectExpertTeam\('[^']*'\); alert/);
  assert.match(html, /selectExpertTeam\('x\); alert\(1\);\/\/'\)/);
});

// ── expertTeamReadyHtml ─────────────────────────────────────────────

test('expertTeamReadyHtml: null team → empty string', () => {
  assert.equal(expertTeamReadyHtml(null, { escapeHtml: esc }), '');
});

test('expertTeamReadyHtml: shows team name + icon + "团队已就绪"', () => {
  const html = expertTeamReadyHtml(TEAMS[0], { escapeHtml: esc });
  assert.match(html, /🔍/);
  assert.match(html, /<strong>代码审查<\/strong> 团队已就绪/);
});

test('expertTeamReadyHtml: lists every expert with icon + name', () => {
  const html = expertTeamReadyHtml(TEAMS[0], { escapeHtml: esc });
  assert.match(html, /🏗️ 架构师/);
  assert.match(html, /🔒 安全/);
});

test('expertTeamReadyHtml: handles team with no experts gracefully', () => {
  const html = expertTeamReadyHtml({ id: 't', name: 'Empty', icon: '∅' }, { escapeHtml: esc });
  assert.match(html, /<strong>Empty<\/strong>/);
  assert.match(html, /发送消息后/);
});

test('expertTeamReadyHtml: XSS — expert name escaped', () => {
  const html = expertTeamReadyHtml(
    { id: 't', name: 'T', icon: '🔧', experts: [{ id: 'e', name: '<img onerror=1>', icon: 'x' }] },
    { escapeHtml: esc },
  );
  assert.doesNotMatch(html, /<img onerror/);
  assert.match(html, /&lt;img onerror=1&gt;/);
});

// ── findExpertTeam ──────────────────────────────────────────────────

test('findExpertTeam: hit → returns the team', () => {
  assert.equal(findExpertTeam(TEAMS, 'wr').name, '写作');
});

test('findExpertTeam: miss → null', () => {
  assert.equal(findExpertTeam(TEAMS, 'nope'), null);
});

test('findExpertTeam: defensive — bad inputs → null', () => {
  assert.equal(findExpertTeam(null, 'cr'), null);
  assert.equal(findExpertTeam(TEAMS, ''), null);
  assert.equal(findExpertTeam(TEAMS, null), null);
});
