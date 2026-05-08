import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import CostEstimate from '@/components/usage/CostEstimate.vue'
import { estimateCost, type ModelPricing } from '@/fixtures/usage'

const MODELS: ModelPricing[] = [
  { model: 'm-cheap', inputPerM: 1, outputPerM: 2, color: '#000' },
  { model: 'm-pricy', inputPerM: 10, outputPerM: 50, color: '#fff' },
]

describe('CostEstimate', () => {
  it('estimateCost: 1M in × $1 + 1M out × $2 = $3', () => {
    expect(estimateCost(1_000_000, 1_000_000, MODELS[0]!)).toBeCloseTo(3, 6)
  })

  it('estimateCost handles fractional millions', () => {
    // 500k in × $10/M = $5; 200k out × $50/M = $10 → total $15
    expect(estimateCost(500_000, 200_000, MODELS[1]!)).toBeCloseTo(15, 6)
  })

  it('renders one row per model and totals match estimateCost', () => {
    const totals = [
      { model: 'm-cheap', tokensIn: 1_000_000, tokensOut: 1_000_000 },
      { model: 'm-pricy', tokensIn: 500_000, tokensOut: 200_000 },
    ]
    const w = mount(CostEstimate, { props: { models: MODELS, totals } })
    const rows = w.findAll('[data-testid="cost-row"]')
    expect(rows).toHaveLength(2)

    const costCells = w.findAll('[data-testid="cost-cell"]').map((c) => c.text())
    // Sorted descending by cost: m-pricy ($15) first, then m-cheap ($3)
    expect(costCells[0]).toBe('$15.00')
    expect(costCells[1]).toBe('$3.00')

    expect(w.text()).toContain('合计 $18.00')
  })

  it('falls back gracefully when pricing is unknown', () => {
    const totals = [{ model: 'unknown-model', tokensIn: 1_000_000, tokensOut: 1_000_000 }]
    const w = mount(CostEstimate, { props: { models: MODELS, totals } })
    expect(w.findAll('[data-testid="cost-row"]')).toHaveLength(1)
    // Unknown pricing → cost $0
    expect(w.find('[data-testid="cost-cell"]').text()).toBe('$0.00')
  })
})
