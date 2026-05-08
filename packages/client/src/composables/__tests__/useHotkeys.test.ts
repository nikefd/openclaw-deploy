import { describe, it, expect } from 'vitest'
import { _matches, type Hotkey } from '@/composables/useHotkeys'

function ev(init: Partial<KeyboardEventInit> & { key: string }): KeyboardEvent {
  return new KeyboardEvent('keydown', { bubbles: true, cancelable: true, ...init })
}

describe('useHotkeys / matches', () => {
  it('matches Ctrl+K when configured with mod=true', () => {
    const h: Hotkey = { key: 'k', mod: true, handler: () => {} }
    expect(_matches(ev({ key: 'k', ctrlKey: true }), h)).toBe(true)
    expect(_matches(ev({ key: 'k', metaKey: true }), h)).toBe(true)
    expect(_matches(ev({ key: 'k' }), h)).toBe(false)
  })

  it('is case-insensitive on key', () => {
    const h: Hotkey = { key: 'K', mod: true, handler: () => {} }
    expect(_matches(ev({ key: 'k', ctrlKey: true }), h)).toBe(true)
  })

  it('respects shift / alt requirements', () => {
    const h: Hotkey = { key: '/', mod: true, shift: true, handler: () => {} }
    expect(_matches(ev({ key: '/', ctrlKey: true, shiftKey: true }), h)).toBe(true)
    expect(_matches(ev({ key: '/', ctrlKey: true }), h)).toBe(false)
  })

  it('does not match when modifiers disagree (no mod hint)', () => {
    const h: Hotkey = { key: 'n', ctrl: true, handler: () => {} }
    expect(_matches(ev({ key: 'n', ctrlKey: true }), h)).toBe(true)
    expect(_matches(ev({ key: 'n', metaKey: true }), h)).toBe(false)
    expect(_matches(ev({ key: 'n' }), h)).toBe(false)
  })
})
