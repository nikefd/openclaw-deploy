<script setup lang="ts">
// AgentsView.vue — /v2/agents hub. 2x2 card wall of agent entry points.
import AgentCard from '@/components/agents/AgentCard.vue'

interface AgentEntry {
  emoji: string
  name: string
  description: string
  status: 'active' | 'paused' | 'gray'
  recent: string
  to: string
}

const AGENTS: AgentEntry[] = [
  {
    emoji: '💰',
    name: 'A股金融 Agent',
    description: '实盘信号 / 持仓监控 / 风险告警，每日盯盘',
    status: 'active',
    recent: '今日产出 10 条信号 · 净值 +0.66%',
    to: '/agents/finance',
  },
  {
    emoji: '🧗',
    name: '攀岩教练',
    description: '训练数据分析 + 瓶颈诊断 + 周计划',
    status: 'active',
    recent: '本周已训练 3 次 · 最高 V4+',
    to: '/agents/climbing',
  },
  {
    emoji: '💼',
    name: '面试准备',
    description: '日程 / 公司库 / 系统设计 + 行为面 + 编码题',
    status: 'active',
    recent: '本周 5 场面试待打 · NVIDIA / Pika / Tipsy',
    to: '/agents/interview',
  },
  {
    emoji: '🛰️',
    name: 'AI 前沿日报',
    description: 'Paper / Blog / Tweet 每日精选，含 mermaid 图',
    status: 'active',
    recent: '今日 10 条更新 · Claude 4.5 / DeepSeek-V4',
    to: '/agents/ai-frontier',
  },
]
</script>

<template>
  <div class="agents-view">
    <header class="topbar">
      <div class="prompt"><span class="dollar">$</span> Agent Hub</div>
      <button class="btn-stub" disabled title="Phase E">整理</button>
    </header>

    <main class="grid">
      <AgentCard
        v-for="a in AGENTS"
        :key="a.to"
        :emoji="a.emoji"
        :name="a.name"
        :description="a.description"
        :status="a.status"
        :recent="a.recent"
        :to="a.to"
      />
    </main>
  </div>
</template>

<style scoped lang="scss">
.agents-view {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: var(--bg);
  color: var(--text);
  overflow-y: auto;
  padding: 16px 24px 32px;
  gap: 20px;
}
.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-family: var(--font-mono);
}
.prompt { font-size: 14px; color: var(--text-sec); }
.dollar { color: var(--accent); margin-right: 4px; }
.btn-stub {
  background: transparent;
  border: 1px solid var(--border);
  color: var(--text-sec);
  border-radius: var(--radius-sm);
  padding: 4px 10px;
  font-size: 12px;
  cursor: not-allowed;
  opacity: 0.6;
}
.grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
  max-width: 1100px;
  width: 100%;
  align-self: center;
}
@media (max-width: 720px) {
  .grid { grid-template-columns: 1fr; }
  .agents-view { padding: 12px 16px 24px; }
}
</style>
