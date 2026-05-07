import { describe, it, expect } from 'vitest'
import { effectScope } from 'vue'
import { useAutoScroll } from '@/composables/useAutoScroll'

function makeScroller(opts: { scrollHeight: number; clientHeight: number; scrollTop: number }) {
  const el = document.createElement('div')
  Object.defineProperty(el, 'scrollHeight', { configurable: true, get: () => opts.scrollHeight })
  Object.defineProperty(el, 'clientHeight', { configurable: true, get: () => opts.clientHeight })
  let st = opts.scrollTop
  Object.defineProperty(el, 'scrollTop', {
    configurable: true,
    get: () => st,
    set: (v: number) => { st = v },
  })
  document.body.appendChild(el)
  return el
}

describe('useAutoScroll', () => {
  it('atBottom is true when within threshold', () => {
    const scope = effectScope()
    scope.run(() => {
      const { atBottom, bind, recompute } = useAutoScroll({ threshold: 50 })
      const el = makeScroller({ scrollHeight: 1000, clientHeight: 400, scrollTop: 590 })
      bind(el)
      recompute()
      expect(atBottom.value).toBe(true)
    })
    scope.stop()
  })

  it('atBottom flips to false when user scrolls up past threshold', () => {
    const scope = effectScope()
    scope.run(() => {
      const { atBottom, bind } = useAutoScroll({ threshold: 50 })
      const el = makeScroller({ scrollHeight: 1000, clientHeight: 400, scrollTop: 100 })
      bind(el)
      ;(el as HTMLElement).scrollTop = 100
      el.dispatchEvent(new Event('scroll'))
      expect(atBottom.value).toBe(false)
    })
    scope.stop()
  })

  it('scrollToBottom only moves when pinned (unless force=true)', () => {
    const scope = effectScope()
    scope.run(() => {
      const { bind, scrollToBottom } = useAutoScroll({ threshold: 50 })
      const el = makeScroller({ scrollHeight: 1000, clientHeight: 400, scrollTop: 100 })
      bind(el)
      el.dispatchEvent(new Event('scroll'))
      scrollToBottom()
      expect(el.scrollTop).toBe(100)
      scrollToBottom(true)
      expect(el.scrollTop).toBe(1000)
    })
    scope.stop()
  })
})
