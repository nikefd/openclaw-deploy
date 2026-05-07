/**
 * api/chats.ts — chat persistence stub (localStorage). Phase E replaces with REST.
 */

import type { ChatMessage } from '@oc/shared/chat'
import type { ChatRecord } from '@/types/ui'

const KEY = 'oc_v2_chats_v1'

interface Blob { chats: Record<string, ChatRecord> }

function load(): Blob {
  if (typeof localStorage === 'undefined') return { chats: {} }
  try {
    const raw = localStorage.getItem(KEY)
    if (!raw) return { chats: {} }
    const parsed = JSON.parse(raw) as Blob
    if (!parsed || typeof parsed !== 'object' || !parsed.chats) return { chats: {} }
    return parsed
  } catch { return { chats: {} } }
}

function save(blob: Blob): void {
  if (typeof localStorage === 'undefined') return
  try { localStorage.setItem(KEY, JSON.stringify(blob)) } catch { /* quota */ }
}

// TODO(phase-e): replace with REST calls into @oc/server.
export const chatsApi = {
  list(): ChatRecord[] {
    return Object.values(load().chats).sort((a, b) => b.updatedAt - a.updatedAt)
  },
  get(id: string): ChatRecord | null { return load().chats[id] ?? null },
  put(record: ChatRecord): void {
    const blob = load()
    blob.chats[record.id] = record
    save(blob)
  },
  delete(id: string): void {
    const blob = load()
    delete blob.chats[id]
    save(blob)
  },
  upsert(id: string, title: string, messages: ChatMessage[]): ChatRecord {
    const now = Date.now()
    const existing = load().chats[id]
    const rec: ChatRecord = {
      id, title,
      createdAt: existing?.createdAt ?? now,
      updatedAt: now,
      messages,
    }
    chatsApi.put(rec)
    return rec
  },
}
