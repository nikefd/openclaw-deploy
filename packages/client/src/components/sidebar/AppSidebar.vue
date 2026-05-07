<script setup lang="ts">
// AppSidebar.vue — the chrome around ChatList / MemoryPanel / SkillsPanel.
// Owns the collapse toggle, theme cycler, and a stub user/settings strip at
// the bottom. Tab panes are kept alive so switching doesn't refetch the
// stub APIs every time.
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useSidebarStore } from '@/stores/sidebar'
import { useTheme } from '@/composables/useTheme'
import SidebarTabs from './SidebarTabs.vue'
import ChatList from './ChatList.vue'
import MemoryPanel from './MemoryPanel.vue'
import SkillsPanel from './SkillsPanel.vue'
import ChatSearch from './ChatSearch.vue'

const sidebar = useSidebarStore()
const { collapsed, activeTab } = storeToRefs(sidebar)
const { mode: themeMode, cycle: cycleTheme } = useTheme()

const themeIcon = computed(() => {
  if (themeMode.value === 'dark') return '🌙'
  if (themeMode.value === 'light') return '☀️'
  return '🌓'
})

function onSettings() {
  console.info('[Phase E] open settings')
}
</script>

<template>
  <aside class="sidebar" :class="{ collapsed }">
    <div class="head">
      <div class="logo">
        <span class="dot">🐶</span>
        <span v-if="!collapsed" class="brand">OpenClaw</span>
      </div>
      <button class="icon-btn" :title="collapsed ? '展开' : '折叠'" @click="sidebar.toggleCollapsed">
        {{ collapsed ? '»' : '«' }}
      </button>
    </div>

    <SidebarTabs v-if="!collapsed" />

    <div v-if="!collapsed" class="pane">
      <KeepAlive>
        <ChatList v-if="activeTab === 'chats'" />
        <MemoryPanel v-else-if="activeTab === 'memory'" />
        <SkillsPanel v-else />
      </KeepAlive>
    </div>
    <div v-else class="collapsed-rail">
      <button
        v-for="t in (['chats','memory','skills'] as const)"
        :key="t"
        class="rail-btn"
        :class="{ active: activeTab === t }"
        @click="sidebar.setActiveTab(t)"
      >
        <span v-if="t==='chats'">💬</span>
        <span v-else-if="t==='memory'">🧠</span>
        <span v-else>🛠️</span>
      </button>
    </div>

    <div class="foot">
      <div v-if="!collapsed" class="user">
        <span class="avatar">🐶</span>
        <span class="name">斌哥</span>
      </div>
      <button class="icon-btn" :title="`主题: ${themeMode}`" @click="cycleTheme">
        {{ themeIcon }}
      </button>
      <button class="icon-btn" title="设置" @click="onSettings">⚙️</button>
    </div>

    <ChatSearch />
  </aside>
</template>

<style scoped lang="scss">
.sidebar {
  display: flex;
  flex-direction: column;
  width: 240px;
  height: 100%;
  background: var(--sidebar-bg);
  color: var(--sidebar-fg, var(--text));
  border-right: 1px solid var(--border);
  transition: width 0.16s ease;
  flex-shrink: 0;
}
.sidebar.collapsed { width: 56px; }

.head {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 8px;
  border-bottom: 1px solid var(--border);
}
.logo {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 600;
  font-size: 14px;
  min-width: 0;
}
.dot { font-size: 18px; }
.brand { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

.icon-btn {
  background: transparent;
  border: none;
  color: var(--text-sec);
  cursor: pointer;
  padding: 4px 6px;
  border-radius: 4px;
  font-size: 13px;
}
.icon-btn:hover { background: var(--hover); color: var(--text); }

.pane {
  display: flex;
  flex: 1;
  min-height: 0;
}

.collapsed-rail {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 6px;
  flex: 1;
}
.rail-btn {
  width: 32px;
  height: 32px;
  background: transparent;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 16px;
  color: var(--text-sec);
}
.rail-btn:hover { background: var(--hover); }
.rail-btn.active { background: var(--sidebar-active-bg); color: var(--text); }

.foot {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px;
  border-top: 1px solid var(--border);
}
.user {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
}
.avatar { font-size: 18px; }
</style>
