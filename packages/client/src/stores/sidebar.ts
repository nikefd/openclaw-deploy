// stores/sidebar.ts — sidebar UI state (collapsed, active tab, search query,
// chat list cache). Phase C2 stub data; Phase E will hydrate chatList from the
// real /api/chats endpoint.
import { defineStore } from 'pinia'

export type SidebarTab = 'chats' | 'memory' | 'skills'

export interface ChatSummary {
  id: string
  title: string
  preview: string
  /** epoch ms */
  lastMessageAt: number
  agent?: { emoji: string; name: string; color: string }
}

interface SidebarState {
  collapsed: boolean
  activeTab: SidebarTab
  searchQuery: string
  searchOpen: boolean
  chatList: ChatSummary[]
  activeChatId: string | null
}

const STUB_CHATS: ChatSummary[] = (() => {
  const now = Date.now()
  const m = 60_000
  const h = 60 * m
  const d = 24 * h
  return [
    {
      id: 'stub-1',
      title: '关于 Phase C 重构的讨论',
      preview: '我们把 sidebar 拆成独立组件，stores 走 pinia…',
      lastMessageAt: now - 5 * m,
      agent: { emoji: '🐶', name: '狗蛋', color: '#10a37f' },
    },
    {
      id: 'stub-2',
      title: 'Climbing 5.11d 攻略',
      preview: '今天爬了 V5，左手 crimp 还是有点弱…',
      lastMessageAt: now - 3 * h,
      agent: { emoji: '🧗', name: '攀岩教练', color: '#f59e0b' },
    },
    {
      id: 'stub-3',
      title: 'Finance daily report',
      preview: 'NDX +0.4%, BTC -1.2%, watchlist updated',
      lastMessageAt: now - 1 * d - 2 * h,
      agent: { emoji: '💸', name: '金融Agent', color: '#3b82f6' },
    },
    {
      id: 'stub-4',
      title: 'Resume tailoring for OpenAI',
      preview: 'JD highlights model evals + RLHF infra…',
      lastMessageAt: now - 3 * d,
      agent: { emoji: '📄', name: 'resume-gen', color: '#a855f7' },
    },
    {
      id: 'stub-5',
      title: 'Old debug session: nginx 502',
      preview: 'upstream timed out reading response header',
      lastMessageAt: now - 12 * d,
      agent: { emoji: '🐶', name: '狗蛋', color: '#10a37f' },
    },
  ]
})()

export const useSidebarStore = defineStore('sidebar', {
  state: (): SidebarState => ({
    collapsed: false,
    activeTab: 'chats',
    searchQuery: '',
    searchOpen: false,
    chatList: STUB_CHATS,
    activeChatId: null,
  }),
  getters: {
    width: (s) => (s.collapsed ? 56 : 240),
  },
  actions: {
    toggleCollapsed() {
      this.collapsed = !this.collapsed
    },
    setCollapsed(v: boolean) {
      this.collapsed = v
    },
    setActiveTab(tab: SidebarTab) {
      this.activeTab = tab
    },
    setSearchQuery(q: string) {
      this.searchQuery = q
    },
    openSearch() {
      this.searchOpen = true
    },
    closeSearch() {
      this.searchOpen = false
      this.searchQuery = ''
    },
    setActiveChatId(id: string | null) {
      this.activeChatId = id
    },
    setChatList(list: ChatSummary[]) {
      this.chatList = list
    },
  },
})
