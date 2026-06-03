
# =================== v5.145 晚间深度优化④ ===================
# 基于回测TOP1策略(MACD+RSI Sharpe 2.35)的权重激进优化
# + 盘整期多因子融合 + 情绪自适应信号

# ① MACD+RSI权重激进优化 (v5.144: 2.0 → v5.145: 2.5)
MACD_RSI_SIGNAL_BOOST = 2.5  # v5.145: +25% 激进优化 (基于回测TOP1 Sharpe 2.35)

# 科技成长赛道权重 (v5.144: 0.45 → v5.145: 0.50)
TECH_GROWTH_WEIGHT_BOOST = 0.50  # v5.145: +11% 权重提升

# ② 盘整期多因子融合 (情绪85+自动激活)
CONSOLIDATION_MULTIFACTOR_FUSION = {
    'enabled': True,
    'macd_params': {
        'fast': 10,      # 12 → 10: 更敏感
        'slow': 30,      # 26 → 30: 周期拉长
        'signal': 7      # 9 → 7: 信号加快
    },
    'rsi_params': {
        'period': 12,    # 14 → 12: 更敏感
        'oversold': 35,  # 30 → 35
        'overbought': 65 # 70 → 65
    },
    'ma_filter': {
        'enabled': True,
        'periods': [20, 60],
        'requirement': 'close > MA20 AND MA20 > MA60'
    },
    'fund_flow_filter': {
        'enabled': True,
        'positive_ratio_threshold': 0.60  # 60% 主力资金流向正
    }
}

# ③ 实时情绪自适应信号阈值
SENTIMENT_DRIVEN_MACD_RSI = {
    'extreme_fear': {
        'macd_histogram_threshold': 0.5,
        'macd_crossover_multiplier': 1.2,
        'rsi_oversold': 40,
        'rsi_overbought': 60
    },
    'fear': {
        'macd_histogram_threshold': 1.0,
        'macd_crossover_multiplier': 1.1,
        'rsi_oversold': 35,
        'rsi_overbought': 65
    },
    'normal': {
        'macd_histogram_threshold': 1.5,
        'macd_crossover_multiplier': 1.0,
        'rsi_oversold': 30,
        'rsi_overbought': 70
    },
    'greed': {
        'macd_histogram_threshold': 2.0,
        'macd_crossover_multiplier': 0.8,
        'rsi_oversold': 25,
        'rsi_overbought': 75
    },
    'extreme_greed': {
        'macd_histogram_threshold': 2.5,
        'macd_crossover_multiplier': 0.6,
        'rsi_oversold': 20,
        'rsi_overbought': 80
    }
}

# 配置应用优先级 (v5.145)
CONFIG_APPLICATION_PRIORITY = {
    'MACD_RSI_SIGNAL_BOOST': 1,  # 最高: 权重激进优化
    'CONSOLIDATION_MULTIFACTOR_FUSION': 2,  # 次高: 多因子融合
    'SENTIMENT_DRIVEN_MACD_RSI': 3  # 中等: 情绪自适应
}
