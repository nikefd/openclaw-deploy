<script setup lang="ts">
// MemoryPanel.vue — Phase E3.1 sidebar memory list.
// Click → navigates to /memory/:path which renders in main content area.
import { onMounted } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { useMemory } from '@/composables/useMemory'

const route = useRoute()
const { topEntries, memoryEntries, loading, error, reload } = useMemory()

onMounted(() => { void reload() })

function fmtBytes(n: number): string {
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / 1024 / 1024).toFixed(1)} MB`
}

function fmtDate(ms: number): string {
  const d = new Date(ms)
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${m}-${day}`
}

function isActive(path: string): boolean {
  return route.params.path === path || (Array.isArray(route.params.path) && route.params.path.join('/') === path)
}
</script>

<template>
  <div class="memory-panel">
    <div class="header">
      <span class="title">📂 memory/</span>
      <button class="action" :disabled="loading" @click="reload">{{ loading ? '…' : '刷新' }}</button>
    </div>

    <div v-if="error" class="error">加载失败：{{ error }}</div>

    <div v-if="topEntries.length" class="group">
      <div class="group-title">身份 / 配置</div>
      <RouterLink
        v-for="e in topEntries"
        :key="e.path"
        :to="`/memory/${e.path}`"
        class="item"
        :class="{ active: isActive(e.path) }"
      >
        <div class="t">{{ e.name }}</div>
        <div class="p">{{ e.preview || '(空)' }}</div>
        <div class="meta">{{ fmtBytes(e.sizeBytes) }} · {{ fmtDate(e.mtime) }}</div>
      </RouterLink>
    </div>

    <div v-if="memoryEntries.length" class="group">
      <div class="group-title">每日笔记（{{ memoryEntries.length }}）</div>
      <RouterLink
        v-for="e in memoryEntries"
        :key="e.path"
        :to="`/memory/${e.path}`"
        class="item"
        :class="{ active: isActive(e.path) }"
      >
        <div class="t">{{ e.name }}</div>
        <div class="p">{{ e.preview || '(空)' }}</div>
        <div class="meta">{{ fmtBytes(e.sizeBytes) }} · {{ fmtDate(e.mtime) }}</div>
      </RouterLink>
    </div>

    <div v-if="!loading && !topEntries.length && !memoryEntries.length" class="empty">没有 memory 文件</div>
  </div>
</template>

<style scoped lang="scss">
.memory-panel { display: flex; flex-direction: column; flex: 1; padding: 8px; overflow-y: auto; }
.header { display: flex; align-items: center; padding: 6px 4px; font-size: 12px; color: var(--text-sec); }
.title { flex: 1; font-weight: 600; }
.action {
  background: transparent;
  color: var(--text-sec);
  border: 1px solid var(--border);
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  cursor: pointer;
}
.action[disabled] { opacity: 0.5; cursor: wait; }
.error { color: #d4504e; padding: 8px 4px; font-size: 12px; }

.group { display: flex; flex-direction: column; gap: 4px; margin-top: 8px; }
.group-title {
  font-size: 11px;
  text-transform: uppercase;
  color: var(--text-sec);
  letter-spacing: 0.04em;
  padding: 0 4px 4px;
}

.item {
  background: transparent;
  border: 1px solid transparent;
  border-radius: 6px;
  padding: 8px 10px;
  cursor: pointer;
  text-align: left;
  width: 100%;
  color: var(--sidebar-fg, var(--text));
  display: flex;
  flex-direction: column;
  gap: 2px;
  text-decoration: none;
}
.item:hover { background: var(--hover); border-color: var(--border); }
.item.active { background: var(--hover); border-color: var(--accent, #4c8bf5); }
.t { font-size: 13px; font-weight: 500; }
.p {
  font-size: 11px;
  color: var(--text-sec);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.meta { font-size: 10px; color: var(--text-sec); opacity: 0.8; margin-top: 2px; }
.empty { padding: 16px; text-align: center; color: var(--text-sec); font-size: 12px; }
</style>
