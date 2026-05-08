<script setup lang="ts">
// MetricGroup.vue — horizontal row of KPIs. Wraps on mobile.
</script>

<template>
  <div class="metric-group">
    <slot />
  </div>
</template>

<style scoped lang="scss">
.metric-group {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}
@media (max-width: 720px) {
  .metric-group { flex-direction: column; }
}
</style>
