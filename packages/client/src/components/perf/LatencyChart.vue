<script setup lang="ts">
// LatencyChart.vue — 24h latency trend rendered with CSS gradient bars.
import { computed } from 'vue'
import type { LatencyBucket } from '@/fixtures/perf'

const props = defineProps<{ buckets: LatencyBucket[] }>()

const maxP95 = computed(() => Math.max(1, ...props.buckets.map((b) => b.p95)))

function barHeight(v: number): string {
  return `${Math.max(2, (v / maxP95.value) * 100)}%`
}
</script>

<template>
  <div class="chart">
    <div class="head">
      <div class="title">24h 延迟趋势</div>
      <div class="legend">
        <span class="dot p50" /> P50
        <span class="dot p95" /> P95
      </div>
    </div>
    <div class="bars" role="img" aria-label="latency 24h">
      <div v-for="b in buckets" :key="b.hour" class="col" :title="`${b.label} · p50 ${b.p50}ms · p95 ${b.p95}ms`">
        <div class="bar p95" :style="{ height: barHeight(b.p95) }" />
        <div class="bar p50" :style="{ height: barHeight(b.p50) }" />
        <div class="lbl">{{ b.label.slice(0, 2) }}</div>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.chart {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  margin: 0 14px 14px;
  padding: 12px 14px;
}
.head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}
.title { font-size: 13px; font-weight: 600; color: var(--text); }
.legend { font-size: 11px; color: var(--text-sec); display: flex; align-items: center; gap: 8px; }
.legend .dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 2px;
  margin-right: 2px;
  margin-left: 8px;
}
.legend .dot.p50 { background: var(--accent); }
.legend .dot.p95 { background: linear-gradient(180deg, #f59e0b, #ef4444); }

.bars {
  display: flex;
  align-items: flex-end;
  gap: 4px;
  height: 140px;
  padding-top: 6px;
}
.col {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  align-items: center;
  height: 100%;
  position: relative;
}
.bar {
  width: 60%;
  border-radius: 2px 2px 0 0;
  position: absolute;
  bottom: 16px;
}
.bar.p95 {
  background: linear-gradient(180deg, #f59e0b, #ef4444);
  opacity: 0.55;
}
.bar.p50 {
  background: var(--accent);
}
.lbl {
  position: absolute;
  bottom: 0;
  font-size: 9px;
  color: var(--text-sec);
}
</style>
