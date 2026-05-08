<template>
  <transition
    enter-active-class="animate-slide-down"
    leave-active-class="animate-slide-up"
  >
    <div v-if="showBanner" class="connection-banner" :class="bannerClass">
      <div class="banner-content">
        <span class="banner-icon">{{ icon }}</span>
        <span class="banner-text">{{ message }}</span>
        <button v-if="showRetry" class="banner-btn" @click="handleRetry">
          {{ retryText }}
        </button>
      </div>
    </div>
  </transition>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useConnectionRecovery } from '@/composables/useConnectionRecovery'

const { state, forceReconnect } = useConnectionRecovery()

const showBanner = computed(() => {
  return !state.value.isOnline || state.value.lastError
})

const bannerClass = computed(() => {
  if (!state.value.isOnline) return 'offline'
  if (state.value.isConnecting) return 'connecting'
  if (state.value.lastError) return 'error'
  return 'success'
})

const icon = computed(() => {
  if (!state.value.isOnline) return '📡'
  if (state.value.isConnecting) return '🔄'
  if (state.value.lastError) return '⚠️'
  return '✅'
})

const message = computed(() => {
  if (!state.value.isOnline) return '设备离线'
  if (state.value.isConnecting) return '重新连接中...'
  if (state.value.lastError) {
    if (state.value.nextRetryIn > 0) {
      return `连接失败，${state.value.nextRetryIn}s 后重试`
    }
    return `连接失败: ${state.value.lastError}`
  }
  return '已连接'
})

const showRetry = computed(() => {
  return state.value.lastError && !state.value.isConnecting && state.value.nextRetryIn === 0
})

const retryText = computed(() => {
  return `重试 (${state.value.retryCount}/${5})`
})

const handleRetry = async () => {
  await forceReconnect()
}
</script>

<style scoped>
.connection-banner {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 9999;
  padding: 8px 16px;
  background: var(--bg-secondary);
  border-bottom: 1px solid var(--border-color);
  font-size: 14px;
  transition: all 0.3s ease;
}

.connection-banner.offline {
  background: #d32f2f;
  color: white;
  border-bottom-color: #b71c1c;
}

.connection-banner.connecting {
  background: #f57c00;
  color: white;
  border-bottom-color: #e65100;
}

.connection-banner.error {
  background: #f57f17;
  color: white;
  border-bottom-color: #f57c00;
}

.connection-banner.success {
  background: #388e3c;
  color: white;
  border-bottom-color: #2e7d32;
  opacity: 0.8;
}

.banner-content {
  display: flex;
  align-items: center;
  gap: 8px;
  max-width: 1200px;
  margin: 0 auto;
}

.banner-icon {
  font-size: 16px;
  flex-shrink: 0;
}

.banner-text {
  flex: 1;
  font-weight: 500;
}

.banner-btn {
  padding: 4px 12px;
  border: 1px solid rgba(255, 255, 255, 0.5);
  background: rgba(255, 255, 255, 0.1);
  color: white;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  transition: all 0.2s;
}

.banner-btn:hover {
  background: rgba(255, 255, 255, 0.2);
  border-color: white;
}

@keyframes slide-down {
  from {
    transform: translateY(-100%);
    opacity: 0;
  }
  to {
    transform: translateY(0);
    opacity: 1;
  }
}

@keyframes slide-up {
  from {
    transform: translateY(0);
    opacity: 1;
  }
  to {
    transform: translateY(-100%);
    opacity: 0;
  }
}

.animate-slide-down {
  animation: slide-down 0.3s ease;
}

.animate-slide-up {
  animation: slide-up 0.3s ease;
}
</style>
