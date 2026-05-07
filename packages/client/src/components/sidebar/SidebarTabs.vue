<script setup lang="ts">
// SidebarTabs.vue — three-tab segmented control (Chats / Memory / Skills).
// The actual tab panes are kept alive by AppSidebar so switching tabs is
// instant.
import { storeToRefs } from 'pinia'
import { useSidebarStore, type SidebarTab } from '@/stores/sidebar'

const sidebar = useSidebarStore()
const { activeTab } = storeToRefs(sidebar)

const tabs: Array<{ id: SidebarTab; label: string; icon: string }> = [
  { id: 'chats', label: 'Chats', icon: '💬' },
  { id: 'memory', label: 'Memory', icon: '🧠' },
  { id: 'skills', label: 'Skills', icon: '🛠️' },
]
</script>

<template>
  <div class="tabs">
    <button
      v-for="t in tabs"
      :key="t.id"
      class="tab"
      :class="{ active: activeTab === t.id }"
      @click="sidebar.setActiveTab(t.id)"
    >
      <span class="ic">{{ t.icon }}</span>
      <span class="lbl">{{ t.label }}</span>
    </button>
  </div>
</template>

<style scoped lang="scss">
.tabs {
  display: flex;
  gap: 2px;
  padding: 6px 8px 0;
}
.tab {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  background: transparent;
  border: none;
  color: var(--text-sec);
  cursor: pointer;
  padding: 6px 4px;
  border-radius: 6px;
  font-size: 11px;
  transition: background 0.12s, color 0.12s;
}
.tab:hover { background: var(--hover); color: var(--text); }
.tab.active {
  background: var(--sidebar-active-bg);
  color: var(--sidebar-fg, var(--text));
  font-weight: 600;
}
.ic { font-size: 13px; }
</style>
