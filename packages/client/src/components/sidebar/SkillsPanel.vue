<script setup lang="ts">
// SkillsPanel.vue — list of available agent skills. Phase C2 stub; Phase E
// will fetch from /api/skills (the registry the host already serves).
import { onMounted, ref } from 'vue'
import { fetchSkills, type SkillSummary } from '@/api/skills'

const skills = ref<SkillSummary[]>([])
const loading = ref(true)

onMounted(async () => {
  skills.value = await fetchSkills()
  loading.value = false
})

function open(s: SkillSummary) {
  console.info('[Phase E] open skill', s.id)
}
</script>

<template>
  <div class="skills-panel">
    <div class="header">SKILLS（共 {{ skills.length }}）</div>
    <div v-if="loading" class="empty">加载中…</div>
    <div v-else class="list">
      <button
        v-for="s in skills"
        :key="s.id"
        class="item"
        :title="s.description"
        @click="open(s)"
      >
        <span class="ic">{{ s.emoji }}</span>
        <span class="info">
          <span class="n">{{ s.name }}</span>
          <span class="d">{{ s.description }}</span>
        </span>
      </button>
    </div>
  </div>
</template>

<style scoped lang="scss">
.skills-panel { display: flex; flex-direction: column; flex: 1; padding: 8px; overflow-y: auto; }
.header {
  padding: 6px 4px;
  font-size: 11px;
  color: var(--text-sec);
  font-weight: 600;
}
.list { display: flex; flex-direction: column; gap: 4px; }
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
