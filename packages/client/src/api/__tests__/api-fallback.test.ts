/**
 * api-fallback.test.ts — Phase E1 verification of the frontend fetch→fixture
 * fallback pattern. Two scenarios per representative API: real fetch succeeds
 * (returns proxied data), and real fetch fails (returns the bundled fixture).
 *
 * We pick three of the eight modules (finance, tasks, ai-frontier) to keep
 * this file tight; the other five share the exact same pattern.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { fetchFinanceDashboard } from '@/api/finance'
import { fetchTasks } from '@/api/tasks'
import { fetchFrontierItems } from '@/api/ai-frontier'

const realFetch = globalThis.fetch

afterEach(() => {
  globalThis.fetch = realFetch
  vi.restoreAllMocks()
})

function mockOkJson(body: unknown): typeof fetch {
  return vi.fn(async () =>
    new Response(JSON.stringify(body), {
      status: 200,
      headers: { 'content-type': 'application/json' },
    }),
  ) as unknown as typeof fetch
}

function mockReject(): typeof fetch {
  return vi.fn(async () => {
    throw new TypeError('network down')
  }) as unknown as typeof fetch
}

describe('api/finance — fetch path', () => {
  it('returns upstream payload when shape matches v2 dashboard', async () => {
    globalThis.fetch = mockOkJson({
      netValue: 999,
      pnlToday: 10,
      pnlTodayPct: 1,
      positions: 1,
      alerts: 0,
      holdings: [],
      signals: [],
      riskAlerts: [],
    })
    const r = await fetchFinanceDashboard()
    expect(r.netValue).toBe(999)
  })

  it('falls back to fixture when fetch rejects', async () => {
    globalThis.fetch = mockReject()
    const r = await fetchFinanceDashboard()
    // Fixture has known mock holdings — just assert it's the canned shape.
    expect(r.holdings.length).toBeGreaterThan(0)
  })

  it('falls back when upstream returns {fallback:true}', async () => {
    globalThis.fetch = mockOkJson({ fallback: true, error: 'x' })
    const r = await fetchFinanceDashboard()
    expect(r.holdings.length).toBeGreaterThan(0)
  })
})

describe('api/tasks — fetch path', () => {
  it('returns upstream array verbatim', async () => {
    globalThis.fetch = mockOkJson([
      { runId: 't-1', sessionKey: 's-1', parent: null, label: 'real task', status: 'running', startedAt: Date.now(), durationMs: 1000 },
    ])
    const r = await fetchTasks()
    expect(r).toHaveLength(1)
    expect(r[0]!.runId).toBe('t-1')
  })

  it('falls back to STUB_TASKS when upstream 503', async () => {
    globalThis.fetch = vi.fn(async () =>
      new Response(JSON.stringify({ fallback: true }), { status: 503 }),
    ) as unknown as typeof fetch
    const r = await fetchTasks()
    expect(r.length).toBeGreaterThan(0) // fixture has many
  })
})

describe('api/ai-frontier — placeholder always falls back', () => {
  it('uses fixture when upstream rejects', async () => {
    globalThis.fetch = mockReject()
    const r = await fetchFrontierItems()
    expect(r.length).toBeGreaterThan(0)
    expect(r[0]!.title).toBeTruthy()
  })

  it('returns upstream items when upstream succeeds', async () => {
    globalThis.fetch = mockOkJson([
      { id: 'x', title: 'real item', summary: 's', source: 'paper', url: 'http://x', ts: 't', mermaid: '' },
    ])
    const r = await fetchFrontierItems()
    expect(r).toHaveLength(1)
    expect(r[0]!.title).toBe('real item')
  })
})

describe('api fallback layer — sanity', () => {
  beforeEach(() => {
    globalThis.fetch = mockReject()
  })
  it('all 3 helpers resolve without throwing under network failure', async () => {
    await expect(fetchFinanceDashboard()).resolves.toBeDefined()
    await expect(fetchTasks()).resolves.toBeDefined()
    await expect(fetchFrontierItems()).resolves.toBeDefined()
  })
})
