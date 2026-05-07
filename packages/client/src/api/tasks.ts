// api/tasks.ts — Phase D2 stub. Replace with real fetch('/api/tasks/list')
// once the agents-api / TaskFlow side ships an endpoint.
import { STUB_TASKS, type TaskFixture } from '@/fixtures/tasks'

export async function fetchTasks(): Promise<TaskFixture[]> {
  await new Promise((r) => setTimeout(r, 60))
  return STUB_TASKS
}

export type { TaskFixture, TaskStatus, TaskRuntime } from '@/fixtures/tasks'
