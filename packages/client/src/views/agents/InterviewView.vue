<script setup lang="ts">
// InterviewView.vue — /v2/agents/interview dashboard.
import { computed } from 'vue'
import { useInterviewData } from '@/composables/useInterviewData'
import DashboardPanel from '@/components/agents/DashboardPanel.vue'
import TimelineList from '@/components/agents/TimelineList.vue'
import type { CompanyStatus } from '@/api/interview'

const { loading, data, error } = useInterviewData()

interface SchedRow {
  date: string
  title: string
  subtitle: string
  meta: string
}

const scheduleRows = computed<SchedRow[]>(() => {
  if (!data.value) return []
  return data.value.schedule.map((s) => ({
    date: `${s.date}  ${s.time}`,
    title: `${s.company} — ${s.round}`,
    subtitle: `面试官：${s.interviewer}`,
    meta: `状态：${s.status}`,
  }))
})

function statusColor(s: CompanyStatus): string {
  switch (s) {
    case 'active': return 'green'
    case 'paused': return 'yellow'
    case 'rejected': return 'red'
    case 'offer': return 'blue'
  }
}
</script>

<template>
  <div class="view">
    <header class="topbar">
      <RouterLink to="/agents" class="back">← Agent Hub</RouterLink>
      <h1>💼 面试准备</h1>
      <span class="hint">stub 数据 · Phase E 接 /api/interview</span>
    </header>

    <div v-if="loading" class="state">加载中…</div>
    <div v-else-if="error" class="state err">加载失败：{{ error }}</div>

    <template v-else-if="data">
      <DashboardPanel title="本周日程" :subtitle="`${data.schedule.length} 场面试`">
        <TimelineList
          :items="scheduleRows"
          date-key="date"
          title-key="title"
          subtitle-key="subtitle"
          meta-key="meta"
        />
      </DashboardPanel>

      <DashboardPanel title="公司库" subtitle="状态 / 进度跟踪">
        <div class="company-grid">
          <div
            v-for="c in data.companies"
            :key="c.name"
            class="company-card"
            :class="['s-' + statusColor(c.status)]"
          >
            <div class="c-head">
              <span class="c-emoji">{{ c.emoji }}</span>
              <span class="c-name">{{ c.name }}</span>
              <span class="c-status">{{ c.status }}</span>
            </div>
            <div class="c-round">{{ c.round }}</div>
            <div class="c-meta">最近一次：{{ c.lastTouch }}</div>
            <div class="c-notes">{{ c.notes }}</div>
          </div>
        </div>
      </DashboardPanel>

      <DashboardPanel title="准备进度">
        <div class="progress-list">
          <div v-for="p in data.progress" :key="p.topic" class="prow">
            <div class="phead">
              <span class="ptopic">{{ p.topic }}</span>
              <span class="pcount">{{ p.done }} / {{ p.total }}</span>
            </div>
            <div class="bar"><div class="fill" :style="{ width: (p.done / p.total * 100) + '%' }" /></div>
            <div class="pnote">{{ p.note }}</div>
          </div>
        </div>
      </DashboardPanel>
    </template>
  </div>
</template>

<style scoped lang="scss">
.view {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px 24px 32px;
  background: var(--bg);
  color: var(--text);
  overflow-y: auto;
}
.topbar { display: flex; align-items: baseline; gap: 14px; }
.topbar h1 { margin: 0; font-size: 20px; }
.back { color: var(--text-sec); font-size: 13px; text-decoration: none; }
.back:hover { color: var(--accent); }
.hint { font-size: 11px; color: var(--text-sec); margin-left: auto; }
.state { padding: 24px; color: var(--text-sec); &.err { color: var(--danger); } }

.company-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 12px;
}
.company-card {
  background: var(--bg);
  border: 1px solid var(--border);
  border-left: 3px solid var(--text-sec);
  border-radius: var(--radius-md);
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  &.s-green { border-left-color: #10a37f; }
  &.s-yellow { border-left-color: #f0b429; }
  &.s-red { border-left-color: #ef4444; }
  &.s-blue { border-left-color: #2f6fed; }
}
.c-head { display: flex; align-items: center; gap: 8px; }
.c-emoji { font-size: 18px; }
.c-name { font-weight: 600; flex: 1; }
.c-status { font-size: 10px; color: var(--text-sec); text-transform: uppercase; }
.c-round { font-size: 13px; }
.c-meta { font-size: 11px; color: var(--text-sec); }
.c-notes { font-size: 12px; color: var(--text-sec); margin-top: 4px; font-style: italic; }

.progress-list { display: flex; flex-direction: column; gap: 14px; }
.prow { display: flex; flex-direction: column; gap: 4px; }
.phead { display: flex; justify-content: space-between; font-size: 13px; }
.ptopic { font-weight: 500; }
.pcount { color: var(--text-sec); font-variant-numeric: tabular-nums; }
.bar { height: 6px; background: var(--bg-elevated); border-radius: 3px; overflow: hidden; }
.fill { height: 100%; background: linear-gradient(to right, var(--accent), var(--accent-soft)); transition: width 0.3s ease; }
.pnote { font-size: 11px; color: var(--text-sec); }
</style>
