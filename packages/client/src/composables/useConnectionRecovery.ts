/**
 * useConnectionRecovery.ts — Mobile network resilience
 *
 * Handles network disconnections gracefully:
 * - Detects connection loss (online/offline)
 * - Auto-reconnect with exponential backoff
 * - Restores active streams after network recovery
 * - Prevents zombie connections
 */

import { ref, onMounted, onUnmounted } from 'vue'

export interface ConnectionState {
  isOnline: boolean
  isConnecting: boolean
  lastError?: string
  retryCount: number
  nextRetryIn: number
}

const MAX_RETRIES = 5
const INITIAL_RETRY_DELAY = 1000 // 1s
const MAX_RETRY_DELAY = 30000 // 30s

export function useConnectionRecovery() {
  const state = ref<ConnectionState>({
    isOnline: navigator.onLine,
    isConnecting: false,
    retryCount: 0,
    nextRetryIn: 0,
  })

  let retryTimer: ReturnType<typeof setTimeout> | null = null
  let countdownTimer: ReturnType<typeof setInterval> | null = null

  /**
   * Handle online event
   */
  const handleOnline = () => {
    state.value.isOnline = true
    state.value.retryCount = 0
    state.value.lastError = undefined

    // Trigger reconnect immediately
    reconnect()
  }

  /**
   * Handle offline event
   */
  const handleOffline = () => {
    state.value.isOnline = false
    state.value.lastError = 'Network disconnected'
    clearRetryTimer()
  }

  /**
   * Calculate retry delay with exponential backoff
   */
  const getRetryDelay = (attempt: number): number => {
    const delay = INITIAL_RETRY_DELAY * Math.pow(2, attempt)
    const jitter = Math.random() * 1000 // 0-1s random jitter
    return Math.min(delay + jitter, MAX_RETRY_DELAY)
  }

  /**
   * Attempt to reconnect
   */
  const reconnect = async () => {
    if (!state.value.isOnline) {
      state.value.lastError = 'Device is offline'
      return
    }

    if (state.value.isConnecting) return

    state.value.isConnecting = true
    try {
      // Test connection by pinging the server
      const response = await fetch('/api/health', {
        method: 'GET',
        cache: 'no-cache',
        signal: AbortSignal.timeout(5000), // 5s timeout
      })

      if (response.ok) {
        state.value.isConnecting = false
        state.value.retryCount = 0
        state.value.lastError = undefined

        // Trigger app-wide reconnection
        window.dispatchEvent(new CustomEvent('connection-recovered'))
        return true
      } else {
        throw new Error(`Server returned ${response.status}`)
      }
    } catch (err) {
      state.value.isConnecting = false
      state.value.lastError = (err as Error).message

      // Schedule retry
      if (state.value.retryCount < MAX_RETRIES) {
        const delay = getRetryDelay(state.value.retryCount)
        state.value.retryCount++
        scheduleRetry(delay)
        return false
      } else {
        state.value.lastError = 'Max retries exceeded'
        return false
      }
    }
  }

  /**
   * Schedule next retry with countdown
   */
  const scheduleRetry = (delayMs: number) => {
    state.value.nextRetryIn = Math.ceil(delayMs / 1000)

    // Countdown timer
    if (countdownTimer) clearInterval(countdownTimer)
    countdownTimer = setInterval(() => {
      state.value.nextRetryIn--
      if (state.value.nextRetryIn <= 0) {
        clearInterval(countdownTimer!)
        countdownTimer = null
      }
    }, 1000)

    // Retry timer
    clearRetryTimer()
    retryTimer = setTimeout(() => {
      retryTimer = null
      void reconnect()
    }, delayMs)
  }

  /**
   * Clear retry timer
   */
  const clearRetryTimer = () => {
    if (retryTimer) {
      clearTimeout(retryTimer)
      retryTimer = null
    }
    if (countdownTimer) {
      clearInterval(countdownTimer)
      countdownTimer = null
    }
    state.value.nextRetryIn = 0
  }

  /**
   * Force immediate reconnect
   */
  const forceReconnect = async () => {
    state.value.retryCount = 0
    clearRetryTimer()
    return reconnect()
  }

  onMounted(() => {
    // Listen for online/offline events
    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)

    // Check connection on visibility change (app comes to foreground)
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'visible') {
        // User came back to app, check connection
        void forceReconnect()
      }
    })

    // Also check on app focus
    window.addEventListener('focus', () => {
      void forceReconnect()
    })
  })

  onUnmounted(() => {
    window.removeEventListener('online', handleOnline)
    window.removeEventListener('offline', handleOffline)
    clearRetryTimer()
  })

  return {
    state,
    reconnect,
    forceReconnect,
  }
}

/**
 * Global connection monitor (run once on app startup)
 */
export function setupConnectionMonitor() {
  const { state, forceReconnect } = useConnectionRecovery()

  // Periodically check if we're still connected (every 30s)
  const healthCheckInterval = setInterval(async () => {
    if (state.value.isOnline && !state.value.isConnecting) {
      try {
        const response = await fetch('/api/health', {
          cache: 'no-cache',
          signal: AbortSignal.timeout(3000),
        })
        if (!response.ok) {
          await forceReconnect()
        }
      } catch {
        await forceReconnect()
      }
    }
  }, 30000)

  return () => clearInterval(healthCheckInterval)
}
