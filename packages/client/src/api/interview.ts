// Phase D1 — interview API stub. Phase E hits /api/interview/{schedule,companies,progress}.

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

export async function fetchInterviewDashboard(): Promise<InterviewDashboard> {
  const { IV_DASHBOARD } = await import('@/fixtures/agents/interview')
  await new Promise((r) => setTimeout(r, 50))
  return IV_DASHBOARD
}
