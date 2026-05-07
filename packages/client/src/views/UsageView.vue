<script setup lang="ts">
// UsageView.vue — token + cost summary.
import { onMounted } from 'vue'
import { useUsageData, type UsageRange } from '@/composables/useUsageData'
import UsageOverview from '@/components/usage/UsageOverview.vue'
import DailyTrend from '@/components/usage/DailyTrend.vue'
import ModelBreakdown from '@/components/usage/ModelBreakdown.vue'
import CostEstimate from '@/components/usage/CostEstimate.vue'

const {
  loading,
  range,
  today,
  week,
  month,
  breakdown,
  rangeDays,
  models,
  reload,
} = useUsageData()

onMounted(() => {
  void reload()
})

const RANGES: Array<{ value: UsageRange; label: string; disabled?: boolean }> = [
  { value: 'today', label: '今日' },
  { value: 'week', label: '本周' },
  { value: 'month', label: '本月' },
  { value: 'custom', label: '自定义', disabled: true },
]
</script>

<template>
  <div class="usage-view">
    <header class="page-head">
      <div>
        <h1>💰 Token 用量</h1>
        <p class="sub">每天烧多少、每个模型贡献多少、估算成本一眼看穿。</p>
      </div>
      <div class="ranges">
        <button
          v-for="r in RANGES"
          :key="r.value"
          class="chip"
          :class="{ active: range === r.value, disabled: r.disabled }"
          :disabled="r.disabled"
          @click="!r.disabled && (range = r.value)"
        >
          {{ r.label }}
        </button>
      </div>
    </header>

    <UsageOverview :today="today" :week="week" :month="month" />

    <div class="grid">
      <DailyTrend :days="rangeDays" />
      <ModelBreakdown :models="models" :totals="breakdown" />
    </div>

    <CostEstimate :models="models" :totals="breakdown" />

    <div v-if="loading" class="loading">加载中…</div>
  </div>
</template>

<style scoped lang="scss">
.usage-view {
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

.ranges { display: flex; gap: 6px; }
.chip {
  background: transparent;
  border: 1px solid var(--border);
  color: var(--text-sec);
  border-radius: 999px;
  font-size: 12px;
  padding: 4px 12px;
  cursor: pointer;
}
.chip:hover:not(.disabled) { background: var(--hover); color: var(--text); }
.chip.active { background: var(--accent-soft); color: var(--accent); border-color: var(--accent); }
.chip.disabled { opacity: 0.4; cursor: not-allowed; }

.grid {
  display: grid;
  grid-template-columns: 1.4fr 1fr;
  gap: 12px;
}
@media (max-width: 800px) {
  .grid { grid-template-columns: 1fr; }
}

.loading {
  text-align: center;
  color: var(--text-sec);
  font-size: 12px;
}
</style>
