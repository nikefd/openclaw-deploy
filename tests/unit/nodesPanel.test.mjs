// tests/unit/nodesPanel.test.mjs — pure helpers for the Nodes admin panel.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  pendingNodeCardHtml,
  pendingNodesListHtml,
  nodeMeta,
  connectedNodeCardHtml,
  connectedNodesListHtml,
} from '../../web/src/ui/nodesPanel.js';

const fixedDate = new Date('2026-04-25T10:30:00Z').getTime();

// --- pendingNodeCardHtml ---
test('pendingNodeCardHtml: full fields', () => {
  const html = pendingNodeCardHtml({
    requestId: 'req-1', deviceId: 'dev-abcdef0123456789',
    displayName: 'iPhone-Bing', platform: 'iOS', roles: ['client', 'observer'],
  });
  assert.match(html, /class="node-card pending"/);
  assert.match(html, /iPhone-Bing/);
  assert.match(html, />iOS</);
  assert.match(html, /dev-abcdef012345\.\.\./); // sliced to 16 chars
  assert.match(html, /client, observer/);
  assert.match(html, /approveDevice\('req-1'\)/);
  assert.match(html, /rejectDevice\('req-1'\)/);
});

test('pendingNodeCardHtml: falls back to deviceId when no requestId', () => {
  const html = pendingNodeCardHtml({ deviceId: 'dev-xyz', displayName: 'X' });
  assert.match(html, /approveDevice\('dev-xyz'\)/);
});

test('pendingNodeCardHtml: falls back to deviceId slice for displayName', () => {
  const html = pendingNodeCardHtml({ deviceId: 'dev-1234567890abcdef' });
  // displayName fallback is slice(0,12) of deviceId
  assert.match(html, />dev-12345678</);
});

test('pendingNodeCardHtml: deviceId missing → N/A', () => {
  const html = pendingNodeCardHtml({ requestId: 'r1', displayName: 'foo' });
  assert.match(html, /N\/A\.\.\./);
});

test('pendingNodeCardHtml: role (singular) becomes 1-element list', () => {
  const html = pendingNodeCardHtml({ requestId: 'r', deviceId: 'd', role: 'admin' });
  assert.match(html, /角色: admin/);
});

test('pendingNodeCardHtml: HTML-escapes displayName', () => {
  const html = pendingNodeCardHtml({
    requestId: 'r', deviceId: 'd', displayName: '<img src=x>',
  });
  assert.ok(!html.includes('<img src=x>'));
  assert.match(html, /&lt;img src=x&gt;/);
});

test('pendingNodeCardHtml: HTML-escapes platform', () => {
  const html = pendingNodeCardHtml({
    requestId: 'r', deviceId: 'd', displayName: 'n', platform: '<bad>',
  });
  assert.match(html, /&lt;bad&gt;/);
});

// --- pendingNodesListHtml ---
test('pendingNodesListHtml: empty input → empty string', () => {
  assert.equal(pendingNodesListHtml([]), '');
  assert.equal(pendingNodesListHtml(null), '');
  assert.equal(pendingNodesListHtml(undefined), '');
});

test('pendingNodesListHtml: includes header + N cards', () => {
  const html = pendingNodesListHtml([
    { requestId: 'a', deviceId: 'da', displayName: 'A' },
    { requestId: 'b', deviceId: 'db', displayName: 'B' },
  ]);
  assert.match(html, /待审批的配对请求/);
  const cardCount = (html.match(/class="node-card pending"/g) || []).length;
  assert.equal(cardCount, 2);
});

// --- nodeMeta ---
test('nodeMeta: online via .connected', () => {
  const m = nodeMeta({ connected: true, displayName: 'N', lastConnectMs: fixedDate }, 'zh-CN');
  assert.equal(m.online, true);
  assert.equal(m.statusText, 'online');
  assert.match(m.statusEmoji, /在线/);
});

test('nodeMeta: online via .status === "connected"', () => {
  const m = nodeMeta({ status: 'connected' });
  assert.equal(m.online, true);
});

test('nodeMeta: offline + lastConnectMs missing → "从未"', () => {
  const m = nodeMeta({ status: 'idle' });
  assert.equal(m.online, false);
  assert.equal(m.lastSeen, '从未');
  assert.equal(m.statusText, 'offline');
  assert.match(m.statusEmoji, /离线/);
});

test('nodeMeta: name fallback chain (displayName > name > nodeId-slice > "Node")', () => {
  assert.equal(nodeMeta({ displayName: 'A', name: 'B', nodeId: 'cccccccccccc' }).name, 'A');
  assert.equal(nodeMeta({ name: 'B', nodeId: 'cccccccccccc' }).name, 'B');
  assert.equal(nodeMeta({ nodeId: 'abcdefghijklmnop' }).name, 'abcdefghijkl');
  assert.equal(nodeMeta({}).name, 'Node');
});

test('nodeMeta: caps from .capabilities or .caps, default "N/A"', () => {
  assert.equal(nodeMeta({ capabilities: ['shell', 'fs'] }).caps, 'shell, fs');
  assert.equal(nodeMeta({ caps: ['exec'] }).caps, 'exec');
  assert.equal(nodeMeta({}).caps, 'N/A');
});

test('nodeMeta: platform default', () => {
  assert.equal(nodeMeta({}).platform, 'unknown');
});

// --- connectedNodeCardHtml ---
test('connectedNodeCardHtml: online card has "connected" class', () => {
  const html = connectedNodeCardHtml({
    connected: true, displayName: 'N1', platform: 'linux',
    capabilities: ['exec'], lastConnectMs: fixedDate,
  });
  assert.match(html, /class="node-card connected"/);
  assert.match(html, /node-status online/);
  assert.match(html, /N1/);
  assert.match(html, /linux/);
  assert.match(html, /exec/);
});

test('connectedNodeCardHtml: offline card lacks "connected" class', () => {
  const html = connectedNodeCardHtml({ status: 'idle', displayName: 'N2' });
  assert.match(html, /class="node-card "/);
  assert.match(html, /node-status offline/);
});

test('connectedNodeCardHtml: escapes displayName + platform', () => {
  const html = connectedNodeCardHtml({
    displayName: '<n>', platform: '<p>', connected: false,
  });
  assert.ok(!html.includes('<n>'));
  assert.ok(!html.includes('<p>'));
  assert.match(html, /&lt;n&gt;/);
  assert.match(html, /&lt;p&gt;/);
});

// --- connectedNodesListHtml ---
test('connectedNodesListHtml: empty → empty-state message', () => {
  const html = connectedNodesListHtml([]);
  assert.match(html, /暂无已连接节点/);
  assert.ok(!html.includes('node-card'));
});

test('connectedNodesListHtml: null/undefined → empty-state', () => {
  assert.match(connectedNodesListHtml(null), /暂无已连接节点/);
  assert.match(connectedNodesListHtml(undefined), /暂无已连接节点/);
});

test('connectedNodesListHtml: includes header + N cards', () => {
  const html = connectedNodesListHtml([
    { displayName: 'A', connected: true },
    { displayName: 'B', status: 'idle' },
  ]);
  assert.match(html, /已知节点/);
  const cardCount = (html.match(/class="node-card[^-][^"]*"/g) || []).length;
  assert.equal(cardCount, 2);
});
