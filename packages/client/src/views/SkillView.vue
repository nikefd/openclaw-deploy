<script setup lang="ts">
// SkillView.vue — Phase E3.1 reader view for /v2/skills/:source/:name
import { ref, watch, onMounted, nextTick, computed } from 'vue'
import { useRoute, useRouter, RouterLink } from 'vue-router'
import { fetchSkillContent, type SkillFile, type SkillSource } from '@/api/skills'
import { useMarkdown } from '@/composables/useMarkdown'

const route = useRoute()
const router = useRouter()
const { render, attachCodeCopyButtons } = useMarkdown()

const skill = ref<SkillFile | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
const bodyRef = ref<HTMLElement | null>(null)

const source = computed<SkillSource>(() => (route.params.source === 'user' ? 'user' : 'builtin'))
const name = computed<string>(() => String(route.params.name ?? ''))

async function load(): Promise<void> {
  if (!name.value) return
  loading.value = true
  error.value = null
  try {
    skill.value = await fetchSkillContent(name.value, source.value)
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
    skill.value = null
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch(() => route.fullPath, load)
watch(skill, async () => {
  await nextTick()
  attachCodeCopyButtons(bodyRef.value)
})

function back(): void {
  if (window.history.length > 1) router.back()
  else router.push('/')
}
</script>

<template>
  <div class="skill-reader">
    <header class="topbar">
      <button class="back" @click="back" title="返回">←</button>
      <div class="title">
        <span class="emoji">🛠️</span>
        <span class="name">{{ skill?.name || name }}</span>
        <span class="badge" :class="source">{{ source === 'user' ? '用户' : '内置' }}</span>
      </div>
      <RouterLink class="link" to="/">关闭</RouterLink>
    </header>

    <div v-if="loading" class="state">读取中…</div>
    <div v-else-if="error" class="state error">读取失败：{{ error }}</div>
    <div v-else-if="skill" class="content">
      <div class="loc" :title="skill.location">{{ skill.location }}</div>
      <div ref="bodyRef" class="markdown" v-html="render(skill.content)" />
    </div>
  </div>
</template>

<style scoped lang="scss">
.skill-reader {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg, #1a1a1e);
  color: var(--text, #e4e4e7);
}
.topbar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 24px;
  border-bottom: 1px solid var(--border, #2a2a30);
  background: var(--bg, #1a1a1e);
  position: sticky;
  top: 0;
  z-index: 1;
}
.back {
  background: transparent;
  color: var(--text, #e4e4e7);
  border: 1px solid var(--border, #2a2a30);
  border-radius: 4px;
  width: 32px; height: 28px;
  cursor: pointer; font-size: 14px;
}
.title { flex: 1; display: flex; align-items: center; gap: 8px; overflow: hidden; }
.emoji { font-size: 20px; }
.name { font-size: 16px; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.badge { font-size: 10px; padding: 2px 6px; border-radius: 3px; border: 1px solid var(--border, #2a2a30); color: var(--text-sec, #a1a1aa); }
.badge.user { color: #4c8bf5; border-color: #4c8bf5; }
.badge.builtin { color: #71717a; }
.link { color: var(--text-sec, #a1a1aa); font-size: 12px; text-decoration: none; padding: 4px 10px; border-radius: 4px; border: 1px solid var(--border, #2a2a30); }
.link:hover { color: var(--text, #e4e4e7); }
.state { padding: 40px; text-align: center; color: var(--text-sec, #a1a1aa); }
.state.error { color: #d4504e; }
.content { flex: 1; overflow-y: auto; padding: 32px 48px; max-width: 880px; margin: 0 auto; width: 100%; box-sizing: border-box; }
.loc { font-size: 11px; color: var(--text-sec, #a1a1aa); font-family: ui-monospace, monospace; margin-bottom: 16px; word-break: break-all; }
.markdown { font-size: 15px; line-height: 1.7; }
.markdown :deep(h1) { font-size: 24px; margin: 24px 0 12px; }
.markdown :deep(h2) { font-size: 19px; margin: 20px 0 10px; }
.markdown :deep(h3) { font-size: 16px; margin: 16px 0 8px; }
.markdown :deep(p) { margin: 10px 0; }
.markdown :deep(ul), .markdown :deep(ol) { padding-left: 24px; margin: 10px 0; }
.markdown :deep(li) { margin: 4px 0; }
.markdown :deep(pre) { background: var(--bg-elevated, #27272a); padding: 14px; border-radius: 6px; overflow-x: auto; font-size: 13px; margin: 12px 0; }
.markdown :deep(code) { font-family: ui-monospace, SFMono-Regular, monospace; }
.markdown :deep(:not(pre) > code) { background: var(--bg-elevated, #27272a); padding: 2px 6px; border-radius: 3px; font-size: 13px; }
.markdown :deep(blockquote) { border-left: 3px solid var(--border, #2a2a30); padding-left: 14px; color: var(--text-sec, #a1a1aa); margin: 12px 0; }
.markdown :deep(a) { color: #4c8bf5; }
</style>
