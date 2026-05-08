<script setup lang="ts">
// PerfFilters.vue — time window pills + endpoint pattern input.
import { ref, watch } from 'vue'
import type { TimeWindow } from '@/fixtures/perf'

const props = defineProps<{ window: TimeWindow; pattern: string }>()
const emit = defineEmits<{
  (e: 'update:window', w: TimeWindow): void
  (e: 'update:pattern', p: string): void
}>()

const WINDOWS: TimeWindow[] = ['1h', '6h', '24h', '7d']

const local = ref(props.pattern)
watch(() => props.pattern, (v) => { local.value = v })

let debounce: ReturnType<typeof setTimeout> | null = null
watch(local, (v) => {
  if (debounce) clearTimeout(debounce)
  debounce = setTimeout(() => emit('update:pattern', v), 200)
})
</script>

<template>
  <div class="filters">
    <div class="windows">
      <button
        v-for="w in WINDOWS"
        :key="w"
        class="pill"
        :class="{ active: window === w }"
        @click="emit('update:window', w)"
      >{{ w }}</button>
    </div>
    <input
      v-model="local"
      class="pattern"
      type="search"
      placeholder="筛选 endpoint…"
      aria-label="endpoint pattern"
    />
  </div>
</template>

<style scoped lang="scss">
.filters {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 10px 14px;
  border-bottom: 1px solid var(--border);
}
.windows { display: flex; gap: 4px; }
.pill {
  background: transparent;
  border: 1px solid var(--border);
  color: var(--text-sec);
  padding: 4px 10px;
  border-radius: 999px;
  cursor: pointer;
  font-size: 12px;
}
.pill:hover { background: var(--hover); color: var(--text); }
.pill.active { background: var(--accent); color: #fff; border-color: var(--accent); }
.pattern {
  flex: 1;
  max-width: 320px;
  background: var(--input-bg);
  color: var(--text);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 5px 10px;
  font-size: 12px;
  outline: none;
}
.pattern:focus { border-color: var(--accent); }
</style>
