import { apiUrl } from './_base'
// Phase E1 — finance API. Tries /api/finance/dashboard on the v2 server first
// (which proxies to finance-api on :7684); falls back to the local fixture if
// the upstream is unreachable, errors out, or returns {fallback:true}.
//
// /api/finance/holdings + /api/finance/signals are NOT implemented upstream
// (verified probe 2026-05-07). The v2 server returns 503 + fallback:true for
// those, so the helpers below always end up using fixtures. They stay in the
// API layer so callers don't need to know.

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

async function fixture(): Promise<FinanceDashboard> {
  const { FINANCE_DASHBOARD } = await import('@/fixtures/agents/finance')
  return FINANCE_DASHBOARD
}

export async function fetchFinanceDashboard(): Promise<FinanceDashboard> {
  try {
    const r = await fetch(apiUrl('/finance/dashboard'), { credentials: 'include' })
    if (!r.ok) throw new Error(`http ${r.status}`)
    const body = await r.json()
    if (body && typeof body === 'object' && 'fallback' in body && body.fallback) {
      return fixture()
    }
    // The real upstream payload is shaped quite differently from our v2
    // dashboard (it returns {account, positions, signals, …}). For Phase E1
    // we accept both: if the upstream response already matches our shape,
    // pass it through; otherwise fall back to fixture so the UI keeps
    // rendering. A proper transform lives in Phase E4.
    if (body && typeof body === 'object' && 'netValue' in body) {
      return body as FinanceDashboard
    }
    return fixture()
  } catch {
    return fixture()
  }
}
