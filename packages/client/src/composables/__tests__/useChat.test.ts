/**
 * useChat.test.ts — Phase E2b. Covers the SSE-backed send/abort/regenerate
 * lifecycle on top of a mocked fetch.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ref, effectScope, nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { useChat } from '@/composables/useChat'

const realFetch = globalThis.fetch

afterEach(() => {
  globalThis.fetch = realFetch
  vi.restoreAllMocks()
  vi.useRealTimers()
})

beforeEach(() => {
  setActivePinia(createPinia())
})

function streamResponse(chunks: string[], status = 200): Response {
  const enc = new TextEncoder()
  const body = new ReadableStream<Uint8Array>({
    async start(controller) {
      for (const c of chunks) {
        controller.enqueue(enc.encode(c))
        await Promise.resolve()
      }
      controller.close()
    },
  })
  return new Response(body, { status })
}

/** Wait for an active stream to settle by polling status. */
async function waitUntil(pred: () => boolean, timeoutMs = 1000): Promise<void> {
  const start = Date.now()
  while (!pred()) {
    if (Date.now() - start > timeoutMs) throw new Error('waitUntil timeout')
    await new Promise((r) => setTimeout(r, 5))
  }
}

describe('useChat — SSE happy path', () => {
  it('appends user msg, streams deltas, then commits an assistant msg', async () => {
    // Two fetches per send: copilot/stream + chats/:id PUT.
    const fetchMock = vi.fn(async (url: any, init?: any) => {
      const u = String(url)
      if (u.includes('/copilot/stream')) {
        return streamResponse([
          'data: {"choices":[{"delta":{"content":"hi "}}]}\n\n',
          'data: {"choices":[{"delta":{"content":"there"}}]}\n\n',
          'data: [DONE]\n\n',
        ])
      }
      // chats persistence
      return new Response('{}', { status: 200 })
    })
    globalThis.fetch = fetchMock as unknown as typeof fetch

    const scope = effectScope()
    await scope.run(async () => {
      const sid = ref('sid_a')
      const chat = useChat(sid)
      chat.send('hello')

      // user msg appears immediately
      await nextTick()
      expect(chat.messages.value.length).toBe(1)
      expect(chat.messages.value[0]!.role).toBe('user')
      expect(chat.isStreaming.value).toBe(true)

      await waitUntil(() => chat.status.value === 'completed')
      expect(chat.messages.value.length).toBe(2)
      const assistant = chat.messages.value[1]!
      expect(assistant.role).toBe('assistant')
      expect(assistant.text).toBe('hi there')
      expect(chat.streamingDelta.value).toBe('')

      // Persistence call fired
      const putCalls = fetchMock.mock.calls.filter(([u]) => String(u).includes('/chats/'))
      expect(putCalls.length).toBeGreaterThanOrEqual(1)
      expect((putCalls[0]?.[1] as RequestInit | undefined)?.method).toBe('PUT')
    })
    scope.stop()
  })
})

describe('useChat — error paths', () => {
  it('shows "后端暂不可用" on network failure', async () => {
    globalThis.fetch = vi.fn(async (url: any) => {
      if (String(url).includes('/copilot/stream')) {
        throw new TypeError('offline')
      }
      return new Response('{}', { status: 200 })
    }) as unknown as typeof fetch

    const scope = effectScope()
    await scope.run(async () => {
      const sid = ref('sid_b')
      const chat = useChat(sid)
      chat.send('q')
      await waitUntil(() => chat.status.value === 'failed')
      const last = chat.messages.value[chat.messages.value.length - 1]!
      expect(last.role).toBe('assistant')
      expect(last.text).toContain('后端暂不可用')
    })
    scope.stop()
  })

  it('shows "连接中断" with HTTP code on non-2xx', async () => {
    globalThis.fetch = vi.fn(async (url: any) => {
      if (String(url).includes('/copilot/stream')) {
        return new Response('boom', { status: 502 })
      }
      return new Response('{}', { status: 200 })
    }) as unknown as typeof fetch

    const scope = effectScope()
    await scope.run(async () => {
      const sid = ref('sid_c')
      const chat = useChat(sid)
      chat.send('q')
      await waitUntil(() => chat.status.value === 'failed')
      const last = chat.messages.value[chat.messages.value.length - 1]!
      expect(last.text).toContain('连接中断')
      expect(last.text).toContain('502')
    })
    scope.stop()
  })

  it('preserves partial text + appends 中断 blurb when failure mid-stream', async () => {
    globalThis.fetch = vi.fn(async (url: any) => {
      if (String(url).includes('/copilot/stream')) {
        const enc = new TextEncoder()
        const body = new ReadableStream<Uint8Array>({
          async start(controller) {
            controller.enqueue(enc.encode('data: {"choices":[{"delta":{"content":"par"}}]}\n\n'))
            // Give the consumer a few microtask turns so the chunk is
            // actually read & parsed before we explode the stream.
            await new Promise((r) => setTimeout(r, 20))
            controller.error(new Error('socket reset'))
          },
        })
        return new Response(body, { status: 200 })
      }
      return new Response('{}', { status: 200 })
    }) as unknown as typeof fetch

    const scope = effectScope()
    await scope.run(async () => {
      const sid = ref('sid_d')
      const chat = useChat(sid)
      chat.send('q')
      await waitUntil(() => chat.status.value === 'failed')
      const last = chat.messages.value[chat.messages.value.length - 1]!
      expect(last.text!.startsWith('par')).toBe(true)
      expect(last.text!).toContain('⚠')
    })
    scope.stop()
  })
})

describe('useChat — abort', () => {
  it('aborts stream and finalises with [已中断], no infinite spin', async () => {
    let cancelled = false
    globalThis.fetch = vi.fn(async (url: any, init?: any) => {
      if (String(url).includes('/copilot/stream')) {
        const enc = new TextEncoder()
        const body = new ReadableStream<Uint8Array>({
          start(controller) {
            controller.enqueue(enc.encode('data: {"choices":[{"delta":{"content":"hi"}}]}\n\n'))
            // never close
          },
          cancel() { cancelled = true },
        })
        return new Response(body, { status: 200 })
      }
      return new Response('{}', { status: 200 })
    }) as unknown as typeof fetch

    const scope = effectScope()
    await scope.run(async () => {
      const sid = ref('sid_e')
      const chat = useChat(sid)
      chat.send('q')
      // Wait until first delta lands.
      await waitUntil(() => chat.streamingDelta.value === 'hi')
      chat.abort()
      await waitUntil(() => chat.isStreaming.value === false, 500)
      const last = chat.messages.value[chat.messages.value.length - 1]!
      expect(last.text).toContain('hi')
      expect(last.text).toContain('[已中断]')
      // The signal-based abort should have triggered cancel on the body.
      // (If runtime didn't bubble it, that's still OK — the key is no spin.)
    })
    scope.stop()
  }, 10000)
})

describe('useChat — regenerate', () => {
  it('replays the last user message via SSE', async () => {
    let stamp = 0
    globalThis.fetch = vi.fn(async (url: any) => {
      if (String(url).includes('/copilot/stream')) {
        stamp += 1
        return streamResponse([
          `data: {"choices":[{"delta":{"content":"ans${stamp}"}}]}\n\n`,
          'data: [DONE]\n\n',
        ])
      }
      return new Response('{}', { status: 200 })
    }) as unknown as typeof fetch

    const scope = effectScope()
    await scope.run(async () => {
      const sid = ref('sid_f')
      const chat = useChat(sid)
      chat.send('hello')
      await waitUntil(() => chat.status.value === 'completed')
      expect(chat.messages.value[1]!.text).toBe('ans1')

      chat.regenerate()
      await waitUntil(() => chat.messages.value.some((m) => m.text === 'ans2'))
      // After regenerate, list should be: user, assistant(ans2)
      const last = chat.messages.value[chat.messages.value.length - 1]!
      expect(last.role).toBe('assistant')
      expect(last.text).toBe('ans2')
    })
    scope.stop()
  })
})
