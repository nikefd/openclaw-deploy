/**
 * chat-stream.ts
 *
 * Socket.IO `/chat-run` namespace. This is the heart of Phase B:
 *
 *   start  -> kicks off a run, broadcasts deltas to room=sid
 *   resume -> client supplies lastSeq, we replay events with seq > lastSeq
 *   abort  -> AbortController on the active run
 *
 * Critical invariant: client disconnect MUST NOT cancel the upstream call.
 * The run lives in `activeRuns` keyed by sid; deltas keep flowing into the
 * room (which may have zero subscribers) and into the persistent events
 * store, so a reconnecting client can replay everything it missed.
 */

import { randomUUID } from 'node:crypto'
import type { Server, Socket, Namespace } from 'socket.io'
import type {
  ClientToServer,
  ServerToClient,
  StartRunRequest,
  AnyServerEvent,
} from '@oc/shared/events'
import { streamCopilot } from './upstream/copilot-bridge.js'
import {
  createChatEventsStore,
  defaultChatEventsStore,
  type ChatEventsStore,
  type StoredEvent,
} from './chat-events-store.js'

interface ActiveRun {
  sid: string
  runId: string
  seq: number
  abortController: AbortController
  collected: string
  startedAt: number
}

export interface AttachOptions {
  /** Override the persistent events store (tests inject a temp dir). */
  eventsStore?: ChatEventsStore
}

export function attachChatStream(
  io: Server<ClientToServer, ServerToClient>,
  opts: AttachOptions = {},
): Namespace<ClientToServer, ServerToClient> {
  const ns = io.of('/chat-run') as Namespace<ClientToServer, ServerToClient>
  const store = opts.eventsStore ?? defaultChatEventsStore
  const activeRuns = new Map<string, ActiveRun>() // key: sid

  ns.on('connection', (socket) => {
    // eslint-disable-next-line no-console
    console.log(`[chat-run] connect id=${socket.id}`)

    socket.on('start', (req: StartRunRequest) => {
      void handleStart(ns, store, activeRuns, socket, req)
    })

    socket.on('resume', (sid: string, lastSeq?: number) => {
      void handleResume(store, socket, sid, lastSeq ?? 0)
    })

    socket.on('abort', (sid: string) => {
      handleAbort(activeRuns, sid)
    })

    socket.on('disconnect', (reason) => {
      // eslint-disable-next-line no-console
      console.log(`[chat-run] disconnect id=${socket.id} reason=${reason}`)
      // NOTE: we DO NOT cancel any active run here. The run continues,
      // events keep being persisted, and a reconnect via `resume` replays.
    })
  })

  return ns
}

async function handleStart(
  ns: Namespace<ClientToServer, ServerToClient>,
  store: ChatEventsStore,
  activeRuns: Map<string, ActiveRun>,
  socket: Socket<ClientToServer, ServerToClient>,
  req: StartRunRequest,
): Promise<void> {
  if (!req || typeof req.sid !== 'string' || !req.sid) {
    return
  }
  const sid = req.sid
  await socket.join(sid)

  // If a run is already active for this sid, refuse politely (caller can
  // abort first). For Phase B we keep it simple: emit run.failed and bail.
  const existing = activeRuns.get(sid)
  if (existing) {
    const seq = existing.seq + 1
    existing.seq = seq
    const ev: AnyServerEvent = {
      type: 'run.failed',
      sid,
      runId: existing.runId,
      error: 'run already in progress for sid',
      seq,
    }
    ns.to(sid).emit('run.failed', stripType(ev))
    void persist(store, sid, ev)
    return
  }

  const runId = randomUUID()
  const run: ActiveRun = {
    sid,
    runId,
    seq: 0,
    abortController: new AbortController(),
    collected: '',
    startedAt: Date.now(),
  }
  activeRuns.set(sid, run)

  // seq 0: queued
  const queued: AnyServerEvent = { type: 'run.queued', sid, runId, seq: 0 }
  ns.to(sid).emit('run.queued', stripType(queued))
  await persist(store, sid, queued)

  // Kick off upstream — DO NOT await; we want the socket handler to return
  // so the next 'resume'/'abort' frames can be processed concurrently.
  void runUpstream(ns, store, activeRuns, run, req)
}

async function runUpstream(
  ns: Namespace<ClientToServer, ServerToClient>,
  store: ChatEventsStore,
  activeRuns: Map<string, ActiveRun>,
  run: ActiveRun,
  req: StartRunRequest,
): Promise<void> {
  const { sid, runId } = run

  // Optional 'run.started' bump — not strictly required by the spec, but it
  // gives clients a deterministic transition out of 'queued'. It is part of
  // the ServerToClient interface, so we include it.
  run.seq += 1
  const started: AnyServerEvent = {
    type: 'run.started',
    sid,
    runId,
    seq: run.seq,
  }
  ns.to(sid).emit('run.started', stripType(started))
  await persist(store, sid, started)

  // Build a minimal messages array — Phase B does not yet hydrate full
  // history on the server side; we forward whatever the client sent + the
  // user's input as a final user message.
  const upstreamMessages: Array<{ role: string; content: string }> = []
  if (Array.isArray(req.history)) {
    for (const m of req.history) {
      if (typeof (m as any)?.text === 'string') {
        upstreamMessages.push({ role: m.role, content: (m as any).text })
      }
    }
  }
  upstreamMessages.push({ role: 'user', content: req.input })

  await streamCopilot({
    messages: upstreamMessages,
    model: req.model,
    signal: run.abortController.signal,
    onDelta: (delta) => {
      run.seq += 1
      run.collected += delta
      const ev: AnyServerEvent = {
        type: 'message.delta',
        sid,
        runId,
        delta,
        seq: run.seq,
      }
      ns.to(sid).emit('message.delta', stripType(ev))
      void persist(store, sid, ev)
    },
    onComplete: (output) => {
      run.seq += 1
      const ev: AnyServerEvent = {
        type: 'run.completed',
        sid,
        runId,
        output: output || run.collected,
        usage: {},
        seq: run.seq,
      }
      ns.to(sid).emit('run.completed', stripType(ev))
      void persist(store, sid, ev).then(() => store.flush(sid))
      activeRuns.delete(sid)
    },
    onError: (err) => {
      run.seq += 1
      const ev: AnyServerEvent = {
        type: 'run.failed',
        sid,
        runId,
        error: err?.message || String(err),
        seq: run.seq,
      }
      ns.to(sid).emit('run.failed', stripType(ev))
      void persist(store, sid, ev).then(() => store.flush(sid))
      activeRuns.delete(sid)
    },
  })
}

async function handleResume(
  store: ChatEventsStore,
  socket: Socket<ClientToServer, ServerToClient>,
  sid: string,
  lastSeq: number,
): Promise<void> {
  if (!sid) return
  await socket.join(sid)
  const missed = await store.getEventsAfter(sid, lastSeq)
  for (const ev of missed) {
    const kind = ev.kind
    // emit only to the resuming socket — the room broadcast already handles
    // any *new* deltas after this point.
    socket.emit(kind, ev.data as any)
  }
}

function handleAbort(activeRuns: Map<string, ActiveRun>, sid: string): void {
  const run = activeRuns.get(sid)
  if (!run) return
  run.abortController.abort()
  // run.failed is emitted by the onError path of streamCopilot.
}

// ---------- helpers ----------

function stripType<T extends { type: string }>(ev: T): Omit<T, 'type'> {
  const { type: _t, ...rest } = ev
  return rest
}

async function persist(
  store: ChatEventsStore,
  sid: string,
  ev: AnyServerEvent,
): Promise<void> {
  const { type, ...data } = ev
  const stored: StoredEvent = {
    kind: type,
    data: data as Record<string, unknown>,
    seq: (ev as any).seq as number,
    ts: Date.now(),
  }
  await store.appendEvent(sid, stored)
}

// re-export for convenience
export { createChatEventsStore }
