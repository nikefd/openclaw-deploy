// tests/unit/file-stripHeavy.test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const { stripHeavy } = require('../../services/file/lib/stripHeavy.js');

test('stripHeavy: returns input unchanged when no messages', () => {
  assert.equal(stripHeavy(null), null);
  assert.equal(stripHeavy(undefined), undefined);
  assert.deepEqual(stripHeavy({}), {});
  assert.deepEqual(stripHeavy({ messages: null }), { messages: null });
});

test('stripHeavy: chat with no heavy content is unchanged (same reference)', () => {
  const chat = { id: 'a', messages: [{ role: 'user', text: 'hi' }] };
  assert.equal(stripHeavy(chat), chat); // identity — no copy
});

test('stripHeavy: replaces images array with placeholder + count preserved', () => {
  const chat = {
    id: 'a',
    messages: [{ role: 'user', text: 'pic', images: ['data:image/png;base64,AAAA', 'b64:longstring'] }],
  };
  const out = stripHeavy(chat);
  assert.equal(out._stripped, true);
  assert.equal(out.messages[0]._stripped, true);
  assert.deepEqual(out.messages[0].images, ['[image]', '[image]']);
  // original NOT mutated
  assert.notEqual(out, chat);
  assert.equal(chat.messages[0].images[0].startsWith('data:image'), true);
});

test('stripHeavy: drops attachment data/content/base64 fields, keeps metadata', () => {
  const chat = {
    messages: [{
      role: 'user',
      attachments: [
        { name: 'a.png', size: 1000, data: 'AAAAAAAA' },
        { name: 'b.txt', content: 'hello world' },
        { name: 'c.bin', base64: 'XXX' },
        { name: 'd.txt', size: 5 }, // no heavy fields
      ],
    }],
  };
  const out = stripHeavy(chat);
  assert.equal(out._stripped, true);
  assert.equal(out.messages[0]._stripped, true);
  assert.equal(out.messages[0].attachments[0].name, 'a.png');
  assert.equal(out.messages[0].attachments[0].size, 1000);
  assert.equal('data' in out.messages[0].attachments[0], false);
  assert.equal('content' in out.messages[0].attachments[1], false);
  assert.equal('base64' in out.messages[0].attachments[2], false);
});

test('stripHeavy: long inline image string replaced (>200 chars)', () => {
  const longB64 = 'data:image/png;base64,' + 'A'.repeat(300);
  const chat = { messages: [{ role: 'assistant', image: longB64, text: 'see' }] };
  const out = stripHeavy(chat);
  assert.equal(out.messages[0].image, '[image]');
  assert.equal(out._stripped, true);
});

test('stripHeavy: short image string is preserved (< 200 chars)', () => {
  const shortUrl = 'https://example.com/pic.png';
  const chat = { messages: [{ role: 'assistant', image: shortUrl }] };
  const out = stripHeavy(chat);
  assert.equal(out, chat); // identity — nothing stripped
});

test('stripHeavy: handles non-object messages safely', () => {
  const chat = { messages: [null, undefined, 'string', 42, { role: 'user', text: 'hi' }] };
  const out = stripHeavy(chat);
  // No heavy → identity
  assert.equal(out, chat);
});

test('stripHeavy: only heavy messages get _stripped marker; clean ones do not', () => {
  const chat = {
    messages: [
      { role: 'user', text: 'plain' },
      { role: 'user', text: 'heavy', images: ['data:image/png;base64,AAA'] },
    ],
  };
  const out = stripHeavy(chat);
  assert.equal(out.messages[0]._stripped, undefined);
  assert.equal(out.messages[1]._stripped, true);
});

test('stripHeavy: empty arrays are not flagged', () => {
  const chat = { messages: [{ role: 'user', images: [], attachments: [] }] };
  const out = stripHeavy(chat);
  assert.equal(out, chat);
});
