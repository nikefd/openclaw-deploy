// Phase D1 — AI frontier composable.
import { ref, onMounted } from 'vue'
import { fetchFrontierItems, type FrontierItem } from '@/api/ai-frontier'

export function useAiFrontierData() {
  const loading = ref(true)
  const data = ref<FrontierItem[]>([])
  const error = ref<string | null>(null)

  async function reload(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      data.value = await fetchFrontierItems()
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
