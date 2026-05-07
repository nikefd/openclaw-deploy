<script setup lang="ts">
// FileTreeNode.vue — single node in the recursive tree. Folders expand/collapse,
// files emit a select event.
import { computed, ref, watch } from 'vue'
import type { FileNode } from '@/fixtures/files'

const props = defineProps<{
  node: FileNode
  selectedPath: string | null
  filter: string
  depth?: number
  /** Force-open all folders that match (used during search). */
  forceOpen?: boolean
}>()

const emit = defineEmits<{
  (e: 'select', path: string): void
}>()

const open = ref(props.depth === 0)

watch(
  () => props.forceOpen,
  (v) => { if (v) open.value = true },
)

const depth = computed(() => props.depth ?? 0)

const isMatch = computed(() => {
  if (!props.filter) return true
  return matches(props.node, props.filter.toLowerCase())
})

function matches(n: FileNode, q: string): boolean {
  if (n.name.toLowerCase().includes(q)) return true
  return !!n.children?.some((c) => matches(c, q))
}

function iconFor(n: FileNode): string {
  if (n.kind === 'folder') return open.value ? '📂' : '📁'
  const ext = (n.ext ?? '').toLowerCase()
  if (['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'].includes(ext)) return '🖼️'
  if (['mp3', 'wav', 'flac', 'ogg'].includes(ext)) return '🎵'
  if (['mp4', 'mov', 'mkv', 'webm'].includes(ext)) return '🎬'
  if (['zip', 'tar', 'gz', 'bin'].includes(ext)) return '📦'
  return '📄'
}

function fmtSize(b?: number): string {
  if (b == null) return ''
  if (b < 1024) return `${b}B`
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)}KB`
  return `${(b / 1024 / 1024).toFixed(1)}MB`
}

function onClick(): void {
  if (props.node.kind === 'folder') {
    open.value = !open.value
  } else {
    emit('select', props.node.path)
  }
}
</script>

<template>
  <div v-if="isMatch" class="node">
    <div
      class="row"
      :class="{ selected: selectedPath === node.path && node.kind === 'file' }"
      :style="{ paddingLeft: `${depth * 12 + 6}px` }"
      role="treeitem"
      :aria-expanded="node.kind === 'folder' ? open : undefined"
      tabindex="0"
      @click="onClick"
      @keydown.enter.prevent="onClick"
      @keydown.space.prevent="onClick"
    >
      <span v-if="node.kind === 'folder'" class="caret">{{ open ? '▼' : '▶' }}</span>
      <span v-else class="caret-pad" />
      <span class="ico">{{ iconFor(node) }}</span>
      <span class="name">{{ node.name === '/' ? '/' : node.name }}</span>
      <span v-if="node.kind === 'file'" class="size">{{ fmtSize(node.size) }}</span>
    </div>
    <div v-if="node.kind === 'folder' && open" class="children">
      <FileTreeNode
        v-for="child in node.children ?? []"
        :key="child.path"
        :node="child"
        :selected-path="selectedPath"
        :filter="filter"
        :depth="depth + 1"
        :force-open="!!filter"
        @select="(p) => emit('select', p)"
      />
    </div>
  </div>
</template>

<style scoped lang="scss">
.row {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px;
  font-size: 13px;
  cursor: pointer;
  user-select: none;
  border-radius: 4px;
  color: var(--text);
}
.row:hover { background: var(--hover); }
.row.selected { background: var(--accent-soft); color: var(--text); }
.caret { width: 10px; color: var(--text-sec); font-size: 10px; }
.caret-pad { width: 10px; }
.ico { width: 18px; text-align: center; }
.name { flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.size { color: var(--text-sec); font-size: 11px; }
</style>
