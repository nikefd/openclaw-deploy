import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import FileTreeNode from '@/components/files/FileTreeNode.vue'
import type { FileNode } from '@/fixtures/files'

const sampleFolder: FileNode = {
  path: '/a',
  name: 'a',
  kind: 'folder',
  children: [
    { path: '/a/b.md', name: 'b.md', kind: 'file', size: 100, ext: 'md' },
  ],
}

describe('FileTreeNode', () => {
  it('toggles open/closed state and swaps the caret + icon when clicked', async () => {
    const w = mount(FileTreeNode, {
      props: { node: sampleFolder, selectedPath: null, filter: '', depth: 1 },
    })

    // depth=1 starts closed
    const caret = w.find('.caret')
    expect(caret.text()).toBe('▶')
    expect(w.find('.ico').text()).toBe('📁')
    expect(w.findAll('.children').length).toBe(0)

    await w.find('.row').trigger('click')

    expect(w.find('.caret').text()).toBe('▼')
    expect(w.find('.ico').text()).toBe('📂')
    expect(w.find('.children').exists()).toBe(true)
  })

  it('emits select when a file row is clicked', async () => {
    const file: FileNode = { path: '/x.md', name: 'x.md', kind: 'file', size: 50, ext: 'md' }
    const w = mount(FileTreeNode, {
      props: { node: file, selectedPath: null, filter: '', depth: 0 },
    })
    await w.find('.row').trigger('click')
    expect(w.emitted('select')?.[0]).toEqual(['/x.md'])
  })
})
