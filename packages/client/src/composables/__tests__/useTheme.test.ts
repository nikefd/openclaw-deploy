import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useThemeStore, THEME_STORAGE_KEY } from '@/stores/theme'
import { _internals } from '@/composables/useTheme'

describe('useTheme', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    document.documentElement.removeAttribute('data-theme')
    localStorage.clear()
  })

  it('apply() writes <html data-theme=...> for explicit modes', () => {
    _internals.apply('dark')
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark')
    _internals.apply('light')
    expect(document.documentElement.getAttribute('data-theme')).toBe('light')
  })

  it('apply("auto") resolves via prefers-color-scheme', () => {
    _internals.apply('auto')
    const v = document.documentElement.getAttribute('data-theme')
    expect(v === 'dark' || v === 'light').toBe(true)
  })

  it('store.setMode persists to localStorage', () => {
    const t = useThemeStore()
    t.setMode('light')
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe('light')
    t.setMode('dark')
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe('dark')
    t.setMode('auto')
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe('auto')
  })

  it('cycle() rotates auto -> dark -> light -> auto', () => {
    const t = useThemeStore()
    t.setMode('auto')
    t.cycle()
    expect(t.mode).toBe('dark')
    t.cycle()
    expect(t.mode).toBe('light')
    t.cycle()
    expect(t.mode).toBe('auto')
  })
})
