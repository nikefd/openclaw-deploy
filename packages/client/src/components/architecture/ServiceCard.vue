<script setup lang="ts">
// ServiceCard.vue — single block in the architecture diagram.
defineProps<{
  name: string
  port?: number | string
  emoji: string
  desc?: string
  tone?: 'gateway' | 'auth' | 'data' | 'agent' | 'edge'
}>()
</script>

<template>
  <div class="card" :class="`tone-${tone ?? 'data'}`">
    <div class="head">
      <span class="emoji">{{ emoji }}</span>
      <strong>{{ name }}</strong>
      <span v-if="port" class="port">:{{ port }}</span>
    </div>
    <div v-if="desc" class="desc">{{ desc }}</div>
  </div>
</template>

<style scoped lang="scss">
.card {
  border: 1px solid var(--border);
  background: var(--bg-elevated);
  border-radius: var(--radius-md);
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}
.head {
  display: flex;
  align-items: baseline;
  gap: 6px;
  flex-wrap: wrap;
}
.emoji { font-size: 16px; }
strong { color: var(--text); font-size: 13px; }
.port {
  font-family: var(--font-mono);
  color: var(--text-sec);
  font-size: 11px;
}
.desc { font-size: 11px; color: var(--text-sec); line-height: 1.45; }

.tone-gateway { border-color: rgba(96, 165, 250, 0.5); background: linear-gradient(135deg, rgba(96, 165, 250, 0.1), transparent); }
.tone-auth    { border-color: rgba(192, 132, 252, 0.5); background: linear-gradient(135deg, rgba(192, 132, 252, 0.1), transparent); }
.tone-data    { border-color: rgba(251, 191, 36, 0.5); background: linear-gradient(135deg, rgba(251, 191, 36, 0.1), transparent); }
.tone-agent   { border-color: rgba(16, 163, 127, 0.5); background: linear-gradient(135deg, rgba(16, 163, 127, 0.1), transparent); }
.tone-edge    { border-color: rgba(239, 68, 68, 0.5); background: linear-gradient(135deg, rgba(239, 68, 68, 0.1), transparent); }
</style>
