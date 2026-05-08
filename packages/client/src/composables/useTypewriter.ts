/**
 * useTypewriter — reveal a string char by char as a reactive ref.
 */

import { ref, watch, onScopeDispose, type Ref } from 'vue'

export interface TypewriterOptions {
  intervalMs?: number
  charsPerTick?: number
  enabled?: boolean
}

export interface TypewriterHandle {
  display: Ref<string>
  flush: () => void
  cancel: () => void
}

export function useTypewriter(
  source: Ref<string>,
  opts: TypewriterOptions = {},
): TypewriterHandle {
  const intervalMs = opts.intervalMs ?? 16
  const charsPerTick = Math.max(1, opts.charsPerTick ?? 2)
  const enabled = opts.enabled ?? true

  const display = ref<string>(enabled ? '' : source.value)
  let timer: ReturnType<typeof setInterval> | null = null

  function tick() {
    const target = source.value
    if (display.value.length >= target.length) {
      stop()
      return
    }
    const next = display.value.length + charsPerTick
    display.value = target.slice(0, next)
  }

  function ensureRunning() {
    if (timer) return
    timer = setInterval(tick, intervalMs)
  }

  function stop() {
    if (timer) {
      clearInterval(timer)
      timer = null
    }
  }

  function flush() {
    display.value = source.value
    stop()
  }

  function cancel() {
    stop()
  }

  if (!enabled) {
    watch(source, (v) => { display.value = v })
    return { display, flush, cancel }
  }

  watch(
    source,
    (next, prev) => {
      if (next.length < (prev?.length ?? 0) || next.length < display.value.length) {
        display.value = ''
      }
      if (display.value.length < next.length) {
        ensureRunning()
      }
    },
    { immediate: true },
  )

  onScopeDispose(stop)

  return { display, flush, cancel }
}
