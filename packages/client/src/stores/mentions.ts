// stores/mentions.ts — bridge between MessageInput (owned by C1) and
// MentionPopup (owned by C2). MessageInput emits `update:mention` calls into
// this store; MentionPopup reads `open / query / triggerEl` and on selection
// calls `apply(value)` which the MessageInput listens to via an event the
// composable re-publishes (or, fallback, via document keydown — see
// composables/useMentions.ts).
import { defineStore } from 'pinia'

export interface MentionAgent {
  id: string
  handle: string // e.g. '@金融Agent'
  name: string
  description: string
  emoji: string
}

export const STUB_AGENTS: MentionAgent[] = [
  {
    id: 'finance',
    handle: '@金融Agent',
    name: '金融Agent',
    description: '股票 / 加密 / 宏观，实时数据看板',
    emoji: '💸',
  },
  {
    id: 'climbing',
    handle: '@攀岩教练',
    name: '攀岩教练',
    description: '训练计划 / 动作分析 / 拉伸',
    emoji: '🧗',
  },
  {
    id: 'goudan',
    handle: '@狗蛋',
    name: '狗蛋',
    description: '通用助手',
    emoji: '🐶',
  },
  {
    id: 'code',
    handle: '@code',
    name: 'code',
    description: '代码助手',
    emoji: '💻',
  },
]

interface MentionState {
  open: boolean
  query: string
  selectedIdx: number
  /** screen position for the popup (computed by the input) */
  anchor: { x: number; y: number } | null
  /** monotonic counter used to signal "apply this insertion" to MessageInput */
  applyTick: number
  applyValue: string
}

export const useMentionsStore = defineStore('mentions', {
  state: (): MentionState => ({
    open: false,
    query: '',
    selectedIdx: 0,
    anchor: null,
    applyTick: 0,
    applyValue: '',
  }),
  getters: {
    filtered(state): MentionAgent[] {
      const q = state.query.trim().toLowerCase()
      if (!q) return STUB_AGENTS
      return STUB_AGENTS.filter(
        (a) =>
          a.name.toLowerCase().includes(q) ||
          a.handle.toLowerCase().includes(q) ||
          a.id.toLowerCase().includes(q),
      )
    },
  },
  actions: {
    show(query: string, anchor: { x: number; y: number } | null) {
      this.open = true
      this.query = query
      this.anchor = anchor
      this.selectedIdx = 0
    },
    setQuery(q: string) {
      this.query = q
      this.selectedIdx = 0
    },
    hide() {
      this.open = false
      this.query = ''
      this.anchor = null
    },
    moveSelection(delta: number) {
      const len = this.filtered.length
      if (!len) return
      this.selectedIdx = (this.selectedIdx + delta + len) % len
    },
    pickCurrent(): MentionAgent | null {
      const list = this.filtered
      return list[this.selectedIdx] ?? null
    },
    apply(value: string) {
      this.applyValue = value
      this.applyTick += 1
      this.hide()
    },
  },
})
