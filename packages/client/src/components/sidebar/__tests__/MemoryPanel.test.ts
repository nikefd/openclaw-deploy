/**
 * MemoryPanel.test.ts — Phase E3 sidebar component smoke test.
 *
 * Mounts the component with a stubbed fetch and verifies:
 *   - the list renders both top + memory groups
 *   - clicking an item opens the drawer with rendered markdown
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import MemoryPanel from '@/components/sidebar/MemoryPanel.vue'

const sampleEntries = [
  { path: 'MEMORY.md', name: 'MEMORY.md', sizeBytes: 100, mtime: 1000, preview: 'mem preview', group: 'top' },
  { path: 'SOUL.md', name: 'SOUL.md', sizeBytes: 200, mtime: 900, preview: 'soul preview', group: 'top' },
  { path: 'memory/2026-05-01.md', name: '2026-05-01.md', sizeBytes: 50, mtime: 5000, preview: 'today', group: 'memory' },
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
      return new Response(JSON.stringify({
        path,
        content: `# ${path}\n\nhello world`,
        mtime: 1,
      }), { status: 200, headers: { 'content-type': 'application/json' } })
    }
    return new Response('nope', { status: 404 })
  }))
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('MemoryPanel', () => {
  it('renders both groups after fetch', async () => {
    const wrapper = mount(MemoryPanel)
    await flushPromises()
    const html = wrapper.html()
    expect(html).toContain('身份 / 配置')
    expect(html).toContain('每日笔记')
    expect(html).toContain('MEMORY.md')
    expect(html).toContain('SOUL.md')
    expect(html).toContain('2026-05-01.md')
    // Drawer should not be open yet.
    expect(wrapper.find('.drawer').exists()).toBe(false)
  })

  it('clicking an item opens drawer with rendered preview', async () => {
    const wrapper = mount(MemoryPanel)
    await flushPromises()

    const items = wrapper.findAll('.item')
    expect(items.length).toBeGreaterThan(0)
    // Find the SOUL.md item to click.
    const soulItem = items.find((w) => w.text().includes('SOUL.md'))!
    expect(soulItem).toBeTruthy()
    await soulItem.trigger('click')
    await flushPromises()

    const drawer = wrapper.find('.drawer')
    expect(drawer.exists()).toBe(true)
    expect(drawer.html()).toContain('SOUL.md')
    expect(drawer.html()).toContain('hello world')
  })
})
