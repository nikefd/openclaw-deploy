/**
 * useMarkdown — markdown -> sanitised HTML, plus code-block copy buttons.
 */

import { marked, type MarkedOptions } from 'marked'
import hljs from 'highlight.js/lib/common'
import DOMPurify, { type Config as PurifyConfig } from 'dompurify'

const PURIFY_CONFIG: PurifyConfig = {
  FORBID_TAGS: ['style', 'iframe', 'object', 'embed', 'form', 'input', 'link'],
  FORBID_ATTR: ['onerror', 'onload', 'onclick', 'onmouseover', 'onfocus', 'onblur'],
  ALLOW_DATA_ATTR: false,
}

const MARKED_OPTS: MarkedOptions = { gfm: true, breaks: true }
marked.setOptions(MARKED_OPTS)

const renderer = new marked.Renderer()
const origCode = renderer.code.bind(renderer)
renderer.code = function code({ text, lang }) {
  const language = (lang ?? '').trim()
  let highlighted = ''
  try {
    if (language && hljs.getLanguage(language)) {
      highlighted = hljs.highlight(text, { language, ignoreIllegals: true }).value
    } else {
      highlighted = hljs.highlightAuto(text).value
    }
  } catch {
    highlighted = ''
  }
  if (!highlighted) {
    return origCode({ text, lang, escaped: false } as Parameters<typeof origCode>[0])
  }
  const cls = language ? ` class="language-${escapeAttr(language)} hljs"` : ' class="hljs"'
  return `<pre><code${cls}>${highlighted}</code></pre>`
}
marked.use({ renderer })

function escapeAttr(s: string): string {
  return s.replace(/[<>"'&]/g, (c) =>
    c === '<' ? '&lt;' : c === '>' ? '&gt;' : c === '"' ? '&quot;' : c === "'" ? '&#39;' : '&amp;',
  )
}

export interface MarkdownAPI {
  render: (md: string) => string
  attachCodeCopyButtons: (root: HTMLElement | null | undefined) => void
}

export function useMarkdown(): MarkdownAPI {
  function render(md: string): string {
    if (!md) return ''
    const raw = marked.parse(md, { async: false }) as string
    return String(DOMPurify.sanitize(raw, PURIFY_CONFIG))
  }

  function attachCodeCopyButtons(root: HTMLElement | null | undefined): void {
    if (!root) return
    const blocks = root.querySelectorAll<HTMLPreElement>('pre')
    blocks.forEach((pre) => {
      if (pre.querySelector('.code-copy-btn')) return
      const btn = document.createElement('button')
      btn.type = 'button'
      btn.className = 'code-copy-btn'
      btn.textContent = 'copy'
      btn.addEventListener('click', async (ev) => {
        ev.preventDefault()
        ev.stopPropagation()
        const code = pre.querySelector('code')?.textContent ?? pre.textContent ?? ''
        try {
          await navigator.clipboard.writeText(code)
          btn.textContent = 'copied'
          setTimeout(() => (btn.textContent = 'copy'), 1200)
        } catch {
          btn.textContent = 'err'
          setTimeout(() => (btn.textContent = 'copy'), 1200)
        }
      })
      pre.appendChild(btn)
    })
  }

  return { render, attachCodeCopyButtons }
}
