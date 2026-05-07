/**
 * legacy.test.ts — Phase E1 adapter coverage.
 *
 * Boots a tiny Express app that mounts createLegacyRouter() with a fake
 * fetch impl, then drives requests via supertest-style raw http (we already
 * use plain http elsewhere — keeps deps slim).
 */

import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import http from 'node:http'
import express from 'express'
import { promises as fsp } from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { createLegacyRouter } from '../legacy.js'

interface FakeUpstream {
  status: number
  body: string
  contentType?: string
  delayMs?: number
  reject?: Error
}

function fakeFetchFor(table: Record<string, FakeUpstream>): typeof fetch {
  return (async (url: string | URL, init?: RequestInit) => {
    const u = new URL(String(url))
    const key = `${u.protocol}//${u.host}${u.pathname}`
    const cfg = table[key]
    if (!cfg) {
      // Mimic ECONNREFUSED.
      throw new TypeError(`fetch failed: no fake for ${key}`)
    }
    if (cfg.reject) throw cfg.reject
    if (cfg.delayMs) {
      await new Promise<void>((resolve, reject) => {
        const t = setTimeout(resolve, cfg.delayMs)
        const signal = init?.signal as AbortSignal | undefined
        if (signal) {
          signal.addEventListener('abort', () => {
            clearTimeout(t)
            const err = new Error('aborted')
            err.name = 'AbortError'
            reject(err)
          })
        }
      })
    }
    return new Response(cfg.body, {
      status: cfg.status,
      headers: { 'content-type': cfg.contentType ?? 'application/json' },
    }) as unknown as Response
  }) as unknown as typeof fetch
}

function bootApp(fetchImpl: typeof fetch, opts?: { interviewFile?: string; timeoutMs?: number }) {
  const app = express()
  app.use(
    createLegacyRouter({
      fetchImpl,
      timeoutMs: opts?.timeoutMs,
      interviewScheduleFile: opts?.interviewFile,
    }),
  )
  const server = http.createServer(app)
  return new Promise<{ server: http.Server; url: string }>((resolve) => {
    server.listen(0, () => {
      const addr = server.address()
      if (!addr || typeof addr === 'string') throw new Error('no address')
      resolve({ server, url: `http://127.0.0.1:${addr.port}` })
    })
  })
}

async function getJson(url: string): Promise<{ status: number; body: unknown; raw: string }> {
  const res = await fetch(url)
  const raw = await res.text()
  let body: unknown
  try {
    body = JSON.parse(raw)
  } catch {
    body = raw
  }
  return { status: res.status, body, raw }
}

describe('legacy adapter — proxy success', () => {
  let server: http.Server
  let baseUrl: string
  beforeAll(async () => {
    const fakeFetch = fakeFetchFor({
      'http://127.0.0.1:7684/api/finance/dashboard': {
        status: 200,
        body: JSON.stringify({ netValue: 1234.5, ok: true }),
      },
    })
    const booted = await bootApp(fakeFetch)
    server = booted.server
    baseUrl = booted.url
  })
  afterAll(() => new Promise<void>((r) => server.close(() => r())))

  it('forwards 200 + body verbatim', async () => {
    const r = await getJson(`${baseUrl}/api/finance/dashboard`)
    expect(r.status).toBe(200)
    expect(r.body).toEqual({ netValue: 1234.5, ok: true })
  })
})

describe('legacy adapter — upstream 5xx → fallback', () => {
  let server: http.Server
  let baseUrl: string
  beforeAll(async () => {
    const fakeFetch = fakeFetchFor({
      'http://127.0.0.1:7684/api/finance/dashboard': {
        status: 500,
        body: 'boom',
        contentType: 'text/plain',
      },
    })
    const booted = await bootApp(fakeFetch)
    server = booted.server
    baseUrl = booted.url
  })
  afterAll(() => new Promise<void>((r) => server.close(() => r())))

  it('returns 503 with fallback:true', async () => {
    const r = await getJson(`${baseUrl}/api/finance/dashboard`)
    expect(r.status).toBe(503)
    expect(r.body).toMatchObject({ fallback: true })
  })
})

describe('legacy adapter — upstream timeout → fallback', () => {
  let server: http.Server
  let baseUrl: string
  beforeAll(async () => {
    const fakeFetch = fakeFetchFor({
      'http://127.0.0.1:7684/api/finance/dashboard': {
        status: 200,
        body: '{}',
        delayMs: 200,
      },
    })
    // Use a 50ms timeout so the test runs fast (not the production 5s).
    const booted = await bootApp(fakeFetch, { timeoutMs: 50 })
    server = booted.server
    baseUrl = booted.url
  })
  afterAll(() => new Promise<void>((r) => server.close(() => r())))

  it('aborts and returns 503 + fallback:true', async () => {
    const r = await getJson(`${baseUrl}/api/finance/dashboard`)
    expect(r.status).toBe(503)
    expect(r.body).toMatchObject({ error: 'upstream_timeout', fallback: true })
  })
})

describe('legacy adapter — placeholder routes always fall back', () => {
  let server: http.Server
  let baseUrl: string
  beforeAll(async () => {
    const booted = await bootApp(fakeFetchFor({}))
    server = booted.server
    baseUrl = booted.url
  })
  afterAll(() => new Promise<void>((r) => server.close(() => r())))

  it.each([
    '/api/ai-frontier/items',
    '/api/tasks/list',
    '/api/finance/holdings',
    '/api/finance/signals',
  ])('%s → 503 fallback', async (route) => {
    const r = await getJson(`${baseUrl}${route}`)
    expect(r.status).toBe(503)
    expect(r.body).toMatchObject({ fallback: true })
  })
})

describe('legacy adapter — interview schedule reads file', () => {
  let server: http.Server
  let baseUrl: string
  let tmpFile: string
  beforeAll(async () => {
    const tmpDir = await fsp.mkdtemp(path.join(os.tmpdir(), 'oc-e1-iv-'))
    tmpFile = path.join(tmpDir, 'iv.json')
    await fsp.writeFile(tmpFile, JSON.stringify({ items: ['ok'] }))
    const booted = await bootApp(fakeFetchFor({}), { interviewFile: tmpFile })
    server = booted.server
    baseUrl = booted.url
  })
  afterAll(() => new Promise<void>((r) => server.close(() => r())))

  it('serves the file', async () => {
    const r = await getJson(`${baseUrl}/api/interview/schedule`)
    expect(r.status).toBe(200)
    expect(r.body).toEqual({ items: ['ok'] })
  })

  it('falls back if the file is missing', async () => {
    // Re-mount with a bad path on a one-shot server.
    const booted = await bootApp(fakeFetchFor({}), {
      interviewFile: '/nonexistent/iv.json',
    })
    const r = await getJson(`${booted.url}/api/interview/schedule`)
    expect(r.status).toBe(503)
    expect(r.body).toMatchObject({ error: 'file_missing', fallback: true })
    await new Promise<void>((resolve) => booted.server.close(() => resolve()))
  })
})
