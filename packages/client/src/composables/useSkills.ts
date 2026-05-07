// composables/useSkills.ts — Phase E3 sidebar skills data wrapper.
import { ref, shallowRef, computed, type Ref, type ShallowRef, type ComputedRef } from 'vue'
import {
  fetchSkillsList,
  fetchSkillContent,
  type SkillEntry,
  type SkillFile,
  type SkillSource,
} from '@/api/skills'

export interface UseSkillsAPI {
  entries: ShallowRef<SkillEntry[]>
  userEntries: ComputedRef<SkillEntry[]>
  builtinEntries: ComputedRef<SkillEntry[]>
  loading: Ref<boolean>
  error: Ref<string | null>
  selected: Ref<{ name: string; source: SkillSource } | null>
  current: ShallowRef<SkillFile | null>
  contentLoading: Ref<boolean>
  contentError: Ref<string | null>
  reload: () => Promise<void>
  open: (name: string, source: SkillSource) => Promise<void>
  clearSelection: () => void
}

export function useSkills(): UseSkillsAPI {
  const entries = shallowRef<SkillEntry[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  const selected = ref<{ name: string; source: SkillSource } | null>(null)
  const current = shallowRef<SkillFile | null>(null)
  const contentLoading = ref(false)
  const contentError = ref<string | null>(null)

  const userEntries = computed(() => entries.value.filter((e) => e.source === 'user'))
  const builtinEntries = computed(() => entries.value.filter((e) => e.source === 'builtin'))

  async function reload(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      entries.value = await fetchSkillsList()
    } catch (e) {
      error.value = e instanceof Error ? e.message : String(e)
    } finally {
      loading.value = false
    }
  }

  async function open(name: string, source: SkillSource): Promise<void> {
    selected.value = { name, source }
    contentLoading.value = true
    contentError.value = null
    try {
      current.value = await fetchSkillContent(name, source)
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
    userEntries,
    builtinEntries,
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
