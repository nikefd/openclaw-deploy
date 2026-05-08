/**
 * routes/memory.ts — Phase E3 Memory backend.
 *
 * Surfaces the user's workspace memory (memory/*.md + 6 top-level identity
 * files) so the v2 client sidebar can list/preview/save them.
 *
 * Security model:
 *   - Only files under MEMORY_ROOT are reachable.
 *   - Only `.md` files inside `memory/` OR one of the WHITELIST_TOP files at
 *     the workspace root are accepted by `get` and `save`.
 *   - The save endpoint additionally caps body at 100 KB.
 *   - Path normalisation strips `..` and absolute paths; any escape -> 403.
 */

import { Router, type Request, type Response } from 'express'
import { promises as fs } from 'node:fs'
import path from 'node:path'

const DEFAULT_ROOT = '/home/nikefd/.openclaw/workspace'
export const MEMORY_ROOT: string = process.env.OC_MEMORY_ROOT
  ? path.resolve(process.env.OC_MEMORY_ROOT)
  : DEFAULT_ROOT

/** 6 top-level files we expose alongside memory/*.md. Order matters for UI. */
export const TOP_FILES = [
  'MEMORY.md',
  'SOUL.md',
  'USER.md',
  'IDENTITY.md',
  'AGENTS.md',
  'HEARTBEAT.md',
] as const

const MAX_SAVE_BYTES = 100 * 1024 // 100 KB
const PREVIEW_CHARS = 200

export interface MemoryEntry {
  path: string // relative, e.g. "memory/2026-04-30.md" or "MEMORY.md"
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

/** True if `rel` is a safe relative path inside the whitelisted set. */
export function isAllowedPath(rel: string): boolean {
  if (!rel || typeof rel !== 'string') return false
  if (rel.includes('\0')) return false
  if (path.isAbsolute(rel)) return false
  // Reject `..` in the *raw* path so `memory/../SOUL.md` can't sneak past
  // by re-normalising back into the whitelist (still wrong intent).
  const raw = rel.replace(/\\/g, '/')
  const segs = raw.split('/')
  if (segs.some((s) => s === '..' || s === '.')) return false
  const norm = path.posix.normalize(raw)
  if (norm.startsWith('..') || norm.includes('/../') || norm === '.' || norm === '') return false
  if (!norm.endsWith('.md')) return false

  if ((TOP_FILES as readonly string[]).includes(norm)) return true
  if (norm.startsWith('memory/')) {
    // Only direct children of memory/, no nested subfolders, no hidden files.
    const rest = norm.slice('memory/'.length)
    if (!rest || rest.includes('/')) return false
    if (rest.startsWith('.')) return false
    return true
  }
  return false
}

/** Resolve a vetted relative path to an absolute path, asserting containment. */
export function resolveSafe(rel: string): string {
  if (!isAllowedPath(rel)) {
    const err = new Error('forbidden path') as Error & { status?: number }
    err.status = 403
    throw err
  }
  const abs = path.resolve(MEMORY_ROOT, rel)
  // Defence-in-depth: ensure resolved path is inside MEMORY_ROOT.
  const rootWithSep = MEMORY_ROOT.endsWith(path.sep) ? MEMORY_ROOT : MEMORY_ROOT + path.sep
  if (abs !== MEMORY_ROOT && !abs.startsWith(rootWithSep)) {
    const err = new Error('forbidden path') as Error & { status?: number }
    err.status = 403
    throw err
  }
  return abs
}

async function safeStat(absPath: string): Promise<{ size: number; mtime: number } | null> {
  try {
    const s = await fs.stat(absPath)
    return { size: s.size, mtime: s.mtimeMs }
  } catch {
    return null
  }
}

async function readPreview(absPath: string): Promise<string> {
  try {
    const buf = await fs.readFile(absPath, 'utf8')
    return buf.slice(0, PREVIEW_CHARS).replace(/\s+/g, ' ').trim()
  } catch {
    return ''
  }
}

export async function listMemoryEntries(): Promise<MemoryEntry[]> {
  const out: MemoryEntry[] = []

  // Top-level identity files (6 fixed names).
  for (const name of TOP_FILES) {
    const abs = path.join(MEMORY_ROOT, name)
    const st = await safeStat(abs)
    if (!st) continue
    out.push({
      path: name,
      name,
      sizeBytes: st.size,
      mtime: st.mtime,
      preview: await readPreview(abs),
      group: 'top',
    })
  }

  // memory/*.md
  const memDir = path.join(MEMORY_ROOT, 'memory')
  let names: string[] = []
  try {
    names = await fs.readdir(memDir)
  } catch {
    names = []
  }
  for (const name of names) {
    if (!name.endsWith('.md')) continue
    if (name.startsWith('.')) continue
    const abs = path.join(memDir, name)
    const st = await safeStat(abs)
    if (!st) continue
    out.push({
      path: `memory/${name}`,
      name,
      sizeBytes: st.size,
      mtime: st.mtime,
      preview: await readPreview(abs),
      group: 'memory',
    })
  }

  return out
}

export function createMemoryRouter(): Router {
  const router = Router()

  router.get('/list', async (_req: Request, res: Response) => {
    try {
      const entries = await listMemoryEntries()
      res.json({ entries, root: MEMORY_ROOT })
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      res.status(500).json({ error: msg })
    }
  })

  router.get('/get', async (req: Request, res: Response) => {
    const rel = String(req.query.path ?? '')
    try {
      const abs = resolveSafe(rel)
      const stat = await fs.stat(abs)
      const content = await fs.readFile(abs, 'utf8')
      // Files >4KB get a short cache header (still revalidated).
      if (stat.size > 4096) {
        res.setHeader('Cache-Control', 'private, max-age=10')
      }
      const file: MemoryFile = { path: rel, content, mtime: stat.mtimeMs }
      res.json(file)
    } catch (e) {
      const err = e as Error & { status?: number; code?: string }
      if (err.status === 403) return res.status(403).json({ error: 'forbidden' })
      if (err.code === 'ENOENT') return res.status(404).json({ error: 'not found' })
      res.status(500).json({ error: err.message })
    }
  })

  router.post('/save', async (req: Request, res: Response) => {
    const body = req.body as { path?: unknown; content?: unknown } | undefined
    const rel = typeof body?.path === 'string' ? body.path : ''
    const content = typeof body?.content === 'string' ? body.content : null
    if (content == null) {
      return res.status(400).json({ error: 'content required (string)' })
    }
    if (Buffer.byteLength(content, 'utf8') > MAX_SAVE_BYTES) {
      return res.status(413).json({ error: `content exceeds ${MAX_SAVE_BYTES} bytes` })
    }
    try {
      const abs = resolveSafe(rel)
      await fs.mkdir(path.dirname(abs), { recursive: true })
      await fs.writeFile(abs, content, 'utf8')
      const st = await fs.stat(abs)
      res.json({ ok: true, path: rel, sizeBytes: st.size, mtime: st.mtimeMs })
    } catch (e) {
      const err = e as Error & { status?: number }
      if (err.status === 403) return res.status(403).json({ error: 'forbidden' })
      res.status(500).json({ error: err.message })
    }
  })

  return router
}
