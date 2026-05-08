<script setup lang="ts">
// FinanceView.vue — /v2/agents/finance dashboard.
// Stub data only; Phase E wires real backend (port 7684/7685).
import { computed } from 'vue'
import { useFinanceData } from '@/composables/useFinanceData'
import DashboardPanel from '@/components/agents/DashboardPanel.vue'
import MetricGroup from '@/components/agents/MetricGroup.vue'
import KpiCard from '@/components/agents/KpiCard.vue'
import DataTable, { type Column } from '@/components/agents/DataTable.vue'
import type { Holding } from '@/api/finance'

const { loading, data, error } = useFinanceData()

const holdingsColumns: Column<Holding>[] = [
  { key: 'code', label: '代码', align: 'left' },
  { key: 'name', label: '名称', align: 'left' },
  { key: 'qty', label: '数量', align: 'right' },
  {
    key: 'cost',
    label: '成本',
    align: 'right',
    format: (v) => Number(v).toFixed(2),
  },
  {
    key: 'price',
    label: '现价',
    align: 'right',
    format: (v) => Number(v).toFixed(2),
  },
  {
    key: 'price',
    label: '盈亏',
    align: 'right',
    format: (_v, row) => {
      const pnl = (row.price - row.cost) * row.qty
      const pct = ((row.price - row.cost) / row.cost) * 100
      const sign = pnl >= 0 ? '+' : ''
      return `${sign}${pnl.toFixed(0)} (${sign}${pct.toFixed(1)}%)`
    },
  },
  {
    key: 'weight',
    label: '占比',
    align: 'right',
    format: (v) => `${(Number(v) * 100).toFixed(1)}%`,
  },
]

const formattedNetValue = computed(() => {
  if (!data.value) return '—'
  return `¥${data.value.netValue.toLocaleString('zh-CN', { maximumFractionDigits: 0 })}`
})
const formattedPnl = computed(() => {
  if (!data.value) return '—'
  const sign = data.value.pnlToday >= 0 ? '+' : ''
  return `${sign}¥${data.value.pnlToday.toLocaleString('zh-CN', { maximumFractionDigits: 0 })}`
})
</script>

<template>
  <div class="view">
    <header class="topbar">
      <RouterLink to="/agents" class="back">← Agent Hub</RouterLink>
      <h1>💰 A股金融 Agent</h1>
      <span class="hint">stub 数据 · Phase E 接真后端</span>
    </header>

    <div v-if="loading" class="state">加载中…</div>
    <div v-else-if="error" class="state err">加载失败：{{ error }}</div>

    <template v-else-if="data">
      <MetricGroup>
        <KpiCard
          label="账户净值"
          :value="formattedNetValue"
          :delta="data.pnlTodayPct * 100"
        />
        <KpiCard
          label="当日盈亏"
          :value="formattedPnl"
          :delta="data.pnlTodayPct * 100"
        />
        <KpiCard label="持仓数" :value="data.positions" />
        <KpiCard label="风控告警" :value="data.alerts" />
      </MetricGroup>

      <div class="layout">
        <div class="main">
          <DashboardPanel title="持仓" subtitle="按占比排序">
            <DataTable
              :columns="holdingsColumns"
              :rows="data.holdings"
              initial-sort-key="weight"
              initial-sort-dir="desc"
            />
          </DashboardPanel>

          <div class="row-2">
            <DashboardPanel title="止损 / 止盈看板">
              <div class="stub-board">
                <div class="stub-row">
                  <span class="stub-label">触发止损线</span>
                  <span class="stub-val warn">2 只</span>
                </div>
                <div class="stub-row">
                  <span class="stub-label">逼近止盈</span>
                  <span class="stub-val ok">1 只</span>
                </div>
                <div class="stub-row">
                  <span class="stub-label">移动止盈激活</span>
                  <span class="stub-val">3 只</span>
                </div>
                <div class="ph">📊 Phase E: echarts 渐变图占位</div>
              </div>
            </DashboardPanel>

            <DashboardPanel title="实时风险告警">
              <ul class="alerts">
                <li v-for="a in data.riskAlerts" :key="a.id" :class="['lvl-' + a.level]">
                  <span class="badge">{{ a.level.toUpperCase() }}</span>
                  <div>
                    <div class="atitle">{{ a.title }}</div>
                    <div class="adetail">{{ a.detail }}</div>
                  </div>
                </li>
              </ul>
            </DashboardPanel>
          </div>

          <div class="row-2">
            <DashboardPanel title="策略复盘">
              <div class="ph tall">🧩 近 30 日策略胜率 / 滑点 / 换手 — Phase E</div>
            </DashboardPanel>
            <DashboardPanel title="回测对比">
              <div class="ph tall">📈 多策略 PnL 曲线 — Phase E</div>
            </DashboardPanel>
          </div>
        </div>

        <aside class="side">
          <DashboardPanel title="交易信号流" subtitle="最近 10 条">
            <ul class="signals">
              <li v-for="s in data.signals" :key="s.id">
                <div class="sig-head">
                  <span class="sig-ts">{{ s.ts }}</span>
                  <span class="sig-action" :class="s.action.toLowerCase()">{{ s.action }}</span>
                </div>
                <div class="sig-name">{{ s.code }} {{ s.name }}</div>
                <div class="sig-reason">{{ s.reason }}</div>
                <div class="sig-conf">置信度 {{ (s.confidence * 100).toFixed(0) }}%</div>
              </li>
            </ul>
          </DashboardPanel>
        </aside>
      </div>
    </template>
  </div>
</template>

<style scoped lang="scss">
.view {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px 24px 32px;
  background: var(--bg);
  color: var(--text);
  overflow-y: auto;
}
.topbar { display: flex; align-items: baseline; gap: 14px; }
.topbar h1 { margin: 0; font-size: 20px; }
.back { color: var(--text-sec); font-size: 13px; text-decoration: none; }
.back:hover { color: var(--accent); }
.hint { font-size: 11px; color: var(--text-sec); margin-left: auto; }
.state { padding: 24px; color: var(--text-sec); &.err { color: var(--danger); } }

.layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 320px;
  gap: 16px;
}
.main { display: flex; flex-direction: column; gap: 16px; min-width: 0; }
.row-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
@media (max-width: 1024px) {
  .layout { grid-template-columns: 1fr; }
  .row-2 { grid-template-columns: 1fr; }
}

.stub-board { display: flex; flex-direction: column; gap: 8px; }
.stub-row { display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px dashed var(--border); }
.stub-label { color: var(--text-sec); font-size: 13px; }
.stub-val { font-weight: 600; }
.stub-val.warn { color: #f0b429; }
.stub-val.ok { color: #10a37f; }
.ph {
  margin-top: 12px;
  padding: 24px;
  background: linear-gradient(135deg, var(--accent-soft), transparent);
  border: 1px dashed var(--border);
  border-radius: var(--radius-md);
  color: var(--text-sec);
  font-size: 13px;
  text-align: center;
}
.ph.tall { padding: 56px 24px; }

.alerts { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 10px; }
.alerts li { display: flex; gap: 10px; align-items: flex-start; }
.alerts .badge {
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 4px;
  font-weight: 700;
  flex-shrink: 0;
  margin-top: 2px;
}
.lvl-high .badge { background: rgba(239, 68, 68, 0.18); color: #ef4444; }
.lvl-medium .badge { background: rgba(240, 180, 41, 0.2); color: #f0b429; }
.lvl-low .badge { background: rgba(16, 163, 127, 0.18); color: #10a37f; }
.atitle { font-size: 13px; font-weight: 500; }
.adetail { font-size: 12px; color: var(--text-sec); margin-top: 2px; }

.side { min-width: 0; }
.signals { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 12px; }
.signals li {
  padding: 10px;
  border-radius: var(--radius-sm);
  background: var(--bg);
  border: 1px solid var(--border);
}
.sig-head { display: flex; justify-content: space-between; align-items: center; }
.sig-ts { font-size: 11px; color: var(--text-sec); font-family: var(--font-mono); }
.sig-action {
  font-size: 11px;
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 3px;
  &.buy { background: rgba(16, 163, 127, 0.18); color: #10a37f; }
  &.sell { background: rgba(239, 68, 68, 0.18); color: #ef4444; }
  &.hold { background: var(--hover); color: var(--text-sec); }
  &.watch { background: rgba(240, 180, 41, 0.2); color: #f0b429; }
}
.sig-name { font-size: 13px; font-weight: 500; margin-top: 4px; }
.sig-reason { font-size: 12px; color: var(--text-sec); margin-top: 2px; line-height: 1.4; }
.sig-conf { font-size: 11px; color: var(--text-sec); margin-top: 4px; }
</style>
