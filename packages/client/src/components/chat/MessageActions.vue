<script setup lang="ts">
/**
 * MessageActions — copy-only (Phase E4).
 *
 * Earlier iterations had regenerate / delete buttons inline with each
 * bubble. They were rarely useful (regenerate sat on assistant only,
 * delete was destructive without confirmation) and added noise. We now
 * keep just one button: copy, with a 1s "已复制" feedback.
 */
import { ref } from 'vue'
import type { ChatMessage } from '@oc/shared/chat'

const props = defineProps<{
  message: ChatMessage
}>()

const copied = ref(false)
let resetTimer: ReturnType<typeof setTimeout> | null = null

async function copy() {
  const text = props.message.text ?? ''
  if (!text) return
  try {
    if (navigator?.clipboard?.writeText) {
      await navigator.clipboard.writeText(text)
    } else {
      // Fallback for older Safari / non-secure contexts.
      const ta = document.createElement('textarea')
      ta.value = text
      ta.style.position = 'fixed'
      ta.style.opacity = '0'
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
    }
    copied.value = true
    if (resetTimer) clearTimeout(resetTimer)
    resetTimer = setTimeout(() => { copied.value = false }, 1000)
  } catch {
    // ignore; UI just won't flip
  }
}
</script>

<template>
  <div class="actions">
    <button
      class="act"
      type="button"
      :title="copied ? '已复制' : '复制'"
      :aria-label="copied ? '已复制' : '复制'"
      @click="copy"
    >
      <span v-if="copied" class="label copied">✓ 已复制</span>
      <span v-else class="label">⧉ 复制</span>
    </button>
  </div>
</template>

<style scoped>
.actions { display: inline-flex; gap: 4px; opacity: 0.55; transition: opacity 0.15s; }
.actions:hover { opacity: 1; }
.act {
  border: 1px solid var(--border);
  background: transparent;
  color: var(--text-sec);
  height: 24px;
  padding: 0 8px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 11px;
  line-height: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.act:hover { background: var(--hover); color: var(--text); }
.label.copied { color: var(--accent, #10a37f); }
</style>
