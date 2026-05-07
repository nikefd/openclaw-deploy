/**
 * useSseStream.test.ts — Phase E2b SSE parser & lifecycle.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { openSseStream } from '@/composables/useSseStream'

const realFetch = globalThis.fetch

afterEach(() => {
  globalThis.fetch = realFetch
  vi.restoreAllMocks()
  vi.useRealTimers()
})

/** Build a Response whose body emits the supplied chunks (UTF-8 strings). */
function streamResponse(chunks: string[], status = 200): Response {
  const enc = new TextEncoder()
  const body = new ReadableStream<Uint8Array>({
    async start(controller) {
      for (const c of chunks) {
        controller.enqueue(enc.encode(c))
        // Yield so the consumer can advance between frames.
        await Promise.resolve()
      }
      controller.close()
    },
  })
  return new Response(body, {
    status,
    headers: { 'content-type': 'text/event-stream' },
  })
}

describe('openSseStream — happy path', () => {
  it('accumulates choices[0].delta.content across frames', async () => {
    globalThis.fetch = vi.fn(async () =>
      streamResponse([
        'data: {"choices":[{"delta":{"content":"hel"}}]}\n\n',
        'data: {"choices":[{"delta":{"content":"lo"}}]}\n\n',
        'data: {"choices":[{"delta":{"content":" world"}}]}\n\n',
        'data: [DONE]\n\n',
      ]),
    ) as unknown as typeof fetch

    const deltas: string[] = []
    let doneCalled = false
    const errors: string[] = []
    const h = openSseStream(
      { sid: 's', messages: [{ role: 'user', content: 'hi' }] },
      {
        onDelta: (d) => deltas.push(d),
        onDone: () => { doneCalled = true },
        onError: (e) => errors.push(e.kind),
      },
    )
    await h.done
    expect(deltas.join('')).toBe('hello world')
    expect(doneCalled).toBe(true)
    expect(errors).toEqual([])
  })

  it('handles frames split across chunk boundaries', async () => {
    globalThis.fetch = vi.fn(async () =>
      streamResponse([
        'data: {"choices":[{"delta":{"con',
        'tent":"abc"}}]}\n\nda',
        'ta: {"choices":[{"delta":{"content":"de"}}]}\n\n',
        'data: [DONE]\n\n',
      ]),
    ) as unknown as typeof fetch

    const deltas: string[] = []
    const h = openSseStream(
      { sid: 's', messages: [] },
      { onDelta: (d) => deltas.push(d), onDone: () => {}, onError: () => {} },
    )
    await h.done
    expect(deltas.join('')).toBe('abcde')
  })

  it('treats stream end without [DONE] as success', async () => {
    globalThis.fetch = vi.fn(async () =>
      streamResponse([
        'data: {"choices":[{"delta":{"content":"x"}}]}\n\n',
      ]),
    ) as unknown as typeof fetch
    let done = false
    const errs: string[] = []
    const h = openSseStream(
      { sid: 's', messages: [] },
      { onDelta: () => {}, onDone: () => { done = true }, onError: (e) => errs.push(e.kind) },
    )
    await h.done
    expect(done).toBe(true)
    expect(errs).toEqual([])
  })

  it('silently skips malformed JSON frames', async () => {
    globalThis.fetch = vi.fn(async () =>
      streamResponse([
        'data: {not json}\n\n',
        'data: {"choices":[{"delta":{"content":"ok"}}]}\n\n',
        'data: [DONE]\n\n',
      ]),
    ) as unknown as typeof fetch
    const deltas: string[] = []
    const h = openSseStream(
      { sid: 's', messages: [] },
      { onDelta: (d) => deltas.push(d), onDone: () => {}, onError: () => {} },
    )
    await h.done
    expect(deltas.join('')).toBe('ok')
  })
})

describe('openSseStream — error paths', () => {
  it('reports network kind when fetch rejects', async () => {
    globalThis.fetch = vi.fn(async () => { throw new TypeError('offline') }) as unknown as typeof fetch
    let captured = ''
    const h = openSseStream(
      { sid: 's', messages: [] },
      { onDelta: () => {}, onDone: () => {}, onError: (e) => { captured = e.kind } },
    )
    await h.done
    expect(captured).toBe('network')
  })

  it('reports http kind on non-2xx', async () => {
    globalThis.fetch = vi.fn(async () => new Response('boom', { status: 502 })) as unknown as typeof fetch
    let kind = ''
    let status = 0
    const h = openSseStream(
      { sid: 's', messages: [] },
      { onDelta: () => {}, onDone: () => {}, onError: (e) => { kind = e.kind; status = e.status ?? 0 } },
    )
    await h.done
    expect(kind).toBe('http')
    expect(status).toBe(502)
  })

  it('aborts cleanly without infinite spin', async () => {
    // Stream that never closes — simulate hung gateway.
    globalThis.fetch = vi.fn(async () => {
      const body = new ReadableStream<Uint8Array>({
        start(c) {
          c.enqueue(new TextEncoder().encode('data: {"choices":[{"delta":{"content":"a"}}]}\n\n'))
          // Intentionally do not close.
        },
      })
      return new Response(body, { status: 200 })
    }) as unknown as typeof fetch

    let deltaSeen = false
    let kind = ''
    const h = openSseStream(
      { sid: 's', messages: [], chunkTimeoutMs: 0 },
      {
        onDelta: () => { deltaSeen = true },
        onDone: () => { kind = 'done' },
        onError: (e) => { kind = e.kind },
      },
    )
    // Wait for first chunk, then abort.
    await new Promise((r) => setTimeout(r, 10))
    h.abort()
    await h.done
    expect(deltaSeen).toBe(true)
    expect(kind).toBe('aborted')
  })

  it('times out when no chunks arrive within chunkTimeoutMs', async () => {
    vi.useFakeTimers()
    // Body that produces nothing for a long time.
    globalThis.fetch = vi.fn(async () => {
      const body = new ReadableStream<Uint8Array>({ start() { /* hang */ } })
      return new Response(body, { status: 200 })
    }) as unknown as typeof fetch

    let kind = ''
    const h = openSseStream(
      { sid: 's', messages: [], chunkTimeoutMs: 100 },
      { onDelta: () => {}, onDone: () => {}, onError: (e) => { kind = e.kind } },
    )
    await vi.advanceTimersByTimeAsync(150)
    // Reader.cancel() rejects pending read → finish() may race, give it a tick.
    vi.useRealTimers()
    await h.done
    expect(kind).toBe('timeout')
  })
})

describe('openSseStream — request shape', () => {
  it('POSTs JSON with stream:true, sid as user, and provided model', async () => {
    let captured: { url?: string; init?: RequestInit } = {}
    globalThis.fetch = vi.fn(async (url: any, init: any) => {
      captured = { url: String(url), init }
      return streamResponse(['data: [DONE]\n\n'])
    }) as unknown as typeof fetch

    const h = openSseStream(
      {
        sid: 'sid_123',
        messages: [{ role: 'user', content: 'hi' }],
        model: 'openclaw/opus',
        url: '/v2/api/copilot/stream',
      },
      { onDelta: () => {}, onDone: () => {}, onError: () => {} },
    )
    await h.done
    expect(captured.url).toBe('/v2/api/copilot/stream')
    expect(captured.init?.method).toBe('POST')
    const body = JSON.parse(captured.init?.body as string)
    expect(body.stream).toBe(true)
    expect(body.user).toBe('sid_123')
    expect(body.model).toBe('openclaw/opus')
    expect(body.messages).toEqual([{ role: 'user', content: 'hi' }])
  })
})
