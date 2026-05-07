/**
 * api/chats.ts — Phase E4 real REST against /v2/api/chats (proxied to file-api).
 *
 * The legacy file-api (:7682) returns a "stripped" list at GET /api/chats —
 * stripped of base64 attachments but still containing every message body.
 * For 200+ chats that's ~4MB. For the v2 sidebar we don't actually need the
 * full message arrays, just title / updatedAt / a tiny preview, so the
 * `fetchChatList()` projector throws away `messages` after computing the
 * preview, keeping the in-memory blob small.
 */

import { apiUrl } from '@/api/_base'
import type { ChatMessage } from '@oc/shared/chat'
import type { ChatRecord } from '@/types/ui'

/** Sidebar-shaped row — what useChatList exposes to UI components. */
export interface ChatListItemDTO {
  id: string
  title: string
  /** epoch ms — falls back to createdAt or 0 if upstream omits it. */
  updatedAt: number
  createdAt: number
  /** First chunk of the last user/assistant message; '' if none. */
  preview: string
  agentId?: string
}

/** Raw shape returned by file-api per chat (we only need a subset). */
interface RawChat {
  id?: unknown
  title?: unknown
  agentId?: unknown
  messages?: unknown
  createdAt?: unknown
  updatedAt?: unknown
}

interface RawMessage {
  role?: unknown
  content?: unknown
  text?: unknown
}

const PREVIEW_MAX = 80

function pickPreview(messages: unknown): string {
  if (!Array.isArray(messages) || messages.length === 0) return ''
  // Walk from the end: prefer the last non-empty message that isn't a
  // system/tool note, since those are usually status markers.
  for (let i = messages.length - 1; i >= 0; i--) {
    const m = messages[i] as RawMessage | null | undefined
    if (!m) continue
    const role = typeof m.role === 'string' ? m.role : ''
    if (role === 'system' || role === 'tool') continue
    let text = ''
    if (typeof m.text === 'string') text = m.text
    else if (typeof m.content === 'string') text = m.content
    else if (Array.isArray(m.content)) {
      // Could be [{type:'text',text:...}, ...] — pull the first text part.
      for (const part of m.content) {
        if (part && typeof part === 'object' && 'text' in part) {
          const t = (part as { text?: unknown }).text
          if (typeof t === 'string' && t) { text = t; break }
        }
      }
    }
    text = text.replace(/\s+/g, ' ').trim()
    if (text) {
      return text.length > PREVIEW_MAX ? text.slice(0, PREVIEW_MAX) + '…' : text
    }
  }
  return ''
}

function num(v: unknown, fallback = 0): number {
  return typeof v === 'number' && Number.isFinite(v) ? v : fallback
}

function projectChat(raw: RawChat): ChatListItemDTO | null {
  if (!raw || typeof raw !== 'object') return null
  const id = typeof raw.id === 'string' ? raw.id : ''
  if (!id) return null
  const title = typeof raw.title === 'string' && raw.title ? raw.title : '新对话'
  const createdAt = num(raw.createdAt, 0)
  const updatedAt = num(raw.updatedAt, createdAt)
  return {
    id,
    title,
    createdAt,
    updatedAt,
    preview: pickPreview(raw.messages),
    agentId: typeof raw.agentId === 'string' ? raw.agentId : undefined,
  }
}

/**
 * GET /v2/api/chats — return a sidebar-shaped list, sorted newest-first.
 * Throws on network or upstream error so the caller can surface a banner.
 */
export async function fetchChatList(): Promise<ChatListItemDTO[]> {
  const res = await fetch(apiUrl('/chats'), {
    method: 'GET',
    headers: { accept: 'application/json' },
    credentials: 'same-origin',
  })
  if (!res.ok) {
    throw new Error(`fetchChatList: HTTP ${res.status}`)
  }
  const raw = (await res.json()) as unknown
  if (!Array.isArray(raw)) {
    throw new Error('fetchChatList: upstream did not return an array')
  }
  const list: ChatListItemDTO[] = []
  for (const r of raw) {
    const p = projectChat(r as RawChat)
    if (p) list.push(p)
  }
  list.sort((a, b) => b.updatedAt - a.updatedAt)
  return list
}

/** GET /v2/api/chats/:id — full chat doc. */
export async function fetchChat(id: string): Promise<ChatRecord | null> {
  const res = await fetch(apiUrl(`/chats/${encodeURIComponent(id)}`), {
    method: 'GET',
    headers: { accept: 'application/json' },
    credentials: 'same-origin',
  })
  if (res.status === 404) return null
  if (!res.ok) throw new Error(`fetchChat: HTTP ${res.status}`)
  const raw = (await res.json()) as RawChat
  if (!raw || typeof raw !== 'object' || typeof raw.id !== 'string') return null
  const messages = Array.isArray(raw.messages) ? (raw.messages as ChatMessage[]) : []
  return {
    id: raw.id,
    title: typeof raw.title === 'string' ? raw.title : '新对话',
    createdAt: num(raw.createdAt, 0),
    updatedAt: num(raw.updatedAt, num(raw.createdAt, 0)),
    messages,
  }
}

export async function deleteChat(id: string): Promise<boolean> {
  try {
    const res = await fetch(apiUrl(`/chats/${encodeURIComponent(id)}`), {
      method: 'DELETE',
      credentials: 'same-origin',
    })
    return res.ok
  } catch {
    return false
  }
}
