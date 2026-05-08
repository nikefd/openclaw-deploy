<script setup lang="ts">
// TaskDetailDrawer.vue — right-side slide-in.
// Shows runId, sessionKey, parent link, children list, full timeline.
// All actions are placeholders for Phase E (kill / log / steer).
import { computed } from 'vue'
import type { TaskFixture } from '@/fixtures/tasks'

const props = defineProps<{ task: TaskFixture | null }>()
defineEmits<{ (e: 'close'): void }>()

const fmt = new Intl.DateTimeFormat('zh-CN', {
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  hour12: false,
})

function fmtTime(ts: number): string {
  return fmt.format(new Date(ts))
}

const timeline = computed(() => props.task?.timeline ?? [])
</script>

<template>
  <Transition name="slide">
    <aside v-if="task" class="drawer">
      <header>
        <div class="title">
          <span class="emoji">📋</span>
          <h2>{{ task.label }}</h2>
        </div>
        <button class="close" @click="$emit('close')">✕</button>
      </header>

      <section class="meta">
        <div class="kv"><span>状态</span><strong>{{ task.status }}</strong></div>
        <div class="kv"><span>runId</span><code>{{ task.runId }}</code></div>
        <div class="kv"><span>sessionKey</span><code class="mono">{{ task.sessionKey }}</code></div>
        <div class="kv"><span>parent</span><code>{{ task.parent ?? '— (root)' }}</code></div>
        <div class="kv"><span>model</span><code>{{ task.model }}</code></div>
        <div class="kv">
          <span>tokens</span>
          <strong>{{ task.tokensIn.toLocaleString() }} in / {{ task.tokensOut.toLocaleString() }} out</strong>
        </div>
      </section>

      <section v-if="task.children.length" class="children">
        <h3>子任务</h3>
        <ul>
          <li v-for="c in task.children" :key="c"><code>{{ c }}</code></li>
        </ul>
      </section>

      <section class="timeline">
        <h3>时间线</h3>
        <ol>
          <li v-for="(ev, i) in timeline" :key="i" :class="`ev ev-${ev.kind}`">
            <span class="ts">{{ fmtTime(ev.ts) }}</span>
            <span class="kind">{{ ev.kind }}</span>
            <span class="text">{{ ev.text }}</span>
          </li>
        </ol>
      </section>

      <footer>
        <button disabled title="即将开放">⛔ Kill</button>
        <button disabled title="即将开放">📜 Log</button>
        <button disabled title="即将开放">🎯 Steer</button>
      </footer>
    </aside>
  </Transition>
</template>

<style scoped lang="scss">
.drawer {
  position: fixed;
  top: 0;
  right: 0;
  width: 420px;
  max-width: 90vw;
  height: 100vh;
  background: var(--bg-elevated);
  border-left: 1px solid var(--border);
  box-shadow: var(--popup-shadow);
  display: flex;
  flex-direction: column;
  z-index: 50;
}
header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid var(--border);
}
.title { display: flex; align-items: center; gap: 8px; min-width: 0; }
.title h2 {
  font-size: 14px;
  margin: 0;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: var(--text);
}
.emoji { font-size: 18px; }
.close {
  background: transparent;
  border: none;
  color: var(--text-sec);
  cursor: pointer;
  font-size: 16px;
  padding: 4px 8px;
  border-radius: 6px;
}
.close:hover { background: var(--hover); color: var(--text); }

section { padding: 12px 16px; border-bottom: 1px solid var(--border); }
section h3 { font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-sec); margin: 0 0 8px; }

.kv {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  font-size: 12px;
  padding: 3px 0;
  gap: 12px;
}
.kv span { color: var(--text-sec); }
.kv strong, .kv code { color: var(--text); font-weight: 500; }
.mono { font-family: var(--font-mono); font-size: 11px; word-break: break-all; }

.children ul { margin: 0; padding-left: 18px; }
.children li { font-size: 12px; padding: 2px 0; }

.timeline { flex: 1; overflow-y: auto; }
.timeline ol {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.ev {
  display: grid;
  grid-template-columns: 64px 60px 1fr;
  gap: 8px;
  align-items: baseline;
  font-size: 12px;
  padding-left: 8px;
  border-left: 2px solid var(--border);
}
.ev .ts { color: var(--text-sec); font-family: var(--font-mono); }
.ev .kind { color: var(--text-sec); }
.ev .text { color: var(--text); }
.ev-spawn { border-color: #60a5fa; }
.ev-tool { border-color: #94a3b8; }
.ev-message { border-color: #fbbf24; }
.ev-done { border-color: #10a37f; }
.ev-error { border-color: #ef4444; }

footer {
  display: flex;
  gap: 8px;
  padding: 12px 16px;
  border-top: 1px solid var(--border);
}
footer button {
  flex: 1;
  background: var(--bg);
  color: var(--text-sec);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 6px;
  font-size: 12px;
  cursor: not-allowed;
  opacity: 0.6;
}

.slide-enter-active, .slide-leave-active { transition: transform 0.2s ease, opacity 0.2s ease; }
.slide-enter-from, .slide-leave-to { transform: translateX(100%); opacity: 0; }
</style>
