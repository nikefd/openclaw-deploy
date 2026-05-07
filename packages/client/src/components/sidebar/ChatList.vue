<script setup lang="ts">
/**
 * ChatList.vue — Phase E4 hydrated against /v2/api/chats.
 *
 * On mount we hit the real list endpoint, project results onto ChatSummary,
 * and push them into the sidebar store so ChatSearch (Ctrl+K) can reuse the
 * same cache. We DO NOT auto-poll; reload is manual via the refresh button.
 *
 * Active highlighting follows the route's :sid param (single source of
 * truth) so opening a chat URL directly highlights the right row.
 */
import { computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useSidebarStore, type ChatSummary } from '@/stores/sidebar'
import { useChatList } from '@/composables/useChatList'
import { deleteChat } from '@/api/chats'
import ChatListItem from './ChatListItem.vue'

const sidebar = useSidebarStore()
const { activeChatId } = storeToRefs(sidebar)
const router = useRouter()
const route = useRoute()

const { chats, loading, error, reload } = useChatList()

// Project DTO -> ChatSummary so the existing sidebar consumers keep working.
const summaries = computed<ChatSummary[]>(() =>
  chats.value.map((c) => ({
    id: c.id,
    title: c.title || '(无标题)',
    preview: c.preview,
    lastMessageAt: c.updatedAt || c.createdAt || 0,
  })),
)

// Push into the store for ChatSearch reuse.
watch(
  summaries,
  (list) => sidebar.setChatList(list),
  { immediate: true },
)

// Sync active id from route on every route change.
const routeSid = computed<string | null>(() => {
  const v = route.params.sid
  return typeof v === 'string' && v ? v : null
})
watch(
  routeSid,
  (id) => sidebar.setActiveChatId(id),
  { immediate: true },
)

onMounted(() => {
  void reload()
})

interface Group { label: string; items: ChatSummary[] }

function bucketLabel(ts: number, now: number): string {
  if (!ts) return '更早'
  const d = new Date(ts)
  const today = new Date(now)
  const sameDay =
    d.getFullYear() === today.getFullYear() &&
    d.getMonth() === today.getMonth() &&
    d.getDate() === today.getDate()
  if (sameDay) return '今天'
  const yest = new Date(now - 86_400_000)
  const sameYest =
    d.getFullYear() === yest.getFullYear() &&
    d.getMonth() === yest.getMonth() &&
    d.getDate() === yest.getDate()
  if (sameYest) return '昨天'
  if (now - ts < 7 * 86_400_000) return '本周'
  return '更早'
}

const grouped = computed<Group[]>(() => {
  const now = Date.now()
  const buckets: Record<string, ChatSummary[]> = {
    今天: [], 昨天: [], 本周: [], 更早: [],
  }
  // summaries are already sorted desc by updatedAt (fetchChatList sorts).
  for (const c of summaries.value) {
    buckets[bucketLabel(c.lastMessageAt, now)]!.push(c)
  }
  return (['今天', '昨天', '本周', '更早'] as const)
    .map((label) => ({ label, items: buckets[label]! }))
    .filter((g) => g.items.length > 0)
})

function onSelect(id: string) {
  sidebar.setActiveChatId(id)
  router.push(`/c/${id}`).catch(() => {})
}

function onNewChat() {
  // Mint a fresh sid client-side; ChatView handles the rest.
  const fresh = `chat_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
  router.push(`/c/${fresh}`).catch(() => {})
}

function onRename(id: string) {
  // Phase E4 punts on rename UI — file-api accepts a PUT but there's no
  // dialog primitive in v2 yet. Log and noop.
  console.info('[Phase E4] rename TODO', id)
}

async function onDelete(id: string) {
  if (typeof window !== 'undefined' && !window.confirm('删除这条对话？')) return
  const ok = await deleteChat(id)
  if (ok) {
    chats.value = chats.value.filter((c) => c.id !== id)
    if (activeChatId.value === id) {
      sidebar.setActiveChatId(null)
      router.push('/').catch(() => {})
    }
  }
}
</script>

<template>
  <div class="chat-list">
    <div class="head">
      <button class="new-chat" @click="onNewChat">+ 新建 chat</button>
      <button
        class="refresh"
        :disabled="loading"
        :title="loading ? '加载中…' : '刷新'"
        @click="reload"
      >
        {{ loading ? '…' : '↻' }}
      </button>
    </div>

    <div v-if="error" class="error">
      加载失败：{{ error }}
    </div>

    <div v-if="loading && summaries.length === 0" class="empty">加载中…</div>

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

    <div v-if="!loading && grouped.length === 0 && !error" class="empty">
      暂无对话<br />
      <span class="empty-sub">点击上面的「+ 新建 chat」开始</span>
    </div>
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
.head {
  display: flex;
  gap: 6px;
  margin-bottom: 6px;
}
.new-chat {
  flex: 1;
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
.refresh {
  width: 32px;
  background: transparent;
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--text-sec);
  cursor: pointer;
  font-size: 13px;

  &:hover:not(:disabled) { background: var(--hover); color: var(--text); }
  &:disabled { opacity: 0.5; cursor: wait; }
}
.error {
  margin: 4px 0;
  padding: 6px 10px;
  font-size: 11px;
  color: #d4504e;
  background: rgba(212, 80, 78, 0.08);
  border-radius: 6px;
}
.group + .group { margin-top: 8px; }
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
  line-height: 1.5;
}
.empty-sub { font-size: 11px; opacity: 0.7; }
</style>
