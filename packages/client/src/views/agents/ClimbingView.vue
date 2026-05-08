<script setup lang="ts">
// ClimbingView.vue — /v2/agents/climbing dashboard.
import { computed } from 'vue'
import { useClimbingData } from '@/composables/useClimbingData'
import DashboardPanel from '@/components/agents/DashboardPanel.vue'
import MetricGroup from '@/components/agents/MetricGroup.vue'
import KpiCard from '@/components/agents/KpiCard.vue'
import TimelineList from '@/components/agents/TimelineList.vue'

const { loading, data, error } = useClimbingData()

interface SessionRow {
  date: string
  title: string
  meta: string
}

// TimelineList wants generic item rows; massage the sessions into them.
const sessionRows = computed<SessionRow[]>(() => {
  if (!data.value) return []
  return data.value.sessions.map((s) => ({
    date: s.date,
    title: `${s.gym} · ${s.durationMin} 分钟`,
    meta: `${s.routes} 条路线 · 完成 ${s.maxSend} · 尝试 ${s.maxAttempt} · 完成率 ${(s.sendRate * 100).toFixed(0)}%`,
  }))
})

interface CardItem {
  key: 'bottleneck' | 'plan' | 'warmup'
  emoji: string
  title: string
}
const CARDS: CardItem[] = [
  { key: 'bottleneck', emoji: '🔍', title: '瓶颈分析' },
  { key: 'plan', emoji: '📅', title: '训练计划' },
  { key: 'warmup', emoji: '🤸', title: '热身 / 拉伸' },
]
</script>

<template>
  <div class="view">
    <header class="topbar">
      <RouterLink to="/agents" class="back">← Agent Hub</RouterLink>
      <h1>🧗 攀岩教练</h1>
      <span class="hint">stub 数据 · Phase E 接 /api/agents/fitness</span>
    </header>

    <div v-if="loading" class="state">加载中…</div>
    <div v-else-if="error" class="state err">加载失败：{{ error }}</div>

    <template v-else-if="data">
      <MetricGroup>
        <KpiCard label="本周训练" :value="`${data.weeklyCount} 次`" />
        <KpiCard label="最高级别" :value="data.topGrade" />
        <KpiCard label="红点路线" :value="data.redpointCount" />
        <KpiCard label="训练频次" :value="`${data.freqPerWeek} 次/周`" />
      </MetricGroup>

      <div class="cards">
        <DashboardPanel
          v-for="c in CARDS"
          :key="c.key"
          :title="`${c.emoji} ${c.title}`"
        >
          <template #actions>
            <button class="btn-stub" disabled>更新</button>
          </template>
          <pre class="md">{{ data[c.key] }}</pre>
        </DashboardPanel>
      </div>

      <DashboardPanel title="训练历史" :subtitle="`最近 ${data.sessions.length} 次`">
        <TimelineList
          :items="sessionRows"
          date-key="date"
          title-key="title"
          meta-key="meta"
        />
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

.cards { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; }
@media (max-width: 1024px) { .cards { grid-template-columns: 1fr; } }
.md {
  margin: 0;
  font-family: var(--font-mono);
  font-size: 12px;
  white-space: pre-wrap;
  color: var(--text);
  background: var(--bg);
  padding: 10px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
  line-height: 1.6;
}
.btn-stub {
  background: transparent;
  border: 1px solid var(--border);
  color: var(--text-sec);
  border-radius: var(--radius-sm);
  padding: 2px 8px;
  font-size: 11px;
  cursor: not-allowed;
  opacity: 0.6;
}
</style>
