<script setup lang="ts">
// AgentCard.vue — reusable agent tile used by AgentsView's hub grid.
// Click navigates to the given route via vue-router.
import { useRouter } from 'vue-router'

interface Props {
  emoji: string
  name: string
  description: string
  status: 'active' | 'paused' | 'gray'
  recent?: string
  to: string
}

const props = defineProps<Props>()
const router = useRouter()

function go(): void {
  void router.push(props.to)
}

function onKey(e: KeyboardEvent): void {
  if (e.key === 'Enter' || e.key === ' ') {
    e.preventDefault()
    go()
  }
}
</script>

<template>
  <button class="agent-card" type="button" @click="go" @keydown="onKey">
    <div class="head">
      <span class="emoji">{{ emoji }}</span>
      <span class="status" :class="status" :title="status" />
    </div>
    <div class="name">{{ name }}</div>
    <div class="desc">{{ description }}</div>
    <div v-if="recent" class="recent">{{ recent }}</div>
  </button>
</template>

<style scoped lang="scss">
.agent-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 20px;
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  color: var(--text);
  text-align: left;
  cursor: pointer;
  transition: transform 0.12s ease, border-color 0.12s ease, box-shadow 0.12s ease;
  font-family: inherit;

  &:hover {
    transform: translateY(-2px);
    border-color: var(--accent);
    box-shadow: var(--shadow-1);
  }
  &:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }
}
.head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.emoji { font-size: 36px; line-height: 1; }
.status {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--text-sec);
  &.active { background: #10a37f; box-shadow: 0 0 8px rgba(16, 163, 127, 0.5); }
  &.paused { background: #f0b429; }
  &.gray { background: var(--text-sec); }
}
.name { font-size: 18px; font-weight: 600; }
.desc { font-size: 13px; color: var(--text-sec); line-height: 1.5; }
.recent {
  margin-top: auto;
  font-size: 12px;
  color: var(--text-sec);
  padding-top: 8px;
  border-top: 1px dashed var(--border);
}
</style>
