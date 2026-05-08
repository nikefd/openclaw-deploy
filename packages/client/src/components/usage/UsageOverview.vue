<script setup lang="ts">
// UsageOverview.vue — three big number cards (today / week / month).
defineProps<{
  today: { tokensIn: number; tokensOut: number }
  week: { tokensIn: number; tokensOut: number }
  month: { tokensIn: number; tokensOut: number }
}>()

function fmt(n: number): string {
  if (n < 1000) return String(n)
  if (n < 1_000_000) return `${(n / 1000).toFixed(1)}k`
  if (n < 1_000_000_000) return `${(n / 1_000_000).toFixed(2)}M`
  return `${(n / 1_000_000_000).toFixed(2)}B`
}
</script>

<template>
  <div class="overview">
    <div class="card today">
      <div class="cap">今日</div>
      <div class="big">{{ fmt(today.tokensIn + today.tokensOut) }}</div>
      <div class="sub">{{ fmt(today.tokensIn) }} in · {{ fmt(today.tokensOut) }} out</div>
    </div>
    <div class="card week">
      <div class="cap">本周</div>
      <div class="big">{{ fmt(week.tokensIn + week.tokensOut) }}</div>
      <div class="sub">{{ fmt(week.tokensIn) }} in · {{ fmt(week.tokensOut) }} out</div>
    </div>
    <div class="card month">
      <div class="cap">本月</div>
      <div class="big">{{ fmt(month.tokensIn + month.tokensOut) }}</div>
      <div class="sub">{{ fmt(month.tokensIn) }} in · {{ fmt(month.tokensOut) }} out</div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.overview {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}
.card {
  padding: 18px 20px;
  border-radius: var(--radius-md);
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  position: relative;
  overflow: hidden;
}
.card::before {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(135deg, var(--accent-soft), transparent 60%);
  pointer-events: none;
}
.cap {
  font-size: 12px;
  color: var(--text-sec);
  text-transform: uppercase;
  letter-spacing: 0.08em;
}
.big {
  font-size: 30px;
  font-weight: 700;
  color: var(--text);
  margin-top: 4px;
  font-feature-settings: 'tnum';
}
.sub {
  font-size: 12px;
  color: var(--text-sec);
  margin-top: 4px;
  font-family: var(--font-mono);
}
.today .big { color: #60a5fa; }
.week .big { color: #c084fc; }
.month .big { color: #10a37f; }
</style>
