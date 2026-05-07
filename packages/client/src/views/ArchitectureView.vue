<script setup lang="ts">
// ArchitectureView.vue — static project architecture overview.
import SystemDiagram from '@/components/architecture/SystemDiagram.vue'
import DataFlowList from '@/components/architecture/DataFlowList.vue'
</script>

<template>
  <div class="arch-view">
    <header class="page-head">
      <h1>🗺️ 项目架构</h1>
      <p class="sub">
        zhangyangbin.com 跑着一套自建 ChatGPT 风格前端 + 多个旁路服务。
        前端在 Nginx 下，按路径分发到 Gateway、File-API、Auth 以及若干 agent 服务。
        本页是给狗蛋（也给斌哥）随手回顾的全景图。
      </p>
    </header>

    <SystemDiagram />

    <DataFlowList />

    <section class="hint">
      <h3>📌 关键约定</h3>
      <ul>
        <li><code>/</code> 永远指向 <code>/var/www/chat/index.html</code>，不要被改回 OpenClaw 原版 dashboard。</li>
        <li>v2 前端挂在 <code>/v2/</code>，用 vite 构建，路由通过 vue-router 的 history 模式。</li>
        <li>Nginx 同时维护 <code>sites-available</code> 和 <code>sites-enabled</code>，当前不是 symlink，改一处必须同步另一处。</li>
        <li>Gateway 走 18789，所有 OpenClaw 控制流（chat / tools / streams）都从这里进出。</li>
        <li>File-API 7682 处理聊天历史、文件上传、copilot 类资源；用 cookie 校验。</li>
      </ul>
    </section>
  </div>
</template>

<style scoped lang="scss">
.arch-view {
  flex: 1;
  overflow-y: auto;
  padding: 24px clamp(16px, 4vw, 48px) 80px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  background: var(--bg);
  color: var(--text);
}
.page-head { display: flex; flex-direction: column; gap: 6px; }
h1 { margin: 0; font-size: 20px; font-weight: 600; }
.sub { margin: 0; color: var(--text-sec); font-size: 13px; line-height: 1.6; max-width: 760px; }

.hint {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 14px 18px;
}
.hint h3 { margin: 0 0 8px; font-size: 13px; font-weight: 600; color: var(--text); }
.hint ul { margin: 0; padding-left: 20px; }
.hint li { font-size: 12px; line-height: 1.7; color: var(--text-sec); }
.hint code { background: var(--bg); border: 1px solid var(--border); padding: 1px 5px; border-radius: 4px; font-family: var(--font-mono); color: var(--text); }
</style>
