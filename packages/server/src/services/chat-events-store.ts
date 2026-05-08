/**
 * chat-events-store.ts
 *
 * Phase B persistence for the per-session "events" stream that backs
 * Socket.IO replay-on-resume. Stored as `events: [...]` field on
 * `<chatsDir>/<sid>.json` — extends, never replaces, the legacy chat file.
 *
 * Writes are debounced (200ms) per-sid and flushed via atomic rename
 * (`<file>.tmp.<rand>` -> `<file>`) so a crash mid-write can't truncate the
 * existing chat. fs/promises only — no sync IO.
 */

import { promises as fs } from 'node:fs'
import path from 'node:path'
import os from 'node:os'
import type { AnyServerEvent } from '@oc/shared/events'

export interface StoredEvent {
  /** event kind, e.g. 'message.delta' */
  kind: AnyServerEvent['type']
  /** raw payload (the event minus the discriminator) */
  data: Record<string, unknown>
  seq: number
  /** Unix ms */
  ts: number
}

export interface ChatEventsStoreOptions {
  /** absolute dir holding <sid>.json files */
  chatsDir: string
  /** debounce (ms) for write coalescing — default 200 */
  debounceMs?: number
  /** max events kept on disk per chat — default 500 */
  keepLast?: number
}

interface PendingState {
  /** in-memory snapshot of events[] (truncated to keepLast) */
  events: StoredEvent[]
  /** active debounce timer */
  timer: NodeJS.Timeout | null
  /** whether at least one flush has loaded the file */
  loaded: boolean
  /** chained promise so callers can await the latest flush */
  flushPromise: Promise<void>
}

export interface ChatEventsStore {
  appendEvent(sid: string, ev: StoredEvent): Promise<void>
  getEventsAfter(sid: string, lastSeq: number): Promise<StoredEvent[]>
  /** force-flush any pending debounced write for `sid` */
  flush(sid: string): Promise<void>
  /** flush every pending sid (used in tests / shutdown) */
  flushAll(): Promise<void>
  truncateEvents(sid: string, keepLast?: number): Promise<void>
}

export function createChatEventsStore(opts: ChatEventsStoreOptions): ChatEventsStore {
  const chatsDir = opts.chatsDir
  const debounceMs = opts.debounceMs ?? 200
  const defaultKeepLast = opts.keepLast ?? 500

  const pending = new Map<string, PendingState>()

  function chatPath(sid: string): string {
    return path.join(chatsDir, `${sid}.json`)
  }

  async function readChatFile(sid: string): Promise<Record<string, unknown>> {
    try {
      const raw = await fs.readFile(chatPath(sid), 'utf8')
      return JSON.parse(raw)
    } catch (err: any) {
      if (err && err.code === 'ENOENT') return {}
      throw err
    }
  }

  async function atomicWrite(sid: string, data: Record<string, unknown>): Promise<void> {
    await fs.mkdir(chatsDir, { recursive: true })
    const tmp = chatPath(sid) + `.tmp.${process.pid}.${Math.random().toString(36).slice(2, 8)}`
    await fs.writeFile(tmp, JSON.stringify(data), 'utf8')
    await fs.rename(tmp, chatPath(sid))
  }

  async function ensureLoaded(sid: string): Promise<PendingState> {
    let st = pending.get(sid)
    if (st && st.loaded) return st
    if (!st) {
      st = { events: [], timer: null, loaded: false, flushPromise: Promise.resolve() }
      pending.set(sid, st)
    }
    const existing = await readChatFile(sid)
    const arr = Array.isArray(existing.events) ? (existing.events as StoredEvent[]) : []
    st.events = arr.slice(-defaultKeepLast)
    st.loaded = true
    return st
  }

  async function doFlush(sid: string): Promise<void> {
    const st = pending.get(sid)
    if (!st) return
    if (st.timer) {
      clearTimeout(st.timer)
      st.timer = null
    }
    const existing = await readChatFile(sid)
    existing.events = st.events.slice(-defaultKeepLast)
    await atomicWrite(sid, existing)
  }

  function scheduleFlush(sid: string): void {
    const st = pending.get(sid)
    if (!st) return
    if (st.timer) return
    st.timer = setTimeout(() => {
      st.timer = null
      st.flushPromise = st.flushPromise.then(() => doFlush(sid)).catch((err) => {
        // eslint-disable-next-line no-console
        console.error(`[chat-events-store] flush failed sid=${sid}:`, err)
      })
    }, debounceMs)
  }

  return {
    async appendEvent(sid, ev) {
      const st = await ensureLoaded(sid)
      st.events.push(ev)
      if (st.events.length > defaultKeepLast * 2) {
        st.events = st.events.slice(-defaultKeepLast)
      }
      scheduleFlush(sid)
    },

    async getEventsAfter(sid, lastSeq) {
      // Prefer in-memory if present (covers writes still in debounce window);
      // fall back to disk for cold-start / cross-process reads.
      const st = pending.get(sid)
      if (st && st.loaded) {
        return st.events.filter((e) => e.seq > lastSeq)
      }
      const existing = await readChatFile(sid)
      const arr = Array.isArray(existing.events) ? (existing.events as StoredEvent[]) : []
      return arr.filter((e) => e.seq > lastSeq)
    },

    async flush(sid) {
      const st = pending.get(sid)
      if (!st) return
      // chain through pending promise so we await any in-flight write too
      st.flushPromise = st.flushPromise.then(() => doFlush(sid))
      await st.flushPromise
    },

    async flushAll() {
      const sids = Array.from(pending.keys())
      await Promise.all(sids.map((s) => this.flush(s)))
    },

    async truncateEvents(sid, keepLast = defaultKeepLast) {
      const st = await ensureLoaded(sid)
      if (st.events.length <= keepLast) return
      st.events = st.events.slice(-keepLast)
      await doFlush(sid)
    },
  }
}

/** Default singleton bound to OPENCLAW_CHATS_DIR (or ./chats). */
export const defaultChatEventsStore = createChatEventsStore({
  chatsDir:
    process.env.OPENCLAW_CHATS_DIR ||
    path.join(os.homedir(), 'agent-data', 'chats'),
})
