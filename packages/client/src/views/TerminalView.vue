<script setup lang="ts">
/**
 * TerminalView.vue — Terminal access panel
 *
 * Phase F.0: Terminal integration
 *
 * Supports two modes:
 * 1. Local: iframe loading /terminal/ (ttyd)
 * 2. Remote: (placeholder for future multi-node support)
 *
 * Architecture:
 * - UI layer: TerminalView (presentation)
 * - Composable: useTerminal (state + setup)
 * - API: fetch /terminal/ or remote shell endpoint
 */

import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useTerminal } from '@/composables/useTerminal'

const containerRef = ref<HTMLDivElement | null>(null)
const { isReady, loadTerminal, unloadTerminal } = useTerminal()

onMounted(() => {
  loadTerminal()
})

onBeforeUnmount(() => {
  unloadTerminal()
})
</script>

<template>
  <div class="terminal-view">
    <div class="terminal-header">
      <h2>Terminal</h2>
      <p class="terminal-hint">Access system terminal via ttyd</p>
    </div>

    <div 
      ref="containerRef"
      class="terminal-container"
      :class="{ loading: !isReady }"
    >
      <!-- ttyd will iframe here -->
      <iframe 
        v-if="isReady"
        class="terminal-frame"
        src="/terminal/"
        title="Terminal"
      />
      <div v-else class="terminal-loading">
        <div class="spinner"></div>
        <p>Loading terminal...</p>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.terminal-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg);
  color: var(--text);
  overflow: hidden;
}

.terminal-header {
  padding: 16px;
  border-bottom: 1px solid var(--border);
  background: var(--sidebar-bg);

  h2 {
    margin: 0 0 4px 0;
    font-size: 16px;
    font-weight: 600;
    color: var(--text);
  }

  .terminal-hint {
    margin: 0;
    font-size: 12px;
    color: var(--text-sec);
  }
}

.terminal-container {
  flex: 1;
  min-height: 0;
  position: relative;
  background: #1e1e1e;
  overflow: hidden;

  &.loading {
    display: flex;
    align-items: center;
    justify-content: center;
  }
}

.terminal-frame {
  width: 100%;
  height: 100%;
  border: none;
  background: #1e1e1e;
}

.terminal-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  color: var(--text-sec);
  font-size: 13px;
}

.spinner {
  width: 32px;
  height: 32px;
  border: 2px solid rgba(255, 255, 255, 0.2);
  border-top-color: rgba(255, 255, 255, 0.8);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
