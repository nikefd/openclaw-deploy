<script setup lang="ts">
// ModelDropdown.vue — picks the active model from the Models pinia store.
// Phase C2: stub list with 5 entries, no persistence.
// Phase E: store list comes from /api/models, selection persists per-chat.
//
// Usage: <ModelDropdown @change="(id) => …" />. The component also writes the
// new id back into stores/models.ts so any other consumer (ChatPane via
// Phase D wiring) sees the change.
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useModelsStore, type ModelOption } from '@/stores/models'

const emit = defineEmits<{
  (e: 'change', id: string): void
}>()

const store = useModelsStore()
const { list, currentId } = storeToRefs(store)
const current = computed<ModelOption>(() => store.current)

const open = ref(false)
const root = ref<HTMLElement | null>(null)

function toggle() { open.value = !open.value }
function close() { open.value = false }

function pick(m: ModelOption) {
  store.setCurrent(m.id)
  emit('change', m.id)
  close()
}

function fmtCtx(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(0) + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(0) + 'k'
  return String(n)
}

function onDocClick(ev: MouseEvent) {
  if (!root.value) return
  if (!root.value.contains(ev.target as Node)) close()
}

onMounted(() => document.addEventListener('mousedown', onDocClick))
onBeforeUnmount(() => document.removeEventListener('mousedown', onDocClick))

// Expose currentId for parent test inspection (storyboards / vitest).
defineExpose({ currentId, open })
</script>

<template>
  <div ref="root" class="model-dd" :class="{ open }">
    <button class="trigger" @click="toggle" type="button">
      <span class="ic">{{ current.icon }}</span>
      <span class="nm">{{ current.name }}</span>
      <span class="caret">▾</span>
    </button>
    <Transition name="dd">
      <div v-if="open" class="menu" role="listbox">
        <button
          v-for="m in list"
          :key="m.id"
          class="opt"
          :class="{ active: m.id === currentId }"
          role="option"
          :aria-selected="m.id === currentId"
          @click="pick(m)"
        >
          <span class="ic">{{ m.icon }}</span>
          <span class="info">
            <span class="row1">
              <span class="nm">{{ m.name }}</span>
              <span v-if="m.id === currentId" class="check">✓</span>
            </span>
            <span class="meta">
              <span>{{ m.provider }}</span>
              <span>· {{ fmtCtx(m.contextWindow) }} ctx</span>
              <span>· ${{ m.pricePerMTokIn }}/M in · ${{ m.pricePerMTokOut }}/M out</span>
            </span>
          </span>
        </button>
      </div>
    </Transition>
  </div>
</template>

<style scoped lang="scss">
.model-dd { position: relative; display: inline-block; }
.trigger {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: var(--accent-soft);
  border: 1px solid transparent;
  color: var(--accent);
  font-size: 12px;
  padding: 4px 10px;
  border-radius: 999px;
  cursor: pointer;
}
.trigger:hover { border-color: var(--accent); }
.caret { font-size: 9px; transform: translateY(1px); }

.menu {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  z-index: 50;
  min-width: 320px;
  max-width: 380px;
  background: var(--popup-bg, var(--bg-elevated));
  border: 1px solid var(--popup-border, var(--border));
  border-radius: 8px;
  box-shadow: var(--popup-shadow, 0 6px 20px rgba(0, 0, 0, 0.3));
  padding: 4px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.opt {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  background: transparent;
  border: none;
  padding: 8px 10px;
  border-radius: 6px;
  cursor: pointer;
  text-align: left;
  width: 100%;
  color: var(--text);
}
.opt:hover { background: var(--hover); }
.opt.active { background: var(--accent-soft); }
.opt .ic { font-size: 16px; flex: 0 0 22px; text-align: center; }
.info { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.row1 { display: flex; align-items: center; gap: 6px; }
.nm { font-size: 13px; font-weight: 500; }
.check { color: var(--accent); }
.meta {
  font-size: 10px;
  color: var(--text-sec);
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.dd-enter-active, .dd-leave-active { transition: opacity 0.1s, transform 0.1s; }
.dd-enter-from, .dd-leave-to { opacity: 0; transform: translateY(-4px); }
</style>
