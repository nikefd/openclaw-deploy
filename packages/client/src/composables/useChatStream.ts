/**
 * composables/useChatStream.ts
 *
 * Wraps the singleton Socket.IO client with a reactive run-state model and
 * the resume-on-reconnect logic that is the whole point of Phase B.
 *
 * The contract:
 *   - state.lastSeq is bumped on every server event (run.queued, deltas,
 *     run.completed, run.failed, etc.)
 *   - lastSeq is mirrored into sessionStorage under
 *     `oc_v2_lastseq_${sid}` so a hard page refresh can resume the run.
 *   - On `connect` (initial *or* reconnect), if a sessionId is bound and
 *     lastSeq > 0, we automatically `emit('resume', sid, lastSeq)` so the
 *     server replays anything we missed.
 */

import { reactive, watch, type Ref } from 'vue'
import type { StartRunRequest } from '@oc/shared/events'
import { getChatSocket, type ChatSocket } from '../api/chat-socket'
import { useChatStore } from '../stores/chat'

export type ChatStreamStatus =
  | 'idle'
  | 'queued'
  | 'streaming'
  | 'completed'
  | 'failed'

export interface ChatStreamState {
  status: ChatStreamStatus
  delta: string
  lastSeq: number
  error: string | null
  /** number of pending events we processed since the last reset (tests) */
  queue: number
}

export interface UseChatStreamOptions {
  sessionId: Ref<string | null>
}

const SS_KEY = (sid: string) => `oc_v2_lastseq_${sid}`

function readPersistedSeq(sid: string | null): number {
  if (!sid || typeof sessionStorage === 'undefined') return 0
  const v = sessionStorage.getItem(SS_KEY(sid))
  if (!v) return 0
  const n = Number(v)
  return Number.isFinite(n) && n > 0 ? n : 0
}

function writePersistedSeq(sid: string | null, seq: number): void {
  if (!sid || typeof sessionStorage === 'undefined') return
  try {
    sessionStorage.setItem(SS_KEY(sid), String(seq))
  } catch {
    /* quota exhausted — ignore */
  }
}

export function useChatStream(opts: UseChatStreamOptions) {
  const state = reactive<ChatStreamState>({
    status: 'idle',
    delta: '',
    lastSeq: 0,
    error: null,
    queue: 0,
  })

  const store = useChatStore()
  const socket: ChatSocket = getChatSocket()

  // Hydrate lastSeq from sessionStorage when sid changes.
  watch(
    () => opts.sessionId.value,
    (sid) => {
      state.lastSeq = readPersistedSeq(sid)
    },
    { immediate: true },
  )

  function bump(seq: number) {
    if (typeof seq !== 'number') return
    if (seq > state.lastSeq) {
      state.lastSeq = seq
      writePersistedSeq(opts.sessionId.value, seq)
    }
    state.queue += 1
  }

  // ---- server -> client wiring (idempotent install) ----

  let installed = false
  function installListeners() {
    if (installed) return
    installed = true

    socket.on('connect', () => {
      const sid = opts.sessionId.value
      if (sid && state.lastSeq > 0) {
        socket.emit('resume', sid, state.lastSeq)
      }
    })

    socket.on('run.queued', (e) => {
      state.status = 'queued'
      state.error = null
      state.delta = ''
      bump(e.seq)
    })

    socket.on('run.started', (e) => {
      state.status = 'streaming'
      bump(e.seq)
    })

    socket.on('message.delta', (e) => {
      state.status = 'streaming'
      state.delta += e.delta
      store.appendDelta(e.sid, e.delta)
      bump(e.seq)
    })

    socket.on('tool.started', (e) => {
      bump(e.seq)
    })

    socket.on('tool.completed', (e) => {
      bump(e.seq)
    })

    socket.on('run.completed', (e) => {
      state.status = 'completed'
      bump(e.seq)
      store.commitStreaming(e.sid)
    })

    socket.on('run.failed', (e) => {
      state.status = 'failed'
      state.error = e.error
      bump(e.seq)
      store.commitStreaming(e.sid)
    })
  }

  // ---- public api ----

  function connect() {
    installListeners()
    if (!socket.connected) socket.connect()
  }

  function disconnect() {
    socket.disconnect()
  }

  function start(req: StartRunRequest) {
    installListeners()
    state.status = 'queued'
    state.delta = ''
    state.error = null
    state.queue = 0
    state.lastSeq = 0
    writePersistedSeq(req.sid, 0)
    if (!socket.connected) {
      socket.once('connect', () => socket.emit('start', req))
      socket.connect()
    } else {
      socket.emit('start', req)
    }
  }

  function abort() {
    const sid = opts.sessionId.value
    if (!sid) return
    socket.emit('abort', sid)
  }

  return { state, connect, disconnect, start, abort }
}
