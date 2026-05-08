// composables/useSidebar.ts — thin wrapper exposing the sidebar store with a
// few derived actions. The store is the source of truth; this composable just
// lets components avoid importing pinia directly.
import { storeToRefs } from 'pinia'
import { useSidebarStore } from '@/stores/sidebar'

export function useSidebar() {
  const store = useSidebarStore()
  const refs = storeToRefs(store)
  return {
    ...refs,
    toggleCollapsed: store.toggleCollapsed,
    setCollapsed: store.setCollapsed,
    setActiveTab: store.setActiveTab,
    setSearchQuery: store.setSearchQuery,
    openSearch: store.openSearch,
    closeSearch: store.closeSearch,
    setActiveChatId: store.setActiveChatId,
  }
}
