/**
 * useChatList.test.ts — Phase E4 composable behavior over a mocked fetch.
 */
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useChatList } from '@/composables/useChatList'

const realFetch = globalThis.fetch
afterEach(() => { globalThis.fetch = realFetch; vi.restoreAllMocks() })

describe('useChatList', () => {
  it('reload populates chats and clears loading', async () => {
    globalThis.fetch = vi.fn(async () =>
      new Response(JSON.stringify([
        { id: 'a', title: 'A', updatedAt: 2, messages: [] },
        { id: 'b', title: 'B', updatedAt: 1, messages: [] },
      ]), { status: 200, headers: { 'content-type': 'application/json' } }),
    ) as unknown as typeof fetch

    const h = useChatList()
    expect(h.chats.value).toEqual([])
    expect(h.loading.value).toBe(false)

    const p = h.reload()
    expect(h.loading.value).toBe(true)
    await p

    expect(h.loading.value).toBe(false)
    expect(h.chats.value).toHaveLength(2)
    expect(h.chats.value[0]!.id).toBe('a') // newest first by updatedAt
    expect(h.error.value).toBeNull()
  })

  it('reload surfaces error and leaves chats untouched', async () => {
    globalThis.fetch = vi.fn(async () =>
      new Response('{}', { status: 500 }),
    ) as unknown as typeof fetch

    const h = useChatList()
    await h.reload()
    expect(h.error.value).toMatch(/HTTP 500/)
    expect(h.chats.value).toEqual([])
    expect(h.loading.value).toBe(false)
  })
})
