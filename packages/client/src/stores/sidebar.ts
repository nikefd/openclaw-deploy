// stores/sidebar.ts — sidebar UI state (collapsed, active tab, search query,
// chat list cache).
//
// Phase E4: chatList is now populated from the real /v2/api/chats endpoint
// via the ChatList component on mount (AppSidebar keeps the panel alive
// across tab switches, so this is a one-shot fetch). The shape is kept
// stable so ChatSearch (Ctrl+K) still works.
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

export const useSidebarStore = defineStore('sidebar', {
  state: (): SidebarState => ({
    collapsed: false,
    activeTab: 'chats',
    searchQuery: '',
    searchOpen: false,
    chatList: [],
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
