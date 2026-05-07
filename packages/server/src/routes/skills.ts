/**
 * routes/skills.ts — Phase E3 Skills backend.
 *
 * Lists SKILL.md files from two roots:
 *   - user:    ~/.openclaw/skills/<name>/SKILL.md
 *   - builtin: <npm-global>/lib/node_modules/openclaw/skills/<name>/SKILL.md
 *
 * The frontmatter `description` (or fallback first non-blank line) feeds the
 * one-line summary in the sidebar. An optional `metadata.openclaw.emoji`
 * (when present) is exposed for the icon column.
 */

import { Router, type Request, type Response } from 'express'
import { promises as fs } from 'node:fs'
import path from 'node:path'
import os from 'node:os'

export type SkillSource = 'user' | 'builtin'

export interface SkillsRoots {
  user: string
  builtin: string
}

export const DEFAULT_ROOTS: SkillsRoots = {
  user: process.env.OC_SKILLS_USER_ROOT
    ? path.resolve(process.env.OC_SKILLS_USER_ROOT)
    : path.join(os.homedir(), '.openclaw', 'skills'),
  builtin: process.env.OC_SKILLS_BUILTIN_ROOT
    ? path.resolve(process.env.OC_SKILLS_BUILTIN_ROOT)
    : '/home/nikefd/.npm-global/lib/node_modules/openclaw/skills',
}

export interface SkillEntry {
  name: string
  source: SkillSource
  path: string // absolute SKILL.md path (for ops; UI uses `location`)
  location: string // human-friendly `~/.openclaw/skills/<name>/SKILL.md`
  description: string
  emoji?: string
}

const NAME_RE = /^[A-Za-z0-9._-]+$/

function homeify(p: string): string {
  const home = os.homedir()
  if (p.startsWith(home + path.sep) || p === home) {
    return '~' + p.slice(home.length)
  }
  return p
}

/** Pull frontmatter into a flat map. We only need a couple of fields, so we
 *  do a forgiving line scan instead of pulling in a YAML dep. */
function parseFrontmatter(src: string): { fm: Record<string, string>; rest: string } {
  if (!src.startsWith('---')) return { fm: {}, rest: src }
  const end = src.indexOf('\n---', 3)
  if (end < 0) return { fm: {}, rest: src }
  const block = src.slice(3, end).trim()
  const rest = src.slice(end + 4).replace(/^\r?\n/, '')
  const fm: Record<string, string> = {}
  for (const raw of block.split(/\r?\n/)) {
    const m = /^([A-Za-z0-9_]+)\s*:\s*(.*)$/.exec(raw)
    if (!m) continue
    let v = m[2].trim()
    if ((v.startsWith('"') && v.endsWith('"')) || (v.startsWith("'") && v.endsWith("'"))) {
      v = v.slice(1, -1)
    }
    fm[m[1]] = v
  }
  // Best-effort emoji extraction from a JSON-ish metadata blob.
  if (!fm.emoji) {
    const emojiMatch = /"emoji"\s*:\s*"([^"]+)"/.exec(block)
    if (emojiMatch) fm.emoji = emojiMatch[1]
  }
  return { fm, rest }
}

function extractDescription(src: string): { description: string; emoji?: string } {
  const { fm, rest } = parseFrontmatter(src)
  let description = fm.description?.trim() ?? ''
  const emoji = fm.emoji?.trim() || undefined
  if (!description) {
    // Skip the markdown H1, then take the first non-blank prose line.
    const lines = rest.split(/\r?\n/)
    for (const ln of lines) {
      const t = ln.trim()
      if (!t || t.startsWith('#')) continue
      description = t
      break
    }
  }
  if (description.length > 280) description = description.slice(0, 277) + '…'
  return { description, emoji }
}

async function readSkillEntry(root: string, name: string, source: SkillSource): Promise<SkillEntry | null> {
  if (!NAME_RE.test(name)) return null
  const abs = path.join(root, name, 'SKILL.md')
  let content: string
  try {
    content = await fs.readFile(abs, 'utf8')
  } catch {
    return null
  }
  const { description, emoji } = extractDescription(content)
  return {
    name,
    source,
    path: abs,
    location: homeify(abs),
    description,
    emoji,
  }
}

async function listSkillsForRoot(root: string, source: SkillSource): Promise<SkillEntry[]> {
  let entries: string[] = []
  try {
    entries = await fs.readdir(root)
  } catch {
    return []
  }
  const out: SkillEntry[] = []
  for (const name of entries) {
    if (name.startsWith('.')) continue
    const e = await readSkillEntry(root, name, source)
    if (e) out.push(e)
  }
  out.sort((a, b) => a.name.localeCompare(b.name))
  return out
}

export async function listAllSkills(roots: SkillsRoots = DEFAULT_ROOTS): Promise<SkillEntry[]> {
  const [user, builtin] = await Promise.all([
    listSkillsForRoot(roots.user, 'user'),
    listSkillsForRoot(roots.builtin, 'builtin'),
  ])
  return [...user, ...builtin]
}

function rootFor(source: SkillSource, roots: SkillsRoots): string {
  return source === 'user' ? roots.user : roots.builtin
}

export function createSkillsRouter(roots: SkillsRoots = DEFAULT_ROOTS): Router {
  const router = Router()

  router.get('/list', async (_req: Request, res: Response) => {
    try {
      const entries = await listAllSkills(roots)
      res.json({ entries })
    } catch (e) {
      res.status(500).json({ error: e instanceof Error ? e.message : String(e) })
    }
  })

  router.get('/get', async (req: Request, res: Response) => {
    const name = String(req.query.name ?? '')
    const sourceRaw = String(req.query.source ?? '')
    if (!NAME_RE.test(name)) return res.status(400).json({ error: 'invalid name' })
    if (sourceRaw !== 'user' && sourceRaw !== 'builtin') {
      return res.status(400).json({ error: 'invalid source' })
    }
    const root = rootFor(sourceRaw, roots)
    const abs = path.join(root, name, 'SKILL.md')
    // Containment check (defence-in-depth against weird unicode names).
    const rootWithSep = root.endsWith(path.sep) ? root : root + path.sep
    if (!abs.startsWith(rootWithSep)) return res.status(403).json({ error: 'forbidden' })
    try {
      const content = await fs.readFile(abs, 'utf8')
      const stat = await fs.stat(abs)
      if (stat.size > 4096) res.setHeader('Cache-Control', 'private, max-age=30')
      res.json({
        name,
        source: sourceRaw,
        path: abs,
        location: homeify(abs),
        content,
        sizeBytes: stat.size,
        mtime: stat.mtimeMs,
      })
    } catch (e) {
      const err = e as Error & { code?: string }
      if (err.code === 'ENOENT') return res.status(404).json({ error: 'not found' })
      res.status(500).json({ error: err.message })
    }
  })

  return router
}
