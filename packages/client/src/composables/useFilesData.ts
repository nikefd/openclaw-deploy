// composables/useFilesData.ts — Phase D3 stub-driven file tree + content loader.
import { ref, shallowRef, type Ref, type ShallowRef } from 'vue'
import { fetchFileTree, fetchFileContent, type FileContentResponse } from '@/api/files'
import type { FileNode } from '@/fixtures/files'

export interface UseFilesDataAPI {
  tree: ShallowRef<FileNode | null>
  treeLoading: Ref<boolean>
  treeError: Ref<string | null>
  loadTree: () => Promise<void>

  current: ShallowRef<FileContentResponse | null>
  contentLoading: Ref<boolean>
  contentError: Ref<string | null>
  loadContent: (path: string) => Promise<void>
}

export function useFilesData(): UseFilesDataAPI {
  const tree = shallowRef<FileNode | null>(null)
  const treeLoading = ref(false)
  const treeError = ref<string | null>(null)

  const current = shallowRef<FileContentResponse | null>(null)
  const contentLoading = ref(false)
  const contentError = ref<string | null>(null)

  async function loadTree(): Promise<void> {
    treeLoading.value = true
    treeError.value = null
    try {
      tree.value = await fetchFileTree()
    } catch (e) {
      treeError.value = e instanceof Error ? e.message : String(e)
    } finally {
      treeLoading.value = false
    }
  }

  async function loadContent(path: string): Promise<void> {
    contentLoading.value = true
    contentError.value = null
    try {
      current.value = await fetchFileContent(path)
    } catch (e) {
      contentError.value = e instanceof Error ? e.message : String(e)
    } finally {
      contentLoading.value = false
    }
  }

  return { tree, treeLoading, treeError, loadTree, current, contentLoading, contentError, loadContent }
}
