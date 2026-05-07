<script setup lang="ts">
// FileToolbar.vue — search box + disabled upload/new/refresh stubs.
import { ref, watch } from 'vue'

const props = defineProps<{ filter: string; refreshing?: boolean }>()
const emit = defineEmits<{
  (e: 'update:filter', v: string): void
  (e: 'refresh'): void
}>()

const local = ref(props.filter)
watch(() => props.filter, (v) => { local.value = v })
watch(local, (v) => emit('update:filter', v))
</script>

<template>
  <div class="toolbar">
    <input
      v-model="local"
      class="search"
      type="search"
      placeholder="搜索文件名…"
      aria-label="搜索文件"
    />
    <button class="btn" disabled title="Phase E">⬆ 上传</button>
    <button class="btn" disabled title="Phase E">＋ 新建</button>
    <button class="btn" :disabled="refreshing" title="刷新" @click="emit('refresh')">
      🔄 刷新
    </button>
  </div>
</template>

<style scoped lang="scss">
.toolbar {
  display: flex;
  gap: 8px;
  padding: 8px;
  border-bottom: 1px solid var(--border);
  align-items: center;
}
.search {
  flex: 1;
  background: var(--input-bg);
  color: var(--text);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 6px 10px;
  font-size: 13px;
  outline: none;
}
.search:focus { border-color: var(--accent); }
.btn {
  background: transparent;
  border: 1px solid var(--border);
  color: var(--text-sec);
  border-radius: var(--radius-sm);
  padding: 6px 10px;
  font-size: 12px;
  cursor: pointer;
}
.btn:hover:not(:disabled) { background: var(--hover); color: var(--text); }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
