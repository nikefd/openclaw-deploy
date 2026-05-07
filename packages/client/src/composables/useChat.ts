/**
 * useChat — high-level send/abort/regenerate API for components.
 *
 * Wraps useChatStream (Phase B socket lifecycle) + chatStore (per-sid
 * history). On run.completed/failed we materialise messages into the store.
 */

import { computed, watch, type Ref } from 'vue'
import { getChatSocket } from '@/api/chat-socket'
import { useChatStream } from '@/composables/useChatStream'
import { useChatStore } from '@/stores/chat'
import type { ChatMessage } from '@oc/shared/chat'
import type {
  RunCompletedEvent,
  RunFailedEvent,
} from '@oc/shared/events'

export type ChatStatus = 'idle' | 'queued' | 'streaming' | 'completed' | 'failed'

let listenersBound = false

function bindRunFinalizers(store: ReturnType<typeof useChatStore>) {
  if (listenersBound) return
  listenersBound = true
  const socket = getChatSocket()

  socket.on('run.completed', (e: RunCompletedEvent) => {
    const list = store.ensureList(e.sid)
    list.push({
      id: `m_${e.runId}`,
      role: 'assistant',
      createdAt: Date.now(),
      content: [{ type: 'text', text: e.output ?? '' }],
      text: e.output ?? '',
      usage: e.usage,
    })
  })

  socket.on('run.failed', (e: RunFailedEvent) => {
    const list = store.ensureList(e.sid)
    list.push({
      id: `m_err_${e.runId}`,
      role: 'system',
      createdAt: Date.now(),
      content: [{ type: 'text', text: `[run failed] ${e.error}` }],
      text: `[run failed] ${e.error}`,
    })
  })
}

export interface UseChatHandle {
  messages: Ref<ChatMessage[]>
  status: Ref<ChatStatus>
  streamingDelta: Ref<string>
  isStreaming: Ref<boolean>
  error: Ref<string | null>
  send: (text: string, opts?: { model?: string }) => void
  abort: () => void
  regenerate: () => void
  connect: () => void
}

export function useChat(sid: Ref<string>): UseChatHandle {
  const store = useChatStore()
  bindRunFinalizers(store)

  const sidRef = computed<string | null>(() => sid.value || null)
  const stream = useChatStream({ sessionId: sidRef })

  watch(
    sid,
    (id) => {
      if (id) store.ensureList(id)
      store.currentSid = id
    },
    { immediate: true },
  )

  const messages = computed<ChatMessage[]>(() => store.ensureList(sid.value))
  const status = computed<ChatStatus>(() => stream.state.status as ChatStatus)
  const streamingDelta = computed<string>(() =>
    store.streaming.sid === sid.value ? store.streaming.delta : '',
  )
  const isStreaming = computed<boolean>(
    () => stream.state.status === 'streaming' || stream.state.status === 'queued',
  )
  const error = computed<string | null>(() => stream.state.error)

  function send(text: string, opts: { model?: string } = {}) {
    const trimmed = text.trim()
    if (!trimmed) return
    const userMsg: ChatMessage = {
      id: `u_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
      role: 'user',
      createdAt: Date.now(),
      content: [{ type: 'text', text: trimmed }],
      text: trimmed,
    }
    store.appendMessage(sid.value, userMsg)
    stream.start({ sid: sid.value, input: trimmed, model: opts.model })
  }

  function abort() {
    stream.abort()
    const buffered = store.streaming.sid === sid.value ? store.streaming.delta : ''
    const list = store.ensureList(sid.value)
    if (buffered) {
      list.push({
        id: `m_abort_${Date.now()}`,
        role: 'assistant',
        createdAt: Date.now(),
        content: [{ type: 'text', text: buffered + '\n\n_[已中断]_' }],
        text: buffered + '\n\n_[已中断]_',
      })
    } else {
      list.push({
        id: `m_abort_${Date.now()}`,
        role: 'system',
        createdAt: Date.now(),
        content: [{ type: 'text', text: '[已中断]' }],
        text: '[已中断]',
      })
    }
    store.clearStreaming()
  }

  function regenerate() {
    const list = store.ensureList(sid.value)
    while (list.length > 0 && list[list.length - 1]!.role !== 'user') {
      list.pop()
    }
    const lastUser = list[list.length - 1]
    if (!lastUser || lastUser.role !== 'user') return
    const text = lastUser.text ?? ''
    if (!text) return
    stream.start({ sid: sid.value, input: text })
  }

  function connect() { stream.connect() }

  return { messages, status, streamingDelta, isStreaming, error, send, abort, regenerate, connect }
}
