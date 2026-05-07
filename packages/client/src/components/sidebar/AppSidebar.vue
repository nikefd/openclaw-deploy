<script setup lang="ts">
// AppSidebar.vue — the chrome around ChatList / MemoryPanel / SkillsPanel.
// Owns the collapse toggle, theme cycler, and a stub user/settings strip at
// the bottom. Tab panes are kept alive so switching doesn't refetch the
// stub APIs every time.
import { storeToRefs } from 'pinia'
import { useSidebarStore } from '@/stores/sidebar'
import SidebarTabs from './SidebarTabs.vue'
import ChatList from './ChatList.vue'
import MemoryPanel from './MemoryPanel.vue'
import SkillsPanel from './SkillsPanel.vue'
import ChatSearch from './ChatSearch.vue'
import SidebarFooter from './SidebarFooter.vue'
import { RouterLink } from 'vue-router'

const sidebar = useSidebarStore()
const { collapsed, activeTab } = storeToRefs(sidebar)
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

    <div v-if="!collapsed" class="aux-section">
      <div class="aux">
        <RouterLink to="/agents" class="aux-link">🤖 Agents</RouterLink>
        <RouterLink to="/terminal" class="aux-link">💻 Terminal</RouterLink>
        <RouterLink to="/tasks" class="aux-link">📋 Tasks</RouterLink>
        <RouterLink to="/usage" class="aux-link">💰 Usage</RouterLink>
        <RouterLink to="/architecture" class="aux-link">🗺️ Architecture</RouterLink>
        <RouterLink to="/files" class="aux-link">📁 Files</RouterLink>
        <RouterLink to="/perf" class="aux-link">📊 Perf</RouterLink>
      </div>
      <SidebarFooter :collapsed="collapsed" />
    </div>
    <div v-else class="aux-collapsed">
      <SidebarFooter :collapsed="collapsed" />
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

.aux {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 6px 8px;
}
.aux-link {
  display: block;
  padding: 6px 10px;
  border-radius: var(--radius-sm, 6px);
  color: var(--text-sec);
  font-size: 13px;
  text-decoration: none;
}
.aux-link:hover { background: var(--hover); color: var(--text); }
.aux-link.router-link-active { background: var(--sidebar-active-bg); color: var(--text); }

.aux-section {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  border-top: 1px solid var(--border);
}

.aux {
  flex: 1;
  overflow-y: auto;
}

.aux-collapsed {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 6px;
  border-top: 1px solid var(--border);
}
</style>
