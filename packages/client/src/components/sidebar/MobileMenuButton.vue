<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useSidebarStore } from '@/stores/sidebar'

const sidebar = useSidebarStore()
const shouldShow = ref(false)

function checkAndUpdate() {
  shouldShow.value = window.innerWidth <= 768
}

onMounted(() => {
  checkAndUpdate()
  window.addEventListener('resize', checkAndUpdate)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', checkAndUpdate)
})

const handleClick = () => {
  sidebar.toggleCollapsed()
}
</script>

<template>
  <button
    v-if="shouldShow"
    @click="handleClick"
    type="button"
    title="Toggle sidebar"
    class="mobile-menu-btn"
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
