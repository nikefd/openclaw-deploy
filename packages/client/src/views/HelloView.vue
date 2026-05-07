<script setup lang="ts">
/**
 * Phase B demo page.
 *
 * Steps you can verify by eye:
 *   1. Click "Connect" — status flips to idle.
 *   2. Type something and "Send" — status: queued -> streaming, deltas
 *      appear ~10/sec from the MOCK_UPSTREAM generator.
 *   3. Hard-refresh the page mid-stream. lastSeq is in sessionStorage,
 *      so on connect we auto-emit `resume` and the remainder shows up.
 */
import { onMounted, ref } from 'vue'
import { useChatStream } from '@/composables/useChatStream'

const sessionId = ref<string>(
  // stable per-tab so refresh actually exercises resume
  (typeof sessionStorage !== 'undefined' && sessionStorage.getItem('oc_v2_demo_sid')) ||
    `demo-${Date.now()}`,
)
if (typeof sessionStorage !== 'undefined') {
  sessionStorage.setItem('oc_v2_demo_sid', sessionId.value)
}

const sidRef = ref<string | null>(sessionId.value)
const { state, connect, start, abort } = useChatStream({ sessionId: sidRef })

const input = ref('hello v2')

onMounted(() => {
  // Auto-connect on mount so a refresh during a live run can resume.
  connect()
})

function send() {
  start({ sid: sessionId.value, input: input.value })
}

function newSession() {
  const sid = `demo-${Date.now()}`
  if (typeof sessionStorage !== 'undefined') {
    sessionStorage.setItem('oc_v2_demo_sid', sid)
  }
  sessionId.value = sid
  sidRef.value = sid
  state.delta = ''
  state.status = 'idle'
  state.lastSeq = 0
  state.error = null
}
</script>

<template>
  <section class="hello">
    <h1>OpenClaw Web v2 — Phase B demo</h1>
    <p class="hint">
      Socket.IO <code>/chat-run</code> + seq + auto-resume. 用 <code>MOCK_UPSTREAM=1</code> 跑 server 时每 100ms 推一帧 <code>token-N</code>。
    </p>

    <div class="row">
      <label>sid</label>
      <code>{{ sessionId }}</code>
      <button @click="newSession">new sid</button>
    </div>

    <div class="row">
      <input v-model="input" placeholder="say something" />
      <button @click="send" :disabled="state.status === 'streaming' || state.status === 'queued'">
        send
      </button>
      <button @click="abort" :disabled="state.status !== 'streaming' && state.status !== 'queued'">
        abort
      </button>
    </div>

    <div class="status">
      <span>status: <b>{{ state.status }}</b></span>
      <span>lastSeq: <b>{{ state.lastSeq }}</b></span>
      <span v-if="state.error" class="err">error: {{ state.error }}</span>
    </div>

    <pre class="delta">{{ state.delta || '(no delta yet)' }}</pre>
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
.row {
  display: flex;
  gap: 8px;
  align-items: center;
  margin: 12px 0;
}
.row label {
  font-size: 13px;
  color: #666;
}
.row input {
  flex: 1;
  padding: 6px 10px;
  font: inherit;
  border: 1px solid #ccc;
  border-radius: 6px;
}
.row button {
  padding: 6px 12px;
  border: 1px solid #ccc;
  background: #fafafa;
  border-radius: 6px;
  cursor: pointer;
}
.row button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.status {
  display: flex;
  gap: 16px;
  font-size: 13px;
  color: #444;
  margin: 8px 0;
}
.status .err {
  color: #b00020;
}
.delta {
  background: #0b1020;
  color: #d2e2ff;
  padding: 12px;
  border-radius: 6px;
  min-height: 80px;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 13px;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}
.hint {
  color: #888;
  font-size: 13px;
}
</style>
