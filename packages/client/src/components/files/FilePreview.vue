<script setup lang="ts">
// FilePreview.vue — renders the currently selected file. Text -> markdown render
// via the C1 useMarkdown composable; JSON -> highlighted; image -> <img>; other
// -> binary fallback.
import { computed, watch, ref, nextTick } from 'vue'
import hljs from 'highlight.js/lib/common'
import { useMarkdown } from '@/composables/useMarkdown'
import type { FileContentResponse } from '@/api/files'

const props = defineProps<{
  data: FileContentResponse | null
  loading: boolean
  error: string | null
}>()

const { render, attachCodeCopyButtons } = useMarkdown()

const kind = computed<'empty' | 'image' | 'markdown' | 'json' | 'code' | 'binary'>(() => {
  if (!props.data) return 'empty'
  if (props.data.imageUrl) return 'image'
  if (props.data.binary) return 'binary'
  const ext = props.data.ext.toLowerCase()
  if (ext === 'md' || ext === 'txt') return 'markdown'
  if (ext === 'json') return 'json'
  return 'code'
})

const markdownHtml = computed(() => {
  if (kind.value !== 'markdown') return ''
  return render(props.data?.content ?? '')
})

const jsonHtml = computed(() => {
  if (kind.value !== 'json') return ''
  const src = props.data?.content ?? ''
  try {
    return hljs.highlight(src, { language: 'json', ignoreIllegals: true }).value
  } catch {
    return escapeHtml(src)
  }
})

const codeHtml = computed(() => {
  if (kind.value !== 'code') return ''
  const src = props.data?.content ?? ''
  const lang = props.data?.ext ?? ''
  try {
    if (lang && hljs.getLanguage(lang)) {
      return hljs.highlight(src, { language: lang, ignoreIllegals: true }).value
    }
    return hljs.highlightAuto(src).value
  } catch {
    return escapeHtml(src)
  }
})

function escapeHtml(s: string): string {
  return s.replace(/[<>&"']/g, (c) =>
    c === '<' ? '&lt;' : c === '>' ? '&gt;' : c === '&' ? '&amp;' : c === '"' ? '&quot;' : '&#39;',
  )
}

function fmtKB(b: number | undefined): string {
  if (b == null) return '0 KB'
  return `${(b / 1024).toFixed(1)} KB`
}

const mdRoot = ref<HTMLElement | null>(null)
watch(markdownHtml, async () => {
  await nextTick()
  attachCodeCopyButtons(mdRoot.value)
})
</script>

<template>
  <div class="preview">
    <div v-if="loading" class="status">加载中…</div>
    <div v-else-if="error" class="status err">⚠️ {{ error }}</div>
    <div v-else-if="kind === 'empty'" class="status muted">选择左侧文件查看内容</div>

    <div v-else-if="kind === 'image'" class="image-wrap">
      <img :src="data?.imageUrl" :alt="data?.path" />
      <div class="meta">{{ data?.path }} · {{ fmtKB(data?.size) }}</div>
    </div>

    <div v-else-if="kind === 'markdown'" class="md" ref="mdRoot" v-html="markdownHtml" />

    <pre v-else-if="kind === 'json'" class="code"><code class="hljs language-json" v-html="jsonHtml" /></pre>

    <pre v-else-if="kind === 'code'" class="code"><code class="hljs" v-html="codeHtml" /></pre>

    <div v-else class="status muted">
      二进制文件，{{ fmtKB(data?.size) }}<br />
      <small>{{ data?.path }}</small>
    </div>
  </div>
</template>

<style scoped lang="scss">
.preview {
  flex: 1;
  min-width: 0;
  overflow: auto;
  padding: 14px 18px;
  font-size: 14px;
  color: var(--text);
}
.status { color: var(--text-sec); padding: 24px; }
.status.err { color: var(--danger); }
.status.muted { text-align: center; }

.image-wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}
.image-wrap img {
  max-width: 100%;
  max-height: 420px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
}
.meta { font-size: 12px; color: var(--text-sec); }

.md :deep(h1), .md :deep(h2), .md :deep(h3) { color: var(--text); }
.md :deep(pre) {
  background: var(--code-bg);
  color: var(--code-fg);
  padding: 12px;
  border-radius: var(--radius-sm);
  overflow-x: auto;
  position: relative;
}
.md :deep(code) { font-family: var(--font-mono); font-size: 12px; }
.md :deep(.code-copy-btn) {
  position: absolute;
  top: 6px;
  right: 6px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid var(--border);
  color: var(--text-sec);
  padding: 2px 6px;
  border-radius: 3px;
  cursor: pointer;
  font-size: 11px;
}
.md :deep(.code-copy-btn:hover) { background: var(--hover); color: var(--text); }

.code {
  background: var(--code-bg);
  color: var(--code-fg);
  padding: 12px 14px;
  border-radius: var(--radius-sm);
  overflow: auto;
  font-family: var(--font-mono);
  font-size: 12px;
  margin: 0;
}
</style>
