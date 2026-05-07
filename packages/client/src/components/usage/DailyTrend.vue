<script setup lang="ts">
// DailyTrend.vue — CSS bar chart for 30-day usage.
// No chart lib; each bar's height % is computed against the max.
import { computed } from 'vue'
import type { DailyUsage } from '@/fixtures/usage'

const props = defineProps<{ days: readonly DailyUsage[] }>()

const max = computed(() => {
  let m = 0
  for (const d of props.days) {
    const t = d.tokensIn + d.tokensOut
    if (t > m) m = t
  }
  return m || 1
})

function pct(d: DailyUsage): number {
  return Math.max(2, ((d.tokensIn + d.tokensOut) / max.value) * 100)
}

function fmt(n: number): string {
  if (n < 1000) return String(n)
  if (n < 1_000_000) return `${(n / 1000).toFixed(0)}k`
  return `${(n / 1_000_000).toFixed(1)}M`
}
</script>

<template>
  <div class="trend">
    <header>
      <h3>30 天趋势</h3>
      <span class="hint">峰值 {{ fmt(max) }} tokens</span>
    </header>
    <div class="bars">
      <div
        v-for="d in days"
        :key="d.date"
        class="bar"
        :style="{ height: pct(d) + '%' }"
        :title="`${d.date}: ${fmt(d.tokensIn + d.tokensOut)} (${fmt(d.tokensIn)} in / ${fmt(d.tokensOut)} out)`"
      />
    </div>
    <footer>
      <span>{{ days[0]?.date ?? '—' }}</span>
      <span>{{ days[days.length - 1]?.date ?? '—' }}</span>
    </footer>
  </div>
</template>

<style scoped lang="scss">
.trend {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
header { display: flex; justify-content: space-between; align-items: baseline; }
header h3 { margin: 0; font-size: 13px; font-weight: 600; color: var(--text); }
.hint { font-size: 11px; color: var(--text-sec); font-family: var(--font-mono); }

.bars {
  display: flex;
  align-items: flex-end;
  gap: 3px;
  height: 140px;
}
.bar {
  flex: 1;
  background: linear-gradient(to top, var(--accent), #34d399);
  border-radius: 2px 2px 0 0;
  min-height: 2px;
  transition: opacity 0.12s ease, transform 0.12s ease;
  cursor: help;
}
.bar:hover { opacity: 0.85; transform: scaleY(1.02); }

footer {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: var(--text-sec);
  font-family: var(--font-mono);
}
</style>
