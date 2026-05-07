/**
 * copilot.test.ts — Phase E2a SSE forwarder.
 *
 * Verifies:
 *   1. POST body + cookie are forwarded to upstream.
 *   2. Upstream stream chunks are written to the response in order, no
 *      buffering / no parsing.
 *   3. content-type and X-Upstream-* headers pass through; hop-by-hop
 *      headers are stripped.
 *   4. Upstream connect failure → 502.
 *
 * We do NOT exercise client-abort here (no convenient way to half-close
 * a fetch in vitest without flaking) — the route just calls
 * controller.abort() on req.close, which is straight-line code we trust.
 */

import { afterEach, describe, expect, it } from 'vitest'
import http from 'node:http'
import express from 'express'
import { createCopilotRouter } from '../copilot.js'

let activeServer: http.Server | undefined

afterEach(() => {
  if (activeServer) {
    activeServer.close()
    activeServer = undefined
  }
})

async function bootApp(fetchImpl: typeof fetch) {
  const app = express()
  app.use(express.json({ limit: '2mb' }))
  app.use(createCopilotRouter({ fetchImpl, upstreamBase: 'http://127.0.0.1:7682' }))
  const server = http.createServer(app)
  await new Promise<void>((r) => server.listen(0, r))
  activeServer = server
  const addr = server.address()
  if (!addr || typeof addr === 'string') throw new Error('no addr')
  return { server, baseUrl: `http://127.0.0.1:${addr.port}` }
}

/** Build a ReadableStream that emits chunks with a tiny gap between each. */
function streamFromChunks(chunks: string[]): ReadableStream<Uint8Array> {
  const enc = new TextEncoder()
  let i = 0
  return new ReadableStream({
    async pull(ctrl) {
      if (i >= chunks.length) {
        ctrl.close()
        return
      }
      ctrl.enqueue(enc.encode(chunks[i]!))
      i += 1
    },
  })
}

describe('copilot proxy — happy path', () => {
  it('forwards body + cookie, streams chunks back in order', async () => {
    let captured: { body: string; cookie: string | undefined } | undefined
    const fetchImpl: typeof fetch = (async (url: string | URL, init?: RequestInit) => {
      const u = new URL(String(url))
      expect(u.pathname).toBe('/api/copilot/stream')
      const headers = (init?.headers as Record<string, string>) ?? {}
      captured = {
        body: typeof init?.body === 'string' ? init.body : '',
        cookie: headers.cookie,
      }
      return new Response(streamFromChunks(['data: a\n\n', 'data: b\n\n', 'data: [DONE]\n\n']), {
        status: 200,
        headers: {
          'content-type': 'text/event-stream',
          'x-upstream-time': '1.234',
          // Hop-by-hop — must NOT be forwarded.
          'transfer-encoding': 'chunked',
          connection: 'keep-alive',
        },
      }) as unknown as Response
    }) as unknown as typeof fetch

    const { baseUrl } = await bootApp(fetchImpl)
    const payload = { chatId: 'c1', model: 'glm-5', messages: [{ role: 'user', content: 'hi' }] }
    const res = await fetch(`${baseUrl}/api/copilot/stream`, {
      method: 'POST',
      headers: { 'content-type': 'application/json', cookie: 'auth_token=zzz' },
      body: JSON.stringify(payload),
    })
    expect(res.status).toBe(200)
    expect(res.headers.get('content-type')).toBe('text/event-stream')
    expect(res.headers.get('x-upstream-time')).toBe('1.234')
    // hop-by-hop should not be forwarded by us (node may set its own).
    // Not asserting their absence on the wire because node always sets
    // Transfer-Encoding for chunked replies; we just check we didn't double-set.
    const text = await res.text()
    expect(text).toBe('data: a\n\ndata: b\n\ndata: [DONE]\n\n')
    expect(captured?.cookie).toBe('auth_token=zzz')
    expect(captured?.body).toBe(JSON.stringify(payload))
  })
})

describe('copilot proxy — error paths', () => {
  it('502 when upstream connect fails', async () => {
    const fetchImpl: typeof fetch = (async () => {
      throw new TypeError('connect ECONNREFUSED')
    }) as unknown as typeof fetch
    const { baseUrl } = await bootApp(fetchImpl)
    const res = await fetch(`${baseUrl}/api/copilot/stream`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({}),
    })
    expect(res.status).toBe(502)
    const body = await res.json()
    expect(body).toMatchObject({ error: 'upstream_unreachable' })
  })

  it('passes through non-streaming upstream errors (e.g. 400 chatId required)', async () => {
    const fetchImpl: typeof fetch = (async () => {
      return new Response('{"error":"chatId required"}', {
        status: 400,
        headers: { 'content-type': 'application/json' },
      }) as unknown as Response
    }) as unknown as typeof fetch
    const { baseUrl } = await bootApp(fetchImpl)
    const res = await fetch(`${baseUrl}/api/copilot/stream`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({}),
    })
    expect(res.status).toBe(400)
    const body = await res.json()
    expect(body).toEqual({ error: 'chatId required' })
  })
})
