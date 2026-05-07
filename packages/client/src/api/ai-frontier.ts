import { apiUrl } from './_base'
// Phase E1 — AI frontier API. Upstream /api/ai-frontier/items is NOT yet
// implemented (probed 2026-05-07 → 404). The v2 server registers a 503
// placeholder so we always fall through to the fixture here. Once the real
// endpoint lands, this file does not need to change.

export type FrontierSource = 'paper' | 'blog' | 'tweet'

export interface FrontierItem {
  id: string
  title: string
  summary: string
  source: FrontierSource
  url: string
  ts: string
  mermaid: string
}

async function fixture(): Promise<FrontierItem[]> {
  const { FRONTIER_ITEMS } = await import('@/fixtures/agents/ai-frontier')
  return FRONTIER_ITEMS
}

export async function fetchFrontierItems(): Promise<FrontierItem[]> {
  try {
    const r = await fetch(apiUrl('/ai-frontier/items'), { credentials: 'include' })
    if (!r.ok) throw new Error(`http ${r.status}`)
    const body = await r.json()
    if (body && typeof body === 'object' && !Array.isArray(body) && 'fallback' in body && body.fallback) {
      return fixture()
    }
    if (Array.isArray(body)) return body as FrontierItem[]
    return fixture()
  } catch {
    return fixture()
  }
}
