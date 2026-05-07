// Phase D1 — AI frontier API stub. Phase E hits /api/ai-frontier/items.

export type FrontierSource = 'paper' | 'blog' | 'tweet'

export interface FrontierItem {
  id: string
  title: string
  summary: string
  source: FrontierSource
  url: string
  ts: string
  mermaid: string // empty string = no diagram; rendering deferred to Phase E
}

export async function fetchFrontierItems(): Promise<FrontierItem[]> {
  const { FRONTIER_ITEMS } = await import('@/fixtures/agents/ai-frontier')
  await new Promise((r) => setTimeout(r, 50))
  return FRONTIER_ITEMS
}
