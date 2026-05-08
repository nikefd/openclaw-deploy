/**
 * chats.test.ts — Phase E2a chat persistence proxy.
 *
 * Boots a tiny Express app that mounts createChatsRouter() with a fake
 * fetch impl, then drives requests via real http. Mirrors the legacy.test
 * style.
 */

import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import http from 'node:http'
import express from 'express'
import { createChatsRouter } from '../chats.js'

interface Recorded {
  url: string
  method: string
  headers: Record<string, string>
  body?: string
}

function fakeFetch(
  table: Record<string, { status: number; body: string; contentType?: string }>,
  recorded: Recorded[],
): typeof fetch {
  return (async (input: string | URL, init?: RequestInit) => {
    const url = String(input)
    const u = new URL(url)
    const key = `${u.protocol}//${u.host}${u.pathname}`
    recorded.push({
      url,
      method: init?.method ?? 'GET',
      headers: (init?.headers as Record<string, string>) ?? {},
      body: typeof init?.body === 'string' ? init.body : undefined,
    })
    const cfg = table[key]
    if (!cfg) throw new TypeError(`no fake for ${key}`)
    return new Response(cfg.body, {
      status: cfg.status,
      headers: { 'content-type': cfg.contentType ?? 'application/json' },
    }) as unknown as Response
  }) as unknown as typeof fetch
}

async function bootApp(fetchImpl: typeof fetch): Promise<{ server: http.Server; baseUrl: string }> {
  const app = express()
  app.use(express.json({ limit: '2mb' }))
  app.use(createChatsRouter({ fetchImpl, upstreamBase: 'http://127.0.0.1:7682' }))
  const server = http.createServer(app)
  await new Promise<void>((r) => server.listen(0, r))
  const addr = server.address()
  if (!addr || typeof addr === 'string') throw new Error('no addr')
  return { server, baseUrl: `http://127.0.0.1:${addr.port}` }
}

async function fetchJson(url: string, init?: RequestInit) {
  const res = await fetch(url, init)
  const text = await res.text()
  let body: unknown
  try {
    body = JSON.parse(text)
  } catch {
    body = text
  }
  return { status: res.status, body, text }
}

describe('chats proxy — list + crud', () => {
  let server: http.Server
  let baseUrl: string
  let recorded: Recorded[]

  beforeAll(async () => {
    recorded = []
    const fakeUpstream = fakeFetch(
      {
        'http://127.0.0.1:7682/api/chats': {
          status: 200,
          body: JSON.stringify([{ id: 'chat_1', title: 'one' }]),
        },
        'http://127.0.0.1:7682/api/chats/chat_1': {
          status: 200,
          body: JSON.stringify({ id: 'chat_1', messages: [{ role: 'user', content: 'hi' }] }),
        },
      },
      recorded,
    )
    const booted = await bootApp(fakeUpstream)
    server = booted.server
    baseUrl = booted.baseUrl
  })

  afterAll(() => {
    server.close()
  })

  it('GET /api/chats forwards including query string', async () => {
    const res = await fetchJson(`${baseUrl}/api/chats?since=12345`)
    expect(res.status).toBe(200)
    expect(res.body).toEqual([{ id: 'chat_1', title: 'one' }])
    const last = recorded[recorded.length - 1]
    expect(last.url).toBe('http://127.0.0.1:7682/api/chats?since=12345')
    expect(last.method).toBe('GET')
  })

  it('GET /api/chats/:id forwards cookie header', async () => {
    const res = await fetchJson(`${baseUrl}/api/chats/chat_1`, {
      headers: { cookie: 'auth_token=abc' },
    })
    expect(res.status).toBe(200)
    const last = recorded[recorded.length - 1]
    expect(last.headers.cookie).toBe('auth_token=abc')
    expect(last.url).toBe('http://127.0.0.1:7682/api/chats/chat_1')
  })

  it('PUT /api/chats/:id forwards JSON body', async () => {
    const payload = { id: 'chat_1', messages: [{ role: 'user', content: 'edited' }] }
    const res = await fetchJson(`${baseUrl}/api/chats/chat_1`, {
      method: 'PUT',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(payload),
    })
    expect(res.status).toBe(200)
    const last = recorded[recorded.length - 1]
    expect(last.method).toBe('PUT')
    expect(last.body).toBe(JSON.stringify(payload))
    expect(last.headers['content-type']).toBe('application/json')
  })
})

describe('chats proxy — upstream errors', () => {
  it('502 when upstream is unreachable', async () => {
    const fetchImpl: typeof fetch = (async () => {
      throw new TypeError('fetch failed')
    }) as unknown as typeof fetch
    const { server, baseUrl } = await bootApp(fetchImpl)
    try {
      const res = await fetchJson(`${baseUrl}/api/chats/chat_x`)
      expect(res.status).toBe(502)
      expect(res.body).toMatchObject({ error: 'upstream_unreachable' })
    } finally {
      server.close()
    }
  })

  it('forwards non-2xx body verbatim (e.g. 404 from upstream)', async () => {
    const recorded: Recorded[] = []
    const fakeUpstream = fakeFetch(
      {
        'http://127.0.0.1:7682/api/chats/missing': {
          status: 404,
          body: '{"error":"not found"}',
        },
      },
      recorded,
    )
    const { server, baseUrl } = await bootApp(fakeUpstream)
    try {
      const res = await fetchJson(`${baseUrl}/api/chats/missing`)
      expect(res.status).toBe(404)
      expect(res.body).toEqual({ error: 'not found' })
    } finally {
      server.close()
    }
  })
})
