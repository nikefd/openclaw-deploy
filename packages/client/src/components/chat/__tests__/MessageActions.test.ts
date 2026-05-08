/**
 * MessageActions.test.ts — Phase E4 verifies the bubble-action row is
 * copy-only (no regenerate / delete) and that clicking writes to the
 * clipboard with a 1s "已复制" feedback.
 */
import { afterEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import MessageActions from '@/components/chat/MessageActions.vue'
import type { ChatMessage } from '@oc/shared/chat'

afterEach(() => { vi.restoreAllMocks(); vi.useRealTimers() })

function makeMessage(text: string): ChatMessage {
  return {
    id: 'm1',
    role: 'assistant',
    createdAt: 0,
    content: [{ type: 'text', text }],
    text,
  }
}

describe('MessageActions', () => {
  it('renders exactly one button (copy only)', () => {
    const w = mount(MessageActions, { props: { message: makeMessage('hi') } })
    expect(w.findAll('button')).toHaveLength(1)
    expect(w.text()).toContain('复制')
    expect(w.text()).not.toMatch(/regenerate|刷新|delete|删除/i)
  })

  it('copies message text and flips label to "已复制" for ~1s', async () => {
    vi.useFakeTimers()
    const writeText = vi.fn(async () => { /* ok */ })
    Object.assign(navigator, { clipboard: { writeText } })

    const w = mount(MessageActions, { props: { message: makeMessage('hello world') } })
    await w.find('button').trigger('click')
    await nextTick(); await nextTick()

    expect(writeText).toHaveBeenCalledWith('hello world')
    expect(w.text()).toContain('已复制')

    vi.advanceTimersByTime(1100)
    await nextTick()
    expect(w.text()).toContain('复制')
    expect(w.text()).not.toContain('已复制')
  })

  it('no-ops on empty text', async () => {
    const writeText = vi.fn(async () => { /* ok */ })
    Object.assign(navigator, { clipboard: { writeText } })
    const w = mount(MessageActions, { props: { message: makeMessage('') } })
    await w.find('button').trigger('click')
    expect(writeText).not.toHaveBeenCalled()
  })
})
