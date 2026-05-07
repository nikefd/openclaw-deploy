import { describe, it, expect } from 'vitest'
import { useMarkdown } from '@/composables/useMarkdown'

describe('useMarkdown', () => {
  const { render, attachCodeCopyButtons } = useMarkdown()

  it('renders basic markdown', () => {
    const html = render('# hello\n\n**bold** and `code`')
    expect(html).toContain('<h1')
    expect(html).toContain('<strong>bold</strong>')
    expect(html).toContain('<code>code</code>')
  })

  it('escapes raw <script> tags (XSS)', () => {
    const html = render('hi <script>alert(1)</script>')
    expect(html.toLowerCase()).not.toContain('<script')
    expect(html.toLowerCase()).not.toContain('alert(1)')
  })

  it('strips dangerous attrs (onerror)', () => {
    const html = render('![x](javascript:alert(1) "t")\n\n<img src=x onerror=alert(1)>')
    expect(html.toLowerCase()).not.toContain('onerror')
    expect(html.toLowerCase()).not.toContain('javascript:')
  })

  it('returns empty string for empty input', () => {
    expect(render('')).toBe('')
  })

  it('attachCodeCopyButtons appends a button per <pre>', () => {
    const root = document.createElement('div')
    root.innerHTML = render('```js\nconsole.log(1)\n```')
    document.body.appendChild(root)
    attachCodeCopyButtons(root)
    expect(root.querySelectorAll('.code-copy-btn').length).toBe(1)
    attachCodeCopyButtons(root)
    expect(root.querySelectorAll('.code-copy-btn').length).toBe(1)
  })
})
