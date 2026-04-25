// ui/markdown.js — markdown rendering for chat messages.
//
// Uses globally-loaded marked.js (loaded via <script> in index.html for now).
// Adds a "复制" button to every <pre><code> block.

/**
 * Escape text to safe HTML using DOM (handles all edge cases including
 * non-string inputs gracefully).
 * @param {string} t
 * @returns {string}
 */
export function escDom(t) {
  const d = document.createElement('div');
  d.textContent = t == null ? '' : String(t);
  return d.innerHTML;
}

/**
 * Render markdown text → HTML string. Falls back to escaped text if
 * marked is not loaded or throws.
 * @param {string} text
 * @returns {string}
 */
export function renderMd(text) {
  if (!text) return '';
  if (typeof window === 'undefined' || typeof window.marked === 'undefined') {
    return escDom(text);
  }
  try {
    let html = window.marked.parse(text);
    // Add copy buttons to code blocks. The onclick handler references a
    // global copyCodeBlock — that lives in index.html for now; when UI is
    // fully modularized this will switch to event delegation.
    html = html.replace(
      /<pre><code/g,
      '<pre><button class="copy-code-btn" onclick="copyCodeBlock(this)">复制</button><code'
    );
    return html;
  } catch (e) {
    return escDom(text);
  }
}

/**
 * Click handler for the inline "复制" button on a code block.
 * @param {HTMLElement} btn
 */
export function copyCodeBlock(btn) {
  const code = btn.nextElementSibling;
  if (!code) return;
  const text = code.textContent;
  navigator.clipboard.writeText(text)
    .then(() => {
      btn.textContent = '✅';
      setTimeout(() => { btn.textContent = '复制'; }, 1500);
    })
    .catch(() => {});
}
