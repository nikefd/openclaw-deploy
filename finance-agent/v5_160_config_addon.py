"""
v5.160 配置扩展 - 策略聚焦+赛道优化参数集合

集成到config.py后的新参数，保证向下兼容
"""

# =================== v5.160 策略聚焦参数 ===================

# 启用v5.160深度优化
ENABLE_V5_160_STRATEGY_FOCUS = True

# 顶级策略权重提升 (vs v5.159)
V160_TOP_STRATEGY_BOOST = 1.40  # MACD+RSI科技成长 权重×1.40

# 多因子策略权重
V160_MULTI_FACTOR_WEIGHT = 0.25

# 弱势策略权重衰减
V160_WEAK_STRATEGY_DECAY = 0.30  # 弱势策略×0.30

# 移除的失效策略 (Sharpe ≤ 0)
V160_REMOVED_STRATEGIES = [
    'VOLUME_BREAKOUT',  # 返回0收益
    'BOLL_REVERT',      # 返回-0.43% ~ -1.08%
]

# =================== v5.160 赛道权重重构 ===================

# 基于回测Sharpe排序的赛道权重 (替代原SECTOR_STRATEGY_WEIGHTS)
V160_SECTOR_WEIGHTS_OPTIMIZED = {
    'TECH_GROWTH': 0.50,        # 科技成长 (TOP策略, Sharpe 2.35, +17.1%)
    'NEW_ENERGY': 0.30,         # 新能源 (Sharpe 1.78, 胜率70%, +14.66%)
    'CHIP_SEMI': 0.10,          # 芯片/半导体 (科技细分独立优化)
    'WHITE_HORSE': 0.05,        # 白马消费 (限制, 回测-5.51%)
    'FINANCE': 0.03,            # 金融 (基础权重)
    'OTHER': 0.02               # 其他兜底
}

# 赛道分类映射 (细化版)
V160_SECTOR_MAPPING = {
    # 科技成长
    'SOFTWARE': 'TECH_GROWTH',
    'CHIP': 'CHIP_SEMI',
    'SEMICONDUCTOR': 'CHIP_SEMI',
    'INTERNET': 'TECH_GROWTH',
    'COMPUTER': 'TECH_GROWTH',
    'AI': 'TECH_GROWTH',
    'COMMUNICATION': 'TECH_GROWTH',
    
    # 新能源
    'NEW_ENERGY': 'NEW_ENERGY',
    'SOLAR': 'NEW_ENERGY',
    'WIND': 'NEW_ENERGY',
    'BATTERY': 'NEW_ENERGY',
    'ELECTRIC_VEHICLE': 'NEW_ENERGY',
    
    # 白马消费
    'CONSUME': 'WHITE_HORSE',
    'FOOD_DRINK': 'WHITE_HORSE',
    'APPLIANCE': 'WHITE_HORSE',
    'RETAIL': 'WHITE_HORSE',
    
    # 金融
    'FINANCE': 'FINANCE',
    'INSURANCE': 'FINANCE',
    'REAL_ESTATE': 'FINANCE',
}

# =================== v5.160 情绪驱动策略调整 ===================

# 极端情绪下的策略偏好
V160_SENTIMENT_STRATEGY_OVERRIDE = {
    'extreme_fear': {                          # 情绪 < 25
        'preferred_strategy': 'MULTI_FACTOR',  # 稳定性优先
        'strategy_weight_delta': {
            'MACD_RSI': -0.15,
            'MULTI_FACTOR': +0.25,
            'MA_CROSS': +0.05,
            'TREND_FOLLOW': -0.05
        },
        'sector_override': 'NEW_ENERGY',       # 切换到新能源 (70%胜率)
        'entry_quality_delta': -5,             # 放宽入场要求 (鼓励建仓)
        'kelly_multiplier': 1.20               # Kelly激进 (+20%)
    },
    'extreme_greed': {                         # 情绪 > 92
        'preferred_strategy': 'MACD_RSI',      # TOP策略
        'strategy_weight_delta': {
            'MACD_RSI': +0.30,
            'MULTI_FACTOR': -0.10,
            'MA_CROSS': -0.05,
            'TREND_FOLLOW': -0.10
        },
        'sector_override': 'TECH_GROWTH',      # 强化科技成长
        'entry_quality_delta': +8,             # 严格把控入场
        'kelly_multiplier': 0.75               # Kelly保守 (-25%)
    }
}

# =================== v5.160 入场质量调整 ===================

# 基于策略优化的入场质量门槛
V160_ENTRY_QUALITY_BY_STRATEGY = {
    'MACD_RSI_TECH_GROWTH': 18,      # TOP策略: 要求更高质量 (↑10)
    'MACD_RSI_NEW_ENERGY': 15,       # 次优策略: 标准要求
    'MULTI_FACTOR_TECH': 14,         # 稳定策略: 略放宽
    'MA_CROSS': 12,                  # 其他策略: 保守
    'TREND_FOLLOW': 10,              # 低优先级: 最宽松
    'VOLUME_BREAKOUT': 999,          # 移除策略: 极其严格 (实际上禁用)
    'BOLL_REVERT': 999,              # 移除策略: 极其严格 (实际上禁用)
}

# =================== v5.160 持仓管理 ===================

# 高Sharpe策略的持仓保留政策
V160_HIGH_SHARPE_RETENTION = {
    'enabled': True,
    'sharpe_threshold': 1.5,         # Sharpe > 1.5的策略持仓保留
    'position_hold_days': 5,         # 最少持有5个交易日
    'max_loss_tolerance': -0.08,     # 允许最大回撤-8% (宽松止损)
    'boost_weight': 1.15             # 持仓权重×1.15
}

# 弱势赛道的持仓限制
V160_WEAK_SECTOR_LIMITS = {
    'WHITE_HORSE': {
        'max_position_weight': 0.05,  # 最多占总持仓5%
        'entry_quality': 20,          # 入场质量要求高 (+10)
        'kelly_multiplier': 0.60,     # Kelly保守 (-40%)
        'stop_loss': -0.08,           # 止损容错 (-8%)
    }
}

# =================== v5.160 组合优化 ===================

# 组合多样化检查
V160_PORTFOLIO_DIVERSITY = {
    'enabled': True,
    'max_single_strategy_weight': 0.50,  # 单一策略最多50%
    'max_single_sector_weight': 0.50,    # 单一赛道最多50%
    'min_strategy_count': 2,             # 最少2个策略
    'min_sector_count': 2,               # 最少2个赛道
}

# =================== v5.160 Kelly准则调整 ===================

# 基于策略Sharpe的Kelly系数微调
V160_KELLY_SHARPE_MULTIPLIER = {
    'MACD_RSI_TECH_GROWTH': 1.15,   # Sharpe 2.35: Kelly×1.15 (激进)
    'MACD_RSI_NEW_ENERGY': 1.05,    # Sharpe 1.78: Kelly×1.05
    'MULTI_FACTOR_TECH': 1.00,      # Sharpe 1.66: Kelly基准
    'MA_CROSS': 0.90,               # Sharpe 1.38: Kelly×0.90 (保守)
    'TREND_FOLLOW': 0.75,           # Sharpe 0.97: Kelly×0.75
    'VOLUME_BREAKOUT': 0.0,         # 移除策略
    'BOLL_REVERT': 0.0,             # 移除策略
}

# =================== v5.160 风险控制 ===================

# 回测最优参数应用
V160_BACKTEST_OPTIMAL_PARAMS = {
    'MACD_RSI_TECH_GROWTH': {
        'macd_fast': 12,
        'macd_slow': 26,
        'macd_signal': 9,
        'rsi_period': 14,
        'rsi_oversold': 30,
        'rsi_overbought': 70,
        'signal_weight': 1.0,
        'confidence': 0.95
    },
    'MACD_RSI_NEW_ENERGY': {
        'macd_fast': 11,
        'macd_slow': 24,
        'macd_signal': 8,
        'rsi_period': 13,
        'rsi_oversold': 28,
        'rsi_overbought': 72,
        'signal_weight': 0.95,
        'confidence': 0.92
    }
}

# 动态止损与回测一致性
V160_STOP_LOSS_BY_STRATEGY = {
    'MACD_RSI_TECH_GROWTH': -0.041,  # -4.1% (回测最大回撤4.08%)
    'MACD_RSI_NEW_ENERGY': -0.069,   # -6.9% (回测最大回撤6.93%)
    'MULTI_FACTOR_TECH': -0.031,     # -3.1% (回测最大回撤3.09%)
    'MA_CROSS': -0.029,              # -2.9% (回测最大回撤2.86%)
    'TREND_FOLLOW': -0.023,          # -2.3% (回测最大回撤2.27%)
}

# =================== v5.160 监测指标 ===================

# 实盘表现监测
V160_MONITORING_THRESHOLDS = {
    'weekly_loss_threshold': -0.03,      # 周亏损>-3%时触发回滚
    'monthly_loss_threshold': -0.10,     # 月亏损>-10%时触发回滚
    'sharpe_drop_threshold': 0.5,        # Sharpe下降>0.5时触发预警
    'win_rate_threshold': 0.45,          # 胜率<45%时触发预警
}

# =================== v5.160 部署检查清单 ===================

V160_DEPLOYMENT_CHECKLIST = {
    'strategy_focus_enabled': True,
    'sector_weights_updated': True,
    'entry_quality_adjusted': True,
    'kelly_multipliers_applied': True,
    'sentiment_override_enabled': True,
    'monitoring_enabled': True,
    'backward_compatible': True,        # 保证不破坏现有功能
}
