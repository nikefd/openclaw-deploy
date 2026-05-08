// composables/useTheme.ts — applies the Pinia theme store to <html data-theme>
// and listens for system color-scheme changes when mode === 'auto'. Call
// `useTheme()` once in App.vue (or any persistent root) to bootstrap.
import { onBeforeUnmount, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useThemeStore, type ThemeMode } from '@/stores/theme'

function resolveAuto(): 'dark' | 'light' {
  if (typeof window === 'undefined' || !window.matchMedia) return 'dark'
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

function apply(mode: ThemeMode) {
  if (typeof document === 'undefined') return
  const effective: 'dark' | 'light' = mode === 'auto' ? resolveAuto() : mode
  document.documentElement.setAttribute('data-theme', effective)
}

export function useTheme() {
  const store = useThemeStore()
  const { mode } = storeToRefs(store)

  apply(mode.value)

  let mql: MediaQueryList | null = null
  let mqlListener: ((e: MediaQueryListEvent) => void) | null = null

  function attachAutoListener() {
    if (typeof window === 'undefined' || !window.matchMedia) return
    if (mql && mqlListener) {
      mql.removeEventListener('change', mqlListener)
      mql = null
      mqlListener = null
    }
    if (mode.value !== 'auto') return
    mql = window.matchMedia('(prefers-color-scheme: dark)')
    mqlListener = () => apply('auto')
    mql.addEventListener('change', mqlListener)
  }

  attachAutoListener()

  const stop = watch(mode, (m) => {
    apply(m)
    attachAutoListener()
  })

  onBeforeUnmount(() => {
    stop()
    if (mql && mqlListener) mql.removeEventListener('change', mqlListener)
  })

  return {
    mode,
    setMode: store.setMode,
    cycle: store.cycle,
  }
}

/** Pure helper exposed for unit tests. */
export const _internals = { apply, resolveAuto }
