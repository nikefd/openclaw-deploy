/**
 * useAuth.ts — Authentication operations
 *
 * Encapsulates:
 * - Logout (clear tokens, redirect to /login)
 * - Auth state
 */

import { ref } from 'vue'
import { useRouter } from 'vue-router'

export function useAuth() {
  const router = useRouter()
  const isLoading = ref(false)
  const error = ref<string | null>(null)

  async function logout(): Promise<void> {
    isLoading.value = true
    error.value = null

    try {
      // Call backend logout endpoint
      const res = await fetch('/auth/logout', {
        method: 'POST',
        credentials: 'same-origin',
      })

      if (!res.ok) {
        throw new Error(`Logout failed: HTTP ${res.status}`)
      }

      // Clear local storage
      localStorage.clear()
      
      // Redirect to login
      await router.push('/login')
      
      console.info('[useAuth] logout successful')
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      error.value = msg
      console.error('[useAuth] logout error:', err)
      throw err
    } finally {
      isLoading.value = false
    }
  }

  return {
    isLoading,
    error,
    logout,
  }
}
