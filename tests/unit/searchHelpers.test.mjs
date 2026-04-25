// tests/unit/searchHelpers.test.mjs — pure search helpers for the chat sidebar.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  escReg, highlightText, findSnippet, chatMatches,
} from '../../web/src/ui/searchHelpers.js';

// --- escReg ---
test('escReg: escapes regex metacharacters', () => {
  assert.equal(escReg('a.b*c'), 'a\\.b\\*c');
  assert.equal(escReg('(x|y)'), '\\(x\\|y\\)');
  assert.equal(escReg('^$'), '\\^\\$');
});

test('escReg: leaves plain text alone', () => {
  assert.equal(escReg('hello world'), 'hello world');
});

test('escReg: result is safe inside RegExp', () => {
  // Must compile and match literally
  const re = new RegExp(escReg('a.b*c'));
  assert.ok(re.test('a.b*c'));
  assert.ok(!re.test('axbc')); // '.' should NOT be a wildcard
});

// --- highlightText ---
test('highlightText: empty query → just escaped text', () => {
  assert.equal(highlightText('<a>', ''), '&lt;a&gt;');
});

test('highlightText: wraps matches case-insensitively', () => {
  const out = highlightText('Hello hello HELLO', 'hello');
  assert.equal(out, '<mark>Hello</mark> <mark>hello</mark> <mark>HELLO</mark>');
});

test('highlightText: escapes HTML in source text', () => {
  const out = highlightText('<script>x</script>', 'script');
  assert.match(out, /&lt;<mark>script<\/mark>&gt;/);
  assert.ok(!out.includes('<script>')); // no raw script tag
});

test('highlightText: regex meta in query is treated as literal', () => {
  const out = highlightText('a.b a-b', 'a.b');
  assert.equal(out, '<mark>a.b</mark> a-b'); // dot is literal, not wildcard
});

// --- findSnippet ---
test('findSnippet: returns "" when no match', () => {
  assert.equal(findSnippet('hello world', 'xyz'), '');
});

test('findSnippet: empty inputs', () => {
  assert.equal(findSnippet('', 'x'), '');
  assert.equal(findSnippet('hi', ''), '');
});

test('findSnippet: short text returns full text without ellipses', () => {
  assert.equal(findSnippet('hello world', 'world'), 'hello world');
});

test('findSnippet: leading ellipsis when match is past radius', () => {
  const text = 'a'.repeat(100) + 'NEEDLE' + 'b'.repeat(100);
  const out = findSnippet(text, 'NEEDLE', 10);
  assert.ok(out.startsWith('…'));
  assert.ok(out.endsWith('…'));
  assert.match(out, /NEEDLE/);
});

test('findSnippet: case-insensitive matching, original case in output', () => {
  const out = findSnippet('Hello WoRlD', 'world');
  assert.match(out, /WoRlD/); // preserves original casing in slice
});

// --- chatMatches ---
test('chatMatches: empty query always matches', () => {
  assert.deepEqual(chatMatches({ title: 'foo', messages: [] }, ''), {
    match: true, snippet: '', msgIdx: -1,
  });
});

test('chatMatches: title match → no snippet, msgIdx=-1', () => {
  const out = chatMatches({ title: 'My Chat', messages: [] }, 'chat');
  assert.equal(out.match, true);
  assert.equal(out.msgIdx, -1);
  assert.equal(out.snippet, '');
});

test('chatMatches: title match takes precedence over message match', () => {
  const out = chatMatches(
    { title: 'foo', messages: [{ content: 'foo bar' }] },
    'foo'
  );
  assert.equal(out.msgIdx, -1);
});

test('chatMatches: falls back to first message containing query', () => {
  const out = chatMatches(
    { title: 'unrelated', messages: [
      { content: 'no match here' },
      { content: 'hello WORLD' },
      { content: 'hello world again' },
    ] },
    'world'
  );
  assert.equal(out.match, true);
  assert.equal(out.msgIdx, 1); // first match wins
  assert.match(out.snippet, /WORLD/);
});

test('chatMatches: no match → match:false, no msgIdx', () => {
  const out = chatMatches(
    { title: 'a', messages: [{ content: 'b' }] },
    'xyz'
  );
  assert.equal(out.match, false);
});

test('chatMatches: tolerates non-string message content', () => {
  const out = chatMatches(
    { title: 't', messages: [
      { content: { foo: 'bar' } },     // object, should be skipped
      { content: ['arr'] },             // array, skipped
      { content: 'hello world' },       // matches
    ] },
    'world'
  );
  assert.equal(out.match, true);
  assert.equal(out.msgIdx, 2);
});

test('chatMatches: tolerates missing fields', () => {
  assert.equal(chatMatches({}, 'x').match, false);
  assert.equal(chatMatches(null, '').match, true); // empty q always matches
});

test('chatMatches: case-insensitive', () => {
  const out = chatMatches(
    { title: 'My CHAT', messages: [] },
    'chat'
  );
  assert.equal(out.match, true);
});
