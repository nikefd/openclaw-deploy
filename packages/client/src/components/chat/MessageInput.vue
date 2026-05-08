<script setup lang="ts">
/**
 * MessageInput — autosize textarea, Enter to send, IME-safe, abort button.
 */
import { computed, nextTick, ref, watch } from 'vue'

const props = withDefaults(
  defineProps<{
    isStreaming?: boolean
    disabled?: boolean
    maxRows?: number
    softLimit?: number
  }>(),
  { isStreaming: false, disabled: false, maxRows: 8, softLimit: 4000 },
)

const emit = defineEmits<{
  (e: 'send', text: string): void
  (e: 'abort'): void
}>()

const textareaEl = ref<HTMLTextAreaElement | null>(null)
const text = ref('')
const composing = ref(false)

const overLimit = computed(() => text.value.length > props.softLimit)
const canSend = computed(
  () => !props.disabled && !props.isStreaming && text.value.trim().length > 0,
)

function autosize() {
  const el = textareaEl.value
  if (!el) return
  el.style.height = 'auto'
  const rowPx = 22
  const max = props.maxRows * rowPx + 16
  const next = Math.min(el.scrollHeight, max)
  el.style.height = `${next}px`
  el.style.overflowY = el.scrollHeight > max ? 'auto' : 'hidden'
}

watch(text, () => nextTick(autosize))

function onKeydown(ev: KeyboardEvent) {
  if (ev.key !== 'Enter' || ev.shiftKey || composing.value) return
  ev.preventDefault()
  trigger()
}

function trigger() {
  if (props.isStreaming) {
    emit('abort')
    return
  }
  if (!canSend.value) return
  const payload = text.value.trim()
  emit('send', payload)
  text.value = ''
  nextTick(autosize)
}
</script>

<template>
  <div class="composer" :class="{ 'is-streaming': isStreaming }">
    <div class="toolbar">
      <button type="button" class="tool-btn" disabled title="附件 (Phase E)">📎</button>
      <button type="button" class="tool-btn" disabled title="@mention (C2)">@</button>
      <span class="grow" />
      <span class="counter" :class="{ over: overLimit }">{{ text.length }}/{{ softLimit }}</span>
    </div>

    <div class="input-row">
      <textarea ref="textareaEl" v-model="text" :disabled="disabled" rows="1"
        placeholder="发消息… (Enter 发送 · Shift+Enter 换行)"
        @keydown="onKeydown"
        @compositionstart="composing = true"
        @compositionend="composing = false" />
      <button v-if="!isStreaming" type="button" class="send" :disabled="!canSend" @click="trigger" title="send">➤</button>
      <button v-else type="button" class="send abort" @click="trigger" title="abort">◼</button>
    </div>
  </div>
</template>

<style scoped>
.composer {
  border-top: 1px solid var(--border);
  background: var(--bg);
  padding: 10px 16px 14px;
}
.toolbar { display: flex; align-items: center; gap: 6px; margin-bottom: 6px; }
.grow { flex: 1; }
.tool-btn {
  width: 28px; height: 28px;
  border-radius: 6px;
  border: 1px solid var(--border);
  background: transparent; color: var(--text-sec);
  cursor: pointer; font-size: 14px;
}
.tool-btn[disabled] { opacity: 0.45; cursor: not-allowed; }
.counter { font-size: 11px; color: var(--text-sec); }
.counter.over { color: var(--danger); }

.input-row {
  display: flex; align-items: flex-end; gap: 8px;
  background: var(--input-bg); border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 8px 8px 8px 12px;
  transition: border-color 0.15s;
}
.input-row:focus-within { border-color: var(--accent); }

textarea {
  flex: 1; border: none; background: transparent; outline: none; resize: none;
  color: var(--text); font: inherit; font-size: 15px; line-height: 1.45;
  max-height: calc(8 * 22px + 16px);
}

.send {
  border: none; width: 32px; height: 32px;
  border-radius: 8px; background: var(--accent); color: #fff;
  cursor: pointer; font-size: 14px;
  flex-shrink: 0; align-self: flex-end;
}
.send:disabled { opacity: 0.4; cursor: not-allowed; }
.send.abort { background: var(--danger); }
</style>
