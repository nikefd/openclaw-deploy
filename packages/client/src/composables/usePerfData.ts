// composables/usePerfData.ts — Phase D3 stub-driven perf metrics loader.
import { ref, shallowRef, onScopeDispose, type Ref, type ShallowRef } from 'vue'
import { fetchPerfErrors, fetchPerfSummary, type PerfSummaryResponse } from '@/api/perf'
import type { ErrorEntry, TimeWindow } from '@/fixtures/perf'

export interface UsePerfDataAPI {
  data: ShallowRef<PerfSummaryResponse | null>
  errors: ShallowRef<ErrorEntry[]>
  loading: Ref<boolean>
  error: Ref<string | null>
  window: Ref<TimeWindow>
  pattern: Ref<string>
  refresh: () => Promise<void>
  setWindow: (w: TimeWindow) => void
  setPattern: (p: string) => void
  startAutoRefresh: (ms?: number) => void
  stopAutoRefresh: () => void
}

export function usePerfData(initialWindow: TimeWindow = '24h'): UsePerfDataAPI {
  const data = shallowRef<PerfSummaryResponse | null>(null)
  const errors = shallowRef<ErrorEntry[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const window = ref<TimeWindow>(initialWindow)
  const pattern = ref('')

  let timer: ReturnType<typeof setInterval> | null = null

  async function refresh(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const [summary, errs] = await Promise.all([
        fetchPerfSummary(window.value),
        fetchPerfErrors(window.value, pattern.value),
      ])
      data.value = summary
      errors.value = errs
    } catch (e) {
      error.value = e instanceof Error ? e.message : String(e)
    } finally {
      loading.value = false
    }
  }

  function setWindow(w: TimeWindow): void {
    window.value = w
    void refresh()
  }
  function setPattern(p: string): void {
    pattern.value = p
    void refresh()
  }

  function startAutoRefresh(ms = 10_000): void {
    stopAutoRefresh()
    timer = setInterval(() => void refresh(), ms)
  }
  function stopAutoRefresh(): void {
    if (timer != null) {
      clearInterval(timer)
      timer = null
    }
  }

  onScopeDispose(() => stopAutoRefresh())

  return {
    data,
    errors,
    loading,
    error,
    window,
    pattern,
    refresh,
    setWindow,
    setPattern,
    startAutoRefresh,
    stopAutoRefresh,
  }
}
