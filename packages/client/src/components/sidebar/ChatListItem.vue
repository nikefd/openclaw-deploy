<script setup lang="ts">
// ChatListItem.vue — single chat row. Pure presentational; click bubbles up
// to ChatList which handles the router push so the row stays test-friendly.
import { computed } from 'vue'
import type { ChatSummary } from '@/stores/sidebar'

const props = defineProps<{
  chat: ChatSummary
  active: boolean
  /** For Phase E. Always false in C2. */
  hasUnread?: boolean
}>()

defineEmits<{
  (e: 'select', id: string): void
  (e: 'rename', id: string): void
  (e: 'delete', id: string): void
}>()

function pad2(n: number) {
  return n < 10 ? '0' + n : '' + n
}

const timeLabel = computed(() => {
  const d = new Date(props.chat.lastMessageAt)
  const today = new Date()
  const sameDay =
    d.getFullYear() === today.getFullYear() &&
    d.getMonth() === today.getMonth() &&
    d.getDate() === today.getDate()
  if (sameDay) return `${pad2(d.getHours())}:${pad2(d.getMinutes())}`
  return `${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`
})

const agentEmoji = computed(() => props.chat.agent?.emoji ?? '💬')
</script>

<template>
  <div
    class="chat-item"
    :class="{ active }"
    @click="$emit('select', chat.id)"
  >
    <div class="emoji">{{ agentEmoji }}</div>
    <div class="info">
      <div class="row1">
        <span class="title">{{ chat.title }}</span>
        <span class="time">{{ timeLabel }}</span>
      </div>
      <div class="preview">{{ chat.preview }}</div>
    </div>
    <span v-if="hasUnread" class="dot" />
    <div class="actions" @click.stop>
      <button title="重命名" @click="$emit('rename', chat.id)">✎</button>
      <button title="删除" @click="$emit('delete', chat.id)">✕</button>
    </div>
  </div>
</template>

<style scoped lang="scss">
.chat-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 8px;
  cursor: pointer;
  position: relative;
  transition: background 0.12s ease;

  &:hover {
    background: var(--hover);
    .actions { opacity: 1; }
  }
  &.active {
    background: var(--sidebar-active-bg);
  }
}
.emoji {
  font-size: 18px;
  line-height: 1.2;
  width: 22px;
  text-align: center;
  flex: 0 0 22px;
}
.info {
  flex: 1;
  min-width: 0;
}
.row1 {
  display: flex;
  align-items: baseline;
  gap: 6px;
}
.title {
  flex: 1;
  font-size: 13px;
  font-weight: 500;
  color: var(--sidebar-fg, var(--text));
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.time {
  font-size: 10px;
  color: var(--text-sec);
  flex-shrink: 0;
}
.preview {
  font-size: 11px;
  color: var(--text-sec);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-top: 2px;
}
.dot {
  position: absolute;
  top: 10px;
  right: 8px;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--accent);
}
.actions {
  display: flex;
  gap: 2px;
  opacity: 0;
  transition: opacity 0.12s;
}
.actions button {
  background: transparent;
  border: none;
  color: var(--text-sec);
  cursor: pointer;
  padding: 2px 4px;
  border-radius: 4px;
  font-size: 11px;

  &:hover {
    background: var(--bg-elevated);
    color: var(--text);
  }
}
</style>
