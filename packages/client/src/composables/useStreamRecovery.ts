/**
 * useStreamRecovery.ts — Recover streaming state after page reload
 *
 * When user refreshes page while a stream is in progress:
 * 1. Save streaming state to localStorage before unmount
 * 2. On mount, check if we were streaming for this sid
 * 3. If so, reconnect and resume streaming
 *
 * Follows clean architecture: composable = business logic + state recovery
 */

import { watch, type Ref } from 'vue'

export interface StreamRecoveryState {
  sid: string
  savedDelta: string
  timestamp: number
}

const STORAGE_KEY = 'oc_v2_stream_recovery'

export function useStreamRecovery(
  sid: Ref<string>,
  isStreaming: Ref<boolean>,
  streamingDelta: Ref<string>,
) {
  /**
   * Save stream state to localStorage
   * Called when streaming is in progress and we're about to unmount
   */
  function saveStreamState(): void {
    if (isStreaming.value && streamingDelta.value) {
      const state: StreamRecoveryState = {
        sid: sid.value,
        savedDelta: streamingDelta.value,
        timestamp: Date.now(),
      }
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
      } catch {
        // quota exceeded or disabled
      }
    }
  }

  /**
   * Restore stream state from localStorage
   * Returns the saved state if available and not too old (5 minutes)
   */
  function getStreamState(): StreamRecoveryState | null {
    try {
      const stored = localStorage.getItem(STORAGE_KEY)
      if (!stored) return null

      const state = JSON.parse(stored) as StreamRecoveryState
      const age = Date.now() - state.timestamp
      const MAX_AGE = 5 * 60 * 1000 // 5 minutes

      if (age > MAX_AGE) {
        localStorage.removeItem(STORAGE_KEY)
        return null
      }

      return state
    } catch {
      return null
    }
  }

  /**
   * Clear saved stream state
   * Called when streaming completes or fails
   */
  function clearStreamState(): void {
    try {
      localStorage.removeItem(STORAGE_KEY)
    } catch {
      // ignore
    }
  }

  // Auto-save when streaming changes
  watch(
    [() => isStreaming.value, () => streamingDelta.value],
    () => {
      if (isStreaming.value) {
        saveStreamState()
      }
    },
  )

  return {
    saveStreamState,
    getStreamState,
    clearStreamState,
  }
}
