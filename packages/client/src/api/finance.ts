// Phase D1 — finance API. Currently returns fixture; Phase E will wire the
// real backend (port 7684/7685, /api/finance/dashboard etc.).

export interface Holding {
  code: string
  name: string
  qty: number
  cost: number
  price: number
  weight: number
}

export type SignalAction = 'BUY' | 'SELL' | 'HOLD' | 'WATCH'

export interface TradingSignal {
  id: string
  ts: string
  code: string
  name: string
  action: SignalAction
  reason: string
  confidence: number
}

export type RiskLevel = 'high' | 'medium' | 'low'

export interface RiskAlert {
  id: string
  level: RiskLevel
  title: string
  detail: string
}

export interface FinanceDashboard {
  netValue: number
  pnlToday: number
  pnlTodayPct: number
  positions: number
  alerts: number
  holdings: Holding[]
  signals: TradingSignal[]
  riskAlerts: RiskAlert[]
}

export async function fetchFinanceDashboard(): Promise<FinanceDashboard> {
  const { FINANCE_DASHBOARD } = await import('@/fixtures/agents/finance')
  // Simulate a small async delay so UI loading state is visible in dev.
  await new Promise((r) => setTimeout(r, 50))
  return FINANCE_DASHBOARD
}
