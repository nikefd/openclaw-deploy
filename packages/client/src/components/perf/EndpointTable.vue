<script setup lang="ts">
// EndpointTable.vue — sortable table over endpoint metrics. Default sort: p95 desc.
import { computed, ref } from 'vue'
import type { EndpointMetric } from '@/fixtures/perf'

const props = defineProps<{ rows: EndpointMetric[] }>()

type SortKey = 'endpoint' | 'count' | 'avg' | 'p50' | 'p95' | 'p99' | 'errors'

const sortKey = ref<SortKey>('p95')
const sortDir = ref<'asc' | 'desc'>('desc')

const sorted = computed<EndpointMetric[]>(() => {
  const list = [...props.rows]
  const k = sortKey.value
  const dir = sortDir.value === 'asc' ? 1 : -1
  list.sort((a, b) => {
    const av = a[k]
    const bv = b[k]
    if (typeof av === 'string' && typeof bv === 'string') return av.localeCompare(bv) * dir
    return (Number(av) - Number(bv)) * dir
  })
  return list
})

function sortBy(k: SortKey): void {
  if (sortKey.value === k) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortKey.value = k
    sortDir.value = k === 'endpoint' ? 'asc' : 'desc'
  }
}

function arrow(k: SortKey): string {
  if (sortKey.value !== k) return ''
  return sortDir.value === 'asc' ? ' ▲' : ' ▼'
}

defineExpose({ sortBy, sortKey, sortDir })
</script>

<template>
  <div class="wrap">
    <div class="title">Endpoints</div>
    <table class="tbl">
      <thead>
        <tr>
          <th class="left" @click="sortBy('endpoint')">Endpoint{{ arrow('endpoint') }}</th>
          <th @click="sortBy('count')">Count{{ arrow('count') }}</th>
          <th @click="sortBy('avg')">Avg{{ arrow('avg') }}</th>
          <th @click="sortBy('p50')">P50{{ arrow('p50') }}</th>
          <th @click="sortBy('p95')">P95{{ arrow('p95') }}</th>
          <th @click="sortBy('p99')">P99{{ arrow('p99') }}</th>
          <th @click="sortBy('errors')">Err{{ arrow('errors') }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="r in sorted" :key="r.endpoint">
          <td class="left ep">{{ r.endpoint }}</td>
          <td>{{ r.count.toLocaleString() }}</td>
          <td>{{ r.avg }}ms</td>
          <td>{{ r.p50 }}ms</td>
          <td>{{ r.p95 }}ms</td>
          <td>{{ r.p99 }}ms</td>
          <td :class="{ err: r.errors > 0 }">{{ r.errors }}</td>
        </tr>
        <tr v-if="!sorted.length"><td colspan="7" class="empty">无数据</td></tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped lang="scss">
.wrap {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 10px 12px;
  overflow: auto;
}
.title { font-size: 13px; font-weight: 600; margin-bottom: 8px; color: var(--text); }
.tbl {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}
th, td {
  padding: 6px 8px;
  text-align: right;
  border-bottom: 1px solid var(--border);
  white-space: nowrap;
}
th.left, td.left { text-align: left; }
th {
  cursor: pointer;
  color: var(--text-sec);
  font-weight: 500;
  user-select: none;
}
th:hover { color: var(--text); }
td.ep { font-family: var(--font-mono); font-size: 11px; }
td.err { color: var(--danger); font-weight: 600; }
.empty { text-align: center; color: var(--text-sec); padding: 16px; }
</style>
