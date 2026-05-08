/**
 * api/chats.test.ts — Phase E4. Verifies the projector + sort behavior of
 * fetchChatList(), the 404 handling of fetchChat(), and that the path
 * goes through /v2/api/chats.
 */
import { afterEach, describe, expect, it, vi } from 'vitest'
import { fetchChatList, fetchChat, deleteChat } from '@/api/chats'

const realFetch = globalThis.fetch
afterEach(() => { globalThis.fetch = realFetch; vi.restoreAllMocks() })

function mockJson(body: unknown, status = 200): typeof fetch {
  return vi.fn(async () =>
    new Response(JSON.stringify(body), {
      status,
      headers: { 'content-type': 'application/json' },
    }),
  ) as unknown as typeof fetch
}

describe('api/chats — fetchChatList', () => {
  it('projects raw chats to summaries, sorted newest-first', async () => {
    const calls: string[] = []
    globalThis.fetch = vi.fn(async (url: any) => {
      calls.push(String(url))
      return new Response(JSON.stringify([
        { id: 'a', title: 'older', createdAt: 1, updatedAt: 100, messages: [{ role: 'user', content: 'hi' }] },
        { id: 'b', title: 'newest', createdAt: 1, updatedAt: 999, messages: [{ role: 'assistant', text: 'world ' + 'x'.repeat(200) }] },
        { id: 'c', title: '', createdAt: 5, updatedAt: 50, messages: [] },
      ]), { status: 200, headers: { 'content-type': 'application/json' } })
    }) as unknown as typeof fetch

    const list = await fetchChatList()
    expect(list).toHaveLength(3)
    expect(list[0]!.id).toBe('b')
    expect(list[1]!.id).toBe('a')
    expect(list[2]!.id).toBe('c')
    expect(list[2]!.title).toBe('(无标题)')
    // preview should be truncated to ~80 chars + ellipsis
    expect(list[0]!.preview.length).toBeLessThanOrEqual(81)
    expect(list[0]!.preview.endsWith('…')).toBe(true)
    // hits /v2/api/chats
    expect(calls[0]).toMatch(/\/v2\/api\/chats(\?|$)/)
  })

  it('throws on HTTP error', async () => {
    globalThis.fetch = mockJson({ error: 'boom' }, 500)
    await expect(fetchChatList()).rejects.toThrow(/HTTP 500/)
  })

  it('throws when payload is not an array', async () => {
    globalThis.fetch = mockJson({ not: 'a list' })
    await expect(fetchChatList()).rejects.toThrow(/array/)
  })

  it('drops chats without an id', async () => {
    globalThis.fetch = mockJson([{ title: 'no id' }, { id: 'ok', title: 'k', updatedAt: 1 }])
    const list = await fetchChatList()
    expect(list).toHaveLength(1)
    expect(list[0]!.id).toBe('ok')
  })

  it('preview prefers last user/assistant text, skipping system/tool', async () => {
    globalThis.fetch = mockJson([
      {
        id: 'p',
        title: 't',
        updatedAt: 1,
        messages: [
          { role: 'user', text: 'real msg' },
          { role: 'tool', text: 'noisy tool note' },
          { role: 'system', content: '[已中断]' },
        ],
      },
    ])
    const [c] = await fetchChatList()
    expect(c!.preview).toBe('real msg')
  })
})

describe('api/chats — fetchChat', () => {
  it('returns a normalized record', async () => {
    globalThis.fetch = mockJson({
      id: 'x',
      title: 'hi',
      createdAt: 1,
      updatedAt: 2,
      messages: [{ role: 'user', content: 'a' }],
    })
    const doc = await fetchChat('x')
    expect(doc).not.toBeNull()
    expect(doc!.id).toBe('x')
    expect(doc!.messages).toHaveLength(1)
  })

  it('returns null on 404', async () => {
    globalThis.fetch = mockJson({ error: 'nf' }, 404)
    expect(await fetchChat('missing')).toBeNull()
  })

  it('throws on other errors', async () => {
    globalThis.fetch = mockJson({}, 500)
    await expect(fetchChat('x')).rejects.toThrow()
  })
})

describe('api/chats — deleteChat', () => {
  it('returns true on 200', async () => {
    globalThis.fetch = mockJson({ ok: true })
    expect(await deleteChat('x')).toBe(true)
  })
  it('returns false on network error', async () => {
    globalThis.fetch = vi.fn(async () => { throw new Error('net') }) as unknown as typeof fetch
    expect(await deleteChat('x')).toBe(false)
  })
})
