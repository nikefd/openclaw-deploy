<script setup lang="ts">
/**
 * MessageActions — copy / regenerate / delete buttons.
 */
import { ref } from 'vue'
import type { ChatMessage } from '@oc/shared/chat'

const props = defineProps<{
  message: ChatMessage
  canRegenerate?: boolean
}>()

const emit = defineEmits<{
  (e: 'regenerate', id: string): void
  (e: 'delete', id: string): void
}>()

const copied = ref(false)

async function copy() {
  const text = props.message.text ?? ''
  try {
    await navigator.clipboard.writeText(text)
    copied.value = true
    setTimeout(() => (copied.value = false), 1200)
  } catch { /* ignore */ }
}
</script>

<template>
  <div class="actions">
    <button class="act" type="button" @click="copy" :title="copied ? 'copied' : 'copy'">
      {{ copied ? '✓' : '⧉' }}
    </button>
    <button v-if="canRegenerate" class="act" type="button" title="regenerate"
            @click="emit('regenerate', props.message.id)">↻</button>
    <button class="act act-danger" type="button" title="delete"
            @click="emit('delete', props.message.id)">✕</button>
  </div>
</template>

<style scoped>
.actions { display: inline-flex; gap: 4px; opacity: 0.5; transition: opacity 0.15s; }
.actions:hover { opacity: 1; }
.act {
  border: 1px solid var(--border);
  background: transparent;
  color: var(--text-sec);
  width: 24px; height: 24px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 12px; line-height: 1;
  display: inline-flex; align-items: center; justify-content: center;
}
.act:hover { background: var(--hover); color: var(--text); }
.act-danger:hover { color: var(--danger); border-color: var(--danger); }
</style>
