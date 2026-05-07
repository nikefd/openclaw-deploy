<script setup lang="ts">
// ChatList.vue — groups chats by recency and lays them out. Phase E will
// replace the stub list in stores/sidebar.ts with a real fetch.
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useSidebarStore, type ChatSummary } from '@/stores/sidebar'
import ChatListItem from './ChatListItem.vue'

const sidebar = useSidebarStore()
const { chatList, activeChatId } = storeToRefs(sidebar)
const router = useRouter()

interface Group {
  label: string
  items: ChatSummary[]
}

function bucket(c: ChatSummary, now: number): string {
  const d = new Date(c.lastMessageAt)
  const today = new Date(now)
  const isSameDay = (a: Date, b: Date) =>
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  if (isSameDay(d, today)) return '今天'
  const yest = new Date(now - 86_400_000)
  if (isSameDay(d, yest)) return '昨天'
  if (now - c.lastMessageAt < 7 * 86_400_000) return '本周'
  return '更早'
}

const grouped = computed<Group[]>(() => {
  const now = Date.now()
  const buckets: Record<string, ChatSummary[]> = {
    今天: [],
    昨天: [],
    本周: [],
    更早: [],
  }
  // Newest first
  const sorted = [...chatList.value].sort((a, b) => b.lastMessageAt - a.lastMessageAt)
  for (const c of sorted) {
    const k = bucket(c, now)
    buckets[k]!.push(c)
  }
  return (['今天', '昨天', '本周', '更早'] as const)
    .map((label) => ({ label, items: buckets[label]! }))
    .filter((g) => g.items.length > 0)
})

function onSelect(id: string) {
  sidebar.setActiveChatId(id)
  // router base is /v2/, route path is /c/:sid → URL /v2/c/<id>
  router.push(`/c/${id}`).catch(() => {
    /* silent — route may not exist in dev */
  })
}

function onNewChat() {
  // Phase E: POST /api/chats. For now route to root which renders ChatView.
  router.push('/').catch(() => {})
}

function onRename(id: string) {
  console.info('[Phase E] rename chat', id)
}
function onDelete(id: string) {
  console.info('[Phase E] delete chat', id)
}
</script>

<template>
  <div class="chat-list">
    <button class="new-chat" @click="onNewChat">+ 新建 chat</button>
    <div v-for="g in grouped" :key="g.label" class="group">
      <div class="group-label">{{ g.label }}</div>
      <ChatListItem
        v-for="c in g.items"
        :key="c.id"
        :chat="c"
        :active="c.id === activeChatId"
        @select="onSelect"
        @rename="onRename"
        @delete="onDelete"
      />
    </div>
    <div v-if="grouped.length === 0" class="empty">暂无对话</div>
  </div>
</template>

<style scoped lang="scss">
.chat-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px;
  overflow-y: auto;
  flex: 1;
}
.new-chat {
  margin-bottom: 6px;
  padding: 8px 10px;
  background: transparent;
  color: var(--sidebar-fg, var(--text));
  border: 1px dashed var(--border);
  border-radius: 8px;
  cursor: pointer;
  font-size: 13px;
  text-align: left;

  &:hover { background: var(--hover); }
}
.group + .group {
  margin-top: 8px;
}
.group-label {
  font-size: 10px;
  color: var(--text-sec);
  font-weight: 600;
  padding: 6px 10px 2px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.empty {
  padding: 20px;
  text-align: center;
  color: var(--text-sec);
  font-size: 12px;
}
</style>
