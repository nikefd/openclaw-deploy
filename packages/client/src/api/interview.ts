// Phase E1 — interview API. Tries /api/interview/schedule on the v2 server
// (which serves the static /var/www/chat/data/interview-schedule.json file);
// falls back to the bundled fixture if the upstream is unreachable.

export type InterviewStatus = 'upcoming' | 'completed' | 'cancelled'
export type CompanyStatus = 'active' | 'paused' | 'rejected' | 'offer'

export interface InterviewSchedule {
  date: string
  time: string
  company: string
  round: string
  interviewer: string
  status: InterviewStatus
}

export interface CompanyCard {
  name: string
  emoji: string
  status: CompanyStatus
  round: string
  lastTouch: string
  notes: string
}

export interface PrepProgress {
  topic: string
  done: number
  total: number
  note: string
}

export interface InterviewDashboard {
  schedule: InterviewSchedule[]
  companies: CompanyCard[]
  progress: PrepProgress[]
}

async function fixture(): Promise<InterviewDashboard> {
  const { IV_DASHBOARD } = await import('@/fixtures/agents/interview')
  return IV_DASHBOARD
}

export async function fetchInterviewDashboard(): Promise<InterviewDashboard> {
  try {
    const r = await fetch('/api/interview/schedule', { credentials: 'include' })
    if (!r.ok) throw new Error(`http ${r.status}`)
    const body = await r.json()
    if (body && typeof body === 'object' && 'fallback' in body && body.fallback) {
      return fixture()
    }
    // The static schedule file only contains schedule rows, not the full
    // dashboard (companies/progress). Compose: real schedule + fixture
    // companies+progress until Phase E4 ships proper sources.
    const fb = await fixture()
    if (body && typeof body === 'object' && 'schedule' in body && Array.isArray(body.schedule)) {
      return { ...fb, schedule: body.schedule }
    }
    if (Array.isArray(body)) {
      return { ...fb, schedule: body }
    }
    return body as InterviewDashboard
  } catch {
    return fixture()
  }
}
