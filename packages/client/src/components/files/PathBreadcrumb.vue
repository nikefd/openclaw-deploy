<script setup lang="ts">
// PathBreadcrumb.vue — clickable path segments; clicks emit a navigate event.
import { computed } from 'vue'

const props = defineProps<{ path: string | null }>()
const emit = defineEmits<{ (e: 'navigate', path: string): void }>()

interface Crumb { label: string; path: string }

const segments = computed<Crumb[]>(() => {
  if (!props.path) return [{ label: '/', path: '/' }]
  const parts = props.path.split('/').filter(Boolean)
  const out: Crumb[] = [{ label: '/', path: '/' }]
  let acc = ''
  for (const p of parts) {
    acc += '/' + p
    out.push({ label: p, path: acc })
  }
  return out
})
</script>

<template>
  <nav class="crumbs" aria-label="path">
    <template v-for="(c, i) in segments" :key="c.path">
      <button class="crumb" @click="emit('navigate', c.path)">{{ c.label }}</button>
      <span v-if="i < segments.length - 1" class="sep">/</span>
    </template>
  </nav>
</template>

<style scoped lang="scss">
.crumbs {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 2px;
  padding: 6px 10px;
  border-bottom: 1px solid var(--border);
  font-size: 12px;
  color: var(--text-sec);
}
.crumb {
  background: transparent;
  border: none;
  color: var(--text-sec);
  cursor: pointer;
  padding: 2px 4px;
  border-radius: 3px;
  font-size: 12px;
}
.crumb:hover { background: var(--hover); color: var(--text); }
.sep { color: var(--text-sec); }
</style>
