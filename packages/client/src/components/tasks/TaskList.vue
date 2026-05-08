<script setup lang="ts">
// TaskList.vue — virtualization not needed for stub data. Just stack rows.
import type { TaskFixture } from '@/fixtures/tasks'
import TaskRow from './TaskRow.vue'

defineProps<{
  tasks: readonly TaskFixture[]
  loading?: boolean
  selectedId?: string | null
}>()

defineEmits<{ (e: 'select', t: TaskFixture): void }>()
</script>

<template>
  <div class="list" :class="{ loading }">
    <div v-if="tasks.length === 0 && !loading" class="empty">没有匹配的任务</div>
    <TaskRow
      v-for="t in tasks"
      :key="t.runId"
      :task="t"
      :selected="t.runId === selectedId"
      @select="$emit('select', $event)"
    />
  </div>
</template>

<style scoped lang="scss">
.list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  transition: opacity 0.15s ease;
}
.list.loading { opacity: 0.6; }
.empty {
  text-align: center;
  padding: 40px 0;
  color: var(--text-sec);
  font-size: 13px;
}
</style>
