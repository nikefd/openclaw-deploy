<script setup lang="ts" generic="T">
// DataTable.vue — minimal sortable table. No external deps.
// Pass `columns` and `rows`; clicking a column header toggles asc/desc.
import { computed, ref } from 'vue'

export interface Column<U> {
  key: keyof U & string
  label: string
  align?: 'left' | 'right' | 'center'
  format?: (v: U[keyof U], row: U) => string
}

const props = defineProps<{
  columns: Column<T>[]
  rows: T[]
  initialSortKey?: keyof T & string
  initialSortDir?: 'asc' | 'desc'
}>()

const sortKey = ref<(keyof T & string) | null>(props.initialSortKey ?? null)
const sortDir = ref<'asc' | 'desc'>(props.initialSortDir ?? 'asc')

function toggle(col: Column<T>): void {
  if (sortKey.value === col.key) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortKey.value = col.key
    sortDir.value = 'asc'
  }
}

const sorted = computed<T[]>(() => {
  const k = sortKey.value
  if (!k) return props.rows
  const dir = sortDir.value === 'asc' ? 1 : -1
  return [...props.rows].sort((a, b) => {
    const va = (a as Record<string, unknown>)[k]
    const vb = (b as Record<string, unknown>)[k]
    if (typeof va === 'number' && typeof vb === 'number') return (va - vb) * dir
    return String(va ?? '').localeCompare(String(vb ?? '')) * dir
  })
})

function cell(row: T, col: Column<T>): string {
  const v = row[col.key as keyof T]
  if (col.format) return col.format(v, row)
  return String(v ?? '')
}
</script>

<template>
  <div class="table-wrap">
    <table class="data-table">
      <thead>
        <tr>
          <th
            v-for="col in columns"
            :key="col.key"
            :class="[col.align ?? 'left', { active: sortKey === col.key }]"
            @click="toggle(col)"
          >
            {{ col.label }}
            <span v-if="sortKey === col.key" class="arr">{{ sortDir === 'asc' ? '▲' : '▼' }}</span>
          </th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(row, i) in sorted" :key="i">
          <td v-for="col in columns" :key="col.key" :class="col.align ?? 'left'">
            {{ cell(row, col) }}
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped lang="scss">
.table-wrap { width: 100%; overflow-x: auto; }
.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
  font-variant-numeric: tabular-nums;
}
th, td {
  padding: 8px 10px;
  border-bottom: 1px solid var(--border);
}
th {
  background: var(--bg-elevated);
  color: var(--text-sec);
  font-weight: 500;
  cursor: pointer;
  user-select: none;
  white-space: nowrap;
  &:hover { color: var(--text); }
  &.active { color: var(--accent); }
}
.left { text-align: left; }
.right { text-align: right; }
.center { text-align: center; }
.arr { font-size: 10px; margin-left: 4px; }
tbody tr:hover { background: var(--hover); }
</style>
