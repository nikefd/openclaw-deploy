// tests/unit/modelDropdown.test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { modelDropdownHtml } from '../../web/src/ui/modelDropdown.js';

const MODELS = [
  { id: 'claude-opus-4.7', name: 'Claude Opus 4.7', emoji: '🧠', desc: '强大', cost: '$$$' },
  { id: 'claude-sonnet-4.5', name: 'Claude Sonnet 4.5', emoji: '⚡', desc: '快速', cost: '$$' },
  { id: 'gpt-5.2', name: 'GPT-5.2', emoji: '🌟', desc: '通用', cost: '$$' },
];

test('modelDropdownHtml: empty input → empty string', () => {
  assert.equal(modelDropdownHtml([], 'x'), '');
  assert.equal(modelDropdownHtml(null, 'x'), '');
  assert.equal(modelDropdownHtml(undefined, 'x'), '');
});

test('modelDropdownHtml: renders all models', () => {
  const html = modelDropdownHtml(MODELS, 'gpt-5.2');
  const cards = (html.match(/class="model-option/g) || []).length;
  assert.equal(cards, 3);
});

test('modelDropdownHtml: marks current model active', () => {
  const html = modelDropdownHtml(MODELS, 'claude-sonnet-4.5');
  assert.match(html, /class="model-option active" onclick="setCurrentModel\('claude-sonnet-4\.5'\)/);
  // others not active
  const notActive = (html.match(/class="model-option" onclick=/g) || []).length;
  assert.equal(notActive, 2);
});

test('modelDropdownHtml: no active when current id not in list', () => {
  const html = modelDropdownHtml(MODELS, 'unknown-model');
  assert.ok(!html.includes(' active"'));
});

test('modelDropdownHtml: shows name, desc, cost, emoji', () => {
  const html = modelDropdownHtml(MODELS, '');
  assert.match(html, /Claude Opus 4\.7/);
  assert.match(html, /强大/);
  assert.match(html, /\$\$\$/);
  assert.match(html, /🧠/);
});

test('modelDropdownHtml: HTML-escapes name field (defuse injection)', () => {
  const evil = [{ id: 'x', name: '<script>alert(1)</script>', emoji: '?', desc: 'd', cost: 'c' }];
  const html = modelDropdownHtml(evil, '');
  assert.ok(!html.includes('<script>alert(1)'));
  assert.match(html, /&lt;script&gt;alert\(1\)&lt;\/script&gt;/);
});

test('modelDropdownHtml: HTML-escapes desc + cost + emoji', () => {
  const evil = [{ id: 'x', name: 'n', emoji: '<e>', desc: '<d>', cost: '<c>' }];
  const html = modelDropdownHtml(evil, '');
  assert.match(html, /&lt;e&gt;/);
  assert.match(html, /&lt;d&gt;/);
  assert.match(html, /&lt;c&gt;/);
});

test('modelDropdownHtml: defuses single-quote in id (would break onclick)', () => {
  const evil = [{ id: "x'); alert(1);('", name: 'n', emoji: 'e', desc: 'd', cost: 'c' }];
  const html = modelDropdownHtml(evil, '');
  // The single-quote must be escaped (either as \\' or HTML entity) so
  // the surrounding setCurrentModel('...') stays well-formed.
  assert.ok(!/setCurrentModel\('x'\)/.test(html), 'raw quote must not break out');
});

test('modelDropdownHtml: handles missing fields gracefully', () => {
  const sparse = [{ id: 'a' }, { id: 'b', name: 'B' }];
  const html = modelDropdownHtml(sparse, 'a');
  assert.match(html, /class="model-option active" onclick="setCurrentModel\('a'\)/);
  assert.match(html, /class="model-option" onclick="setCurrentModel\('b'\)/);
});
