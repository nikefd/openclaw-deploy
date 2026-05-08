<script setup lang="ts">
/**
 * MessageBubble — renders one chat message.
 *  - user: right-aligned plain text bubble
 *  - assistant: left-aligned markdown-rendered bubble + caret while streaming
 *  - system: centered grey pill
 *
 * Phase E4: per-message action row is copy-only (see MessageActions.vue).
 * The regenerate/delete emits are kept on the component for backwards
 * compatibility with MessageList's listener wiring but never fire from
 * the bubble itself anymore.
 */
import { computed, nextTick, ref, watch } from 'vue'
import type { ChatMessage } from '@oc/shared/chat'
import { useMarkdown } from '@/composables/useMarkdown'
import MessageActions from './MessageActions.vue'

const props = withDefaults(
  defineProps<{
    message: ChatMessage
    streaming?: boolean
    streamingText?: string
  }>(),
  { streaming: false, streamingText: '' },
)

defineEmits<{
  (e: 'regenerate', id: string): void
  (e: 'delete', id: string): void
}>()

const md = useMarkdown()
const htmlRoot = ref<HTMLElement | null>(null)

const role = computed(() => props.message.role)
const isUser = computed(() => role.value === 'user')
const isAssistant = computed(() => role.value === 'assistant')
const isSystem = computed(() => role.value === 'system' || role.value === 'tool')

const liveText = computed(() => {
  if (props.streaming && props.streamingText) return props.streamingText
  return props.message.text ?? ''
})

const renderedHtml = computed(() => (isAssistant.value ? md.render(liveText.value) : ''))

watch(
  renderedHtml,
  () => {
    if (!isAssistant.value) return
    nextTick(() => md.attachCodeCopyButtons(htmlRoot.value))
  },
  { immediate: true },
)
</script>

<template>
  <div class="bubble-row" :class="{ user: isUser, assistant: isAssistant, system: isSystem }" :data-role="role">
    <div v-if="isSystem" class="system-note">{{ liveText }}</div>

    <div v-else-if="isUser" class="bubble user-bubble">
      <div class="text">{{ liveText }}</div>
      <div class="row-actions">
        <MessageActions :message="message" />
      </div>
    </div>

    <div v-else class="bubble asst-bubble">
      <div class="avatar">🤖</div>
      <div class="body">
        <div ref="htmlRoot" class="text oc-md" v-html="renderedHtml" />
        <span v-if="streaming" class="oc-streaming-caret" aria-hidden="true">▌</span>
        <div v-if="!streaming" class="row-actions">
          <MessageActions :message="message" />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.bubble-row { display: flex; margin: 8px 0; width: 100%; }
.bubble-row.user { justify-content: flex-end; }
.bubble-row.assistant { justify-content: flex-start; }
.bubble-row.system { justify-content: center; }

.system-note {
  font-size: 12px; color: var(--text-sec);
  background: var(--bg-elevated);
  padding: 4px 12px; border-radius: 999px;
  max-width: 70%; text-align: center;
  border: 1px solid var(--border);
}

.bubble {
  max-width: min(75ch, 85%);
  padding: 10px 14px;
  border-radius: var(--radius-md);
  line-height: 1.6; font-size: 15px;
  word-break: break-word; position: relative;
}

.user-bubble { background: var(--bubble-user); color: var(--text); white-space: pre-wrap; }
[data-theme='dark'] .user-bubble { color: #fff; }

.asst-bubble {
  background: var(--bubble-assistant);
  display: flex; gap: 12px; align-items: flex-start;
  border: 1px solid var(--border);
  max-width: min(75ch, 92%);
}
.asst-bubble .avatar {
  width: 28px; height: 28px;
  border-radius: 6px;
  background: var(--accent); color: #fff;
  flex-shrink: 0; display: flex; align-items: center; justify-content: center;
  font-size: 14px;
}
.asst-bubble .body { flex: 1; min-width: 0; }

.row-actions { margin-top: 6px; display: flex; justify-content: flex-end; }
.text { word-wrap: break-word; }
</style>
