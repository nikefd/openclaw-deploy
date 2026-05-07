<script setup lang="ts">
// SkillsPanel.vue — Phase E3 sidebar skills list backed by /api/skills.
// Two groups (user / builtin); click → drawer with full SKILL.md.
import { onMounted, ref, watch, nextTick } from 'vue'
import { useSkills } from '@/composables/useSkills'
import { useMarkdown } from '@/composables/useMarkdown'
import type { SkillSource } from '@/api/skills'

const {
  userEntries,
  builtinEntries,
  loading,
  error,
  selected,
  current,
  contentLoading,
  contentError,
  reload,
  open,
  clearSelection,
} = useSkills()

const { render, attachCodeCopyButtons } = useMarkdown()
const previewBox = ref<HTMLElement | null>(null)

onMounted(() => { void reload() })

watch(current, async () => {
  await nextTick()
  attachCodeCopyButtons(previewBox.value)
})

function isActive(name: string, source: SkillSource): boolean {
  return selected.value?.name === name && selected.value?.source === source
}
</script>

<template>
  <div class="skills-panel">
    <div class="header">
      <span class="title">SKILLS</span>
      <button class="action" :disabled="loading" @click="reload">{{ loading ? '…' : '刷新' }}</button>
    </div>

    <div v-if="error" class="error">加载失败：{{ error }}</div>

    <div v-if="userEntries.length" class="group">
      <div class="group-title">👤 用户自定义（{{ userEntries.length }}）</div>
      <button
        v-for="s in userEntries"
        :key="`user:${s.name}`"
        class="item"
        :class="{ active: isActive(s.name, 'user') }"
        :title="s.description"
        @click="open(s.name, 'user')"
      >
        <span class="ic">{{ s.emoji || '🛠️' }}</span>
        <span class="info">
          <span class="n">{{ s.name }}</span>
          <span class="d">{{ s.description }}</span>
        </span>
      </button>
    </div>

    <div v-if="builtinEntries.length" class="group">
      <div class="group-title">📦 内置（{{ builtinEntries.length }}）</div>
      <button
        v-for="s in builtinEntries"
        :key="`builtin:${s.name}`"
        class="item"
        :class="{ active: isActive(s.name, 'builtin') }"
        :title="s.description"
        @click="open(s.name, 'builtin')"
      >
        <span class="ic">{{ s.emoji || '🛠️' }}</span>
        <span class="info">
          <span class="n">{{ s.name }}</span>
          <span class="d">{{ s.description }}</span>
        </span>
      </button>
    </div>

    <div v-if="!loading && !userEntries.length && !builtinEntries.length" class="empty">没有可用 skill</div>

    <Transition name="drawer">
      <div v-if="selected" class="drawer">
        <div class="drawer-head">
          <span class="drawer-title">
            {{ current?.name ?? selected.name }}
            <span class="src">[{{ selected.source }}]</span>
          </span>
          <button class="close" @click="clearSelection">×</button>
        </div>
        <div v-if="contentLoading" class="drawer-body empty">读取中…</div>
        <div v-else-if="contentError" class="drawer-body error">读取失败：{{ contentError }}</div>
        <div v-else-if="current" class="drawer-body">
          <div class="loc">{{ current.location }}</div>
          <div ref="previewBox" class="markdown" v-html="render(current.content)" />
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped lang="scss">
.skills-panel {
  display: flex;
  flex-direction: column;
  flex: 1;
  padding: 8px;
  overflow-y: auto;
  position: relative;
}
.header {
  display: flex;
  align-items: center;
  padding: 6px 4px;
  font-size: 12px;
  color: var(--text-sec);
}
.title { flex: 1; font-weight: 600; }
.action {
  background: transparent;
  color: var(--text-sec);
  border: 1px solid var(--border);
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  cursor: pointer;
}
.action[disabled] { opacity: 0.5; cursor: wait; }
.error { color: #d4504e; padding: 8px 4px; font-size: 12px; }

.group { display: flex; flex-direction: column; gap: 4px; margin-top: 8px; }
.group-title {
  font-size: 11px;
  text-transform: uppercase;
  color: var(--text-sec);
  letter-spacing: 0.04em;
  padding: 0 4px 4px;
}

.item {
  display: flex;
  align-items: center;
  gap: 8px;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 6px;
  padding: 8px 10px;
  cursor: pointer;
  text-align: left;
  width: 100%;
  color: var(--sidebar-fg, var(--text));
}
.item:hover { background: var(--hover); border-color: var(--border); }
.item.active { background: var(--hover); border-color: var(--accent, #4c8bf5); }
.ic { font-size: 18px; flex: 0 0 22px; text-align: center; }
.info { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.n { font-size: 13px; font-weight: 500; }
.d {
  font-size: 11px;
  color: var(--text-sec);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.empty { padding: 16px; text-align: center; color: var(--text-sec); font-size: 12px; }

.drawer {
  position: absolute;
  inset: 0;
  background: var(--bg, #fff);
  display: flex;
  flex-direction: column;
  z-index: 5;
}
.drawer-head {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 10px;
  border-bottom: 1px solid var(--border);
}
.drawer-title { flex: 1; font-size: 13px; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.src { font-size: 10px; color: var(--text-sec); margin-left: 4px; }
.close {
  background: transparent;
  color: var(--text);
  border: 1px solid var(--border);
  border-radius: 4px;
  width: 26px;
  height: 24px;
  cursor: pointer;
  font-size: 14px;
  line-height: 1;
}
.drawer-body { padding: 10px 12px; overflow-y: auto; flex: 1; font-size: 13px; }
.loc { font-size: 11px; color: var(--text-sec); margin-bottom: 8px; word-break: break-all; }
.markdown :deep(pre) { background: var(--bg-elevated, #f5f5f5); padding: 8px; border-radius: 4px; overflow-x: auto; }
.markdown :deep(code) { font-family: ui-monospace, SFMono-Regular, monospace; font-size: 12px; }
.markdown :deep(h1), .markdown :deep(h2), .markdown :deep(h3) { margin-top: 12px; }

.drawer-enter-active, .drawer-leave-active { transition: transform 0.15s ease, opacity 0.15s ease; }
.drawer-enter-from, .drawer-leave-to { transform: translateX(8px); opacity: 0; }
</style>
