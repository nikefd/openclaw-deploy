<script setup lang="ts">
// TasksView.vue — sub-agent task board.
// 4 KPI cards on top, filters, list, right-side detail drawer.
// Auto-refresh every 5s while mounted.
import { onMounted, ref } from 'vue'
import { useTasksData } from '@/composables/useTasksData'
import type { TaskFixture } from '@/fixtures/tasks'
import TaskFilters from '@/components/tasks/TaskFilters.vue'
import TaskList from '@/components/tasks/TaskList.vue'
import TaskDetailDrawer from '@/components/tasks/TaskDetailDrawer.vue'

const {
  filtered,
  counts,
  loading,
  lastUpdated,
  status,
  runtime,
  start,
} = useTasksData({ refreshMs: 5000 })

const selected = ref<TaskFixture | null>(null)

onMounted(() => {
  start()
})

function fmtMs(ms: number): string {
  if (ms <= 0) return '—'
  const sec = Math.floor(ms / 1000)
  if (sec < 60) return `${sec}s`
  const min = Math.floor(sec / 60)
  return `${min}m`
}

function fmtTime(ts: number | null): string {
  if (!ts) return '从未'
  const d = new Date(ts)
  const pad = (n: number) => (n < 10 ? `0${n}` : String(n))
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}
</script>

<template>
  <div class="tasks-view">
    <header class="page-head">
      <div>
        <h1>📋 任务看板</h1>
        <p class="sub">后台 sub-agent 状态、运行时长、token 消耗一目了然。</p>
      </div>
      <div class="refresh">
        <span :class="{ live: loading }">●</span>
        最近刷新 {{ fmtTime(lastUpdated) }}
      </div>
    </header>

    <section class="kpis">
      <div class="kpi"><div class="cap">运行中</div><div class="big">{{ counts.active }}</div></div>
      <div class="kpi"><div class="cap">今日完成</div><div class="big">{{ counts.doneToday }}</div></div>
      <div class="kpi"><div class="cap">失败</div><div class="big danger">{{ counts.failed }}</div></div>
      <div class="kpi"><div class="cap">平均运行</div><div class="big">{{ fmtMs(counts.avgRuntimeMs) }}</div></div>
    </section>

    <TaskFilters
      :status="status"
      :runtime="runtime"
      @update:status="status = $event"
      @update:runtime="runtime = $event"
    />

    <TaskList
      :tasks="filtered"
      :loading="loading"
      :selected-id="selected?.runId ?? null"
      @select="selected = $event"
    />

    <TaskDetailDrawer :task="selected" @close="selected = null" />
  </div>
</template>

<style scoped lang="scss">
.tasks-view {
  flex: 1;
  overflow-y: auto;
  padding: 24px clamp(16px, 4vw, 48px) 80px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  background: var(--bg);
  color: var(--text);
}
.page-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  flex-wrap: wrap;
  gap: 12px;
}
h1 { margin: 0; font-size: 20px; font-weight: 600; }
.sub { margin: 4px 0 0; color: var(--text-sec); font-size: 13px; }

.refresh {
  font-size: 12px;
  color: var(--text-sec);
  font-family: var(--font-mono);
  display: flex;
  align-items: center;
  gap: 6px;
}
.refresh span { color: var(--text-sec); transition: color 0.2s ease; }
.refresh span.live { color: var(--accent); animation: pulse 1.2s ease-in-out infinite; }
@keyframes pulse { 50% { opacity: 0.4; } }

.kpis {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}
.kpi {
  padding: 14px 16px;
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
}
.cap { font-size: 11px; color: var(--text-sec); text-transform: uppercase; letter-spacing: 0.08em; }
.big { font-size: 26px; font-weight: 700; margin-top: 4px; font-feature-settings: 'tnum'; }
.big.danger { color: var(--danger); }
</style>
