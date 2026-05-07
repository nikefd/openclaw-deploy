/**
 * useAutoScroll — keep a container pinned to bottom unless user scrolled up.
 */

import { ref, type Ref } from 'vue'

export interface UseAutoScrollOptions {
  threshold?: number
}

export interface AutoScrollHandle {
  atBottom: Ref<boolean>
  bind: (el: HTMLElement | null | undefined) => () => void
  scrollToBottom: (force?: boolean) => void
  recompute: () => void
}

export function useAutoScroll(opts: UseAutoScrollOptions = {}): AutoScrollHandle {
  const threshold = opts.threshold ?? 50
  const atBottom = ref(true)
  let target: HTMLElement | null = null

  function compute(el: HTMLElement): boolean {
    const distance = el.scrollHeight - el.clientHeight - el.scrollTop
    return distance <= threshold
  }

  function onScroll() {
    if (!target) return
    atBottom.value = compute(target)
  }

  function bind(el: HTMLElement | null | undefined): () => void {
    target = el ?? null
    if (!target) return () => {}
    target.addEventListener('scroll', onScroll, { passive: true })
    atBottom.value = compute(target)
    const captured = target
    return () => {
      captured.removeEventListener('scroll', onScroll)
      if (target === captured) target = null
    }
  }

  function scrollToBottom(force = false): void {
    if (!target) return
    if (!atBottom.value && !force) return
    target.scrollTop = target.scrollHeight
    atBottom.value = true
  }

  function recompute(): void {
    if (target) atBottom.value = compute(target)
  }

  return { atBottom, bind, scrollToBottom, recompute }
}
