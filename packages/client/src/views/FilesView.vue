<script setup lang="ts">
// FilesView.vue — /v2/files. 320px tree on the left, flexible preview on the right.
// Selection persists across reloads via sessionStorage.
import { onMounted, ref, computed, watch } from 'vue'
import { useFilesData } from '@/composables/useFilesData'
import FileTree from '@/components/files/FileTree.vue'
import FilePreview from '@/components/files/FilePreview.vue'
import FileToolbar from '@/components/files/FileToolbar.vue'
import PathBreadcrumb from '@/components/files/PathBreadcrumb.vue'
import type { FileNode } from '@/fixtures/files'

const SEL_KEY = 'oc:v2:files:selected'

const {
  tree,
  treeLoading,
  treeError,
  loadTree,
  current,
  contentLoading,
  contentError,
  loadContent,
} = useFilesData()

const selected = ref<string | null>(null)
const filter = ref('')

function findNode(root: FileNode, path: string): FileNode | null {
  if (root.path === path) return root
  if (root.children) {
    for (const c of root.children) {
      const r = findNode(c, path)
      if (r) return r
    }
  }
  return null
}

function onSelect(path: string): void {
  selected.value = path
  try { sessionStorage.setItem(SEL_KEY, path) } catch { /* quota */ }
  void loadContent(path)
}

function onNavigate(path: string): void {
  // Breadcrumb click: select if it's a file, otherwise just clear preview.
  if (!tree.value) return
  const node = findNode(tree.value, path)
  if (node && node.kind === 'file') {
    onSelect(path)
  } else {
    selected.value = path
  }
}

function onRefresh(): void {
  void loadTree()
  if (selected.value) void loadContent(selected.value)
}

const breadcrumbPath = computed(() => selected.value ?? '/')

watch(tree, (t) => {
  if (!t) return
  const saved = (() => {
    try { return sessionStorage.getItem(SEL_KEY) } catch { return null }
  })()
  if (saved && findNode(t, saved)) {
    selected.value = saved
    void loadContent(saved)
  }
})

onMounted(() => {
  void loadTree()
})
</script>

<template>
  <div class="files-view">
    <FileToolbar v-model:filter="filter" :refreshing="treeLoading" @refresh="onRefresh" />
    <PathBreadcrumb :path="breadcrumbPath" @navigate="onNavigate" />
    <div class="body">
      <aside class="left">
        <FileTree
          :root="tree"
          :selected-path="selected"
          :filter="filter"
          :loading="treeLoading"
          :error="treeError"
          @select="onSelect"
        />
      </aside>
      <section class="right">
        <FilePreview :data="current" :loading="contentLoading" :error="contentError" />
      </section>
    </div>
  </div>
</template>

<style scoped lang="scss">
.files-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg);
  color: var(--text);
}
.body {
  flex: 1;
  display: flex;
  min-height: 0;
}
.left {
  width: 320px;
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  background: var(--bg-elevated);
}
.right {
  flex: 1;
  display: flex;
  min-width: 0;
}
</style>
