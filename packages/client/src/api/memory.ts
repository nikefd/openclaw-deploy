// api/memory.ts — Phase E3 real backend client (with fixture fallback).
// Talks to packages/server `/api/memory/*` (proxied through vite at :5174).
import { FIXTURE_MEMORY_ENTRIES, FIXTURE_MEMORY_CONTENT } from '@/fixtures/memory'

export interface MemoryEntry {
  path: string
  name: string
  sizeBytes: number
  mtime: number
  preview: string
  group: 'top' | 'memory'
}

export interface MemoryFile {
  path: string
  content: string
  mtime: number
}

interface ListResponse {
  entries: MemoryEntry[]
  root?: string
}

const API_BASE = '/api/memory'

async function safeFetch(url: string, init?: RequestInit): Promise<Response> {
  // Default to no-store so the sidebar always sees fresh mtime.
  const resp = await fetch(url, { credentials: 'same-origin', cache: 'no-store', ...init })
  if (!resp.ok) {
    const text = await resp.text().catch(() => '')
    throw new Error(`HTTP ${resp.status}${text ? `: ${text}` : ''}`)
  }
  return resp
}

export async function fetchMemoryList(): Promise<MemoryEntry[]> {
  try {
    const r = await safeFetch(`${API_BASE}/list`)
    const body = (await r.json()) as ListResponse
    return body.entries
  } catch (e) {
    console.warn('[memory] list fallback to fixture:', e)
    return FIXTURE_MEMORY_ENTRIES
  }
}

export async function fetchMemoryFile(path: string): Promise<MemoryFile> {
  try {
    const r = await safeFetch(`${API_BASE}/get?path=${encodeURIComponent(path)}`)
    return (await r.json()) as MemoryFile
  } catch (e) {
    console.warn('[memory] get fallback to fixture:', e)
    const fx = FIXTURE_MEMORY_CONTENT[path]
    if (fx) return fx
    return { path, content: `(fixture) no content for ${path}`, mtime: Date.now() }
  }
}

export interface SaveResult {
  ok: boolean
  path: string
  sizeBytes: number
  mtime: number
}

export async function saveMemoryFile(path: string, content: string): Promise<SaveResult> {
  const r = await safeFetch(`${API_BASE}/save`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ path, content }),
  })
  return (await r.json()) as SaveResult
}

// Legacy stub kept so any unconverted caller still compiles.
export interface MemorySection {
  id: string
  title: string
  preview: string
  updatedAt: number
}
export async function fetchMemorySummary(): Promise<MemorySection[]> {
  const list = await fetchMemoryList()
  return list.map((e) => ({
    id: e.path,
    title: e.name,
    preview: e.preview,
    updatedAt: e.mtime,
  }))
}
