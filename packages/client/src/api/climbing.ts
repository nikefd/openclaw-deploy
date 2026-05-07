import { apiUrl } from './_base'
// Phase E1 — climbing coach API. Tries /api/agents/fitness/sessions on the v2
// server (proxies to agents-api :7685); falls back to the bundled fixture if
// the upstream is unreachable.

export interface ClimbingSession {
  date: string
  gym: string
  durationMin: number
  maxSend: string
  maxAttempt: string
  routes: number
  sendRate: number
}

export interface ClimbingDashboard {
  weeklyCount: number
  topGrade: string
  redpointCount: number
  freqPerWeek: number
  bottleneck: string
  plan: string
  warmup: string
  sessions: ClimbingSession[]
}

async function fixture(): Promise<ClimbingDashboard> {
  const { CLIMB_DASHBOARD } = await import('@/fixtures/agents/climbing')
  return CLIMB_DASHBOARD
}

export async function fetchClimbingDashboard(): Promise<ClimbingDashboard> {
  try {
    const r = await fetch(apiUrl('/agents/fitness/sessions'), { credentials: 'include' })
    if (!r.ok) throw new Error(`http ${r.status}`)
    const body = await r.json()
    if (body && typeof body === 'object' && 'fallback' in body && body.fallback) {
      return fixture()
    }
    // Upstream returns a raw session array (verified probe 2026-05-07). We
    // can't synthesize the full ClimbingDashboard shape from that yet, so
    // for Phase E1 we let the proxy succeed but still hand back the fixture
    // dashboard summary. A proper aggregator lives in Phase E4.
    if (Array.isArray(body)) {
      const fb = await fixture()
      return { ...fb }
    }
    return body as ClimbingDashboard
  } catch {
    return fixture()
  }
}
