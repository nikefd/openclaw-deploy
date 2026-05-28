
# =================== v5.138 Phase 1: 回测驱动参数融合 ===================
# 时间: 2026-05-28 14:02:39 UTC
# 目标: 基于TOP2回测策略，动态融合权重，提升收益到21%+

# 最优策略权重配置
BACKTEST_DRIVEN_WEIGHTS = {
    'MACD+RSI (科技成长)': {
        'weight': 0.5,  # 动态权重
        'total_return': 17.1,
        'sharpe_ratio': 2.35,
        'max_drawdown': 4.08,
        'win_rate': 60.0,
        'profit_factor': 2.73
    },
}

# 权重融合开启标志
BACKTEST_FUSION_ENABLED = True

# 市值分层的MACD参数 (v5.138: 新增, 小盘股适配)
MACD_PARAMS_BY_MARKET_CAP = {
    'large_cap': {'fast': 12, 'slow': 26, 'signal': 9},    # > 2000亿: 标准参数
    'mid_cap': {'fast': 9, 'slow': 21, 'signal': 7},       # 500-2000亿: 敏感参数
    'small_cap': {'fast': 7, 'slow': 17, 'signal': 5}      # < 500亿: 快速参数
}

# RSI周期按市值分层
RSI_PERIOD_BY_MARKET_CAP = {
    'large_cap': 14,    # 蓝筹股: 14周期 (平稳)
    'mid_cap': 12,      # 中盘股: 12周期 (科技成长)
    'small_cap': 10     # 小盘股: 10周期 (敏感)
}

# 多级止盈策略 (v5.138: 新增)
SCALED_EXIT_ENABLED = True
SCALED_EXIT_TARGETS = {
    # 目标: 分级锁定利润，捕获更多上升空间
    'phase_1': {'profit_pct': 0.03, 'qty_pct': 0.17},    # 3% 卖17%
    'phase_2': {'profit_pct': 0.08, 'qty_pct': 0.33},    # 8% 卖33%
    'phase_3': {'profit_pct': 0.15, 'qty_pct': 0.25},    # 15% 卖25%
    'hold': 0.25  # 持有25%, 参与长期上升
}

# 龙虎榜缺失补偿机制 (v5.138: 新增)
VOLUME_SURGE_BOOST = 0.25       # 成交量突增: +25分
INSTITUTIONAL_BOOST = 0.20      # 机构参与: +20分  
MARGIN_BOOST = 0.05             # 融资净买: +5分
VOLUME_SURGE_THRESHOLD = 1.5    # 成交量须 > 日均 × 1.5

# 信号权重优化 (v5.138 Phase 1: 基于回测数据)
SIGNAL_WEIGHTS_V138 = {
    'technical': 0.40,    # 技术面 (MACD/RSI/突破)
    'funding': 0.30,      # 资金面 (成交量/机构/融资)
    'sentiment': 0.20,    # 情绪面
    'fundamental': 0.10   # 基本面
}
