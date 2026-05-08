/**
 * memory.test.ts — Phase E3 verification for /api/memory.
 *
 * Three scenarios:
 *   1. list: returns top-level + memory/*.md from a synthetic root
 *   2. get:  path traversal (`../../etc/passwd` and friends) -> 403
 *   3. save: writing outside whitelist -> 403; legal write succeeds
 */

import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import http from 'node:http'
import { promises as fs } from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import express from 'express'

let tmpRoot: string
let server: http.Server
let baseUrl: string

beforeAll(async () => {
  tmpRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'oc-mem-'))
  // Seed: two top-level files and two memory/ daily notes.
  await fs.writeFile(path.join(tmpRoot, 'MEMORY.md'), '# memory root\n', 'utf8')
  await fs.writeFile(path.join(tmpRoot, 'SOUL.md'), 'soul contents'.repeat(50), 'utf8')
  await fs.mkdir(path.join(tmpRoot, 'memory'))
  await fs.writeFile(path.join(tmpRoot, 'memory', '2026-04-30.md'), 'apr 30', 'utf8')
  await fs.writeFile(path.join(tmpRoot, 'memory', '2026-05-01.md'), 'may 1', 'utf8')
  // Decoy file that must not appear (wrong ext).
  await fs.writeFile(path.join(tmpRoot, 'memory', 'index.json'), '{}', 'utf8')

  process.env.OC_MEMORY_ROOT = tmpRoot
  // Import after env is set.
  const { createMemoryRouter } = await import('../memory.js')

  const app = express()
  app.use(express.json({ limit: '2mb' }))
  app.use('/api/memory', createMemoryRouter())
  server = http.createServer(app)
  await new Promise<void>((r) => server.listen(0, r))
  const addr = server.address()
  if (!addr || typeof addr === 'string') throw new Error('no addr')
  baseUrl = `http://127.0.0.1:${addr.port}`
})

afterAll(async () => {
  await new Promise<void>((r) => server.close(() => r()))
  await fs.rm(tmpRoot, { recursive: true, force: true })
})

async function getJson(p: string): Promise<{ status: number; body: unknown }> {
  const r = await fetch(baseUrl + p)
  const text = await r.text()
  let body: unknown = text
  try { body = JSON.parse(text) } catch { /* keep raw */ }
  return { status: r.status, body }
}

async function postJson(p: string, payload: unknown): Promise<{ status: number; body: unknown }> {
  const r = await fetch(baseUrl + p, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(payload),
  })
  const text = await r.text()
  let body: unknown = text
  try { body = JSON.parse(text) } catch { /* keep raw */ }
  return { status: r.status, body }
}

describe('memory routes', () => {
  it('GET /list returns real files (top + memory/), drops non-md', async () => {
    const { status, body } = await getJson('/api/memory/list')
    expect(status).toBe(200)
    const b = body as { entries: Array<{ path: string; group: string }> }
    const paths = b.entries.map((e) => e.path).sort()
    expect(paths).toContain('MEMORY.md')
    expect(paths).toContain('SOUL.md')
    expect(paths).toContain('memory/2026-04-30.md')
    expect(paths).toContain('memory/2026-05-01.md')
    // index.json must not show up.
    expect(paths).not.toContain('memory/index.json')
    // Groups are correctly assigned.
    const top = b.entries.find((e) => e.path === 'MEMORY.md')!
    expect(top.group).toBe('top')
    const day = b.entries.find((e) => e.path === 'memory/2026-04-30.md')!
    expect(day.group).toBe('memory')
  })

  it('GET /get rejects path traversal with 403', async () => {
    for (const evil of [
      '../../etc/passwd',
      '../etc/passwd',
      '/etc/passwd',
      'memory/../../etc/passwd',
      'memory/../SOUL.md', // would resolve back inside but uses '..'
      'memory/sub/nested.md', // disallowed nesting
      'README.md', // not in whitelist
      '', // empty
    ]) {
      const { status } = await getJson('/api/memory/get?path=' + encodeURIComponent(evil))
      expect(status, `expected 403 for ${evil}`).toBe(403)
    }
    // sanity: a legit one returns 200
    const ok = await getJson('/api/memory/get?path=' + encodeURIComponent('memory/2026-04-30.md'))
    expect(ok.status).toBe(200)
    expect((ok.body as { content: string }).content).toBe('apr 30')
  })

  it('POST /save rejects out-of-whitelist; accepts a legit write', async () => {
    const evil = await postJson('/api/memory/save', {
      path: '../escape.md',
      content: 'nope',
    })
    expect(evil.status).toBe(403)

    const evil2 = await postJson('/api/memory/save', {
      path: '/etc/oc-pwn.md',
      content: 'nope',
    })
    expect(evil2.status).toBe(403)

    const evil3 = await postJson('/api/memory/save', {
      path: 'memory/sub/x.md',
      content: 'nope',
    })
    expect(evil3.status).toBe(403)

    const ok = await postJson('/api/memory/save', {
      path: 'memory/2026-05-01.md',
      content: 'updated by test',
    })
    expect(ok.status).toBe(200)
    const written = await fs.readFile(path.join(tmpRoot, 'memory', '2026-05-01.md'), 'utf8')
    expect(written).toBe('updated by test')

    // Size cap.
    const huge = 'x'.repeat(200 * 1024)
    const tooBig = await postJson('/api/memory/save', {
      path: 'memory/2026-05-01.md',
      content: huge,
    })
    expect(tooBig.status).toBe(413)
  })
})
