/**
 * stores/chat.ts — minimal Pinia store for Phase B.
 *
 * Phase C will replace this with a richer model. For now we only need a
 * place to hold the in-flight delta buffer per sid so HelloView (and any
 * future composable consumer) can render it reactively.
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

  return {
    currentSid,
    messages,
    streaming,
    appendDelta,
    commitStreaming,
    clearStreaming,
  }
})
