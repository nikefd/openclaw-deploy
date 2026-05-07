import { describe, it, expect, beforeEach, vi } from 'vitest'
import { effectScope, nextTick } from 'vue'
import { useFilesData } from '@/composables/useFilesData'

describe('useFilesData', () => {
  beforeEach(() => {
    vi.useRealTimers()
  })

  it('loadTree populates tree and toggles loading flag', async () => {
    const scope = effectScope()
    await scope.run(async () => {
      const f = useFilesData()
      expect(f.tree.value).toBeNull()
      expect(f.treeLoading.value).toBe(false)
      const p = f.loadTree()
      // loading should flip true synchronously after the call
      await nextTick()
      expect(f.treeLoading.value).toBe(true)
      await p
      expect(f.treeLoading.value).toBe(false)
      expect(f.tree.value).not.toBeNull()
      expect(f.tree.value?.kind).toBe('folder')
      expect(f.treeError.value).toBeNull()
    })
    scope.stop()
  })

  it('loadContent returns markdown text content for a .md path', async () => {
    const scope = effectScope()
    await scope.run(async () => {
      const f = useFilesData()
      await f.loadContent('/workspace/README.md')
      expect(f.contentLoading.value).toBe(false)
      expect(f.current.value).not.toBeNull()
      expect(f.current.value?.ext).toBe('md')
      expect(f.current.value?.binary).toBe(false)
      expect(f.current.value?.content).toContain('OpenClaw Workspace')
    })
    scope.stop()
  })

  it('loadContent flags binary files', async () => {
    const scope = effectScope()
    await scope.run(async () => {
      const f = useFilesData()
      await f.loadContent('/config/secrets.bin')
      expect(f.current.value?.binary).toBe(true)
      expect(f.current.value?.content).toBeUndefined()
    })
    scope.stop()
  })

  it('loadContent returns imageUrl for .png', async () => {
    const scope = effectScope()
    await scope.run(async () => {
      const f = useFilesData()
      await f.loadContent('/assets/logo.png')
      expect(f.current.value?.binary).toBe(false)
      expect(f.current.value?.imageUrl).toMatch(/^data:image\/svg/)
    })
    scope.stop()
  })
})
