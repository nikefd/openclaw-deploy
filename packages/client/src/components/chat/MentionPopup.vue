<script setup lang="ts">
// MentionPopup.vue — floating list of agents triggered by `@` in any
// `data-oc-input` field. Reads stores/mentions.ts; the actual `@` detection
// lives in composables/useMentions.ts (called from App.vue once via
// useMentionsFallback()).
//
// When the user picks an entry we write `applyValue` into the mentions store
// — Phase E will let MessageInput observe `applyTick` and splice the handle
// into its textarea. For Phase C2 we also try to do the splice ourselves
// against the currently-focused `data-oc-input` element so the demo works
// end-to-end.
import { computed, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useMentionsStore } from '@/stores/mentions'

const store = useMentionsStore()
const { open, anchor, selectedIdx, applyTick, applyValue } = storeToRefs(store)
const filtered = computed(() => store.filtered)

const style = computed(() => {
  if (!anchor.value) return {}
  return {
    left: anchor.value.x + 'px',
    top: anchor.value.y + 'px',
  }
})

function pick(idx: number) {
  store.selectedIdx = idx
  const a = store.pickCurrent()
  if (a) store.apply(a.handle + ' ')
}

// Best-effort splice into the focused input. Looks for the latest `@…` token
// at or before the caret and replaces it with `applyValue`.
watch(applyTick, () => {
  const el = document.activeElement
  if (!(el instanceof HTMLTextAreaElement || el instanceof HTMLInputElement)) return
  if (!el.hasAttribute('data-oc-input')) return
  const cursor = el.selectionStart ?? el.value.length
  const before = el.value.slice(0, cursor)
  const at = before.lastIndexOf('@')
  if (at < 0) return
  const newVal = before.slice(0, at) + applyValue.value + el.value.slice(cursor)
  el.value = newVal
  const newPos = at + applyValue.value.length
  el.setSelectionRange(newPos, newPos)
  el.dispatchEvent(new Event('input', { bubbles: true }))
})
</script>

<template>
  <Transition name="pop">
    <div v-if="open" class="mention-pop" :style="style" role="listbox">
      <div class="hd">@ mention</div>
      <button
        v-for="(a, idx) in filtered"
        :key="a.id"
        class="row"
        :class="{ active: idx === selectedIdx }"
        role="option"
        :aria-selected="idx === selectedIdx"
        @mouseenter="store.selectedIdx = idx"
        @click="pick(idx)"
      >
        <span class="emoji">{{ a.emoji }}</span>
        <span class="info">
          <span class="n">{{ a.handle }}</span>
          <span class="d">{{ a.description }}</span>
        </span>
      </button>
      <div v-if="filtered.length === 0" class="empty">无匹配 agent</div>
      <div class="hint">↑↓ 选择 · Enter 插入 · Esc 关闭</div>
    </div>
  </Transition>
</template>

<style scoped lang="scss">
.mention-pop {
  position: fixed;
  width: 240px;
  background: var(--popup-bg, var(--bg-elevated));
  border: 1px solid var(--popup-border, var(--border));
  border-radius: 8px;
  box-shadow: var(--popup-shadow, 0 6px 20px rgba(0, 0, 0, 0.3));
  padding: 4px;
  z-index: 200;
  transform: translateY(-100%);
}
.hd {
  font-size: 10px;
  color: var(--text-sec);
  padding: 4px 8px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.row {
  display: flex;
  align-items: center;
  gap: 8px;
  background: transparent;
  border: none;
  padding: 6px 8px;
  border-radius: 6px;
  cursor: pointer;
  text-align: left;
  width: 100%;
  color: var(--text);
}
.row:hover, .row.active { background: var(--hover); }
.emoji { font-size: 16px; flex: 0 0 20px; text-align: center; }
.info { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.n { font-size: 13px; font-weight: 500; }
.d {
  font-size: 11px;
  color: var(--text-sec);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.empty { padding: 10px; text-align: center; color: var(--text-sec); font-size: 11px; }
.hint { font-size: 10px; color: var(--text-sec); padding: 4px 8px 2px; text-align: right; }

.pop-enter-active, .pop-leave-active { transition: opacity 0.1s, transform 0.1s; }
.pop-enter-from, .pop-leave-to { opacity: 0; transform: translateY(-100%) translateY(4px); }
</style>
