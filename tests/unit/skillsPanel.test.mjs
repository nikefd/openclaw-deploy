// tests/unit/skillsPanel.test.mjs — pure UI helpers for the Skills panel.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  escH, filterSkills, skillCardHtml, skillsGridHtml, countsLabel,
} from '../../web/src/ui/skillsPanel.js';

const sample = [
  { name: 'github',    description: 'GitHub CLI',         icon: '🐙', active: true,  builtin: true  },
  { name: 'weather',   description: 'wttr.in forecasts',  icon: '⛅', active: false, builtin: true  },
  { name: 'climbing',  description: 'fitness tracker',    icon: '🧗', active: true,  builtin: false },
  { name: 'finance',   description: 'A股 agent',          icon: '📈', active: false, builtin: false },
];

test('escH: escapes &, <, >', () => {
  assert.equal(escH('<a>&'), '&lt;a&gt;&amp;');
});

test('escH: coerces non-strings', () => {
  assert.equal(escH(7), '7');
});

test('filterSkills: all returns everything', () => {
  assert.equal(filterSkills(sample, 'all', '').length, 4);
});

test('filterSkills: active', () => {
  const out = filterSkills(sample, 'active', '');
  assert.deepEqual(out.map(s => s.name).sort(), ['climbing', 'github']);
});

test('filterSkills: builtin', () => {
  const out = filterSkills(sample, 'builtin', '');
  assert.deepEqual(out.map(s => s.name).sort(), ['github', 'weather']);
});

test('filterSkills: custom (not builtin)', () => {
  const out = filterSkills(sample, 'custom', '');
  assert.deepEqual(out.map(s => s.name).sort(), ['climbing', 'finance']);
});

test('filterSkills: query matches name', () => {
  const out = filterSkills(sample, 'all', 'github');
  assert.deepEqual(out.map(s => s.name), ['github']);
});

test('filterSkills: query matches description (case-insensitive)', () => {
  const out = filterSkills(sample, 'all', 'WTTR');
  assert.deepEqual(out.map(s => s.name), ['weather']);
});

test('filterSkills: query + filter combine', () => {
  const out = filterSkills(sample, 'active', 'climb');
  assert.deepEqual(out.map(s => s.name), ['climbing']);
});

test('filterSkills: tolerates null/undefined skills', () => {
  assert.deepEqual(filterSkills(null, 'all', ''), []);
  assert.deepEqual(filterSkills(undefined, 'active', 'x'), []);
});

test('skillCardHtml: includes name/desc/icon and onclick', () => {
  const html = skillCardHtml(sample[0]);
  assert.match(html, /skill-card/);
  assert.match(html, /onclick="openSkill\('github'\)"/);
  assert.match(html, /🐙/);
  assert.match(html, /GitHub CLI/);
  assert.match(html, /✅ 已启用/);
  assert.match(html, /📦 内置/);
});

test('skillCardHtml: inactive + custom tags', () => {
  const html = skillCardHtml(sample[3]);
  assert.match(html, /未启用/);
  assert.match(html, /🛠 自定义/);
});

test('skillCardHtml: escapes name/description (XSS guard)', () => {
  const html = skillCardHtml({ name: 'x', description: '<script>', icon: '?', active: false, builtin: true });
  assert.ok(!html.includes('<script>'));
  assert.match(html, /&lt;script&gt;/);
});

test('skillsGridHtml: empty state', () => {
  const html = skillsGridHtml([]);
  assert.match(html, /没有匹配的技能/);
});

test('skillsGridHtml: concatenates cards', () => {
  const html = skillsGridHtml(sample.slice(0, 2));
  assert.equal((html.match(/skill-card/g) || []).length, 2);
});

test('countsLabel: counts total / active / custom', () => {
  assert.equal(countsLabel(sample), '4 个技能 · 2 已启用 · 2 自定义');
});

test('countsLabel: empty', () => {
  assert.equal(countsLabel([]), '0 个技能 · 0 已启用 · 0 自定义');
});
