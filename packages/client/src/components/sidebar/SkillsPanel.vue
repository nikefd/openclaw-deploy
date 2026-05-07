<script setup lang="ts">
// SkillsPanel.vue — Phase E3.1 sidebar skills list.
// Click → navigates to /skills/:source/:name in main content area.
import { onMounted } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { useSkills } from '@/composables/useSkills'
import type { SkillSource } from '@/api/skills'

const route = useRoute()
const { userEntries, builtinEntries, loading, error, reload } = useSkills()

onMounted(() => { void reload() })

function isActive(name: string, source: SkillSource): boolean {
  return route.params.name === name && route.params.source === source
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
      <RouterLink
        v-for="s in userEntries"
        :key="`user:${s.name}`"
        :to="`/skills/user/${s.name}`"
        class="item"
        :class="{ active: isActive(s.name, 'user') }"
        :title="s.description"
      >
        <span class="ic">{{ s.emoji || '🛠️' }}</span>
        <span class="info">
          <span class="n">{{ s.name }}</span>
          <span class="d">{{ s.description }}</span>
        </span>
      </RouterLink>
    </div>

    <div v-if="builtinEntries.length" class="group">
      <div class="group-title">📦 内置（{{ builtinEntries.length }}）</div>
      <RouterLink
        v-for="s in builtinEntries"
        :key="`builtin:${s.name}`"
        :to="`/skills/builtin/${s.name}`"
        class="item"
        :class="{ active: isActive(s.name, 'builtin') }"
        :title="s.description"
      >
        <span class="ic">{{ s.emoji || '🛠️' }}</span>
        <span class="info">
          <span class="n">{{ s.name }}</span>
          <span class="d">{{ s.description }}</span>
        </span>
      </RouterLink>
    </div>

    <div v-if="!loading && !userEntries.length && !builtinEntries.length" class="empty">没有可用 skill</div>
  </div>
</template>

<style scoped lang="scss">
.skills-panel { display: flex; flex-direction: column; flex: 1; padding: 8px; overflow-y: auto; }
.header { display: flex; align-items: center; padding: 6px 4px; font-size: 12px; color: var(--text-sec); }
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
  text-decoration: none;
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
</style>
