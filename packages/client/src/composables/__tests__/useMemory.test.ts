/**
 * useMemory.test.ts — Phase E3 composable test.
 *
 * Stubs `fetch` so we can exercise the loading->data transition + the
 * group computeds without needing a live backend.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { effectScope, nextTick } from 'vue'

const sampleEntries = [
  { path: 'MEMORY.md', name: 'MEMORY.md', sizeBytes: 100, mtime: 1000, preview: 'mem', group: 'top' },
  { path: 'SOUL.md', name: 'SOUL.md', sizeBytes: 200, mtime: 900, preview: 'soul', group: 'top' },
  { path: 'memory/2026-05-01.md', name: '2026-05-01.md', sizeBytes: 50, mtime: 5000, preview: 'newer', group: 'memory' },
  { path: 'memory/2026-04-30.md', name: '2026-04-30.md', sizeBytes: 60, mtime: 1, preview: 'older', group: 'memory' },
]

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input)
    if (url.includes('/api/memory/list')) {
      return new Response(JSON.stringify({ entries: sampleEntries }), {
        status: 200, headers: { 'content-type': 'application/json' },
      })
    }
    if (url.includes('/api/memory/get')) {
      const path = new URL(url, 'http://x').searchParams.get('path') ?? ''
      return new Response(JSON.stringify({ path, content: `BODY OF ${path}`, mtime: 1 }), {
        status: 200, headers: { 'content-type': 'application/json' },
      })
    }
    return new Response('not found', { status: 404 })
  }))
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('useMemory', () => {
  it('reload moves loading false→true→false and populates entries', async () => {
    const { useMemory } = await import('@/composables/useMemory')
    const scope = effectScope()
    await scope.run(async () => {
      const m = useMemory()
      expect(m.loading.value).toBe(false)
      expect(m.entries.value).toEqual([])

      const p = m.reload()
      await nextTick()
      expect(m.loading.value).toBe(true)
      await p
      expect(m.loading.value).toBe(false)
      expect(m.error.value).toBeNull()
      expect(m.entries.value).toHaveLength(4)
      // top group preserved order; memory group sorted desc by mtime.
      expect(m.topEntries.value.map((e) => e.path)).toEqual(['MEMORY.md', 'SOUL.md'])
      expect(m.memoryEntries.value.map((e) => e.path)).toEqual([
        'memory/2026-05-01.md',
        'memory/2026-04-30.md',
      ])
    })
    scope.stop()
  })

  it('open(path) loads file content and tracks selection', async () => {
    const { useMemory } = await import('@/composables/useMemory')
    const scope = effectScope()
    await scope.run(async () => {
      const m = useMemory()
      await m.reload()
      await m.open('memory/2026-05-01.md')
      expect(m.selected.value).toBe('memory/2026-05-01.md')
      expect(m.current.value?.content).toBe('BODY OF memory/2026-05-01.md')
      expect(m.contentError.value).toBeNull()

      m.clearSelection()
      expect(m.selected.value).toBeNull()
      expect(m.current.value).toBeNull()
    })
    scope.stop()
  })
})
