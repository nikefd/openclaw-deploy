<script setup lang="ts">
/**
 * ChatPane — composes the chat surface for a single sid.
 */
import { onMounted, toRefs } from 'vue'
import { useChat } from '@/composables/useChat'
import MessageList from './MessageList.vue'
import MessageInput from './MessageInput.vue'

const props = withDefaults(
  defineProps<{
    sid: string
    modelLabel?: string
  }>(),
  { modelLabel: 'claude-opus-4.7' },
)

const { sid } = toRefs(props)
const chat = useChat(sid)

onMounted(() => chat.connect())

function onSend(text: string) { chat.send(text) }
function onAbort() { chat.abort() }
function onRegenerate(_id: string) { chat.regenerate() }
function onDelete(id: string) {
  const idx = chat.messages.value.findIndex((m) => m.id === id)
  if (idx >= 0) chat.messages.value.splice(idx, 1)
}
</script>

<template>
  <section class="chat-pane">
    <header class="topbar">
      <div class="title">对话 · <code>{{ sid }}</code></div>
      <div class="model-tag" title="C2's ModelDropdown sits in App.vue overlay">
        Model: {{ modelLabel }}
      </div>
      <div class="status" :data-status="chat.status.value">{{ chat.status.value }}</div>
    </header>

    <MessageList
      :messages="chat.messages.value"
      :streaming-delta="chat.streamingDelta.value"
      :is-streaming="chat.isStreaming.value"
      @regenerate="onRegenerate"
      @delete="onDelete"
    />

    <MessageInput
      :is-streaming="chat.isStreaming.value"
      @send="onSend"
      @abort="onAbort"
    />
  </section>
</template>

<style scoped>
.chat-pane {
  flex: 1; display: flex; flex-direction: column;
  min-width: 0; background: var(--bg); height: 100%;
}
.topbar {
  display: flex; align-items: center; gap: 12px;
  padding: 10px 16px; border-bottom: 1px solid var(--border);
  background: var(--bg-elevated); flex-shrink: 0;
}
.title { font-size: 14px; font-weight: 600; }
.title code {
  font-family: var(--font-mono);
  font-size: 12px; color: var(--text-sec); background: transparent;
}
.model-tag {
  font-size: 12px; color: var(--accent);
  background: var(--accent-soft);
  padding: 2px 10px; border-radius: 999px;
}
.status {
  margin-left: auto; font-size: 12px; color: var(--text-sec);
  text-transform: uppercase; letter-spacing: 0.04em;
}
.status[data-status='streaming'], .status[data-status='queued'] { color: var(--accent); }
.status[data-status='failed'] { color: var(--danger); }
</style>
