<script setup lang="ts">
// ModelBreakdown.vue — horizontal stacked bar by model.
import { computed } from 'vue'
import type { ModelPricing } from '@/fixtures/usage'

const props = defineProps<{
  models: readonly ModelPricing[]
  totals: ReadonlyArray<{ model: string; tokensIn: number; tokensOut: number }>
}>()

const grand = computed(() =>
  props.totals.reduce((acc, t) => acc + t.tokensIn + t.tokensOut, 0) || 1,
)

interface Slice {
  model: string
  total: number
  pct: number
  color: string
}

const slices = computed<Slice[]>(() =>
  props.totals
    .map((t) => {
      const pricing = props.models.find((m) => m.model === t.model)
      const total = t.tokensIn + t.tokensOut
      return {
        model: t.model,
        total,
        pct: (total / grand.value) * 100,
        color: pricing?.color ?? '#94a3b8',
      }
    })
    .sort((a, b) => b.total - a.total),
)

function fmt(n: number): string {
  if (n < 1000) return String(n)
  if (n < 1_000_000) return `${(n / 1000).toFixed(0)}k`
  return `${(n / 1_000_000).toFixed(2)}M`
}
</script>

<template>
  <div class="breakdown">
    <header>
      <h3>按模型分布</h3>
      <span class="hint">{{ fmt(grand) }} tokens 合计</span>
    </header>
    <div class="bar">
      <div
        v-for="s in slices"
        :key="s.model"
        class="seg"
        :style="{ width: s.pct + '%', background: s.color }"
        :title="`${s.model}: ${fmt(s.total)} (${s.pct.toFixed(1)}%)`"
      />
    </div>
    <ul class="legend">
      <li v-for="s in slices" :key="s.model">
        <span class="dot" :style="{ background: s.color }" />
        <code class="m">{{ s.model }}</code>
        <span class="t">{{ fmt(s.total) }}</span>
        <span class="p">{{ s.pct.toFixed(1) }}%</span>
      </li>
    </ul>
  </div>
</template>

<style scoped lang="scss">
.breakdown {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
header { display: flex; justify-content: space-between; align-items: baseline; }
header h3 { margin: 0; font-size: 13px; color: var(--text); font-weight: 600; }
.hint { font-size: 11px; color: var(--text-sec); font-family: var(--font-mono); }

.bar {
  display: flex;
  height: 22px;
  border-radius: 6px;
  overflow: hidden;
  background: var(--bg);
  border: 1px solid var(--border);
}
.seg { transition: opacity 0.12s ease; }
.seg:hover { opacity: 0.85; }

.legend {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.legend li {
  display: grid;
  grid-template-columns: 12px 1fr auto auto;
  gap: 10px;
  align-items: center;
  font-size: 12px;
}
.dot { width: 10px; height: 10px; border-radius: 3px; }
.m { color: var(--text); font-family: var(--font-mono); }
.t, .p { color: var(--text-sec); font-family: var(--font-mono); }
</style>
