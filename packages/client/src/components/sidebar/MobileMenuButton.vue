<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useSidebarStore } from '@/stores/sidebar'

const sidebar = useSidebarStore()
const isMobile = ref(false)

function checkAndUpdate() {
  isMobile.value = window.innerWidth <= 768
}

const handleClick = () => {
  console.log('[MobileMenuButton] 点击按钮，当前 collapsed:', sidebar.collapsed);
  sidebar.toggleCollapsed();
  console.log('[MobileMenuButton] 点击后 collapsed:', sidebar.collapsed);
}

onMounted(() => {
  checkAndUpdate()
  window.addEventListener('resize', checkAndUpdate)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', checkAndUpdate)
})
</script>

<template>
  <!-- 不用 v-if，直接用 CSS 隐藏 -->
  <button
    @click="handleClick"
    type="button"
    title="Toggle sidebar"
    class="mobile-menu-btn"
    :style="{ display: isMobile ? 'block' : 'none' }"
  >
    ☰
  </button>
</template>

<style scoped>
.mobile-menu-btn {
  position: fixed;
  top: 50px;
  left: 12px;
  width: 40px;
  height: 40px;
  z-index: 9999;
  background: var(--sidebar-bg);
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 20px;
  cursor: pointer;
  color: var(--text);
  padding: 0;
  transition: background 0.2s ease;
}

.mobile-menu-btn:hover {
  background: var(--accent, #6366f1);
}

.mobile-menu-btn:active {
  opacity: 0.8;
}
</style>
