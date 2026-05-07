<script setup lang="ts">
/**
 * ChatView — route container.
 *
 * Phase E4 changes:
 *   - on `/` (chat-root): if localStorage has `oc_v2_last_sid` and it
 *     points at a chat that still exists upstream, redirect to /c/<id>.
 *     Otherwise stay on the bare new-chat surface (no auto-redirect away).
 *   - on `/c/:sid`: hydrate the chat store with messages from
 *     /v2/api/chats/:id (best-effort; missing → empty surface, treat as
 *     fresh chat). Also write `oc_v2_last_sid` so resume works next time.
 */
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import ChatPane from '@/components/chat/ChatPane.vue'
import { useChatStore } from '@/stores/chat'
import { fetchChat } from '@/api/chats'
import type { ChatMessage } from '@oc/shared/chat'

const LAST_SID_KEY = 'oc_v2_last_sid'

const route = useRoute()
const router = useRouter()
const store = useChatStore()

const sid = computed<string>(() => {
  const fromRoute = (route.params.sid as string | undefined) ?? ''
  return fromRoute
})

const hydratedFor = ref<string | null>(null)

function readLastSid(): string | null {
  try {
    return typeof localStorage !== 'undefined' ? localStorage.getItem(LAST_SID_KEY) : null
  } catch { return null }
}
function writeLastSid(id: string): void {
  try {
    if (typeof localStorage !== 'undefined') localStorage.setItem(LAST_SID_KEY, id)
  } catch { /* quota / disabled */ }
}

// Resume on `/` only — never auto-redirect once user lands on /c/:sid.
watch(
  () => route.name,
  (name) => {
    if (name !== 'chat-root') return
    const last = readLastSid()
    if (last) {
      router.replace({ name: 'chat', params: { sid: last } }).catch(() => {})
    }
  },
  { immediate: true },
)

// Hydrate messages from server when we land on a sid we haven't loaded yet.
async function hydrate(targetSid: string): Promise<void> {
  if (!targetSid) return
  if (hydratedFor.value === targetSid) return
  hydratedFor.value = targetSid

  // Already have messages in memory (e.g. just sent) — skip the round-trip.
  const existing = store.messages.get(targetSid)
  if (existing && existing.length > 0) return

  try {
    const doc = await fetchChat(targetSid)
    if (!doc) return // fresh chat
    // Normalize legacy {role, content} → ChatMessage shape used by v2.
    const normalized: ChatMessage[] = []
    for (const raw of doc.messages as unknown as Array<Record<string, unknown>>) {
      if (!raw || typeof raw !== 'object') continue
      const role = raw.role as ChatMessage['role'] | undefined
      if (role !== 'user' && role !== 'assistant' && role !== 'system' && role !== 'tool') {
        continue
      }
      let text = ''
      if (typeof raw.text === 'string') text = raw.text
      else if (typeof raw.content === 'string') text = raw.content
      else if (Array.isArray(raw.content)) {
        for (const part of raw.content) {
          if (part && typeof part === 'object' && 'text' in part) {
            const t = (part as { text?: unknown }).text
            if (typeof t === 'string' && t) { text += t }
          }
        }
      }
      const id = (typeof raw.id === 'string' && raw.id) || `m_${normalized.length}_${Math.random().toString(36).slice(2, 8)}`
      const createdAt = typeof raw.createdAt === 'number' ? raw.createdAt : 0
      normalized.push({
        id,
        role,
        createdAt,
        content: [{ type: 'text', text }],
        text,
      })
    }
    // Only replace if we still match the expected sid (user may have navigated).
    if (sid.value === targetSid) {
      store.replaceMessages(targetSid, normalized)
    }
  } catch {
    // network blip → leave the surface empty; next interaction will retry
    // by re-mounting ChatPane.
  }
}

watch(
  sid,
  (id) => {
    if (!id) return
    writeLastSid(id)
    void hydrate(id)
  },
  { immediate: true },
)
</script>

<template>
  <ChatPane v-if="sid" :sid="sid" />
  <div v-else class="empty-pane">
    <div class="empty-card">
      <h2>开始一段新的对话</h2>
      <p>左侧选择历史对话，或点击「+ 新建 chat」。</p>
    </div>
  </div>
</template>

<style scoped>
.empty-pane {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg);
  height: 100%;
}
.empty-card {
  text-align: center;
  color: var(--text-sec);
}
.empty-card h2 {
  font-size: 18px;
  color: var(--text);
  margin: 0 0 6px;
}
.empty-card p {
  font-size: 13px;
  margin: 0;
}
</style>
