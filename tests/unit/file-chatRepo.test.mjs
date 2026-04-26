// tests/unit/file-chatRepo.test.mjs
//
// Repo layer tests using an in-memory fs mock — no real disk I/O.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const path = require('path');
const { createChatRepo } = require('../../services/file/lib/chatRepo.js');
const { stripHeavy } = require('../../services/file/lib/stripHeavy.js');
const { checkChatOverwrite } = require('../../services/file/lib/chatGuards.js');

// ── In-memory fs mock ──────────────────────────────────────────

function makeFsMock(seed = {}) {
  const files = new Map(Object.entries(seed));        // path -> string
  const dirs = new Set();
  return {
    files,
    dirs,
    mkdirSync(p, _opts) { dirs.add(p); },
    existsSync(p) { return files.has(p); },
    readdirSync(dir) {
      const prefix = dir.endsWith('/') ? dir : dir + '/';
      const out = [];
      for (const k of files.keys()) {
        if (k.startsWith(prefix)) {
          const rest = k.slice(prefix.length);
          if (!rest.includes('/')) out.push(rest);
        }
      }
      return out;
    },
    readFileSync(p, _enc) {
      if (!files.has(p)) throw Object.assign(new Error('ENOENT'), { code: 'ENOENT' });
      return files.get(p);
    },
    writeFileSync(p, body, _enc) { files.set(p, String(body)); },
    unlinkSync(p) { files.delete(p); },
  };
}

const CHATS_DIR = '/tmp/chats';
const CHATS_FILE = '/tmp/chat-history.json';

function makeRepo(seed = {}, opts = {}) {
  const fs = makeFsMock(seed);
  const warnings = [];
  const repo = createChatRepo({
    fs,
    chatsDir: CHATS_DIR,
    chatsFile: CHATS_FILE,
    stripHeavy,
    checkChatOverwrite: opts.guard || checkChatOverwrite,
    warn: (...a) => warnings.push(a),
  });
  return { repo, fs, warnings };
}

const cp = (id) => path.join(CHATS_DIR, id + '.json');

// ── createChatRepo: dep validation ─────────────────────────────

test('createChatRepo: missing deps → throws', () => {
  assert.throws(() => createChatRepo(), /missing required deps/);
  assert.throws(() => createChatRepo({}), /missing required deps/);
  assert.throws(() => createChatRepo({ fs: {} }), /missing required deps/);
});

// ── listChats ──────────────────────────────────────────────────

test('listChats: empty dir + no legacy → []', () => {
  const { repo } = makeRepo();
  assert.deepEqual(repo.listChats().data, []);
});

test('listChats: reads per-chat files, sorted by updatedAt desc', () => {
  const { repo } = makeRepo({
    [cp('a')]: JSON.stringify({ id: 'a', updatedAt: 100, messages: [] }),
    [cp('b')]: JSON.stringify({ id: 'b', updatedAt: 300, messages: [] }),
    [cp('c')]: JSON.stringify({ id: 'c', updatedAt: 200, messages: [] }),
  });
  const out = repo.listChats().data;
  assert.deepEqual(out.map((c) => c.id), ['b', 'c', 'a']);
});

test('listChats: skips corrupt JSON', () => {
  const { repo } = makeRepo({
    [cp('ok')]: JSON.stringify({ id: 'ok', updatedAt: 1, messages: [] }),
    [cp('bad')]: '{ not json',
  });
  const out = repo.listChats().data;
  assert.equal(out.length, 1);
  assert.equal(out[0].id, 'ok');
});

test('listChats: ?since filters', () => {
  const { repo } = makeRepo({
    [cp('a')]: JSON.stringify({ id: 'a', updatedAt: 100, messages: [] }),
    [cp('b')]: JSON.stringify({ id: 'b', updatedAt: 300, messages: [] }),
    [cp('c')]: JSON.stringify({ id: 'c', updatedAt: 200, messages: [] }),
  });
  const out = repo.listChats({ since: 150 }).data;
  assert.deepEqual(out.map((c) => c.id), ['b', 'c']);
});

test('listChats: default → stripHeavy applied (images replaced)', () => {
  const heavyImg = 'data:image/png;base64,'.padEnd(500, 'x');
  const { repo } = makeRepo({
    [cp('z')]: JSON.stringify({
      id: 'z', updatedAt: 1,
      messages: [{ role: 'user', content: 'hi', images: [heavyImg] }],
    }),
  });
  const out = repo.listChats().data;
  assert.equal(out[0]._stripped, true);
  assert.deepEqual(out[0].messages[0].images, ['[image]']);
});

test('listChats: full=true → no stripHeavy', () => {
  const heavyImg = 'data:image/png;base64,'.padEnd(500, 'x');
  const { repo } = makeRepo({
    [cp('z')]: JSON.stringify({
      id: 'z', updatedAt: 1,
      messages: [{ role: 'user', content: 'hi', images: [heavyImg] }],
    }),
  });
  const out = repo.listChats({ full: true }).data;
  assert.equal(out[0]._stripped, undefined);
  assert.equal(out[0].messages[0].images[0], heavyImg);
});

test('listChats: legacy file fallback when per-chat dir empty', () => {
  const { repo, fs } = makeRepo({
    [CHATS_FILE]: JSON.stringify([
      { id: 'leg1', updatedAt: 50, messages: [] },
      { id: 'leg2', updatedAt: 70, messages: [] },
    ]),
  });
  const out = repo.listChats().data;
  assert.equal(out.length, 2);
  // After migration the per-chat files exist
  assert.ok(fs.files.has(cp('leg1')));
  assert.ok(fs.files.has(cp('leg2')));
});

// ── bulkSaveChats ──────────────────────────────────────────────

test('bulkSaveChats: writes per-chat + legacy', () => {
  const { repo, fs } = makeRepo();
  const chats = [
    { id: 'a', messages: [], updatedAt: 1 },
    { id: 'b', messages: [], updatedAt: 2 },
  ];
  assert.deepEqual(repo.bulkSaveChats(chats), { ok: true });
  assert.ok(fs.files.has(cp('a')));
  assert.ok(fs.files.has(cp('b')));
  assert.ok(fs.files.has(CHATS_FILE));
  assert.deepEqual(JSON.parse(fs.files.get(CHATS_FILE)), chats);
});

test('bulkSaveChats: ignores entries without id', () => {
  const { repo, fs } = makeRepo();
  repo.bulkSaveChats([{ id: 'ok', messages: [] }, { messages: [] }, null]);
  assert.equal(fs.files.has(cp('ok')), true);
});

test('bulkSaveChats: non-array → throws', () => {
  const { repo } = makeRepo();
  assert.throws(() => repo.bulkSaveChats('nope'), /must be array/);
});

// ── getChatRaw ─────────────────────────────────────────────────

test('getChatRaw: missing → {found:false}', () => {
  const { repo } = makeRepo();
  assert.deepEqual(repo.getChatRaw('missing'), { found: false });
});

test('getChatRaw: returns raw JSON string (not parsed)', () => {
  const raw = '{"id":"x","messages":[]}';
  const { repo } = makeRepo({ [cp('x')]: raw });
  const r = repo.getChatRaw('x');
  assert.equal(r.found, true);
  assert.equal(r.data, raw);
});

test('getChatRaw: empty chatId → throws', () => {
  const { repo } = makeRepo();
  assert.throws(() => repo.getChatRaw(''), /chatId required/);
});

// ── saveChat ───────────────────────────────────────────────────

test('saveChat: new chat → ok + file written', () => {
  const { repo, fs } = makeRepo();
  const c = { id: 'fresh', messages: [{ role: 'user', content: 'hi' }] };
  assert.deepEqual(repo.saveChat('fresh', c), { ok: true });
  assert.equal(fs.files.has(cp('fresh')), true);
  assert.deepEqual(JSON.parse(fs.files.get(cp('fresh'))), c);
});

test('saveChat: empty-overwrite → rejected 409 (file unchanged)', () => {
  const existing = { id: 'x', messages: [{ role: 'user', content: 'keep me' }] };
  const { repo, fs, warnings } = makeRepo({ [cp('x')]: JSON.stringify(existing) });
  const r = repo.saveChat('x', { id: 'x', messages: [] });
  assert.equal(r.ok, false);
  assert.equal(r.status, 409);
  assert.equal(r.reason, 'empty-overwrite');
  // File untouched
  assert.deepEqual(JSON.parse(fs.files.get(cp('x'))), existing);
  // Warn was called
  assert.equal(warnings.length, 1);
  assert.equal(warnings[0][0], '[chats] REFUSED');
});

test('saveChat: streaming-over-final → rejected', () => {
  const existing = {
    id: 'x',
    messages: [{ role: 'assistant', content: 'final answer' }],
  };
  const { repo } = makeRepo({ [cp('x')]: JSON.stringify(existing) });
  const r = repo.saveChat('x', {
    id: 'x',
    messages: [{ role: 'assistant', content: 'partial', _streaming: true }],
  });
  assert.equal(r.ok, false);
  assert.equal(r.reason, 'streaming-over-final');
});

test('saveChat: shrink-finalized > 20 chars → rejected', () => {
  const long = 'A'.repeat(100);
  const existing = { id: 'x', messages: [{ role: 'assistant', content: long }] };
  const { repo } = makeRepo({ [cp('x')]: JSON.stringify(existing) });
  const r = repo.saveChat('x', {
    id: 'x', messages: [{ role: 'assistant', content: 'short' }],
  });
  assert.equal(r.ok, false);
  assert.equal(r.reason, 'shrink-finalized');
});

test('saveChat: corrupt existing file → write proceeds', () => {
  const { repo, fs } = makeRepo({ [cp('x')]: '{ corrupt' });
  const r = repo.saveChat('x', { id: 'x', messages: [] });
  assert.equal(r.ok, true);
  assert.equal(JSON.parse(fs.files.get(cp('x'))).id, 'x');
});

test('saveChat: ACCEPTED-SHRINK warning when msg count drops but allowed', () => {
  // existing has 5 user msgs, no finalized assistant — shrink guard does NOT trigger
  // but we still want the shrink-acceptance log
  const existing = {
    id: 'x',
    messages: [
      { role: 'user', content: '1' },
      { role: 'user', content: '2' },
      { role: 'user', content: '3' },
      { role: 'user', content: '4' },
      { role: 'user', content: '5' },
    ],
  };
  const { repo, warnings } = makeRepo({ [cp('x')]: JSON.stringify(existing) });
  const r = repo.saveChat('x', {
    id: 'x',
    messages: [{ role: 'user', content: '1' }, { role: 'user', content: '2' }],
  });
  assert.equal(r.ok, true);
  const shrinkWarn = warnings.find((w) => w[0] === '[chats] ACCEPTED-SHRINK');
  assert.ok(shrinkWarn, 'expected ACCEPTED-SHRINK warning');
  assert.equal(shrinkWarn[1], 'x');
});

test('saveChat: equal-length write does NOT log ACCEPTED-SHRINK', () => {
  const existing = { id: 'x', messages: [{ role: 'user', content: '1' }] };
  const { repo, warnings } = makeRepo({ [cp('x')]: JSON.stringify(existing) });
  repo.saveChat('x', { id: 'x', messages: [{ role: 'user', content: '2' }] });
  assert.equal(warnings.length, 0);
});

test('saveChat: empty chatId → throws', () => {
  const { repo } = makeRepo();
  assert.throws(() => repo.saveChat('', {}), /chatId required/);
});

// ── deleteChat ─────────────────────────────────────────────────

test('deleteChat: existing → unlinked', () => {
  const { repo, fs } = makeRepo({
    [cp('gone')]: '{"id":"gone","messages":[]}',
  });
  assert.deepEqual(repo.deleteChat('gone'), { ok: true });
  assert.equal(fs.files.has(cp('gone')), false);
});

test('deleteChat: missing → still ok', () => {
  const { repo } = makeRepo();
  assert.deepEqual(repo.deleteChat('ghost'), { ok: true });
});

test('deleteChat: empty chatId → throws', () => {
  const { repo } = makeRepo();
  assert.throws(() => repo.deleteChat(''), /chatId required/);
});
