// ui/tts.js — text-to-speech via the browser SpeechSynthesis API.
//
// Single-instance: speaking text always cancels any in-flight utterance.
// Clicking the same button while speaking stops playback (toggle behaviour).

let curUtter = null;

/**
 * Speak the given text. The button is mutated to reflect playback state
 * (text + 'speaking' class). Called from inline onclick attributes in
 * message action bars; safe to call when SpeechSynthesis is unavailable
 * (silently no-ops).
 *
 * @param {string} text
 * @param {HTMLElement} btn
 */
export function speakText(text, btn) {
  if (typeof speechSynthesis === 'undefined') return;

  // Toggle: clicking the active speaking button stops it.
  if (curUtter) {
    speechSynthesis.cancel();
    if (btn?.classList?.contains('speaking')) {
      btn.classList.remove('speaking');
      btn.textContent = '🔊 朗读';
      curUtter = null;
      return;
    }
  }

  const u = new SpeechSynthesisUtterance(text);
  u.lang = 'zh-CN';
  curUtter = u;

  if (btn) {
    btn.classList.add('speaking');
    btn.textContent = '⏹ 停止';
  }
  u.onend = u.onerror = () => {
    if (btn) {
      btn.classList.remove('speaking');
      btn.textContent = '🔊 朗读';
    }
    curUtter = null;
  };
  speechSynthesis.speak(u);
}

/**
 * Cancel any in-flight TTS playback. Used when navigating away or unloading.
 */
export function stopSpeaking() {
  if (typeof speechSynthesis !== 'undefined') {
    try { speechSynthesis.cancel(); } catch {}
  }
  curUtter = null;
}
