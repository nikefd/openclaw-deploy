import { apiUrl } from './_base'
// Phase E1 — usage API. Tries /api/usage/summary on the v2 server (proxies to
// usage-api :7686 /api/usage). Real response shape is a single aggregate
// {summary, …}, not the v2 dashboard's per-day array. For Phase E1 we keep
// the fixture series so the chart still renders, but we can swap once a
// daily-bucket endpoint exists.

import { STUB_USAGE_DAILY, type DailyUsage } from '@/fixtures/usage'

export async function fetchUsage(): Promise<DailyUsage[]> {
  try {
    const r = await fetch(apiUrl('/usage/summary'), { credentials: 'include' })
    if (!r.ok) throw new Error(`http ${r.status}`)
    const body = await r.json()
    if (body && typeof body === 'object' && 'fallback' in body && body.fallback) {
      return STUB_USAGE_DAILY
    }
    if (Array.isArray(body)) return body as DailyUsage[]
    // Aggregate shape — keep the fixture daily series for now.
    return STUB_USAGE_DAILY
  } catch {
    return STUB_USAGE_DAILY
  }
}

export type { DailyUsage, ModelPricing } from '@/fixtures/usage'
