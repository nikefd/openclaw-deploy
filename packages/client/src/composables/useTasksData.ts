// composables/useTasksData.ts — fetch + filter + auto refresh.
// All filtering happens client-side over a stub list for now.
import { computed, onUnmounted, ref, type Ref } from 'vue'
import { fetchTasks } from '@/api/tasks'
import { bucketRuntime, type TaskFixture, type TaskRuntime, type TaskStatus } from '@/fixtures/tasks'

export type StatusFilter = TaskStatus | 'all'
export type RuntimeFilter = TaskRuntime | 'all'

export interface TasksFilterState {
  status: Ref<StatusFilter>
  runtime: Ref<RuntimeFilter>
}

export function filterTasks(
  tasks: readonly TaskFixture[],
  status: StatusFilter,
  runtime: RuntimeFilter,
): TaskFixture[] {
  return tasks.filter((t) => {
    if (status !== 'all' && t.status !== status) return false
    if (runtime !== 'all' && bucketRuntime(t.durationMs) !== runtime) return false
    return true
  })
}

export interface UseTasksDataOptions {
  /** auto-refresh interval in ms; 0 disables */
  refreshMs?: number
}

export function useTasksData(opts: UseTasksDataOptions = {}) {
  const refreshMs = opts.refreshMs ?? 5000
  const tasks = ref<TaskFixture[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const lastUpdated = ref<number | null>(null)

  const status = ref<StatusFilter>('all')
  const runtime = ref<RuntimeFilter>('all')

  const filtered = computed(() => filterTasks(tasks.value, status.value, runtime.value))

  const counts = computed(() => {
    const all = tasks.value
    const active = all.filter((t) => t.status === 'running').length
    const failed = all.filter((t) => t.status === 'failed').length
    const oneDayAgo = Date.now() - 24 * 60 * 60 * 1000
    const doneToday = all.filter((t) => t.status === 'done' && (t.endedAt ?? 0) >= oneDayAgo).length
    const doneRuntimes = all
      .filter((t) => t.status === 'done')
      .map((t) => t.durationMs)
    const avgRuntimeMs =
      doneRuntimes.length === 0
        ? 0
        : Math.round(doneRuntimes.reduce((a, b) => a + b, 0) / doneRuntimes.length)
    return { active, doneToday, failed, avgRuntimeMs, total: all.length }
  })

  async function reload(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      tasks.value = await fetchTasks()
      lastUpdated.value = Date.now()
    } catch (e) {
      error.value = e instanceof Error ? e.message : String(e)
    } finally {
      loading.value = false
    }
  }

  let timer: ReturnType<typeof setInterval> | null = null
  function start(): void {
    void reload()
    if (refreshMs > 0 && !timer) {
      timer = setInterval(() => {
        void reload()
      }, refreshMs)
    }
  }
  function stop(): void {
    if (timer) {
      clearInterval(timer)
      timer = null
    }
  }
  onUnmounted(stop)

  return {
    tasks,
    filtered,
    counts,
    loading,
    error,
    lastUpdated,
    status,
    runtime,
    reload,
    start,
    stop,
  }
}
