// Phase D1 — finance agent stub data. Replaced by real API in Phase E.
import type {
  FinanceDashboard,
  Holding,
  TradingSignal,
  RiskAlert,
} from '@/api/finance'

export const FINANCE_HOLDINGS: Holding[] = [
  { code: '600519', name: '贵州茅台', qty: 100, cost: 1680.0, price: 1745.5, weight: 0.32 },
  { code: '000858', name: '五粮液', qty: 200, cost: 152.4, price: 148.2, weight: 0.11 },
  { code: '300750', name: '宁德时代', qty: 80, cost: 218.6, price: 245.3, weight: 0.18 },
  { code: '002594', name: '比亚迪', qty: 150, cost: 245.0, price: 256.8, weight: 0.14 },
  { code: '601318', name: '中国平安', qty: 500, cost: 48.2, price: 51.6, weight: 0.13 },
  { code: '600036', name: '招商银行', qty: 400, cost: 36.4, price: 38.9, weight: 0.12 },
]

export const FINANCE_SIGNALS: TradingSignal[] = [
  { id: 's1', ts: '10:32', code: '600519', name: '贵州茅台', action: 'BUY', reason: '突破 20 日均线 + MACD 金叉', confidence: 0.78 },
  { id: 's2', ts: '10:18', code: '300750', name: '宁德时代', action: 'HOLD', reason: '震荡整理，量能不足', confidence: 0.55 },
  { id: 's3', ts: '09:54', code: '000858', name: '五粮液', action: 'SELL', reason: '跌破支撑位，止损', confidence: 0.68 },
  { id: 's4', ts: '09:47', code: '601318', name: '中国平安', action: 'BUY', reason: '估值修复 + 行业轮动信号', confidence: 0.72 },
  { id: 's5', ts: '09:32', code: '002594', name: '比亚迪', action: 'HOLD', reason: '等待财报披露', confidence: 0.50 },
  { id: 's6', ts: '昨日', code: '600036', name: '招商银行', action: 'BUY', reason: '银行板块底部企稳', confidence: 0.65 },
  { id: 's7', ts: '昨日', code: '300059', name: '东方财富', action: 'WATCH', reason: '观察量能突破', confidence: 0.42 },
  { id: 's8', ts: '昨日', code: '600276', name: '恒瑞医药', action: 'BUY', reason: '医药超跌反弹', confidence: 0.61 },
  { id: 's9', ts: '前日', code: '601888', name: '中国中免', action: 'HOLD', reason: '消费复苏不及预期', confidence: 0.48 },
  { id: 's10', ts: '前日', code: '002475', name: '立讯精密', action: 'BUY', reason: '苹果链订单回暖', confidence: 0.70 },
]

export const FINANCE_ALERTS: RiskAlert[] = [
  { id: 'r1', level: 'high', title: '单股集中度告警', detail: '贵州茅台仓位 32%，超出 25% 上限' },
  { id: 'r2', level: 'medium', title: '行业暴露偏高', detail: '消费板块敞口 43%，建议分散' },
  { id: 'r3', level: 'low', title: '波动率提升', detail: '组合 5 日波动率 +15%' },
  { id: 'r4', level: 'low', title: '现金比例偏低', detail: '现金 8%，低于 15% 阈值' },
]

export const FINANCE_DASHBOARD: FinanceDashboard = {
  netValue: 1284530.42,
  pnlToday: 8462.18,
  pnlTodayPct: 0.0066,
  positions: FINANCE_HOLDINGS.length,
  alerts: FINANCE_ALERTS.length,
  holdings: FINANCE_HOLDINGS,
  signals: FINANCE_SIGNALS,
  riskAlerts: FINANCE_ALERTS,
}
