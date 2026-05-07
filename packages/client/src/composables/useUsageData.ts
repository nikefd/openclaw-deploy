// composables/useUsageData.ts — token usage loader + range slicer.
import { computed, ref } from 'vue'
import { fetchUsage } from '@/api/usage'
import { MODELS, modelTotals, sumRange, type DailyUsage } from '@/fixtures/usage'

export type UsageRange = 'today' | 'week' | 'month' | 'custom'

export function useUsageData() {
  const daily = ref<DailyUsage[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const range = ref<UsageRange>('month')

  const today = computed(() => sumRange(daily.value, 1))
  const week = computed(() => sumRange(daily.value, 7))
  const month = computed(() => sumRange(daily.value, 30))

  const breakdown = computed(() => modelTotals(daily.value))

  const rangeDays = computed(() => {
    if (range.value === 'today') return daily.value.slice(-1)
    if (range.value === 'week') return daily.value.slice(-7)
    return daily.value
  })

  async function reload(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      daily.value = await fetchUsage()
    } catch (e) {
      error.value = e instanceof Error ? e.message : String(e)
    } finally {
      loading.value = false
    }
  }

  return {
    daily,
    loading,
    error,
    range,
    today,
    week,
    month,
    breakdown,
    rangeDays,
    models: MODELS,
    reload,
  }
}
