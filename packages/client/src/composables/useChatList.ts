/**
 * useChatList — Phase E4 reactive sidebar chat list.
 *
 * One-shot fetcher over /v2/api/chats with explicit reload. Stays as a
 * factory (not a singleton) so tests can mount fresh state, but the
 * sidebar mounts it once at app boot via AppSidebar.
 */

import { ref, type Ref } from 'vue'
import { fetchChatList, type ChatListItemDTO } from '@/api/chats'

export interface UseChatListAPI {
  chats: Ref<ChatListItemDTO[]>
  loading: Ref<boolean>
  error: Ref<string | null>
  reload: () => Promise<void>
}

export function useChatList(): UseChatListAPI {
  const chats = ref<ChatListItemDTO[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function reload(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      chats.value = await fetchChatList()
    } catch (e) {
      error.value = e instanceof Error ? e.message : String(e)
    } finally {
      loading.value = false
    }
  }

  return { chats, loading, error, reload }
}
