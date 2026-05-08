<script setup lang="ts">
// DataFlowList.vue — narrative of how requests travel through the stack.
interface Flow {
  id: string
  title: string
  steps: string[]
  emoji: string
}

const FLOWS: Flow[] = [
  {
    id: 'chat',
    emoji: '💬',
    title: '聊天消息',
    steps: ['Browser', 'Nginx /v1/', 'Gateway 18789', 'OpenClaw runtime', '流回 socket.io'],
  },
  {
    id: 'file',
    emoji: '📁',
    title: '聊天历史 / 文件上传',
    steps: ['Browser', 'Nginx /api/files/', 'File-API 7682', '本地磁盘 + sqlite'],
  },
  {
    id: 'auth',
    emoji: '🔑',
    title: '登录态校验',
    steps: ['Browser cookie', 'Nginx auth_request', 'Auth 7683', '通过 → 真实路由'],
  },
  {
    id: 'agent',
    emoji: '🤖',
    title: 'Agent 数据写入',
    steps: ['@攀岩教练 触发', 'Gateway 解析', 'Agents-API 7685', 'sessions.json 持久化', '前端 /agents/* 拉新数据'],
  },
  {
    id: 'finance',
    emoji: '💰',
    title: '金融行情',
    steps: ['/finance 页面定时拉', 'Finance 7684', '数据源 / 缓存', '回前端渲染'],
  },
  {
    id: 'usage',
    emoji: '📊',
    title: 'Token 用量统计',
    steps: ['Gateway 上报 usage 事件', 'Usage 7686 聚合', '/v2/usage 拉摘要', 'CostEstimate 渲染'],
  },
]
</script>

<template>
  <div class="flows">
    <h3>主要数据流</h3>
    <ol>
      <li v-for="f in FLOWS" :key="f.id">
        <div class="title"><span class="emoji">{{ f.emoji }}</span><strong>{{ f.title }}</strong></div>
        <div class="path">
          <template v-for="(s, i) in f.steps" :key="i">
            <span class="step">{{ s }}</span>
            <span v-if="i < f.steps.length - 1" class="arr">→</span>
          </template>
        </div>
      </li>
    </ol>
  </div>
</template>

<style scoped lang="scss">
.flows {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 14px 18px;
}
h3 { margin: 0 0 10px; font-size: 13px; font-weight: 600; color: var(--text); }
ol {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
li {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--bg);
}
.title { display: flex; align-items: center; gap: 6px; }
.title strong { color: var(--text); font-size: 13px; }
.emoji { font-size: 16px; }
.path {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-sec);
  font-family: var(--font-mono);
}
.step {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 2px 6px;
}
.arr { color: var(--accent); }
</style>
