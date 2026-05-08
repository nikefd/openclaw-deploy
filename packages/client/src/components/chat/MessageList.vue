<script setup lang="ts">
/**
 * MessageList — message stream + virtual streaming bubble + auto-scroll.
 */
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { ChatMessage } from '@oc/shared/chat'
import { useAutoScroll } from '@/composables/useAutoScroll'
import { useTypewriter } from '@/composables/useTypewriter'
import { useStreamProgress } from '@/composables/useStreamProgress'
import MessageBubble from './MessageBubble.vue'

const props = withDefaults(
  defineProps<{
    messages: ChatMessage[]
    streamingDelta?: string
    isStreaming?: boolean
  }>(),
  { streamingDelta: '', isStreaming: false },
)

const emit = defineEmits<{
  (e: 'regenerate', id: string): void
  (e: 'delete', id: string): void
  (e: 'load-more'): void
}>()

const scrollEl = ref<HTMLDivElement | null>(null)
const { atBottom, bind, scrollToBottom } = useAutoScroll({ threshold: 50 })
let unbind: (() => void) | null = null

const deltaSource = computed(() => props.streamingDelta)
const tw = useTypewriter(deltaSource, { intervalMs: 16, charsPerTick: 3 })
const streamProgress = useStreamProgress(
  computed(() => props.isStreaming),
  deltaSource,
)

const streamingBubble = computed<ChatMessage | null>(() => {
  if (!props.isStreaming) return null
  if (!deltaSource.value && !tw.display.value) return null
  return {
    id: '__streaming__',
    role: 'assistant',
    createdAt: Date.now(),
    content: [{ type: 'text', text: tw.display.value }],
    text: tw.display.value,
  }
})

onMounted(() => {
  unbind = bind(scrollEl.value)
  nextTick(() => scrollToBottom(true))
})
onBeforeUnmount(() => unbind?.())

watch(
  () => [props.messages.length, tw.display.value, props.isStreaming],
  () => nextTick(() => scrollToBottom()),
)

watch(
  () => props.isStreaming,
  (s) => { if (!s) tw.flush() },
)

function bubbleKey(m: ChatMessage, i: number): string {
  return m.id || `${m.role}-${i}`
}
</script>

<template>
  <div ref="scrollEl" class="msg-list">
    <div class="load-more">
      <button type="button" class="load-more-btn" disabled @click="emit('load-more')">
        加载更多历史 (Phase E)
      </button>
    </div>

    <div v-if="messages.length === 0 && !streamingBubble" class="empty">
      <div class="empty-title">开始一段新的对话</div>
      <div class="empty-sub">输入消息，按 Enter 发送 · Shift+Enter 换行</div>
    </div>

    <MessageBubble
      v-for="(m, i) in messages"
      :key="bubbleKey(m, i)"
      :message="m"
      @regenerate="(id) => emit('regenerate', id)"
      @delete="(id) => emit('delete', id)"
    />

    <!-- Progress indicator when streaming but not yet showing bubble -->
    <div v-if="props.isStreaming && !streamingBubble" class="progress-indicator">
      <span class="progress-icon">{{ streamProgress.progress.value.icon }}</span>
      <span class="progress-text">{{ streamProgress.progress.value.message }}</span>
      <span v-if="streamProgress.estimatedTokens.value > 0" class="progress-tokens">
        (~{{ streamProgress.estimatedTokens.value }} tokens)
      </span>
    </div>

    <MessageBubble
      v-if="streamingBubble"
      :key="'__streaming__'"
      :message="streamingBubble"
      :streaming="true"
      :streaming-text="streamingBubble.text"
    />

    <div v-if="!atBottom" class="jump-to-bottom" @click="scrollToBottom(true)">
      ↓ 回到底部
    </div>
  </div>
</template>

<style scoped>
.msg-list {
  flex: 1; overflow-y: auto;
  padding: 16px 24px 24px;
  position: relative; scroll-behavior: smooth;
  display: flex; flex-direction: column;
}
.load-more { display: flex; justify-content: center; margin-bottom: 8px; }
.load-more-btn {
  background: transparent; border: 1px solid var(--border); color: var(--text-sec);
  font-size: 12px; padding: 4px 12px; border-radius: 999px; cursor: pointer;
}
.load-more-btn[disabled] { opacity: 0.45; cursor: not-allowed; }
.empty { margin: auto; text-align: center; color: var(--text-sec); }
.empty-title { font-size: 18px; color: var(--text); margin-bottom: 4px; }
.empty-sub { font-size: 13px; }
.progress-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  margin: 8px 0;
  border-radius: 8px;
  background: var(--bg-elevated);
  color: var(--text-sec);
  font-size: 13px;
  animation: pulse 1.5s ease-in-out infinite;
}
.progress-icon { font-size: 16px; }
.progress-text { flex: 1; }
.progress-tokens { opacity: 0.7; font-size: 12px; }
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}
.jump-to-bottom {
  position: sticky; bottom: 12px; align-self: center;
  background: var(--bg-elevated); border: 1px solid var(--border); color: var(--text);
  font-size: 12px; padding: 4px 12px; border-radius: 999px;
  cursor: pointer; box-shadow: var(--shadow-1);
}
.jump-to-bottom:hover { background: var(--hover); }
</style>
