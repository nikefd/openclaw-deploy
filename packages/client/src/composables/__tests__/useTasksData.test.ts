import { describe, it, expect } from 'vitest'
import { filterTasks } from '@/composables/useTasksData'
import { STUB_TASKS, bucketRuntime } from '@/fixtures/tasks'

describe('useTasksData / filterTasks', () => {
  it('fixture loads with 20 tasks covering all statuses', () => {
    expect(STUB_TASKS).toHaveLength(20)
    const statuses = new Set(STUB_TASKS.map((t) => t.status))
    expect(statuses).toEqual(new Set(['running', 'done', 'failed', 'pending']))
  })

  it('returns all when both filters are "all"', () => {
    expect(filterTasks(STUB_TASKS, 'all', 'all')).toHaveLength(STUB_TASKS.length)
  })

  it('filters by status', () => {
    const running = filterTasks(STUB_TASKS, 'running', 'all')
    expect(running.length).toBeGreaterThan(0)
    expect(running.every((t) => t.status === 'running')).toBe(true)

    const failed = filterTasks(STUB_TASKS, 'failed', 'all')
    expect(failed.every((t) => t.status === 'failed')).toBe(true)
  })

  it('filters by runtime bucket', () => {
    const short = filterTasks(STUB_TASKS, 'all', 'short')
    expect(short.every((t) => bucketRuntime(t.durationMs) === 'short')).toBe(true)

    const long = filterTasks(STUB_TASKS, 'all', 'long')
    expect(long.every((t) => bucketRuntime(t.durationMs) === 'long')).toBe(true)
  })

  it('combines status + runtime', () => {
    const doneShort = filterTasks(STUB_TASKS, 'done', 'short')
    expect(doneShort.every((t) => t.status === 'done' && bucketRuntime(t.durationMs) === 'short')).toBe(true)
  })

  it('bucketRuntime boundaries', () => {
    expect(bucketRuntime(0)).toBe('short')
    expect(bucketRuntime(5 * 60_000)).toBe('short')
    expect(bucketRuntime(5 * 60_000 + 1)).toBe('medium')
    expect(bucketRuntime(30 * 60_000)).toBe('medium')
    expect(bucketRuntime(30 * 60_000 + 1)).toBe('long')
  })
})
