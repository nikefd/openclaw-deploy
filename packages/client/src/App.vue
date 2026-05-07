<script setup lang="ts">
// Minimal scaffold root. Real layout lands in Phase C.
</script>

<template>
  <div class="app-root">
    <header class="app-header">
      <strong>OpenClaw Web v2</strong>
      <span class="badge">scaffold ok</span>
    </header>
    <main>
      <router-view />
    </main>
  </div>
</template>

<style scoped>
.app-root {
  font-family: system-ui, -apple-system, sans-serif;
  padding: 24px;
  color: #222;
}
.app-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 24px;
}
.badge {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 999px;
  background: #e6f4ea;
  color: #1e7e34;
}
</style>
