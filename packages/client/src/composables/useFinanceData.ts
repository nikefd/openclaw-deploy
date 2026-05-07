// Phase D1 — finance composable. Loads dashboard once on mount; exposes
// reactive { loading, data, error, reload }.
import { ref, onMounted } from 'vue'
import { fetchFinanceDashboard, type FinanceDashboard } from '@/api/finance'

export function useFinanceData() {
  const loading = ref(true)
  const data = ref<FinanceDashboard | null>(null)
  const error = ref<string | null>(null)

  async function reload(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      data.value = await fetchFinanceDashboard()
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
