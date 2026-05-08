<script setup lang="ts" generic="T">
// TimelineList.vue — vertical timeline. Used by climbing history + interview
// schedule. Items are pre-sorted; we render whatever order is supplied.
defineProps<{
  items: T[]
  dateKey: keyof T
  titleKey: keyof T
  subtitleKey?: keyof T
  metaKey?: keyof T
}>()
</script>

<template>
  <ul class="timeline">
    <li v-for="(item, i) in items" :key="i" class="row">
      <div class="dot" />
      <div class="content">
        <div class="date">{{ String(item[dateKey]) }}</div>
        <div class="title">{{ String(item[titleKey]) }}</div>
        <div v-if="subtitleKey" class="subtitle">{{ String(item[subtitleKey]) }}</div>
        <div v-if="metaKey" class="meta">{{ String(item[metaKey]) }}</div>
      </div>
    </li>
  </ul>
</template>

<style scoped lang="scss">
.timeline {
  list-style: none;
  margin: 0;
  padding: 0 0 0 12px;
  border-left: 2px solid var(--border);
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.row { position: relative; padding-left: 14px; }
.dot {
  position: absolute;
  left: -7px;
  top: 4px;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--accent);
  box-shadow: 0 0 0 3px var(--bg-elevated);
}
.date { font-size: 11px; color: var(--text-sec); margin-bottom: 2px; }
.title { font-size: 14px; font-weight: 500; color: var(--text); }
.subtitle { font-size: 13px; color: var(--text-sec); margin-top: 2px; }
.meta { font-size: 12px; color: var(--text-sec); margin-top: 2px; }
</style>
