import { apiUrl } from './_base'
// Phase E1 — tasks API. Upstream /api/tasks/list is NOT yet implemented
// (probed 2026-05-07 → 404). The v2 server registers a 503 placeholder, so
// we always fall back to the bundled fixture for now.

import { STUB_TASKS, type TaskFixture } from '@/fixtures/tasks'

export async function fetchTasks(): Promise<TaskFixture[]> {
  try {
    const r = await fetch(apiUrl('/tasks/list'), { credentials: 'include' })
    if (!r.ok) throw new Error(`http ${r.status}`)
    const body = await r.json()
    if (body && typeof body === 'object' && !Array.isArray(body) && 'fallback' in body && body.fallback) {
      return STUB_TASKS
    }
    if (Array.isArray(body)) return body as TaskFixture[]
    return STUB_TASKS
  } catch {
    return STUB_TASKS
  }
}

export type { TaskFixture, TaskStatus, TaskRuntime } from '@/fixtures/tasks'
