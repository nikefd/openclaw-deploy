<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'

const now = ref(new Date().toISOString())
let timer: number | undefined

onMounted(() => {
  timer = window.setInterval(() => {
    now.value = new Date().toISOString()
  }, 1000)
})

onBeforeUnmount(() => {
  if (timer !== undefined) window.clearInterval(timer)
})
</script>

<template>
  <section class="hello">
    <h1>OpenClaw Web v2 — Phase A scaffold</h1>
    <p>Vue 3 + TypeScript + Vite + Pinia + Vue Router 已就位。</p>
    <p>Server time tick: <code>{{ now }}</code></p>
    <p class="hint">下一步：Phase B 接 socket.io / @oc/server。</p>
  </section>
</template>

<style scoped>
.hello h1 {
  margin-top: 0;
  font-size: 22px;
}
.hello code {
  background: #f4f4f5;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 13px;
}
.hint {
  color: #888;
  font-size: 13px;
}
</style>
