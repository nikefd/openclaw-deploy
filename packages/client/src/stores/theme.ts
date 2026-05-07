// stores/theme.ts — theme mode persisted to localStorage. The actual DOM side
// effect (writing <html data-theme>) lives in composables/useTheme.ts so this
// store stays test-friendly and SSR-safe.
import { defineStore } from 'pinia'

export type ThemeMode = 'dark' | 'light' | 'auto'

export const THEME_STORAGE_KEY = 'oc_v2_theme'

function readInitial(): ThemeMode {
  if (typeof localStorage === 'undefined') return 'auto'
  const v = localStorage.getItem(THEME_STORAGE_KEY)
  if (v === 'dark' || v === 'light' || v === 'auto') return v
  return 'auto'
}

export const useThemeStore = defineStore('theme', {
  state: () => ({
    mode: readInitial() as ThemeMode,
  }),
  actions: {
    setMode(m: ThemeMode) {
      this.mode = m
      if (typeof localStorage !== 'undefined') {
        try {
          localStorage.setItem(THEME_STORAGE_KEY, m)
        } catch {
          /* quota — ignore */
        }
      }
    },
    cycle() {
      const order: ThemeMode[] = ['auto', 'dark', 'light']
      const i = order.indexOf(this.mode)
      this.setMode(order[(i + 1) % order.length] ?? 'auto')
    },
  },
})
