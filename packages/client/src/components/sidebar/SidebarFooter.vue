<script setup lang="ts">
/**
 * SidebarFooter.vue — User profile + action buttons
 *
 * Responsible for:
 * - Theme cycling (dark/light/auto)
 * - Clear all chats
 * - Logout
 * - Settings (stub)
 *
 * Delegates to composables for actual business logic.
 */

import { computed, ref } from 'vue'
import { useTheme } from '@/composables/useTheme'
import { useAuth } from '@/composables/useAuth'
import { useSidebarActions } from '@/composables/useSidebarActions'

interface Props {
  collapsed?: boolean
  userName?: string
}

withDefaults(defineProps<Props>(), {
  collapsed: false,
  userName: '斌哥',
})

const { mode: themeMode, cycle: cycleTheme } = useTheme()
const { logout } = useAuth()
const { clearAllChats } = useSidebarActions()

// Confirmation dialogs
const showClearConfirm = ref(false)
const isClearing = ref(false)

const themeIcon = computed(() => {
  if (themeMode.value === 'dark') return '🌙'
  if (themeMode.value === 'light') return '☀️'
  return '🌓'
})

async function confirmClearAll() {
  if (!showClearConfirm.value) {
    showClearConfirm.value = true
    return
  }
  
  try {
    isClearing.value = true
    await clearAllChats()
    showClearConfirm.value = false
  } catch (err) {
    console.error('[SidebarFooter] clearAllChats failed:', err)
  } finally {
    isClearing.value = false
  }
}

function cancelClear() {
  showClearConfirm.value = false
}

async function handleLogout() {
  try {
    await logout()
  } catch (err) {
    console.error('[SidebarFooter] logout failed:', err)
  }
}

function onSettings() {
  console.info('[SidebarFooter] settings (stub)')
}
</script>

<template>
  <div class="sidebar-footer">
    <!-- User Profile -->
    <div v-if="!collapsed" class="user-profile">
      <div class="user-info">
        <span class="avatar">🐶</span>
        <span class="name">{{ userName }}</span>
      </div>
    </div>

    <!-- Action Buttons -->
    <div class="footer-actions" :class="{ collapsed }">
      <!-- Theme -->
      <button
        class="action-btn"
        :title="`Theme: ${themeMode}`"
        @click="cycleTheme"
      >
        <span class="emoji">{{ themeIcon }}</span>
        <span v-if="!collapsed" class="label">Theme</span>
      </button>

      <!-- Clear All -->
      <button
        class="action-btn"
        :title="showClearConfirm ? '确认清空所有对话?' : '清空所有对话'"
        :class="{ confirm: showClearConfirm, loading: isClearing }"
        @click="confirmClearAll"
      >
        <span class="emoji">🗑️</span>
        <span v-if="!collapsed" class="label">{{ showClearConfirm ? 'Confirm?' : 'Clear All' }}</span>
      </button>

      <!-- Settings -->
      <button
        class="action-btn"
        title="Settings"
        @click="onSettings"
      >
        <span class="emoji">⚙️</span>
        <span v-if="!collapsed" class="label">Settings</span>
      </button>

      <!-- Logout -->
      <button
        class="action-btn danger"
        title="Logout"
        @click="handleLogout"
      >
        <span class="emoji">🚪</span>
        <span v-if="!collapsed" class="label">Logout</span>
      </button>
    </div>

    <!-- Confirmation Modal -->
    <Teleport to="body" v-if="showClearConfirm">
      <div class="modal-overlay" @click="cancelClear">
        <div class="modal-dialog" @click.stop>
          <div class="modal-header">
            <span>Clear All Chats?</span>
            <button class="close-btn" @click="cancelClear">✕</button>
          </div>
          <div class="modal-body">
            <p>This will delete all {{ 229 }} conversations. This action cannot be undone.</p>
          </div>
          <div class="modal-footer">
            <button class="btn btn-secondary" @click="cancelClear">Cancel</button>
            <button class="btn btn-danger" @click="confirmClearAll" :disabled="isClearing">
              {{ isClearing ? 'Clearing...' : 'Clear All' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped lang="scss">
.sidebar-footer {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 12px 8px;
  border-top: 1px solid var(--border);
  background: var(--sidebar-bg);
}

.user-profile {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px;
  border-radius: 6px;
  background: var(--hover);
}

.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
}

.avatar {
  font-size: 18px;
  flex-shrink: 0;
}

.name {
  font-size: 13px;
  font-weight: 500;
  color: var(--text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.footer-actions {
  display: flex;
  flex-direction: column;
  gap: 4px;

  &.collapsed {
    gap: 6px;
  }
}

.action-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--text-sec);
  cursor: pointer;
  font-size: 12px;
  transition: all 0.15s ease;

  &:hover {
    background: var(--hover);
    color: var(--text);
  }

  &.confirm {
    background: rgba(239, 68, 68, 0.1);
    color: #ef4444;
  }

  &.danger {
    color: var(--text-sec);

    &:hover {
      background: rgba(239, 68, 68, 0.1);
      color: #ef4444;
    }
  }

  &.loading {
    opacity: 0.6;
    cursor: not-allowed;
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

/* Modal styles */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-dialog {
  background: var(--input-bg);
  border: 1px solid var(--border);
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  min-width: 320px;
  max-width: 480px;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px;
  border-bottom: 1px solid var(--border);
  font-weight: 500;
  color: var(--text);
}

.close-btn {
  background: none;
  border: none;
  color: var(--text-sec);
  cursor: pointer;
  font-size: 18px;
  padding: 0 4px;

  &:hover {
    color: var(--text);
  }
}

.modal-body {
  padding: 16px;
  color: var(--text-sec);
  font-size: 13px;
  line-height: 1.5;
}

.modal-footer {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  padding: 12px 16px;
  border-top: 1px solid var(--border);
}

.btn {
  padding: 8px 16px;
  border: none;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s ease;

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
}

.btn-secondary {
  background: var(--hover);
  color: var(--text);

  &:hover:not(:disabled) {
    background: rgba(255, 255, 255, 0.1);
  }
}

.btn-danger {
  background: rgba(239, 68, 68, 0.1);
  color: #ef4444;

  &:hover:not(:disabled) {
    background: rgba(239, 68, 68, 0.2);
  }
}
</style>
