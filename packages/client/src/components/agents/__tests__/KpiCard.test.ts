import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import KpiCard from '@/components/agents/KpiCard.vue'

describe('KpiCard', () => {
  it('renders label and value', () => {
    const w = mount(KpiCard, { props: { label: '净值', value: '¥1,000' } })
    expect(w.text()).toContain('净值')
    expect(w.text()).toContain('¥1,000')
  })

  it('applies positive class for positive delta', () => {
    const w = mount(KpiCard, { props: { label: 'PnL', value: 1, delta: 1.5 } })
    const delta = w.find('.delta')
    expect(delta.exists()).toBe(true)
    expect(delta.classes()).toContain('pos')
    expect(delta.text()).toBe('+1.50%')
  })

  it('applies negative class for negative delta', () => {
    const w = mount(KpiCard, { props: { label: 'PnL', value: 1, delta: -2.3 } })
    const delta = w.find('.delta')
    expect(delta.classes()).toContain('neg')
    expect(delta.text()).toBe('-2.30%')
  })

  it('applies flat class for zero delta and hides delta when undefined', () => {
    const flat = mount(KpiCard, { props: { label: 'x', value: 1, delta: 0 } })
    expect(flat.find('.delta').classes()).toContain('flat')

    const none = mount(KpiCard, { props: { label: 'x', value: 1 } })
    expect(none.find('.delta').exists()).toBe(false)
  })

  it('respects custom delta suffix', () => {
    const w = mount(KpiCard, { props: { label: 'x', value: 1, delta: 5, deltaSuffix: ' bps' } })
    expect(w.find('.delta').text()).toBe('+5.00 bps')
  })
})
