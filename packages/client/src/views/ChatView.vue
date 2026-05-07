<script setup lang="ts">
/**
 * ChatView — route container.
 */
import { computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import ChatPane from '@/components/chat/ChatPane.vue'

const route = useRoute()
const router = useRouter()

const sid = computed<string>(() => {
  const fromRoute = (route.params.sid as string | undefined) ?? ''
  if (fromRoute) return fromRoute
  if (typeof sessionStorage !== 'undefined') {
    const cached = sessionStorage.getItem('oc_v2_default_sid')
    if (cached) return cached
    const fresh = `chat_${Date.now().toString(36)}`
    sessionStorage.setItem('oc_v2_default_sid', fresh)
    return fresh
  }
  return 'default'
})

watch(
  sid,
  (id) => {
    if (id && route.name === 'chat-root') {
      router.replace({ name: 'chat', params: { sid: id } })
    }
  },
  { immediate: true },
)
</script>

<template>
  <ChatPane :sid="sid" />
</template>
