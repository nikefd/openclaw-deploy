<script setup lang="ts">
// TaskFilters.vue — chip rows for status + runtime. Pure UI; emits update:* so
// the parent (TasksView) can swap the composable's refs.
import type { RuntimeFilter, StatusFilter } from '@/composables/useTasksData'

defineProps<{
  status: StatusFilter
  runtime: RuntimeFilter
}>()

const emit = defineEmits<{
  (e: 'update:status', v: StatusFilter): void
  (e: 'update:runtime', v: RuntimeFilter): void
}>()

const STATUS: Array<{ value: StatusFilter; label: string }> = [
  { value: 'all', label: '全部' },
  { value: 'running', label: '运行中' },
  { value: 'done', label: '已完成' },
  { value: 'failed', label: '失败' },
  { value: 'pending', label: '待启动' },
]

const RUNTIME: Array<{ value: RuntimeFilter; label: string }> = [
  { value: 'all', label: '任意时长' },
  { value: 'short', label: '≤5min' },
  { value: 'medium', label: '≤30min' },
  { value: 'long', label: '>30min' },
]
</script>

<template>
  <div class="filters">
    <div class="row">
      <span class="label">状态</span>
      <button
        v-for="s in STATUS"
        :key="s.value"
        class="chip"
        :class="{ active: status === s.value }"
        @click="emit('update:status', s.value)"
      >
        {{ s.label }}
      </button>
    </div>
    <div class="row">
      <span class="label">时长</span>
      <button
        v-for="r in RUNTIME"
        :key="r.value"
        class="chip"
        :class="{ active: runtime === r.value }"
        @click="emit('update:runtime', r.value)"
      >
        {{ r.label }}
      </button>
    </div>
  </div>
</template>

<style scoped lang="scss">
.filters {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px 14px;
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
}
.row {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.label {
  font-size: 12px;
  color: var(--text-sec);
  width: 38px;
  flex-shrink: 0;
}
.chip {
  background: transparent;
  color: var(--text-sec);
  border: 1px solid var(--border);
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  cursor: pointer;
  transition: background 0.12s ease, color 0.12s ease, border-color 0.12s ease;
}
.chip:hover { background: var(--hover); color: var(--text); }
.chip.active {
  background: var(--accent-soft);
  color: var(--accent);
  border-color: var(--accent);
}
</style>
