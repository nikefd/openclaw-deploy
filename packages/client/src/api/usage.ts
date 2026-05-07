// api/usage.ts — Phase D2 stub. Real path will hit usage-api on :7686
// (proxied to /api/usage/summary by the v2 server).
import { STUB_USAGE_DAILY, type DailyUsage } from '@/fixtures/usage'

export async function fetchUsage(): Promise<DailyUsage[]> {
  await new Promise((r) => setTimeout(r, 60))
  return STUB_USAGE_DAILY
}

export type { DailyUsage, ModelPricing } from '@/fixtures/usage'
