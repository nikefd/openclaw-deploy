// Phase D1 — climbing coach API stub. Phase E swaps to /api/agents/fitness/sessions.

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

export async function fetchClimbingDashboard(): Promise<ClimbingDashboard> {
  const { CLIMB_DASHBOARD } = await import('@/fixtures/agents/climbing')
  await new Promise((r) => setTimeout(r, 50))
  return CLIMB_DASHBOARD
}
