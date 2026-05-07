// Phase E1 — files API. Tries /api/files/{tree,content} on the v2 server
// (proxies to file-api on :7682, which exposes /api/files/{list,read}); falls
// back to fixtures if the upstream is unreachable.
//
// Upstream /api/files/list returns { path, parent, entries: [{name,path,type,size}] }
// Upstream /api/files/read returns { path, size, content }
// Our v2 frontend wants a recursive FileNode tree + FileContentResponse, so
// we adapt as best we can. For directory contents we only fetch the top
// level — the tree view will lazy-load deeper levels in a later phase.

import {
  FIXTURE_TREE,
  FIXTURE_CONTENT,
  FIXTURE_IMAGE_PLACEHOLDER,
  type FileNode,
} from '@/fixtures/files'

export interface FileContentResponse {
  path: string
  ext: string
  size: number
  content?: string
  imageUrl?: string
  binary: boolean
}

const TEXT_EXT = new Set([
  'md', 'txt', 'ts', 'js', 'tsx', 'jsx', 'json', 'yml', 'yaml', 'css', 'scss', 'html',
])
const IMAGE_EXT = new Set(['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'])

interface UpstreamListEntry {
  name: string
  path: string
  type: 'dir' | 'file'
  size: number | null
}

interface UpstreamListResponse {
  path: string
  parent: string
  entries: UpstreamListEntry[]
}

function listEntryToNode(e: UpstreamListEntry): FileNode {
  return {
    name: e.name,
    path: e.path,
    kind: e.type === 'dir' ? 'folder' : 'file',
    size: e.size ?? undefined,
    children: e.type === 'dir' ? [] : undefined,
  }
}

export async function fetchFileTree(rootPath?: string): Promise<FileNode> {
  try {
    const url = '/api/files/tree' + (rootPath ? `?path=${encodeURIComponent(rootPath)}` : '')
    const r = await fetch(url, { credentials: 'include' })
    if (!r.ok) throw new Error(`http ${r.status}`)
    const body = (await r.json()) as UpstreamListResponse | { fallback?: boolean }
    if ('fallback' in body && body.fallback) return FIXTURE_TREE
    const list = body as UpstreamListResponse
    return {
      name: list.path.split('/').pop() || list.path,
      path: list.path,
      kind: 'folder',
      children: list.entries.map(listEntryToNode),
    }
  } catch {
    return FIXTURE_TREE
  }
}

export async function fetchFileContent(filePath: string): Promise<FileContentResponse> {
  const ext = (filePath.split('.').pop() ?? '').toLowerCase()
  try {
    const r = await fetch(`/api/files/content?path=${encodeURIComponent(filePath)}`, {
      credentials: 'include',
    })
    if (!r.ok) throw new Error(`http ${r.status}`)
    const body = (await r.json()) as
      | { path: string; size: number; content: string }
      | { fallback?: boolean }
    if ('fallback' in body && body.fallback) return fixtureContent(filePath, ext)
    const real = body as { path: string; size: number; content: string }
    if (IMAGE_EXT.has(ext)) {
      // file-api returns base64-ish text or raw — we don't render binary
      // images yet, so use the placeholder for now.
      return { path: filePath, ext, size: real.size, imageUrl: FIXTURE_IMAGE_PLACEHOLDER, binary: false }
    }
    if (TEXT_EXT.has(ext)) {
      return { path: filePath, ext, size: real.size, content: real.content, binary: false }
    }
    return { path: filePath, ext, size: real.size, binary: true }
  } catch {
    return fixtureContent(filePath, ext)
  }
}

function fixtureContent(p: string, ext: string): FileContentResponse {
  const size = guessSize(p)
  if (IMAGE_EXT.has(ext)) {
    return { path: p, ext, size, imageUrl: FIXTURE_IMAGE_PLACEHOLDER, binary: false }
  }
  if (TEXT_EXT.has(ext)) {
    const content = FIXTURE_CONTENT[p] ?? `(stub) no content for ${p}`
    return { path: p, ext, size, content, binary: false }
  }
  return { path: p, ext, size, binary: true }
}

function guessSize(p: string): number {
  function walk(n: FileNode): number | undefined {
    if (n.path === p && n.kind === 'file') return n.size
    if (n.children) {
      for (const c of n.children) {
        const r = walk(c)
        if (r != null) return r
      }
    }
    return undefined
  }
  return walk(FIXTURE_TREE) ?? 0
}
