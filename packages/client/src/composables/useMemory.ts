// composables/useMemory.ts — Phase E3 sidebar memory data wrapper.
import { ref, shallowRef, computed, type Ref, type ShallowRef, type ComputedRef } from 'vue'
import { fetchMemoryList, fetchMemoryFile, type MemoryEntry, type MemoryFile } from '@/api/memory'

export interface UseMemoryAPI {
  entries: ShallowRef<MemoryEntry[]>
  topEntries: ComputedRef<MemoryEntry[]>
  memoryEntries: ComputedRef<MemoryEntry[]>
  loading: Ref<boolean>
  error: Ref<string | null>
  selected: Ref<string | null>
  current: ShallowRef<MemoryFile | null>
  contentLoading: Ref<boolean>
  contentError: Ref<string | null>
  reload: () => Promise<void>
  open: (path: string) => Promise<void>
  clearSelection: () => void
}

export function useMemory(): UseMemoryAPI {
  const entries = shallowRef<MemoryEntry[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  const selected = ref<string | null>(null)
  const current = shallowRef<MemoryFile | null>(null)
  const contentLoading = ref(false)
  const contentError = ref<string | null>(null)

  // Top-level identity files appear in their fixed order; daily notes are
  // sorted newest-first, since that's what the user usually wants to see.
  const topEntries = computed(() => entries.value.filter((e) => e.group === 'top'))
  const memoryEntries = computed(() =>
    entries.value
      .filter((e) => e.group === 'memory')
      .slice()
      .sort((a, b) => b.mtime - a.mtime),
  )

  async function reload(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      entries.value = await fetchMemoryList()
    } catch (e) {
      error.value = e instanceof Error ? e.message : String(e)
    } finally {
      loading.value = false
    }
  }

  async function open(path: string): Promise<void> {
    selected.value = path
    contentLoading.value = true
    contentError.value = null
    try {
      current.value = await fetchMemoryFile(path)
    } catch (e) {
      contentError.value = e instanceof Error ? e.message : String(e)
      current.value = null
    } finally {
      contentLoading.value = false
    }
  }

  function clearSelection(): void {
    selected.value = null
    current.value = null
    contentError.value = null
  }

  return {
    entries,
    topEntries,
    memoryEntries,
    loading,
    error,
    selected,
    current,
    contentLoading,
    contentError,
    reload,
    open,
    clearSelection,
  }
}
