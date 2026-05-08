import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { ref, effectScope, nextTick } from 'vue'
import { useTypewriter } from '@/composables/useTypewriter'

describe('useTypewriter', () => {
  beforeEach(() => { vi.useFakeTimers() })
  afterEach(() => { vi.useRealTimers() })

  it('reveals chars over time', async () => {
    const scope = effectScope()
    await scope.run(async () => {
      const src = ref('hello world')
      const { display } = useTypewriter(src, { intervalMs: 16, charsPerTick: 2 })
      expect(display.value).toBe('')
      await vi.advanceTimersByTimeAsync(120)
      expect(display.value).toBe('hello world')
    })
    scope.stop()
  })

  it('flush jumps to full source immediately', () => {
    const scope = effectScope()
    scope.run(() => {
      const src = ref('lorem ipsum')
      const { display, flush } = useTypewriter(src, { intervalMs: 100, charsPerTick: 1 })
      expect(display.value).toBe('')
      flush()
      expect(display.value).toBe('lorem ipsum')
    })
    scope.stop()
  })

  it('shrinking source resets display', async () => {
    const scope = effectScope()
    await scope.run(async () => {
      const src = ref('abcdefgh')
      const { display } = useTypewriter(src, { intervalMs: 16, charsPerTick: 8 })
      await vi.advanceTimersByTimeAsync(40)
      expect(display.value.length).toBeGreaterThan(0)
      src.value = 'xy'
      await nextTick()
      expect(display.value.length).toBeLessThanOrEqual(2)
    })
    scope.stop()
  })

  it('respects enabled=false (no animation)', async () => {
    const scope = effectScope()
    await scope.run(async () => {
      const src = ref('snap')
      const { display } = useTypewriter(src, { enabled: false })
      expect(display.value).toBe('snap')
      src.value = 'snap2'
      await nextTick()
      expect(display.value).toBe('snap2')
    })
    scope.stop()
  })
})
