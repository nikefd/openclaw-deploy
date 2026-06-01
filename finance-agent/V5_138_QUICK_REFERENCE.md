# v5.138 快速参考卡

## 🎯 4大核心优化 (一页纸速记)

### Phase 1: 回测驱动融合
```
TOP 策略: MACD+RSI (科技成长)
17.1% 收益 → 权重50% → BACKTEST_FUSION_ENABLED
```

### Phase 2: 市值分层
```
蓝筹(>2000亿):    MACD(12,26,9)  RSI14
中盘(500-2000亿): MACD(9,21,7)   RSI12  ← 东方证券(180亿)
小盘(<500亿):     MACD(7,17,5)   RSI10  ← 华映科技(20亿)
```

### Phase 3: 多级止盈
```
3% → 卖17% (¥79)
8% → 卖33% (¥330)
15% → 卖25% (¥595)
∞ → 持25% (参与上升)
总: ¥1,604 (+38% vs全清)
```

### Phase 4: 资金面评分 (小盘股)
```
基础: 50分 (无龙虎榜补偿)
成交量突增(>1.5倍): +20分
机构参与(大单活跃): +15分
融资净买(+3%):      +5分
─────────────────────
90分 ✅ 强信号
```

## 📊 预期效果

| 指标 | 当前 | 优化后 | 改进 |
|-----|------|--------|------|
| 收益 | 17.1% | 21%+ | +23% |
| Sharpe | 2.35 | 2.8+ | +19% |
| 回撤 | 4.08% | 3.5% | -14% |
| 胜率 | 60% | 65%+ | +8% |
| 选股 | 25% | 32%+ | +28% |

## 🔧 新增配置 (config.py)

```python
BACKTEST_FUSION_ENABLED = True
MACD_PARAMS_BY_MARKET_CAP = {...}
RSI_PERIOD_BY_MARKET_CAP = {...}
SCALED_EXIT_ENABLED = True
SCALED_EXIT_TARGETS = {...}
SIGNAL_WEIGHTS_V138 = {...}
```

## 📁 核心文件

- `v5_138_phase2_market_cap_adaptive.py` - 市值自适应
- `v5_138_phase3_scaled_exit.py` - 多级止盈
- `v5_138_phase4_funding_enhance.py` - 资金评分

## ⏭️ 后续集成

1. 将Phase代码集成到 `stock_picker.py` 
2. 将Phase代码集成到 `position_manager.py`
3. 完整回测验证
4. 部署 + 重启服务

---
**v5.138 完成状态**: ✅ 代码完成 | ✅ 测试通过 | ⏳ 等待集成
