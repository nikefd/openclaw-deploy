<script setup lang="ts">
// ChatSearch.vue — modal Ctrl+K search overlay. Listens for the global
// hotkey (Ctrl/Cmd+K) and matches against title/preview with a tiny fuzzy
// scorer that good-enough until we wire a server-side index in Phase E.
import { computed, nextTick, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useSidebarStore } from '@/stores/sidebar'
import { useHotkeys } from '@/composables/useHotkeys'

const sidebar = useSidebarStore()
const { searchOpen, chatList } = storeToRefs(sidebar)
const router = useRouter()

const inputRef = ref<HTMLInputElement | null>(null)
const query = ref('')
const selected = ref(0)

useHotkeys([
  {
    key: 'k',
    mod: true,
    handler: () => {
      sidebar.openSearch()
    },
  },
  {
    key: 'Escape',
    handler: () => {
      if (searchOpen.value) sidebar.closeSearch()
    },
    preventDefault: false,
  },
])

watch(searchOpen, async (open) => {
  if (open) {
    query.value = ''
    selected.value = 0
    await nextTick()
    inputRef.value?.focus()
  }
})

function score(text: string, q: string): number {
  if (!q) return 1
  const t = text.toLowerCase()
  const ql = q.toLowerCase()
  if (t.includes(ql)) return 10 + (ql.length / Math.max(1, t.length))
  // very loose: chars in order
  let i = 0
  let last = -1
  let hits = 0
  for (const ch of ql) {
    const idx = t.indexOf(ch, last + 1)
    if (idx === -1) return 0
    if (last !== -1 && idx === last + 1) hits++
    last = idx
    i++
  }
  return 1 + hits
}

const results = computed(() => {
  const q = query.value.trim()
  if (!q) return chatList.value.slice(0, 20)
  return chatList.value
    .map((c) => ({
      chat: c,
      s: Math.max(score(c.title, q), score(c.preview, q) * 0.6),
    }))
    .filter((r) => r.s > 0)
    .sort((a, b) => b.s - a.s)
    .slice(0, 20)
    .map((r) => r.chat)
})

function pick(id: string) {
  sidebar.setActiveChatId(id)
  router.push(`/c/${id}`).catch(() => {})
  sidebar.closeSearch()
}

function onKeydown(ev: KeyboardEvent) {
  if (!searchOpen.value) return
  if (ev.key === 'ArrowDown') {
    selected.value = Math.min(selected.value + 1, results.value.length - 1)
    ev.preventDefault()
  } else if (ev.key === 'ArrowUp') {
    selected.value = Math.max(selected.value - 1, 0)
    ev.preventDefault()
  } else if (ev.key === 'Enter') {
    const r = results.value[selected.value]
    if (r) pick(r.id)
    ev.preventDefault()
  }
}

function onBackdrop() {
  sidebar.closeSearch()
}
</script>

<template>
  <Transition name="fade">
    <div v-if="searchOpen" class="search-overlay" @click="onBackdrop">
      <div class="search-modal" @click.stop @keydown="onKeydown">
        <input
          ref="inputRef"
          v-model="query"
          type="text"
          placeholder="搜索对话…  (Ctrl+K)"
          autocomplete="off"
        />
        <div class="results">
          <div
            v-for="(r, idx) in results"
            :key="r.id"
            class="result"
            :class="{ active: idx === selected }"
            @mouseenter="selected = idx"
            @click="pick(r.id)"
          >
            <div class="t">{{ r.agent?.emoji ?? '💬' }} {{ r.title }}</div>
            <div class="p">{{ r.preview }}</div>
          </div>
          <div v-if="results.length === 0" class="empty">没有匹配的对话</div>
        </div>
        <div class="hint">↑↓ 选择 · Enter 打开 · Esc 关闭</div>
      </div>
    </div>
  </Transition>
</template>

<style scoped lang="scss">
.search-overlay {
  position: fixed;
  inset: 0;
  background: var(--search-overlay-bg, rgba(0, 0, 0, 0.45));
  display: flex;
  justify-content: center;
  align-items: flex-start;
  padding-top: 12vh;
  z-index: 1000;
}
.search-modal {
  width: min(560px, 92vw);
  background: var(--popup-bg, var(--bg-elevated));
  border: 1px solid var(--popup-border, var(--border));
  border-radius: 12px;
  box-shadow: var(--popup-shadow, 0 20px 50px rgba(0, 0, 0, 0.4));
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
input {
  width: 100%;
  padding: 10px 12px;
  background: var(--input-bg);
  color: var(--text);
  border: 1px solid var(--border);
  border-radius: 8px;
  font-size: 14px;
  outline: none;
}
input:focus { border-color: var(--accent); }
.results {
  max-height: 360px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.result {
  padding: 8px 10px;
  border-radius: 6px;
  cursor: pointer;
}
.result.active, .result:hover {
  background: var(--hover);
}
.t { font-size: 13px; color: var(--text); }
.p { font-size: 11px; color: var(--text-sec); margin-top: 2px; }
.empty { padding: 16px; text-align: center; color: var(--text-sec); font-size: 12px; }
.hint { font-size: 10px; color: var(--text-sec); text-align: right; }

.fade-enter-active, .fade-leave-active { transition: opacity 0.12s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
