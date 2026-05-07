<script setup lang="ts">
// DashboardPanel.vue — generic titled panel with optional actions slot.
// Used across all four agent views to keep visual rhythm consistent.
interface Props {
  title: string
  subtitle?: string
}
defineProps<Props>()
</script>

<template>
  <section class="panel">
    <header class="panel-head">
      <div class="title-wrap">
        <h3 class="title">{{ title }}</h3>
        <span v-if="subtitle" class="subtitle">{{ subtitle }}</span>
      </div>
      <div class="actions">
        <slot name="actions" />
      </div>
    </header>
    <div class="body">
      <slot />
    </div>
  </section>
</template>

<style scoped lang="scss">
.panel {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border);
}
.title { margin: 0; font-size: 14px; font-weight: 600; color: var(--text); }
.subtitle { margin-left: 8px; font-size: 12px; color: var(--text-sec); }
.title-wrap { display: flex; align-items: baseline; }
.actions { display: flex; gap: 8px; }
.body { padding: 16px; }
</style>
