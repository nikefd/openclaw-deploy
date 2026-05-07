<script setup lang="ts">
// MemoryPanel.vue — surfaces MEMORY.md sections in the sidebar. Phase C2 uses
// stub data; Phase E will GET /api/memory/summary and add a real "整理" action
// that re-runs the curation prompt on the host.
import { onMounted, ref } from 'vue'
import { fetchMemorySummary, type MemorySection } from '@/api/memory'

const sections = ref<MemorySection[]>([])
const loading = ref(true)

onMounted(async () => {
  sections.value = await fetchMemorySummary()
  loading.value = false
})

function open(s: MemorySection) {
  // TODO Phase E: open the real section in a side drawer or main pane.
  console.info('[Phase E] open memory section', s.id)
  // Cheap toast — alert is loud but acceptable for the demo.
  flashToast(`「${s.title}」 — Phase E 实现`)
}

const toast = ref<string | null>(null)
let toastTimer: number | null = null
function flashToast(msg: string) {
  toast.value = msg
  if (toastTimer) window.clearTimeout(toastTimer)
  toastTimer = window.setTimeout(() => (toast.value = null), 1600)
}
</script>

<template>
  <div class="memory-panel">
    <div class="header">
      <span class="title">MEMORY.md（共 {{ sections.length }} 章节）</span>
      <button class="action" disabled title="Phase E 实现">整理</button>
    </div>
    <div v-if="loading" class="empty">加载中…</div>
    <div v-else class="list">
      <button
        v-for="s in sections"
        :key="s.id"
        class="item"
        @click="open(s)"
      >
        <div class="t">{{ s.title }}</div>
        <div class="p">{{ s.preview }}</div>
      </button>
    </div>
    <Transition name="toast">
      <div v-if="toast" class="toast">{{ toast }}</div>
    </Transition>
  </div>
</template>

<style scoped lang="scss">
.memory-panel { display: flex; flex-direction: column; flex: 1; padding: 8px; overflow-y: auto; position: relative; }
.header {
  display: flex;
  align-items: center;
  padding: 6px 4px;
  font-size: 11px;
  color: var(--text-sec);
}
.title { flex: 1; font-weight: 600; }
.action {
  background: transparent;
  color: var(--text-sec);
  border: 1px solid var(--border);
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  cursor: not-allowed;
  opacity: 0.6;
}
.list { display: flex; flex-direction: column; gap: 4px; margin-top: 4px; }
.item {
  background: transparent;
  border: 1px solid transparent;
  border-radius: 6px;
  padding: 8px 10px;
  cursor: pointer;
  text-align: left;
  width: 100%;
  color: var(--sidebar-fg, var(--text));
}
.item:hover { background: var(--hover); border-color: var(--border); }
.t { font-size: 13px; font-weight: 500; }
.p { font-size: 11px; color: var(--text-sec); margin-top: 2px; }
.empty { padding: 16px; text-align: center; color: var(--text-sec); font-size: 12px; }

.toast {
  position: absolute;
  bottom: 12px;
  left: 50%;
  transform: translateX(-50%);
  background: var(--popup-bg, var(--bg-elevated));
  color: var(--text);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 6px 12px;
  font-size: 12px;
  box-shadow: var(--popup-shadow, 0 6px 16px rgba(0, 0, 0, 0.3));
}
.toast-enter-active, .toast-leave-active { transition: opacity 0.15s, transform 0.15s; }
.toast-enter-from, .toast-leave-to { opacity: 0; transform: translate(-50%, 6px); }
</style>
