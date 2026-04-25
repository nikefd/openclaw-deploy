// ui/messageActions.js — per-message action button handlers (copy, etc).

/**
 * Click handler for the "📋 复制" button on a chat message.
 * Reads the .msg-text content from the closest .message ancestor.
 * @param {HTMLElement} btn
 */
export function copyMessage(btn) {
  const msg = btn.closest('.message');
  if (!msg) return;
  const textEl = msg.querySelector('.msg-text');
  if (!textEl) return;
  const text = textEl.textContent;
  navigator.clipboard.writeText(text)
    .then(() => {
      btn.textContent = '✅ 已复制';
      btn.classList.add('copied');
      setTimeout(() => {
        btn.textContent = '📋 复制';
        btn.classList.remove('copied');
      }, 1500);
    })
    .catch(() => alert('复制失败'));
}
