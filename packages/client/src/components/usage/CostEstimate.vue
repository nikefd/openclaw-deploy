<script setup lang="ts">
// CostEstimate.vue — table with model × tokens × pricing → cost.
import { computed } from 'vue'
import { estimateCost, type ModelPricing } from '@/fixtures/usage'

const props = defineProps<{
  models: readonly ModelPricing[]
  totals: ReadonlyArray<{ model: string; tokensIn: number; tokensOut: number }>
}>()

interface Row {
  model: string
  tokensIn: number
  tokensOut: number
  inputPerM: number
  outputPerM: number
  cost: number
}

const rows = computed<Row[]>(() =>
  props.totals
    .map((t) => {
      const pricing =
        props.models.find((m) => m.model === t.model) ??
        ({ model: t.model, inputPerM: 0, outputPerM: 0, color: '#94a3b8' } as ModelPricing)
      const cost = estimateCost(t.tokensIn, t.tokensOut, pricing)
      return {
        model: t.model,
        tokensIn: t.tokensIn,
        tokensOut: t.tokensOut,
        inputPerM: pricing.inputPerM,
        outputPerM: pricing.outputPerM,
        cost,
      }
    })
    .sort((a, b) => b.cost - a.cost),
)

const total = computed(() => rows.value.reduce((acc, r) => acc + r.cost, 0))

function fmtTok(n: number): string {
  if (n < 1000) return String(n)
  if (n < 1_000_000) return `${(n / 1000).toFixed(1)}k`
  return `${(n / 1_000_000).toFixed(2)}M`
}
function usd(n: number): string {
  return `$${n.toFixed(2)}`
}
</script>

<template>
  <div class="cost">
    <header>
      <h3>成本估算</h3>
      <span class="grand">合计 {{ usd(total) }}</span>
    </header>
    <table data-testid="cost-table">
      <thead>
        <tr>
          <th>模型</th>
          <th class="num">输入</th>
          <th class="num">输出</th>
          <th class="num">in $/M</th>
          <th class="num">out $/M</th>
          <th class="num">成本</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="r in rows" :key="r.model" data-testid="cost-row">
          <td><code>{{ r.model }}</code></td>
          <td class="num">{{ fmtTok(r.tokensIn) }}</td>
          <td class="num">{{ fmtTok(r.tokensOut) }}</td>
          <td class="num">${{ r.inputPerM.toFixed(2) }}</td>
          <td class="num">${{ r.outputPerM.toFixed(2) }}</td>
          <td class="num cost-cell" data-testid="cost-cell">{{ usd(r.cost) }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped lang="scss">
.cost {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 14px 16px;
}
header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 10px;
}
header h3 { margin: 0; font-size: 13px; color: var(--text); font-weight: 600; }
.grand { font-size: 13px; color: var(--accent); font-weight: 600; font-family: var(--font-mono); }

table { width: 100%; border-collapse: collapse; font-size: 12px; }
th, td { padding: 8px 10px; text-align: left; border-bottom: 1px solid var(--border); }
th { color: var(--text-sec); font-weight: 500; }
td code { font-family: var(--font-mono); color: var(--text); }
td { color: var(--text); }
.num { text-align: right; font-family: var(--font-mono); }
.cost-cell { color: var(--accent); font-weight: 600; }
tbody tr:last-child td { border-bottom: none; }
</style>
