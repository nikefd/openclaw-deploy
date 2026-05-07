<script setup lang="ts">
// MemoryPanel.vue — Phase E3 sidebar memory list backed by /api/memory.
// Two groups: 6 fixed top-level identity files, and memory/*.md daily notes
// sorted newest-first. Click → drawer preview rendered through useMarkdown.
import { onMounted, ref, watch, nextTick } from 'vue'
import { useMemory } from '@/composables/useMemory'
import { useMarkdown } from '@/composables/useMarkdown'

const {
  topEntries,
  memoryEntries,
  loading,
  error,
  selected,
  current,
  contentLoading,
  contentError,
  reload,
  open,
  clearSelection,
} = useMemory()

const { render, attachCodeCopyButtons } = useMarkdown()
const previewBox = ref<HTMLElement | null>(null)

onMounted(() => { void reload() })

// Re-attach copy buttons whenever the markdown HTML changes.
watch(current, async () => {
  await nextTick()
  attachCodeCopyButtons(previewBox.value)
})

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
      <button
        v-for="e in topEntries"
        :key="e.path"
        class="item"
        :class="{ active: selected === e.path }"
        @click="open(e.path)"
      >
        <div class="t">{{ e.name }}</div>
        <div class="p">{{ e.preview || '(空)' }}</div>
        <div class="meta">{{ fmtBytes(e.sizeBytes) }} · {{ fmtDate(e.mtime) }}</div>
      </button>
    </div>

    <div v-if="memoryEntries.length" class="group">
      <div class="group-title">每日笔记（{{ memoryEntries.length }}）</div>
      <button
        v-for="e in memoryEntries"
        :key="e.path"
        class="item"
        :class="{ active: selected === e.path }"
        @click="open(e.path)"
      >
        <div class="t">{{ e.name }}</div>
        <div class="p">{{ e.preview || '(空)' }}</div>
        <div class="meta">{{ fmtBytes(e.sizeBytes) }} · {{ fmtDate(e.mtime) }}</div>
      </button>
    </div>

    <div v-if="!loading && !topEntries.length && !memoryEntries.length" class="empty">没有 memory 文件</div>

    <Transition name="drawer">
      <Teleport to="body">
        <div v-if="selected" class="oc-doc-overlay" @click.self="clearSelection">
          <div class="oc-doc-drawer">
            <div class="drawer-head">
              <span class="drawer-title">{{ selected }}</span>
              <button class="close" title="编辑（Phase F 实装）" disabled>✎</button>
              <button class="close" @click="clearSelection">×</button>
            </div>
            <div v-if="contentLoading" class="drawer-body empty">读取中…</div>
            <div v-else-if="contentError" class="drawer-body error">读取失败：{{ contentError }}</div>
            <div
              v-else-if="current"
              ref="previewBox"
              class="drawer-body markdown"
              v-html="render(current.content)"
            />
          </div>
        </div>
      </Teleport>
    </Transition>
  </div>
</template>

<style scoped lang="scss">
.memory-panel {
  display: flex;
  flex-direction: column;
  flex: 1;
  padding: 8px;
  overflow-y: auto;
  position: relative;
}
.header {
  display: flex;
  align-items: center;
  padding: 6px 4px;
  font-size: 12px;
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

.drawer {
  position: absolute;
  inset: 0;
  background: var(--bg, #fff);
  display: flex;
  flex-direction: column;
  z-index: 5;
}
.drawer-head {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 10px;
  border-bottom: 1px solid var(--border);
}
.drawer-title { flex: 1; font-size: 13px; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.close {
  background: transparent;
  color: var(--text);
  border: 1px solid var(--border);
  border-radius: 4px;
  width: 26px;
  height: 24px;
  cursor: pointer;
  font-size: 14px;
  line-height: 1;
}
.close[disabled] { opacity: 0.4; cursor: not-allowed; }
.drawer-body { padding: 10px 12px; overflow-y: auto; flex: 1; font-size: 13px; }
.drawer-body.markdown :deep(pre) { background: var(--bg-elevated, #f5f5f5); padding: 8px; border-radius: 4px; overflow-x: auto; }
.drawer-body.markdown :deep(code) { font-family: ui-monospace, SFMono-Regular, monospace; font-size: 12px; }
.drawer-body.markdown :deep(h1), .drawer-body.markdown :deep(h2), .drawer-body.markdown :deep(h3) { margin-top: 12px; }

.drawer-enter-active, .drawer-leave-active { transition: transform 0.15s ease, opacity 0.15s ease; }
.drawer-enter-from, .drawer-leave-to { transform: translateX(8px); opacity: 0; }
</style>

<style lang="scss">
/* Unscoped — Teleport target is outside this component's DOM tree. */
.oc-doc-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  justify-content: flex-end;
  z-index: 1000;
}
.oc-doc-drawer {
  width: min(880px, 75vw);
  height: 100%;
  background: var(--bg, #1a1a1e);
  color: var(--text, #e4e4e7);
  border-left: 1px solid var(--border, #2a2a30);
  box-shadow: -8px 0 24px rgba(0, 0, 0, 0.35);
  display: flex;
  flex-direction: column;
  animation: oc-doc-slide 0.18s ease-out;
}
@keyframes oc-doc-slide {
  from { transform: translateX(20px); opacity: 0; }
  to { transform: translateX(0); opacity: 1; }
}
.oc-doc-drawer .drawer-head {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border, #2a2a30);
}
.oc-doc-drawer .drawer-title {
  flex: 1;
  font-size: 14px;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.oc-doc-drawer .close {
  background: transparent;
  color: var(--text, #e4e4e7);
  border: 1px solid var(--border, #2a2a30);
  border-radius: 4px;
  width: 30px;
  height: 28px;
  cursor: pointer;
  font-size: 16px;
  line-height: 1;
}
.oc-doc-drawer .close[disabled] { opacity: 0.4; cursor: not-allowed; }
.oc-doc-drawer .drawer-body {
  padding: 16px 20px;
  overflow-y: auto;
  flex: 1;
  font-size: 14px;
  line-height: 1.6;
}
.oc-doc-drawer .drawer-body.empty,
.oc-doc-drawer .drawer-body.error { text-align: center; color: var(--text-sec, #71717a); }
.oc-doc-drawer .drawer-body.markdown pre {
  background: var(--bg-elevated, #27272a);
  padding: 12px;
  border-radius: 6px;
  overflow-x: auto;
  font-size: 12.5px;
}
.oc-doc-drawer .drawer-body.markdown code {
  font-family: ui-monospace, SFMono-Regular, monospace;
}
.oc-doc-drawer .drawer-body.markdown h1,
.oc-doc-drawer .drawer-body.markdown h2,
.oc-doc-drawer .drawer-body.markdown h3 {
  margin-top: 16px;
  margin-bottom: 8px;
}
.oc-doc-drawer .drawer-body.markdown p { margin: 8px 0; }
.oc-doc-drawer .drawer-body.markdown ul,
.oc-doc-drawer .drawer-body.markdown ol { padding-left: 22px; }
</style>
