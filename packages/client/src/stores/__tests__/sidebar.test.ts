import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useSidebarStore } from '@/stores/sidebar'

describe('stores/sidebar', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('toggleCollapsed flips collapsed bool', () => {
    const s = useSidebarStore()
    expect(s.collapsed).toBe(false)
    s.toggleCollapsed()
    expect(s.collapsed).toBe(true)
    s.toggleCollapsed()
    expect(s.collapsed).toBe(false)
  })

  it('width getter reflects collapsed state', () => {
    const s = useSidebarStore()
    expect(s.width).toBe(240)
    s.setCollapsed(true)
    expect(s.width).toBe(56)
  })

  it('setActiveTab updates activeTab', () => {
    const s = useSidebarStore()
    expect(s.activeTab).toBe('chats')
    s.setActiveTab('memory')
    expect(s.activeTab).toBe('memory')
    s.setActiveTab('skills')
    expect(s.activeTab).toBe('skills')
  })

  it('search open/close manages flag and query', () => {
    const s = useSidebarStore()
    s.setSearchQuery('hello')
    s.openSearch()
    expect(s.searchOpen).toBe(true)
    s.closeSearch()
    expect(s.searchOpen).toBe(false)
    expect(s.searchQuery).toBe('')
  })

  it('chat list starts empty (Phase E4 — hydrated from REST)', () => {
    const s = useSidebarStore()
    expect(s.chatList).toEqual([])
  })

  it('setChatList replaces the list', () => {
    const s = useSidebarStore()
    s.setChatList([
      { id: 'a', title: 't', preview: 'p', lastMessageAt: 1 },
    ])
    expect(s.chatList).toHaveLength(1)
    expect(s.chatList[0]!.id).toBe('a')
  })
})
