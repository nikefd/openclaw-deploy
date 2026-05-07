<script setup lang="ts">
// PerfView.vue — /v2/perf. Filters → KPI overview → 24h chart → table + errors.
// Auto-refresh every 10s (stub). Selection state lives in usePerfData.
import { onMounted, onBeforeUnmount } from 'vue'
import { usePerfData } from '@/composables/usePerfData'
import PerfFilters from '@/components/perf/PerfFilters.vue'
import PerfOverview from '@/components/perf/PerfOverview.vue'
import LatencyChart from '@/components/perf/LatencyChart.vue'
import EndpointTable from '@/components/perf/EndpointTable.vue'
import ErrorList from '@/components/perf/ErrorList.vue'

const {
  data,
  errors,
  loading,
  error,
  window,
  pattern,
  refresh,
  setWindow,
  setPattern,
  startAutoRefresh,
  stopAutoRefresh,
} = usePerfData('24h')

onMounted(() => {
  void refresh()
  startAutoRefresh(10_000)
})
onBeforeUnmount(() => stopAutoRefresh())
</script>

<template>
  <div class="perf-view">
    <PerfFilters
      :window="window"
      :pattern="pattern"
      @update:window="setWindow"
      @update:pattern="setPattern"
    />

    <div v-if="error" class="err">⚠️ {{ error }}</div>

    <PerfOverview :summary="data?.summary ?? null" :loading="loading" />

    <LatencyChart :buckets="data?.latency ?? []" />

    <div class="bottom">
      <div class="endpoints"><EndpointTable :rows="data?.endpoints ?? []" /></div>
      <div class="errors"><ErrorList :rows="errors" /></div>
    </div>

    <div v-if="loading" class="hint">刷新中…</div>
  </div>
</template>

<style scoped lang="scss">
.perf-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg);
  color: var(--text);
  overflow: auto;
}
.err {
  padding: 10px 14px;
  color: var(--danger);
  font-size: 13px;
}
.bottom {
  display: grid;
  grid-template-columns: 6fr 4fr;
  gap: 12px;
  padding: 0 14px 14px;
}
@media (max-width: 900px) {
  .bottom { grid-template-columns: 1fr; }
}
.hint {
  position: fixed;
  bottom: 12px;
  right: 18px;
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  color: var(--text-sec);
  font-size: 11px;
  padding: 4px 8px;
  border-radius: 999px;
  pointer-events: none;
}
</style>
