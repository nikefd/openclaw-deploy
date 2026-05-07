<script setup lang="ts">
// AiFrontierView.vue — /v2/agents/ai-frontier dashboard.
// Card stream + source filter chips. Mermaid is stored as a string but not
// rendered yet (Phase E will add mermaid).
import { computed, ref } from 'vue'
import { useAiFrontierData } from '@/composables/useAiFrontierData'
import type { FrontierSource } from '@/api/ai-frontier'

const { loading, data, error } = useAiFrontierData()

type Filter = FrontierSource | 'all'
const filter = ref<Filter>('all')

const FILTERS: { key: Filter; label: string; emoji: string }[] = [
  { key: 'all', label: '全部', emoji: '🌐' },
  { key: 'paper', label: '论文', emoji: '📄' },
  { key: 'blog', label: '博客', emoji: '📝' },
  { key: 'tweet', label: '推文', emoji: '🐦' },
]

const filtered = computed(() => {
  if (filter.value === 'all') return data.value
  return data.value.filter((i) => i.source === filter.value)
})

function setFilter(f: Filter): void {
  filter.value = f
}
</script>

<template>
  <div class="view">
    <header class="topbar">
      <RouterLink to="/agents" class="back">← Agent Hub</RouterLink>
      <h1>🛰️ AI 前沿日报</h1>
      <span class="hint">stub 数据 · Phase E 接 /api/ai-frontier</span>
    </header>

    <div class="chips">
      <button
        v-for="f in FILTERS"
        :key="f.key"
        class="chip"
        :class="{ active: filter === f.key }"
        @click="setFilter(f.key)"
      >
        {{ f.emoji }} {{ f.label }}
      </button>
    </div>

    <div v-if="loading" class="state">加载中…</div>
    <div v-else-if="error" class="state err">加载失败：{{ error }}</div>

    <div v-else class="cards">
      <article v-for="item in filtered" :key="item.id" class="card">
        <header class="cardhead">
          <span class="src" :class="'src-' + item.source">{{ item.source }}</span>
          <span class="ts">{{ item.ts }}</span>
        </header>
        <h3 class="ctitle">{{ item.title }}</h3>
        <p class="csum">{{ item.summary }}</p>
        <div v-if="item.mermaid" class="mermaid-ph">
          <span class="ph-tag">📊 mermaid</span>
          <pre>{{ item.mermaid }}</pre>
        </div>
        <a class="link" :href="item.url" target="_blank" rel="noopener">来源 →</a>
      </article>
    </div>
  </div>
</template>

<style scoped lang="scss">
.view {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px 24px 32px;
  background: var(--bg);
  color: var(--text);
  overflow-y: auto;
}
.topbar { display: flex; align-items: baseline; gap: 14px; }
.topbar h1 { margin: 0; font-size: 20px; }
.back { color: var(--text-sec); font-size: 13px; text-decoration: none; }
.back:hover { color: var(--accent); }
.hint { font-size: 11px; color: var(--text-sec); margin-left: auto; }
.state { padding: 24px; color: var(--text-sec); &.err { color: var(--danger); } }

.chips { display: flex; gap: 8px; flex-wrap: wrap; }
.chip {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  color: var(--text-sec);
  border-radius: 999px;
  padding: 4px 12px;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.12s ease;
  &:hover { color: var(--text); border-color: var(--accent); }
  &.active { background: var(--accent-soft); color: var(--accent); border-color: var(--accent); }
}

.cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 14px; }
.card {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.cardhead { display: flex; justify-content: space-between; align-items: center; }
.src {
  font-size: 10px;
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 3px;
  text-transform: uppercase;
  &.src-paper { background: rgba(47, 111, 237, 0.18); color: #2f6fed; }
  &.src-blog { background: rgba(16, 163, 127, 0.18); color: #10a37f; }
  &.src-tweet { background: rgba(240, 180, 41, 0.2); color: #f0b429; }
}
.ts { font-size: 11px; color: var(--text-sec); font-family: var(--font-mono); }
.ctitle { margin: 0; font-size: 15px; font-weight: 600; }
.csum { margin: 0; font-size: 13px; color: var(--text-sec); line-height: 1.5; }
.mermaid-ph {
  background: var(--bg);
  border: 1px dashed var(--border);
  border-radius: var(--radius-sm);
  padding: 8px;
  font-size: 11px;
  color: var(--text-sec);
  pre { margin: 4px 0 0; font-family: var(--font-mono); white-space: pre-wrap; }
}
.ph-tag { font-weight: 600; color: var(--accent); }
.link { font-size: 12px; color: var(--accent); text-decoration: none; align-self: flex-start; }
.link:hover { text-decoration: underline; }
</style>
