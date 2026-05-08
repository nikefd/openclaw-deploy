/**
 * chat-stream.test.ts — Phase B verification.
 *
 * Three scenarios (all under MOCK_UPSTREAM=1, 100ms/frame, 10 frames):
 *   1. happy path: start -> queued -> N deltas -> completed, monotonic seq
 *   2. resume: drop client mid-stream, server keeps going, reconnect+resume
 *      replays only seq>lastSeq and final delivery is the full stream
 *   3. abort: emit('abort', sid) -> run.failed with error 'aborted'
 */

import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import http from 'node:http'
import { promises as fs } from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { Server as IOServer } from 'socket.io'
import { io as ioc, type Socket as ClientSocket } from 'socket.io-client'
import type { ClientToServer, ServerToClient } from '@oc/shared/events'
import {
  attachChatStream,
  createChatEventsStore,
} from '../chat-stream.js'

process.env.MOCK_UPSTREAM = '1'

let httpServer: http.Server
let io: IOServer<ClientToServer, ServerToClient>
let url: string
let tmpDir: string

beforeAll(async () => {
  tmpDir = await fs.mkdtemp(path.join(os.tmpdir(), 'oc-chat-stream-'))
  const store = createChatEventsStore({ chatsDir: tmpDir, debounceMs: 20 })
  httpServer = http.createServer()
  io = new IOServer(httpServer)
  attachChatStream(io, { eventsStore: store })
  await new Promise<void>((r) => httpServer.listen(0, r))
  const addr = httpServer.address()
  if (!addr || typeof addr === 'string') throw new Error('no address')
  url = `http://127.0.0.1:${addr.port}`
})

afterAll(async () => {
  await new Promise<void>((r) => io.close(() => r()))
  await new Promise<void>((r) => httpServer.close(() => r()))
  try {
    await fs.rm(tmpDir, { recursive: true, force: true })
  } catch {
    /* ignore */
  }
})

function connect(): ClientSocket<ServerToClient, ClientToServer> {
  return ioc(`${url}/chat-run`, {
    transports: ['websocket'],
    reconnection: false,
    forceNew: true,
  })
}

interface Captured {
  kind: string
  seq: number
  payload: any
}

function captureAll(c: ClientSocket<ServerToClient, ClientToServer>): Captured[] {
  const out: Captured[] = []
  const kinds: Array<keyof ServerToClient> = [
    'run.queued',
    'run.started',
    'message.delta',
    'tool.started',
    'tool.completed',
    'run.completed',
    'run.failed',
  ]
  for (const k of kinds) {
    c.on(k as any, (payload: any) => {
      out.push({ kind: k as string, seq: payload?.seq ?? -1, payload })
    })
  }
  return out
}

describe('chat-run namespace', () => {
  it('happy path: queued -> deltas -> completed with monotonic seq', async () => {
    const c = connect()
    const events = captureAll(c)
    await new Promise<void>((r) => c.on('connect', () => r()))

    const sid = `t1-${Date.now()}`
    c.emit('start', { sid, input: 'hi' })

    await new Promise<void>((resolve, reject) => {
      const timeout = setTimeout(
        () => reject(new Error('timeout waiting for run.completed')),
        5000,
      )
      c.on('run.completed', () => {
        clearTimeout(timeout)
        resolve()
      })
      c.on('run.failed', (e) => {
        clearTimeout(timeout)
        reject(new Error('unexpected run.failed: ' + JSON.stringify(e)))
      })
    })

    c.disconnect()

    const kinds = events.map((e) => e.kind)
    expect(kinds[0]).toBe('run.queued')
    expect(kinds[kinds.length - 1]).toBe('run.completed')
    const deltas = events.filter((e) => e.kind === 'message.delta')
    expect(deltas.length).toBe(10) // mock generator emits 10 frames

    // seq must be strictly monotonic increasing
    for (let i = 1; i < events.length; i++) {
      expect(events[i].seq).toBeGreaterThan(events[i - 1].seq)
    }
    expect(events[0].seq).toBe(0) // run.queued is seq=0
  })

  it('resume: client disconnects mid-stream, reconnects with lastSeq', async () => {
    const sid = `t2-${Date.now()}`

    const c1 = connect()
    const events1 = captureAll(c1)
    await new Promise<void>((r) => c1.on('connect', () => r()))
    c1.emit('start', { sid, input: 'hi' })

    // Wait until we've seen at least 3 deltas
    await new Promise<void>((resolve, reject) => {
      const timeout = setTimeout(
        () => reject(new Error('timeout waiting for 3 deltas')),
        3000,
      )
      const check = () => {
        const deltas = events1.filter((e) => e.kind === 'message.delta')
        if (deltas.length >= 3) {
          clearTimeout(timeout)
          resolve()
        } else {
          setTimeout(check, 30)
        }
      }
      check()
    })

    // Snapshot what we got and the highest seq seen.
    const lastSeq = events1[events1.length - 1].seq
    const seenSeqsBeforeDc = events1.map((e) => e.seq)
    expect(lastSeq).toBeGreaterThanOrEqual(3)

    c1.disconnect()
    // Let the server keep streaming for a while without us listening.
    await new Promise((r) => setTimeout(r, 250))

    // Reconnect a fresh client and resume from lastSeq.
    const c2 = connect()
    const events2 = captureAll(c2)
    await new Promise<void>((r) => c2.on('connect', () => r()))
    c2.emit('resume', sid, lastSeq)

    // Wait for run.completed (may come from replay OR from live broadcast).
    await new Promise<void>((resolve, reject) => {
      const timeout = setTimeout(
        () => reject(new Error('timeout waiting for completed on c2')),
        5000,
      )
      c2.on('run.completed', () => {
        clearTimeout(timeout)
        resolve()
      })
      c2.on('run.failed', (e) => {
        clearTimeout(timeout)
        reject(new Error('unexpected run.failed on c2: ' + JSON.stringify(e)))
      })
    })

    c2.disconnect()

    // c2 must NOT receive any seq <= lastSeq
    for (const e of events2) {
      expect(e.seq).toBeGreaterThan(lastSeq)
    }
    // Combined seq set (c1 + c2) must cover the full run with no holes
    const combined = new Set<number>([...seenSeqsBeforeDc, ...events2.map((e) => e.seq)])
    const max = Math.max(...combined)
    for (let s = 0; s <= max; s++) {
      expect(combined.has(s)).toBe(true)
    }
    // And the final event must be run.completed
    expect(events2[events2.length - 1].kind).toBe('run.completed')
  })

  it('abort: emit("abort", sid) -> run.failed with error "aborted"', async () => {
    const sid = `t3-${Date.now()}`
    const c = connect()
    const events = captureAll(c)
    await new Promise<void>((r) => c.on('connect', () => r()))
    c.emit('start', { sid, input: 'hi' })

    // Wait for at least one delta so we know the run is in flight.
    await new Promise<void>((resolve, reject) => {
      const timeout = setTimeout(
        () => reject(new Error('timeout waiting for first delta')),
        3000,
      )
      c.on('message.delta', () => {
        clearTimeout(timeout)
        resolve()
      })
    })

    c.emit('abort', sid)

    const failed = await new Promise<any>((resolve, reject) => {
      const timeout = setTimeout(
        () => reject(new Error('timeout waiting for run.failed')),
        3000,
      )
      c.on('run.failed', (e) => {
        clearTimeout(timeout)
        resolve(e)
      })
      c.on('run.completed', () => {
        clearTimeout(timeout)
        reject(new Error('unexpected completion after abort'))
      })
    })

    expect(failed.error).toBe('aborted')
    // The very last event in our log must be the run.failed we just got.
    expect(events[events.length - 1].kind).toBe('run.failed')

    c.disconnect()
  })
})
