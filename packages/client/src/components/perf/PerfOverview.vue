<script setup lang="ts">
// PerfOverview.vue — 5 KPI cards in a row.
import { computed } from 'vue'
import type { PerfSummary } from '@/fixtures/perf'

const props = defineProps<{ summary: PerfSummary | null; loading: boolean }>()

interface KPI {
  label: string
  value: string
  trend: 'up' | 'down' | 'flat'
  /** for "errorRate" up=bad, for "totalRequests" up=good — controls color. */
  upIsGood: boolean
}

const kpis = computed<KPI[]>(() => {
  const s = props.summary
  if (!s) return []
  return [
    { label: '总请求数', value: fmtNum(s.totalRequests), trend: s.totalRequestsTrend, upIsGood: true },
    { label: '平均响应', value: `${s.avgMs}ms`, trend: s.avgMsTrend, upIsGood: false },
    { label: 'P95', value: `${s.p95Ms}ms`, trend: s.p95MsTrend, upIsGood: false },
    { label: 'P99', value: `${s.p99Ms}ms`, trend: s.p99MsTrend, upIsGood: false },
    { label: '错误率', value: `${(s.errorRate * 100).toFixed(2)}%`, trend: s.errorRateTrend, upIsGood: false },
  ]
})

function fmtNum(n: number): string {
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`
  return String(n)
}

function arrow(t: 'up' | 'down' | 'flat'): string {
  if (t === 'up') return '⬆'
  if (t === 'down') return '⬇'
  return '→'
}

function trendClass(k: KPI): string {
  if (k.trend === 'flat') return 'flat'
  const good = (k.trend === 'up') === k.upIsGood
  return good ? 'good' : 'bad'
}
</script>

<template>
  <div class="overview">
    <div v-for="k in kpis" :key="k.label" class="card">
      <div class="label">{{ k.label }}</div>
      <div class="value">
        {{ k.value }}
        <span class="trend" :class="trendClass(k)">{{ arrow(k.trend) }}</span>
      </div>
    </div>
    <div v-if="!summary && loading" class="card stub">加载中…</div>
  </div>
</template>

<style scoped lang="scss">
.overview {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 12px;
  padding: 14px;
}
.card {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 14px;
}
.label {
  font-size: 12px;
  color: var(--text-sec);
  margin-bottom: 6px;
}
.value {
  font-size: 22px;
  font-weight: 600;
  color: var(--text);
  display: flex;
  align-items: baseline;
  gap: 6px;
}
.trend { font-size: 14px; font-weight: 500; }
.trend.good { color: #22c55e; }
.trend.bad { color: var(--danger); }
.trend.flat { color: var(--text-sec); }
.card.stub { grid-column: 1 / -1; text-align: center; color: var(--text-sec); }

@media (max-width: 900px) {
  .overview { grid-template-columns: repeat(2, 1fr); }
}
</style>
