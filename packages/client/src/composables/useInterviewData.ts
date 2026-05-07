// Phase D1 — interview composable.
import { ref, onMounted } from 'vue'
import { fetchInterviewDashboard, type InterviewDashboard } from '@/api/interview'

export function useInterviewData() {
  const loading = ref(true)
  const data = ref<InterviewDashboard | null>(null)
  const error = ref<string | null>(null)

  async function reload(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      data.value = await fetchInterviewDashboard()
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
