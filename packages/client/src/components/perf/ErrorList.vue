<script setup lang="ts">
// ErrorList.vue — recent error log entries.
import type { ErrorEntry } from '@/fixtures/perf'

defineProps<{ rows: ErrorEntry[] }>()

function fmtTime(ts: number): string {
  const d = new Date(ts)
  return `${String(d.getUTCHours()).padStart(2, '0')}:${String(d.getUTCMinutes()).padStart(2, '0')}:${String(d.getUTCSeconds()).padStart(2, '0')}`
}
</script>

<template>
  <div class="wrap">
    <div class="title">最近错误（{{ rows.length }}）</div>
    <ul class="list">
      <li v-for="(r, i) in rows" :key="i" class="item">
        <div class="row">
          <span class="ts">{{ fmtTime(r.ts) }}</span>
          <span class="status" :class="`s${Math.floor(r.status / 100)}`">{{ r.status }}</span>
          <span class="ep">{{ r.endpoint }}</span>
        </div>
        <div class="msg">{{ r.message }}</div>
      </li>
      <li v-if="!rows.length" class="empty">无错误，干杯 🍻</li>
    </ul>
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
.list { list-style: none; padding: 0; margin: 0; }
.item { padding: 6px 0; border-bottom: 1px solid var(--border); }
.item:last-child { border-bottom: none; }
.row { display: flex; gap: 8px; align-items: center; font-size: 11px; font-family: var(--font-mono); }
.ts { color: var(--text-sec); }
.status {
  border-radius: 3px;
  padding: 1px 6px;
  font-weight: 600;
  font-size: 10px;
}
.status.s5 { background: rgba(239, 68, 68, 0.18); color: #ef4444; }
.status.s4 { background: rgba(245, 158, 11, 0.18); color: #f59e0b; }
.status.s2, .status.s3 { background: rgba(16, 163, 127, 0.18); color: var(--accent); }
.ep { color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.msg { font-size: 12px; color: var(--text-sec); margin-top: 2px; padding-left: 4px; }
.empty { padding: 16px; text-align: center; color: var(--text-sec); }
</style>
