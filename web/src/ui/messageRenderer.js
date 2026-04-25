// ui/messageRenderer.js — pure HTML builder for chat messages.
//
// appendMsg in index.html does three things:
//   1. compute strings (avatar bg, emoji, html for body/actions/images)
//   2. create a DOM node and assign innerHTML
//   3. mount it into messagesEl + scroll
//
// Steps 1+2's HTML construction is what we extract here. The caller still
// owns DOM creation, mounting, scroll, and the .msg-text return ref.
//
// API:
//   messageHtml({
//     role,         'user' | 'assistant'
//     content,      string (raw user text or already-rendered assistant md)
//     agent,        { emoji?, color? } | null
//     withTTS,      bool — include the 🔊 朗读 button on assistant msgs
//     images,       string[] of image urls
//     renderedBody, string of HTML to put inside .msg-text (caller renders
//                   markdown/escapes content; this lib just stamps it)
//     escapeHtml,   for image url + avatar color/emoji
//   }) → { className, innerHtml }
//
// Accepts a pre-rendered body so the caller still controls renderMd / esc.
// Keeps onclick handlers (copyMsg / speakText / openLightbox) referencing
// global functions, matching the existing inline contract.

const PLAIN_HTML = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const ESC_ATTR = (s) => String(s).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;');

/**
 * Build the actions row for a message (copy + optional TTS).
 * @param {{role:string, hasContent:boolean, withTTS:boolean}} opts
 * @returns {string}
 */
export function messageActionsHtml({ role, hasContent, withTTS }) {
  if (!hasContent) return '';
  const ttsBtn = (role === 'assistant' && withTTS)
    ? '<button class="tts-btn" onclick="speakText(this.closest(\'.message\').querySelector(\'.msg-text\').textContent,this)">🔊 朗读</button>'
    : '';
  return '<div class="msg-actions">' + ttsBtn + '<button class="copy-btn" onclick="copyMsg(this)">📋 复制</button></div>';
}

/**
 * Build the images strip for a message.
 * @param {string[]} images
 * @returns {string}
 */
export function messageImagesHtml(images) {
  if (!Array.isArray(images) || images.length === 0) return '';
  let html = '<div class="msg-images">';
  for (const u of images) {
    if (!u) continue;
    html += '<img src="' + ESC_ATTR(u) + '" onclick="openLightbox(this.src)">';
  }
  html += '</div>';
  return html;
}

/**
 * Build a chat message's className + innerHTML.
 * @param {{
 *   role:string,
 *   content:string,
 *   agent:{emoji?:string,color?:string}|null,
 *   withTTS:boolean,
 *   images?:string[],
 *   renderedBody:string,
 * }} opts
 * @returns {{className:string, innerHtml:string}}
 */
export function messageHtml({ role, content, agent, withTTS, images, renderedBody }) {
  const className = 'message ' + role;
  const isUser = role === 'user';
  const emoji = isUser ? '你' : (agent?.emoji || '🦞');
  // Avatar background:
  //   - user: no override (stylesheet handles it, matches old `bg=''` branch)
  //   - assistant: agent.color or fallback to var(--accent)
  const bgAttr = isUser
    ? ''
    : ' style="background:' + ESC_ATTR(agent?.color || 'var(--accent)') + '"';

  const actions = messageActionsHtml({
    role,
    hasContent: !!content,
    withTTS: !!withTTS,
  });
  const imgHtml = messageImagesHtml(images);
  const rawClass = isUser ? ' raw' : '';
  // Avatar emoji is plain text from agent config (not user-supplied), but we
  // still escape defensively.
  const safeEmoji = PLAIN_HTML(emoji);

  const innerHtml =
    '<div class="msg-inner">' +
      '<div class="avatar"' + bgAttr + '>' + safeEmoji + '</div>' +
      '<div style="flex:1">' +
        imgHtml +
        '<div class="msg-text' + rawClass + '">' + (renderedBody || '') + '</div>' +
        actions +
      '</div>' +
    '</div>';

  return { className, innerHtml };
}
