// tests/unit/lookup.test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { getAgent, getModelInfo } from '../../web/src/domain/lookup.js';
import { AGENTS, MODELS } from '../../web/src/config/constants.js';

test('getAgent: known id returns matching record', () => {
  assert.equal(getAgent('main').id, 'main');
  assert.equal(getAgent('climbing').id, 'climbing');
  assert.equal(getAgent('finance').id, 'finance');
});

test('getAgent: unknown id falls back to AGENTS[0] (main)', () => {
  assert.equal(getAgent('does-not-exist'), AGENTS[0]);
  assert.equal(getAgent('').id, 'main');
  assert.equal(getAgent(null).id, 'main');
  assert.equal(getAgent(undefined).id, 'main');
});

test('getAgent: returned record has expected shape', () => {
  const a = getAgent('climbing');
  assert.ok(a.name);
  assert.ok(a.emoji);
  assert.ok(a.color);
  assert.ok(a.desc);
});

test('getModelInfo: known id returns matching record', () => {
  assert.equal(getModelInfo('openclaw').id, 'openclaw');
  assert.equal(getModelInfo('github-copilot/claude-opus-4.7').id, 'github-copilot/claude-opus-4.7');
});

test('getModelInfo: unknown id falls back to MODELS[0] (openclaw default)', () => {
  assert.equal(getModelInfo('not-a-model'), MODELS[0]);
  assert.equal(getModelInfo('').id, 'openclaw');
  assert.equal(getModelInfo(null).id, 'openclaw');
});

test('getModelInfo: returned record has cost label', () => {
  const m = getModelInfo('github-copilot/claude-opus-4.7');
  assert.equal(m.cost, '10x');
});
