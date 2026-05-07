<script setup lang="ts">
// FileTree.vue — wraps the recursive FileTreeNode root.
import type { FileNode } from '@/fixtures/files'
import FileTreeNode from './FileTreeNode.vue'

defineProps<{
  root: FileNode | null
  selectedPath: string | null
  filter: string
  loading?: boolean
  error?: string | null
}>()

const emit = defineEmits<{ (e: 'select', path: string): void }>()
</script>

<template>
  <div class="tree" role="tree">
    <div v-if="loading" class="status">加载中…</div>
    <div v-else-if="error" class="status err">⚠️ {{ error }}</div>
    <FileTreeNode
      v-else-if="root"
      :node="root"
      :selected-path="selectedPath"
      :filter="filter"
      :depth="0"
      @select="(p) => emit('select', p)"
    />
    <div v-else class="status">空</div>
  </div>
</template>

<style scoped lang="scss">
.tree {
  flex: 1;
  overflow-y: auto;
  padding: 4px 4px 12px;
}
.status {
  padding: 12px;
  font-size: 13px;
  color: var(--text-sec);
}
.status.err { color: var(--danger); }
</style>
