// fixtures/usage.ts — Phase D2 stub for token usage.
// 30 days × 5 models. Real numbers will come from usage-api (port 7686).

export interface ModelPricing {
  model: string
  /** USD per 1M input tokens */
  inputPerM: number
  /** USD per 1M output tokens */
  outputPerM: number
  color: string // CSS color used by stacked bar
}

export interface DailyUsage {
  date: string // YYYY-MM-DD
  tokensIn: number
  tokensOut: number
  byModel: Record<string, { tokensIn: number; tokensOut: number }>
}

export const MODELS: ModelPricing[] = [
  { model: 'claude-opus-4.7', inputPerM: 15, outputPerM: 75, color: '#c084fc' },
  { model: 'claude-haiku-4', inputPerM: 1, outputPerM: 5, color: '#60a5fa' },
  { model: 'gpt-5', inputPerM: 10, outputPerM: 40, color: '#34d399' },
  { model: 'glm-5', inputPerM: 0.5, outputPerM: 2, color: '#fbbf24' },
  { model: 'gemini-2.5', inputPerM: 3.5, outputPerM: 14, color: '#f87171' },
]

function pad(n: number): string {
  return n < 10 ? `0${n}` : String(n)
}

function dateKey(d: Date): string {
  return `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())}`
}

function build30Days(): DailyUsage[] {
  const days: DailyUsage[] = []
  const today = new Date()
  for (let i = 29; i >= 0; i--) {
    const d = new Date(today)
    d.setUTCDate(today.getUTCDate() - i)
    const seed = (i * 9301 + 49297) % 233280
    const rand = (k: number) => ((seed * (k + 1)) % 100) / 100
    const byModel: Record<string, { tokensIn: number; tokensOut: number }> = {}
    let totalIn = 0
    let totalOut = 0
    MODELS.forEach((m, idx) => {
      const baseIn = Math.floor(40_000 + rand(idx) * 220_000)
      const baseOut = Math.floor(baseIn * (0.18 + rand(idx + 5) * 0.4))
      byModel[m.model] = { tokensIn: baseIn, tokensOut: baseOut }
      totalIn += baseIn
      totalOut += baseOut
    })
    days.push({ date: dateKey(d), tokensIn: totalIn, tokensOut: totalOut, byModel })
  }
  return days
}

export const STUB_USAGE_DAILY: DailyUsage[] = build30Days()

export function sumRange(days: DailyUsage[], n: number): { tokensIn: number; tokensOut: number } {
  const slice = days.slice(-n)
  return slice.reduce(
    (acc, d) => ({ tokensIn: acc.tokensIn + d.tokensIn, tokensOut: acc.tokensOut + d.tokensOut }),
    { tokensIn: 0, tokensOut: 0 },
  )
}

export function modelTotals(days: DailyUsage[]): Array<{ model: string; tokensIn: number; tokensOut: number }> {
  const totals = new Map<string, { tokensIn: number; tokensOut: number }>()
  for (const m of MODELS) totals.set(m.model, { tokensIn: 0, tokensOut: 0 })
  for (const d of days) {
    for (const [model, v] of Object.entries(d.byModel)) {
      const cur = totals.get(model) ?? { tokensIn: 0, tokensOut: 0 }
      cur.tokensIn += v.tokensIn
      cur.tokensOut += v.tokensOut
      totals.set(model, cur)
    }
  }
  return Array.from(totals.entries()).map(([model, v]) => ({ model, ...v }))
}

export function estimateCost(tokensIn: number, tokensOut: number, pricing: ModelPricing): number {
  return (tokensIn / 1_000_000) * pricing.inputPerM + (tokensOut / 1_000_000) * pricing.outputPerM
}
