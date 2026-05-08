import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import TaskRow from '@/components/tasks/TaskRow.vue'
import type { TaskFixture, TaskStatus } from '@/fixtures/tasks'

function mkTask(status: TaskStatus): TaskFixture {
  return {
    runId: 'run_test',
    sessionKey: 'agent:opus:subagent:test',
    parent: null,
    label: 'test task',
    status,
    startedAt: Date.now() - 60_000,
    endedAt: status === 'running' || status === 'pending' ? null : Date.now(),
    durationMs: 60_000,
    tokensIn: 1000,
    tokensOut: 500,
    model: 'claude-opus-4.7',
    children: [],
    timeline: [],
  }
}

describe('TaskRow', () => {
  it('renders the task label', () => {
    const w = mount(TaskRow, { props: { task: mkTask('running') } })
    expect(w.text()).toContain('test task')
  })

  it.each<[TaskStatus, string, string]>([
    ['running', 'badge-running', '运行中'],
    ['done', 'badge-done', '完成'],
    ['failed', 'badge-failed', '失败'],
    ['pending', 'badge-pending', '待启动'],
  ])('status=%s applies class %s and label "%s"', (status, klass, label) => {
    const w = mount(TaskRow, { props: { task: mkTask(status) } })
    const badge = w.get('[data-testid="status-badge"]')
    expect(badge.classes()).toContain(klass)
    expect(badge.text()).toBe(label)
  })

  it('emits select on click', async () => {
    const task = mkTask('done')
    const w = mount(TaskRow, { props: { task } })
    await w.trigger('click')
    expect(w.emitted('select')?.[0]?.[0]).toMatchObject({ runId: 'run_test' })
  })

  it('action buttons are disabled placeholders', () => {
    const w = mount(TaskRow, { props: { task: mkTask('done') } })
    const btns = w.findAll('.act')
    expect(btns).toHaveLength(3)
    btns.forEach((b) => expect(b.attributes('disabled')).toBeDefined())
  })
})
