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

  it('chat list seeded with stub data', () => {
    const s = useSidebarStore()
    expect(s.chatList.length).toBe(5)
    expect(s.chatList[0]!.id).toBe('stub-1')
  })
})
