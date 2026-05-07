<script setup lang="ts">
// TaskRow.vue — single task line.
// Renders status badge with a class derived from `task.status` so the test
// can assert badge color mapping without inspecting computed styles.
import { computed } from 'vue'
import type { TaskFixture } from '@/fixtures/tasks'

const props = defineProps<{
  task: TaskFixture
  selected?: boolean
}>()

defineEmits<{ (e: 'select', t: TaskFixture): void }>()

const STATUS_LABEL: Record<TaskFixture['status'], string> = {
  running: '运行中',
  done: '完成',
  failed: '失败',
  pending: '待启动',
}

const badgeClass = computed(() => `badge badge-${props.task.status}`)

const totalTokens = computed(() => props.task.tokensIn + props.task.tokensOut)

const runtimeLabel = computed(() => {
  const ms = props.task.durationMs
  if (ms <= 0) return '—'
  const sec = Math.floor(ms / 1000)
  if (sec < 60) return `${sec}s`
  const min = Math.floor(sec / 60)
  if (min < 60) return `${min}m ${sec % 60}s`
  const hr = Math.floor(min / 60)
  return `${hr}h ${min % 60}m`
})

function fmtTokens(n: number): string {
  if (n < 1000) return String(n)
  if (n < 1_000_000) return `${(n / 1000).toFixed(1)}k`
  return `${(n / 1_000_000).toFixed(2)}M`
}
</script>

<template>
  <div class="row" :class="{ selected }" @click="$emit('select', task)">
    <div class="lbl">
      <span :class="badgeClass" data-testid="status-badge">{{ STATUS_LABEL[task.status] }}</span>
      <span class="title">{{ task.label }}</span>
    </div>
    <div class="meta">
      <span class="model" :title="task.model">{{ task.model }}</span>
      <span class="rt">⏱ {{ runtimeLabel }}</span>
      <span class="tk">🪙 {{ fmtTokens(totalTokens) }}</span>
    </div>
    <div class="actions" @click.stop>
      <button class="act" disabled title="kill (即将开放)">⛔</button>
      <button class="act" disabled title="log (即将开放)">📜</button>
      <button class="act" disabled title="steer (即将开放)">🎯</button>
    </div>
  </div>
</template>

<style scoped lang="scss">
.row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  gap: 12px;
  align-items: center;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-elevated);
  cursor: pointer;
  transition: background 0.1s ease, border-color 0.1s ease;
}
.row:hover { background: var(--hover); }
.row.selected { border-color: var(--accent); background: var(--accent-soft); }

.lbl {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}
.title {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: 13px;
  color: var(--text);
}

.badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  border: 1px solid transparent;
  white-space: nowrap;
}
.badge-running { background: rgba(59, 130, 246, 0.15); color: #60a5fa; border-color: rgba(96, 165, 250, 0.4); }
.badge-done    { background: rgba(16, 163, 127, 0.15); color: #10a37f; border-color: rgba(16, 163, 127, 0.4); }
.badge-failed  { background: rgba(239, 68, 68, 0.15); color: #ef4444; border-color: rgba(239, 68, 68, 0.4); }
.badge-pending { background: rgba(148, 163, 184, 0.18); color: #94a3b8; border-color: rgba(148, 163, 184, 0.4); }

.meta {
  display: flex;
  gap: 10px;
  font-size: 12px;
  color: var(--text-sec);
  white-space: nowrap;
}
.model { font-family: var(--font-mono); }

.actions { display: flex; gap: 4px; }
.act {
  background: transparent;
  border: 1px solid var(--border);
  color: var(--text-sec);
  border-radius: 6px;
  padding: 4px 6px;
  cursor: not-allowed;
  font-size: 13px;
  opacity: 0.55;
}
</style>
