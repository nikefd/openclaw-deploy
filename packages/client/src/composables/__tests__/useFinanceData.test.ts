import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { useFinanceData } from '@/composables/useFinanceData'

// Mock the API so we control the resolution timing for the loading-state assertion.
vi.mock('@/api/finance', async () => {
  const actual = await vi.importActual<typeof import('@/api/finance')>('@/api/finance')
  let resolver: ((v: unknown) => void) | null = null
  return {
    ...actual,
    fetchFinanceDashboard: () =>
      new Promise((res) => {
        resolver = res as (v: unknown) => void
        ;(globalThis as unknown as { __resolveFinance: () => void }).__resolveFinance = () =>
          resolver?.({
            netValue: 100,
            pnlToday: 1,
            pnlTodayPct: 0.01,
            positions: 1,
            alerts: 0,
            holdings: [],
            signals: [],
            riskAlerts: [],
          })
      }),
  }
})

function makeHarness() {
  let captured!: ReturnType<typeof useFinanceData>
  const Comp = defineComponent({
    setup() {
      captured = useFinanceData()
      return () => h('div')
    },
  })
  const wrapper = mount(Comp)
  return { wrapper, get: () => captured }
}

describe('useFinanceData', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('starts in loading=true with null data', () => {
    const { get } = makeHarness()
    const c = get()
    expect(c.loading.value).toBe(true)
    expect(c.data.value).toBeNull()
    expect(c.error.value).toBeNull()
  })

  it('transitions to loading=false with data after resolution', async () => {
    const { get } = makeHarness()
    const c = get()
    expect(c.loading.value).toBe(true)
    ;(globalThis as unknown as { __resolveFinance: () => void }).__resolveFinance()
    await flushPromises()
    expect(c.loading.value).toBe(false)
    expect(c.data.value).not.toBeNull()
    expect(c.data.value?.netValue).toBe(100)
    expect(c.error.value).toBeNull()
  })

  it('sets error when reload throws', async () => {
    const { get } = makeHarness()
    const c = get()
    ;(globalThis as unknown as { __resolveFinance: () => void }).__resolveFinance()
    await flushPromises()

    // Force a reload failure by overriding the underlying import once.
    const mod = await import('@/api/finance')
    const orig = mod.fetchFinanceDashboard
    ;(mod as unknown as { fetchFinanceDashboard: () => Promise<unknown> }).fetchFinanceDashboard =
      () => Promise.reject(new Error('boom'))

    await c.reload()
    expect(c.error.value).toBe('boom')
    expect(c.loading.value).toBe(false)

    // Restore.
    ;(mod as unknown as { fetchFinanceDashboard: typeof orig }).fetchFinanceDashboard = orig
  })
})
