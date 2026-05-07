/**
 * useTerminal.ts — Terminal lifecycle management
 *
 * Encapsulates:
 * - ttyd iframe loading detection
 * - Terminal state (ready/loading)
 * - Cleanup on unmount
 *
 * Follows clean architecture: composable = use case + orchestration layer
 */

import { ref } from 'vue'

export function useTerminal() {
  const isReady = ref(false)
  const loadTimeout = ref<ReturnType<typeof setTimeout> | null>(null)

  /**
   * Load terminal iframe
   * ttyd will auto-load at /terminal/ endpoint
   * We just need to set the ready flag after a brief delay
   */
  function loadTerminal(): void {
    // Give ttyd iframe time to initialize
    loadTimeout.value = setTimeout(() => {
      isReady.value = true
      console.info('[useTerminal] terminal loaded')
    }, 500)
  }

  function unloadTerminal(): void {
    if (loadTimeout.value) {
      clearTimeout(loadTimeout.value)
      loadTimeout.value = null
    }
    isReady.value = false
  }

  return {
    isReady,
    loadTerminal,
    unloadTerminal,
  }
}
