/**
 * stores/chat.ts — shared chat state.
 *
 * Phase B introduced this with just a streaming-delta buffer. Phase C1
 * widens it so message history (per-sid) and the currently selected sid
 * live here too.
 */

import { defineStore } from 'pinia'
import { reactive, ref } from 'vue'
import type { ChatMessage } from '@oc/shared/chat'

export const useChatStore = defineStore('chat', () => {
  const currentSid = ref<string | null>(null)
  const messages = reactive(new Map<string, ChatMessage[]>())
  const streaming = reactive<{ sid: string | null; delta: string }>({
    sid: null,
    delta: '',
  })

  function ensureList(sid: string): ChatMessage[] {
    let list = messages.get(sid)
    if (!list) {
      list = reactive<ChatMessage[]>([])
      messages.set(sid, list)
    }
    return list
  }

  function appendMessage(sid: string, msg: ChatMessage): void {
    ensureList(sid).push(msg)
  }

  function replaceMessages(sid: string, list: ChatMessage[]): void {
    messages.set(sid, reactive(list.slice()))
  }

  function popLastByRole(sid: string, role: ChatMessage['role']): ChatMessage | null {
    const list = messages.get(sid)
    if (!list || list.length === 0) return null
    for (let i = list.length - 1; i >= 0; i--) {
      if (list[i]!.role === role) {
        return list.splice(i, 1)[0] ?? null
      }
    }
    return null
  }

  function appendDelta(sid: string, delta: string) {
    if (streaming.sid !== sid) {
      streaming.sid = sid
      streaming.delta = ''
    }
    streaming.delta += delta
  }

  function commitStreaming(sid: string) {
    if (streaming.sid !== sid) return
    streaming.sid = null
    streaming.delta = ''
  }

  function clearStreaming() {
    streaming.sid = null
    streaming.delta = ''
  }

  function clearSession(sid: string) {
    messages.delete(sid)
    if (streaming.sid === sid) clearStreaming()
  }

  return {
    currentSid,
    messages,
    streaming,
    ensureList,
    appendMessage,
    replaceMessages,
    popLastByRole,
    appendDelta,
    commitStreaming,
    clearStreaming,
    clearSession,
  }
})
