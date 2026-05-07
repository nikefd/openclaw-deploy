<script setup lang="ts">
/**
 * SidebarFooter.vue — Minimalist footer with theme + logout
 *
 * Only shows:
 * - Theme toggle (dark/light/auto)
 * - Logout button
 *
 * Delegates to composables for actual business logic.
 */

import { computed } from 'vue'
import { useTheme } from '@/composables/useTheme'
import { useAuth } from '@/composables/useAuth'

interface Props {
  collapsed?: boolean
}

withDefaults(defineProps<Props>(), {
  collapsed: false,
})

const { mode: themeMode, cycle: cycleTheme } = useTheme()
const { logout } = useAuth()

const themeIcon = computed(() => {
  if (themeMode.value === 'dark') return '🌙'
  if (themeMode.value === 'light') return '☀️'
  return '🌓'
})

async function handleLogout() {
  try {
    await logout()
  } catch (err) {
    console.error('[SidebarFooter] logout failed:', err)
  }
}
</script>

<template>
  <div class="sidebar-footer">
    <!-- Theme -->
    <button
      class="footer-btn"
      :title="`Theme: ${themeMode}`"
      @click="cycleTheme"
    >
      <span class="emoji">{{ themeIcon }}</span>
      <span v-if="!collapsed" class="label">Theme</span>
    </button>

    <!-- Logout -->
    <button
      class="footer-btn danger"
      title="Logout"
      @click="handleLogout"
    >
      <span class="emoji">🚪</span>
      <span v-if="!collapsed" class="label">Logout</span>
    </button>
  </div>
</template>

<style scoped lang="scss">
.sidebar-footer {
  display: flex;
  gap: 4px;
  align-items: center;
  padding: 0 8px;
}

.footer-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--text-sec);
  cursor: pointer;
  font-size: 12px;
  transition: all 0.15s ease;
  flex: 1;
  min-width: 0;

  &:hover {
    background: var(--hover);
    color: var(--text);
  }

  &.danger {
    color: var(--text-sec);

    &:hover {
      background: rgba(239, 68, 68, 0.1);
      color: #ef4444;
    }
  }

  .emoji {
    font-size: 14px;
    flex-shrink: 0;
  }

  .label {
    font-size: 12px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
}
</style>
