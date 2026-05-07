// Phase D1 — climbing composable.
import { ref, onMounted } from 'vue'
import { fetchClimbingDashboard, type ClimbingDashboard } from '@/api/climbing'

export function useClimbingData() {
  const loading = ref(true)
  const data = ref<ClimbingDashboard | null>(null)
  const error = ref<string | null>(null)

  async function reload(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      data.value = await fetchClimbingDashboard()
    } catch (e) {
      error.value = e instanceof Error ? e.message : String(e)
    } finally {
      loading.value = false
    }
  }

  onMounted(() => {
    void reload()
  })

  return { loading, data, error, reload }
}
