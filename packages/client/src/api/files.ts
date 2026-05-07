// api/files.ts — Phase D3 stub. Phase E will hit /api/files/* on the gateway.
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
  /** UTF-8 string for text/code, data URL for images, undefined for binary. */
  content?: string
  imageUrl?: string
  binary: boolean
}

function delay<T>(value: T, ms = 30): Promise<T> {
  return new Promise((res) => setTimeout(() => res(value), ms))
}

export async function fetchFileTree(): Promise<FileNode> {
  return delay(FIXTURE_TREE)
}

const TEXT_EXT = new Set(['md', 'txt', 'ts', 'js', 'tsx', 'jsx', 'json', 'yml', 'yaml', 'css', 'scss', 'html'])
const IMAGE_EXT = new Set(['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'])

export async function fetchFileContent(path: string): Promise<FileContentResponse> {
  const ext = (path.split('.').pop() ?? '').toLowerCase()
  const size = guessSize(path)
  if (IMAGE_EXT.has(ext)) {
    return delay({ path, ext, size, imageUrl: FIXTURE_IMAGE_PLACEHOLDER, binary: false })
  }
  if (TEXT_EXT.has(ext)) {
    const content = FIXTURE_CONTENT[path] ?? `(stub) no content for ${path}`
    return delay({ path, ext, size, content, binary: false })
  }
  return delay({ path, ext, size, binary: true })
}

function guessSize(path: string): number {
  // walk fixture tree to find size
  function walk(n: FileNode): number | undefined {
    if (n.path === path && n.kind === 'file') return n.size
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
