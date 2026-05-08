<script setup lang="ts">
// SystemDiagram.vue — static layout of zhangyangbin.com services.
// CSS grid does the positioning; an SVG overlay draws the connector lines.
import ServiceCard from './ServiceCard.vue'
</script>

<template>
  <div class="diagram">
    <svg class="links" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
      <defs>
        <marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill="currentColor" />
        </marker>
      </defs>
      <!-- Browser -> Nginx -->
      <line x1="50" y1="8" x2="50" y2="20" stroke="currentColor" stroke-width="0.4" marker-end="url(#arrow)" />
      <!-- Nginx -> Auth/Gateway/File-API -->
      <line x1="50" y1="32" x2="18" y2="50" stroke="currentColor" stroke-width="0.4" marker-end="url(#arrow)" />
      <line x1="50" y1="32" x2="50" y2="50" stroke="currentColor" stroke-width="0.4" marker-end="url(#arrow)" />
      <line x1="50" y1="32" x2="82" y2="50" stroke="currentColor" stroke-width="0.4" marker-end="url(#arrow)" />
      <!-- Gateway -> Agents/Finance/Usage -->
      <line x1="50" y1="62" x2="22" y2="80" stroke="currentColor" stroke-width="0.4" marker-end="url(#arrow)" />
      <line x1="50" y1="62" x2="50" y2="80" stroke="currentColor" stroke-width="0.4" marker-end="url(#arrow)" />
      <line x1="50" y1="62" x2="78" y2="80" stroke="currentColor" stroke-width="0.4" marker-end="url(#arrow)" />
    </svg>

    <div class="row tier-0">
      <ServiceCard emoji="🌐" name="Browser" tone="edge" desc="Vue 3 + Vite，挂在 /v2/" />
    </div>
    <div class="row tier-1">
      <ServiceCard emoji="🚦" name="Nginx" port="443" tone="edge" desc="TLS / 路由 / cookie auth_request" />
    </div>
    <div class="row tier-2">
      <ServiceCard emoji="🔑" name="Auth" port="7683" tone="auth" desc="登录 / cookie 校验" />
      <ServiceCard emoji="🛰" name="Gateway" port="18789" tone="gateway" desc="OpenClaw API + socket.io，主控通道" />
      <ServiceCard emoji="📁" name="File-API" port="7682" tone="data" desc="聊天历史 / 文件上传 / copilot" />
    </div>
    <div class="row tier-3">
      <ServiceCard emoji="🤖" name="Agents-API" port="7685" tone="agent" desc="健身 / 攀岩等 agent 数据持久化" />
      <ServiceCard emoji="💰" name="Finance" port="7684" tone="agent" desc="行情 / 持仓 / 信号" />
      <ServiceCard emoji="📊" name="Usage" port="7686" tone="agent" desc="Token 用量统计聚合" />
    </div>
  </div>
</template>

<style scoped lang="scss">
.diagram {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 28px;
  padding: 20px;
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  overflow: hidden;
}
.links {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  color: var(--text-sec);
  opacity: 0.55;
}
.row {
  display: grid;
  gap: 16px;
  position: relative;
  z-index: 1;
}
.tier-0, .tier-1 { grid-template-columns: minmax(220px, 280px); justify-content: center; }
.tier-2, .tier-3 { grid-template-columns: repeat(3, minmax(0, 1fr)); }
</style>
