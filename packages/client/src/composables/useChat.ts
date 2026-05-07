/**
 * useChat — high-level send/abort/regenerate API for components.
 *
 * Phase E2b: switched from socket.io fixture path to real SSE against
 * `/v2/api/copilot/stream`. The legacy socket transport (chat-socket.ts +
 * useChatStream.ts) is left in tree for now and will be removed once the
 * SSE path proves out in production.
 *
 * Lifecycle:
 *   - send(text): append user msg, open SSE, accumulate deltas into the
 *     chat store streaming buffer, then commit a single assistant message
 *     and PUT the chat to /v2/api/chats/:id.
 *   - abort(): cancel the in-flight SSE; preserve buffered text + "[已中断]".
 *   - on error: append a "⚠ ..." assistant message; never auto-retry
 *     (tryRecover was the root cause of older infinite-loop bugs —
 *     see MEMORY.md 4/25).
 */

import { computed, ref, watch, type Ref } from 'vue'
import { apiUrl } from '@/api/_base'
import { openSseStream, type SseError, type SseStreamHandle } from '@/composables/useSseStream'
import { useChatStore } from '@/stores/chat'
import type { ChatMessage } from '@oc/shared/chat'

export type ChatStatus = 'idle' | 'queued' | 'streaming' | 'completed' | 'failed'

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

interface ApiMsg { role: 'user' | 'assistant' | 'system'; content: string }

function toApiMessages(list: ChatMessage[], finalUserText: string): ApiMsg[] {
  const out: ApiMsg[] = []
  for (const m of list) {
    if (m.role === 'tool') continue
    const text = m.text ?? ''
    if (!text) continue
    out.push({ role: m.role, content: text })
  }
  // The caller already pushed the user msg into the list; if for some
  // reason it isn't last, force-append the freshly-typed text.
  const last = out[out.length - 1]
  if (!last || last.role !== 'user' || last.content !== finalUserText) {
    out.push({ role: 'user', content: finalUserText })
  }
  return out
}

async function persistChat(sid: string, messages: ChatMessage[]): Promise<void> {
  try {
    await fetch(apiUrl(`/chats/${encodeURIComponent(sid)}`), {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        id: sid,
        updatedAt: Date.now(),
        messages,
      }),
    })
  } catch {
    // Persistence is best-effort; UI already shows the message.
  }
}

function errorBlurb(err: SseError): string {
  switch (err.kind) {
    case 'network': return '⚠ 后端暂不可用'
    case 'http':    return `⚠ 连接中断 (HTTP ${err.status ?? '?'})`
    case 'timeout': return '⚠ 连接中断（30 秒无响应）'
    case 'aborted': return '' // handled by abort() path
    default:        return `⚠ 连接中断（${err.message}）`
  }
}

export function useChat(sid: Ref<string>): UseChatHandle {
  const store = useChatStore()

  const status = ref<ChatStatus>('idle')
  const error = ref<string | null>(null)
  let active: SseStreamHandle | null = null

  watch(
    sid,
    (id) => {
      if (id) store.ensureList(id)
      store.currentSid = id
      // Hard reset transient state when the user switches chats.
      status.value = 'idle'
      error.value = null
    },
    { immediate: true },
  )

  const messages = computed<ChatMessage[]>(() => store.ensureList(sid.value))
  const streamingDelta = computed<string>(() =>
    store.streaming.sid === sid.value ? store.streaming.delta : '',
  )
  const isStreaming = computed<boolean>(
    () => status.value === 'streaming' || status.value === 'queued',
  )

  function commitAssistant(text: string, suffix = ''): void {
    const list = store.ensureList(sid.value)
    list.push({
      id: `m_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
      role: 'assistant',
      createdAt: Date.now(),
      content: [{ type: 'text', text: text + suffix }],
      text: text + suffix,
    })
    void persistChat(sid.value, list.slice())
  }

  function send(text: string, opts: { model?: string } = {}) {
    const trimmed = text.trim()
    if (!trimmed) return
    if (active) {
      // Caller asked to send while a stream is in flight; ignore (UI
      // should disable the send button, but we keep this defensive).
      return
    }

    const list = store.ensureList(sid.value)
    const userMsg: ChatMessage = {
      id: `u_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
      role: 'user',
      createdAt: Date.now(),
      content: [{ type: 'text', text: trimmed }],
      text: trimmed,
    }
    list.push(userMsg)

    // Reset streaming buffer for this sid.
    store.streaming.sid = sid.value
    store.streaming.delta = ''
    status.value = 'streaming'
    error.value = null

    const apiMessages = toApiMessages(list.slice(0, -1), trimmed)
    const targetSid = sid.value

    active = openSseStream(
      { sid: targetSid, messages: apiMessages, model: opts.model },
      {
        onDelta: (chunk) => {
          if (store.streaming.sid !== targetSid) {
            store.streaming.sid = targetSid
            store.streaming.delta = ''
          }
          store.streaming.delta += chunk
        },
        onDone: () => {
          const buffered = store.streaming.sid === targetSid ? store.streaming.delta : ''
          if (buffered) {
            commitAssistant(buffered)
          }
          store.clearStreaming()
          status.value = 'completed'
          active = null
        },
        onError: (err) => {
          const buffered = store.streaming.sid === targetSid ? store.streaming.delta : ''
          if (err.kind === 'aborted') {
            // abort() handles UX itself.
            store.clearStreaming()
            status.value = 'idle'
            active = null
            return
          }
          const blurb = errorBlurb(err)
          if (buffered) {
            commitAssistant(buffered, '\n\n' + blurb)
          } else {
            commitAssistant(blurb)
          }
          error.value = err.message
          store.clearStreaming()
          status.value = 'failed'
          active = null
        },
      },
    )
  }

  function abort() {
    if (!active) return
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
      void persistChat(sid.value, list.slice())
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
    status.value = 'idle'
    active.abort()
    active = null
  }

  function regenerate() {
    if (active) return
    const list = store.ensureList(sid.value)
    while (list.length > 0 && list[list.length - 1]!.role !== 'user') {
      list.pop()
    }
    const lastUser = list[list.length - 1]
    if (!lastUser || lastUser.role !== 'user') return
    const text = lastUser.text ?? ''
    if (!text) return
    // Pop the trailing user msg; send() will re-append it.
    list.pop()
    send(text)
  }

  function connect() {
    // No-op under SSE — kept for backwards-compat with components that
    // still call chat.connect() on mount (ChatPane).
  }

  return { messages, status, streamingDelta, isStreaming, error, send, abort, regenerate, connect }
}
