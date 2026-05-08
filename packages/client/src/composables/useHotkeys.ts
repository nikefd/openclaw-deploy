// composables/useHotkeys.ts — register global keyboard shortcuts. The hook
// returns a disposer in case callers want manual cleanup; otherwise it auto-
// cleans on component unmount.
import { onBeforeUnmount, onMounted } from 'vue'

export interface Hotkey {
  /** key as reported by KeyboardEvent.key, case-insensitive */
  key: string
  ctrl?: boolean
  meta?: boolean
  shift?: boolean
  alt?: boolean
  /** if true, both Ctrl and Meta count (cross-platform default) */
  mod?: boolean
  handler: (ev: KeyboardEvent) => void
  /** preventDefault when matched (default true) */
  preventDefault?: boolean
}

function matches(ev: KeyboardEvent, h: Hotkey): boolean {
  if (ev.key.toLowerCase() !== h.key.toLowerCase()) return false
  if (h.mod) {
    if (!(ev.ctrlKey || ev.metaKey)) return false
  } else {
    if ((h.ctrl ?? false) !== ev.ctrlKey) return false
    if ((h.meta ?? false) !== ev.metaKey) return false
  }
  if ((h.shift ?? false) !== ev.shiftKey) return false
  if ((h.alt ?? false) !== ev.altKey) return false
  return true
}

export function useHotkeys(hotkeys: Hotkey[]) {
  function listener(ev: KeyboardEvent) {
    for (const h of hotkeys) {
      if (matches(ev, h)) {
        if (h.preventDefault !== false) ev.preventDefault()
        h.handler(ev)
        break
      }
    }
  }
  onMounted(() => {
    document.addEventListener('keydown', listener)
  })
  onBeforeUnmount(() => {
    document.removeEventListener('keydown', listener)
  })
  return {
    dispose() {
      document.removeEventListener('keydown', listener)
    },
  }
}

// Exported for unit tests — pure matcher with no DOM coupling.
export const _matches = matches
