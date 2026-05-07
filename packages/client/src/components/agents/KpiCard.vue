<script setup lang="ts">
// KpiCard.vue — single big-number cell with delta + trend placeholder.
// Used in MetricGroup horizontal rows.
import { computed } from 'vue'

interface Props {
  label: string
  value: string | number
  delta?: number // positive/negative percent or amount; sign drives color
  deltaSuffix?: string // e.g. "%" or ""
  trend?: number[] // sparkline placeholder; not rendered yet
}

const props = withDefaults(defineProps<Props>(), {
  deltaSuffix: '%',
})

const deltaClass = computed(() => {
  if (props.delta === undefined || props.delta === 0) return 'flat'
  return props.delta > 0 ? 'pos' : 'neg'
})

const deltaText = computed(() => {
  if (props.delta === undefined) return ''
  const sign = props.delta > 0 ? '+' : ''
  return `${sign}${props.delta.toFixed(2)}${props.deltaSuffix}`
})

const trendBars = computed(() => props.trend ?? [3, 5, 4, 6, 5, 7, 6, 8])
const maxBar = computed(() => Math.max(1, ...trendBars.value))
</script>

<template>
  <div class="kpi">
    <div class="label">{{ label }}</div>
    <div class="value">{{ value }}</div>
    <div class="row">
      <span v-if="delta !== undefined" class="delta" :class="deltaClass">{{ deltaText }}</span>
      <div class="spark" aria-hidden="true">
        <span
          v-for="(b, i) in trendBars"
          :key="i"
          class="bar"
          :style="{ height: `${(b / maxBar) * 100}%` }"
        />
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.kpi {
  flex: 1;
  min-width: 140px;
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.label { font-size: 12px; color: var(--text-sec); }
.value { font-size: 22px; font-weight: 700; color: var(--text); font-variant-numeric: tabular-nums; }
.row { display: flex; align-items: flex-end; justify-content: space-between; margin-top: 4px; }
.delta {
  font-size: 12px;
  padding: 2px 6px;
  border-radius: 4px;
  font-variant-numeric: tabular-nums;
  &.pos { color: #10a37f; background: rgba(16, 163, 127, 0.12); }
  &.neg { color: #ef4444; background: rgba(239, 68, 68, 0.12); }
  &.flat { color: var(--text-sec); }
}
.spark {
  display: flex;
  align-items: flex-end;
  gap: 2px;
  height: 24px;
  width: 80px;
}
.bar {
  flex: 1;
  background: linear-gradient(to top, var(--accent), var(--accent-soft));
  border-radius: 1px;
  min-height: 2px;
}
</style>
