// tests/unit/messageRenderer.test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  messageHtml, messageActionsHtml, messageImagesHtml,
} from '../../web/src/ui/messageRenderer.js';

const AGENT = { emoji: '🦞', color: '#ff8800' };

// ── messageActionsHtml ────────────────────────────────────────────

test('messageActionsHtml: no content → empty', () => {
  assert.equal(messageActionsHtml({ role: 'user', hasContent: false, withTTS: true }), '');
});

test('messageActionsHtml: user message → only copy button', () => {
  const h = messageActionsHtml({ role: 'user', hasContent: true, withTTS: true });
  assert.match(h, /copy-btn/);
  assert.doesNotMatch(h, /tts-btn/);
});

test('messageActionsHtml: assistant + withTTS → both buttons', () => {
  const h = messageActionsHtml({ role: 'assistant', hasContent: true, withTTS: true });
  assert.match(h, /tts-btn/);
  assert.match(h, /copy-btn/);
  assert.match(h, /朗读/);
});

test('messageActionsHtml: assistant without TTS → only copy', () => {
  const h = messageActionsHtml({ role: 'assistant', hasContent: true, withTTS: false });
  assert.doesNotMatch(h, /tts-btn/);
  assert.match(h, /copy-btn/);
});

// ── messageImagesHtml ──────────────────────────────────────────────

test('messageImagesHtml: empty/null → empty', () => {
  assert.equal(messageImagesHtml(null), '');
  assert.equal(messageImagesHtml([]), '');
  assert.equal(messageImagesHtml(undefined), '');
});

test('messageImagesHtml: renders each image with onclick', () => {
  const h = messageImagesHtml(['/a.png', '/b.png']);
  assert.match(h, /msg-images/);
  assert.match(h, /src="\/a\.png"/);
  assert.match(h, /src="\/b\.png"/);
  assert.equal((h.match(/<img/g) || []).length, 2);
  assert.match(h, /openLightbox/);
});

test('messageImagesHtml: skips falsy entries', () => {
  const h = messageImagesHtml(['', null, '/ok.png']);
  assert.equal((h.match(/<img/g) || []).length, 1);
});

test('messageImagesHtml: XSS — quote in url escaped in attr', () => {
  const h = messageImagesHtml(['/x.png" onerror="alert(1)']);
  assert.doesNotMatch(h, /src="\/x\.png" onerror/);
  assert.match(h, /&quot;/);
});

// ── messageHtml ────────────────────────────────────────────────────

test('messageHtml: user role → className "message user", no avatar bg', () => {
  const r = messageHtml({
    role: 'user', content: 'hi', agent: null, withTTS: false,
    images: null, renderedBody: 'hi',
  });
  assert.equal(r.className, 'message user');
  assert.match(r.innerHtml, /<div class="avatar">你<\/div>/);
  assert.match(r.innerHtml, /msg-text raw">hi<\/div>/);
});

test('messageHtml: assistant role → bg style + agent emoji + non-raw msg-text', () => {
  const r = messageHtml({
    role: 'assistant', content: 'ok', agent: AGENT, withTTS: false,
    images: null, renderedBody: '<p>ok</p>',
  });
  assert.equal(r.className, 'message assistant');
  assert.match(r.innerHtml, /style="background:#ff8800"/);
  assert.match(r.innerHtml, />🦞</);
  assert.match(r.innerHtml, /msg-text">/);
  assert.doesNotMatch(r.innerHtml, /msg-text raw/);
  assert.match(r.innerHtml, /<p>ok<\/p>/);
});

test('messageHtml: assistant w/o agent → fallback emoji + accent color', () => {
  const r = messageHtml({
    role: 'assistant', content: 'x', agent: null, withTTS: false,
    images: null, renderedBody: 'x',
  });
  assert.match(r.innerHtml, /var\(--accent\)/);
  assert.match(r.innerHtml, /🦞/);
});

test('messageHtml: empty content → no actions row', () => {
  const r = messageHtml({
    role: 'user', content: '', agent: null, withTTS: false,
    images: null, renderedBody: '',
  });
  assert.doesNotMatch(r.innerHtml, /msg-actions/);
});

test('messageHtml: assistant with content + TTS → tts button present', () => {
  const r = messageHtml({
    role: 'assistant', content: 'x', agent: AGENT, withTTS: true,
    images: null, renderedBody: 'x',
  });
  assert.match(r.innerHtml, /tts-btn/);
  assert.match(r.innerHtml, /copy-btn/);
});

test('messageHtml: with images → images strip rendered before msg-text', () => {
  const r = messageHtml({
    role: 'user', content: 'see pic', agent: null, withTTS: false,
    images: ['/img.png'], renderedBody: 'see pic',
  });
  assert.match(r.innerHtml, /msg-images/);
  // images come before msg-text
  const imgIdx = r.innerHtml.indexOf('msg-images');
  const txtIdx = r.innerHtml.indexOf('msg-text');
  assert.ok(imgIdx > 0 && txtIdx > imgIdx);
});

test('messageHtml: renderedBody is stamped raw (caller already escaped/markdown-rendered)', () => {
  // Caller passes pre-rendered HTML (markdown for assistant, esc'd for user).
  // The lib must NOT double-escape.
  const r = messageHtml({
    role: 'assistant', content: '...', agent: AGENT, withTTS: false,
    images: null, renderedBody: '<strong>bold</strong>',
  });
  assert.match(r.innerHtml, /<strong>bold<\/strong>/);
});

test('messageHtml: XSS — agent.color quote escaped in style attr', () => {
  const r = messageHtml({
    role: 'assistant', content: 'x',
    agent: { emoji: '🐶', color: 'red" onload="alert(1)' },
    withTTS: false, images: null, renderedBody: 'x',
  });
  assert.doesNotMatch(r.innerHtml, /style="background:red" onload/);
  assert.match(r.innerHtml, /&quot;/);
});

test('messageHtml: XSS — agent emoji escaped (defensive)', () => {
  const r = messageHtml({
    role: 'assistant', content: 'x',
    agent: { emoji: '<img onerror=1>', color: '#000' },
    withTTS: false, images: null, renderedBody: 'x',
  });
  assert.doesNotMatch(r.innerHtml, /<img onerror/);
  assert.match(r.innerHtml, /&lt;img onerror=1&gt;/);
});
