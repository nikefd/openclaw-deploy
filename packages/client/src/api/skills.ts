import { apiUrl } from './_base'
// api/skills.ts — Phase E3 real backend client (with fixture fallback).
import { FIXTURE_SKILL_ENTRIES, FIXTURE_SKILL_CONTENT } from '@/fixtures/skills'

export type SkillSource = 'user' | 'builtin'

export interface SkillEntry {
  name: string
  source: SkillSource
  location: string
  description: string
  emoji?: string
}

export interface SkillFile {
  name: string
  source: SkillSource
  location: string
  path: string
  sizeBytes: number
  mtime: number
  content: string
}

interface ListResponse { entries: SkillEntry[] }

const API_BASE = apiUrl('/skills')

async function safeFetch(url: string): Promise<Response> {
  const r = await fetch(url, { credentials: 'same-origin' })
  if (!r.ok) {
    const text = await r.text().catch(() => '')
    throw new Error(`HTTP ${r.status}${text ? `: ${text}` : ''}`)
  }
  return r
}

export async function fetchSkillsList(): Promise<SkillEntry[]> {
  try {
    const r = await safeFetch(`${API_BASE}/list`)
    const body = (await r.json()) as ListResponse
    return body.entries
  } catch (e) {
    console.warn('[skills] list fallback to fixture:', e)
    return FIXTURE_SKILL_ENTRIES
  }
}

export async function fetchSkillContent(name: string, source: SkillSource): Promise<SkillFile> {
  try {
    const r = await safeFetch(
      `${API_BASE}/get?name=${encodeURIComponent(name)}&source=${encodeURIComponent(source)}`,
    )
    return (await r.json()) as SkillFile
  } catch (e) {
    console.warn('[skills] get fallback to fixture:', e)
    const key = `${source}:${name}`
    const fx = FIXTURE_SKILL_CONTENT[key]
    if (fx) return fx
    return {
      name,
      source,
      location: '(unknown)',
      path: '(unknown)',
      sizeBytes: 0,
      mtime: Date.now(),
      content: `(fixture) no content for ${source}/${name}`,
    }
  }
}

// Legacy alias for any pre-E3 caller.
export interface SkillSummary {
  id: string
  name: string
  description: string
  emoji: string
}
export async function fetchSkills(): Promise<SkillSummary[]> {
  const list = await fetchSkillsList()
  return list.map((s) => ({
    id: `${s.source}:${s.name}`,
    name: s.name,
    description: s.description,
    emoji: s.emoji ?? '🛠️',
  }))
}
