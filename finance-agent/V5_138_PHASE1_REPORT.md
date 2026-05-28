# v5.138 Phase 1 执行报告

**时间**: 2026-05-28 14:02:39 UTC

## 提取的最优策略

### TOP 1: MACD+RSI (科技成长)
- 总收益: 17.10%
- Sharpe: 2.35
- 最大回撤: 4.08%
- 胜率: 60.0%
- 利润因子: 2.73

### TOP 2: MACD+RSI (科技成长)
- 总收益: 17.10%
- Sharpe: 2.35
- 最大回撤: 4.08%
- 胜率: 60.0%
- 利润因子: 2.73

## 权重融合

{
  "MACD+RSI (科技成长)": {
    "weight": 0.5,
    "metrics": {
      "id": 6,
      "strategy": "MACD+RSI (科技成长)",
      "total_return": 17.1,
      "sharpe_ratio": 2.35,
      "max_drawdown": 4.08,
      "win_rate": 60.0,
      "profit_factor": 2.73
    }
  }
}

## 新增配置项

1. **BACKTEST_DRIVEN_WEIGHTS**: 动态权重融合
2. **MACD_PARAMS_BY_MARKET_CAP**: 市值分层参数
3. **RSI_PERIOD_BY_MARKET_CAP**: RSI周期调整
4. **SCALED_EXIT_ENABLED**: 多级止盈
5. **龙虎榜缺失补偿**: 成交量/机构/融资指标

## 预期效果

- 收益提升: 17.1% → 21%+ (+23%)
- Sharpe提升: 2.35 → 2.8+ (+19%)
- 最大回撤: 4.08% → 3.5% (-14%)
