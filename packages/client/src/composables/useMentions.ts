// composables/useMentions.ts — pure-ish helpers for detecting an in-progress
// `@mention` token in a text input and a fallback document-level keydown
// listener for the case where MessageInput (owned by Phase C1) has not yet
// exposed a mention hook. The MentionPopup component reads stores/mentions.ts.
import { onBeforeUnmount, onMounted } from 'vue'
import { useMentionsStore } from '@/stores/mentions'

export interface MentionScan {
  trigger: boolean
  /** the text after `@`, possibly empty */
  query: string
  /** index in the source string of the `@` (or -1 if no trigger) */
  atIndex: number
}

/**
 * Look at the text up to (but not including) `cursor` and decide whether the
 * caret is currently inside an @mention token.
 *
 * Rules:
 *  - The latest `@` must be preceded by start-of-string or whitespace.
 *  - From `@` to `cursor` there must be no whitespace.
 *  - An empty query (just typed `@`) still counts as triggered.
 */
export function scanMention(text: string, cursor: number): MentionScan {
  const safe = text.slice(0, Math.max(0, cursor))
  const at = safe.lastIndexOf('@')
  if (at < 0) return { trigger: false, query: '', atIndex: -1 }
  if (at > 0) {
    const prev = safe[at - 1]!
    if (!/\s/.test(prev)) return { trigger: false, query: '', atIndex: -1 }
  }
  const after = safe.slice(at + 1)
  if (/\s/.test(after)) return { trigger: false, query: '', atIndex: -1 }
  return { trigger: true, query: after, atIndex: at }
}

/**
 * Mount-time fallback hook: listen on document for typing in any
 * `<textarea data-oc-input>` or `<input data-oc-input>` and feed the mentions
 * store. C1's MessageInput can later supply its own bridge, in which case this
 * fallback simply finds nothing to listen to (no-op) — both can coexist.
 */
export function useMentionsFallback() {
  const store = useMentionsStore()

  function onInput(ev: Event) {
    const tgt = ev.target as HTMLElement | null
    if (!tgt) return
    if (!(tgt instanceof HTMLTextAreaElement || tgt instanceof HTMLInputElement)) return
    if (!tgt.hasAttribute('data-oc-input')) return
    const cursor = tgt.selectionStart ?? tgt.value.length
    const scan = scanMention(tgt.value, cursor)
    if (scan.trigger) {
      const r = tgt.getBoundingClientRect()
      // Anchor near the input top-left; a real implementation would measure
      // the caret. Sufficient for Phase C2 demo.
      store.show(scan.query, { x: r.left + 12, y: r.top - 8 })
    } else if (store.open) {
      store.hide()
    }
  }

  function onKeyDown(ev: KeyboardEvent) {
    if (!store.open) return
    if (ev.key === 'ArrowDown') {
      store.moveSelection(1)
      ev.preventDefault()
    } else if (ev.key === 'ArrowUp') {
      store.moveSelection(-1)
      ev.preventDefault()
    } else if (ev.key === 'Enter') {
      const pick = store.pickCurrent()
      if (pick) {
        store.apply(pick.handle + ' ')
        ev.preventDefault()
      }
    } else if (ev.key === 'Escape') {
      store.hide()
      ev.preventDefault()
    }
  }

  onMounted(() => {
    document.addEventListener('input', onInput, true)
    document.addEventListener('keydown', onKeyDown, true)
  })
  onBeforeUnmount(() => {
    document.removeEventListener('input', onInput, true)
    document.removeEventListener('keydown', onKeyDown, true)
  })
}
