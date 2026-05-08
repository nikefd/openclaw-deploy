/**
 * useSidebarActions.ts — Business logic for sidebar operations
 *
 * Encapsulates:
 * - Clear all chats (delete + UI update)
 * - Node switcher logic (if needed)
 * - Settings modal state
 *
 * Follows clean architecture: composable = use case + orchestration layer
 */

import { ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useSidebarStore } from '@/stores/sidebar'
import { deleteChat } from '@/api/chats'

export function useSidebarActions() {
  const sidebar = useSidebarStore()
  const { chatList } = storeToRefs(sidebar)
  
  const isLoading = ref(false)
  const error = ref<string | null>(null)

  /**
   * Clear all chats:
   * 1. Get chat list from sidebar store
   * 2. Delete each chat via API
   * 3. Clear sidebar state
   */
  async function clearAllChats(): Promise<void> {
    isLoading.value = true
    error.value = null

    try {
      // Get current list from sidebar store
      const currentChats = [...chatList.value]
      
      // Delete each chat
      const deletePromises = currentChats.map((chat) => 
        deleteChat(chat.id).catch(err => {
          console.warn(`[clearAllChats] failed to delete ${chat.id}:`, err)
        })
      )
      
      await Promise.all(deletePromises)

      // Clear sidebar state
      sidebar.setChatList([])
      sidebar.setActiveChatId(null)
      
      console.info(`[useSidebarActions] cleared ${currentChats.length} chats`)
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      error.value = `Failed to clear chats: ${msg}`
      console.error('[useSidebarActions] clearAllChats error:', err)
      throw err
    } finally {
      isLoading.value = false
    }
  }

  return {
    isLoading,
    error,
    clearAllChats,
  }
}
