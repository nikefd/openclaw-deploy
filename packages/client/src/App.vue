<script setup lang="ts">
/**
 * App root. Layout for v2:
 *   ┌──────────┬─────────────────────────────┐
 *   │ sidebar  │  router-view (ChatView)     │
 *   │  (C2)    │                             │
 *   └──────────┴─────────────────────────────┘
 *
 * Phase C2 fills the sidebar slot left by C1 with <AppSidebar/> and mounts
 * the global <MentionPopup/> overlay + its document-level fallback hook.
 *
 * Theme handling moved to composables/useTheme.ts (called inside AppSidebar
 * which is always mounted). The early-paint `applyInitialTheme` retained so
 * the very first frame doesn't flash.
 */
import { onMounted, ref } from 'vue'
import { useSidebarStore } from '@/stores/sidebar'
// <!-- @C1-placeholder begin -->
// C1 originally rendered an inline sidebar-slot here. C2 swaps in AppSidebar.
import AppSidebar from '@/components/sidebar/AppSidebar.vue'
import MentionPopup from '@/components/chat/MentionPopup.vue'
import ModelDropdown from '@/components/chat/ModelDropdown.vue'
import ConnectionBanner from '@/components/ConnectionBanner.vue'
import { useMentionsFallback } from '@/composables/useMentions'
import { setupConnectionMonitor } from '@/composables/useConnectionRecovery'
// <!-- @C1-placeholder end -->

const sidebar = useSidebarStore()
const isMobile = ref(false)

function applyInitialTheme() {
  if (typeof document === 'undefined') return
  const html = document.documentElement
  if (html.getAttribute('data-theme')) return
  const stored = localStorage.getItem('oc_v2_theme')
  if (stored === 'dark' || stored === 'light') {
    html.setAttribute('data-theme', stored)
    return
  }
  const dark = window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? true
  html.setAttribute('data-theme', dark ? 'dark' : 'light')
}

onMounted(() => {
  applyInitialTheme()
  setupConnectionMonitor() // Monitor connection health
  
  // Check if mobile and listen for resize
  const checkMobile = () => {
    isMobile.value = window.innerWidth <= 768
  }
  checkMobile()
  window.addEventListener('resize', checkMobile)
})
useMentionsFallback()
</script>

<template>
  <div class="app-shell">
    <ConnectionBanner />
    <!-- Mobile menu button - always in DOM, hidden by CSS on desktop -->
    <button 
      class="mobile-menu-btn" 
      @click="sidebar.toggleCollapsed()"
      type="button"
      title="Toggle menu"
    >
      ☰
    </button>
    <!-- @C1-placeholder: was <aside class="sidebar-slot">…</aside> -->
    <AppSidebar />
    <main class="main-pane">
      <router-view />
      <!--
        Phase C2: ModelDropdown is rendered as a floating overlay in the
        top-right of the main pane. Phase D will lift it into ChatPane.topbar
        once C1's component is allowed to be modified.
      -->
      <div class="model-dd-overlay">
        <ModelDropdown />
      </div>
    </main>
    <MentionPopup />
  </div>
</template>

<style>
/* 全局样式 - 不用 scoped，确保 media query 生效 */
.app-shell {
  display: flex;
  height: 100vh;
  width: 100vw;
  overflow: hidden;
}
.main-pane {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  background: var(--bg);
  position: relative;
  padding-top: 0;
}
.model-dd-overlay {
  position: absolute;
  top: 12px;
  right: 16px;
  z-index: 30;
}

/* 菜单按钮 - 桌面隐藏，移动显示 */
.mobile-menu-btn {
  display: none !important;
  position: fixed;
  top: 50px;
  left: 12px;
  z-index: 9999;
  width: 40px;
  height: 40px;
  background: var(--sidebar-bg);
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 20px;
  cursor: pointer;
  color: var(--text);
  transition: background 0.2s ease;
  padding: 0;
}
.mobile-menu-btn:hover {
  background: var(--hover);
}
.mobile-menu-btn:active {
  opacity: 0.8;
}

/* 移动端：显示菜单按钮 */
@media (max-width: 768px) {
  .mobile-menu-btn {
    display: block !important;
  }
  .app-shell {
    flex-direction: column;
  }
  .main-pane {
    width: 100vw;
    height: 100vh;
    padding-top: 40px;
  }
}
</style>
