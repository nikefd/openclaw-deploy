"""v5.100 配置附加模块 — 深度优化配置
此文件包含v5.100的所有新配置,可导入到主config.py中使用
"""

# =================== v5.100: 深度优化配置段 ===================

# v5.100: MACD+RSI优化参数 (按赛道差异化)
# 来源: 回测数据 MACD+RSI(科技成长) 17.1% return, 2.35 Sharpe, 60% win_rate
MACD_RSI_PARAMS_V100 = {
    '科技成长': {
        'macd_fast': 11,
        'macd_slow': 26,
        'macd_signal': 9,
        'rsi_period': 13,
        'rsi_oversold': 28,
        'rsi_overbought': 72,
        'entry_score_boost': 3.5,
        'description': '更敏感的MACD + 更激进的RSI超卖'
    },
    '新能源': {
        'macd_fast': 12,
        'macd_slow': 26,
        'macd_signal': 9,
        'rsi_period': 14,
        'rsi_oversold': 30,
        'rsi_overbought': 70,
        'entry_score_boost': 2.8,
        'description': '平衡型参数组合'
    },
    '白马消费': {
        'macd_fast': 12,
        'macd_slow': 28,
        'macd_signal': 10,
        'rsi_period': 15,
        'rsi_oversold': 35,
        'rsi_overbought': 68,
        'entry_score_boost': 2.5,
        'description': '更长周期,防止噪声'
    },
    '混合池': {
        'macd_fast': 12,
        'macd_slow': 26,
        'macd_signal': 9,
        'rsi_period': 14,
        'rsi_oversold': 30,
        'rsi_overbought': 70,
        'entry_score_boost': 2.8,
        'description': '通用参数'
    }
}

# v5.100: Kelly动态仓位 (基于Sharpe 2.35反推)
# 公式: f = (p*win - (1-p)*loss) / (win*loss)
# p=60%, win=1.5%, loss=0.8% → Kelly=35%, 安全系数0.5 → 17.5%
KELLY_V100 = {
    'enabled': True,
    'kelly_full': 0.35,                    # Kelly完全仓位 35%
    'kelly_half': 0.175,                   # 安全系数0.5 → 17.5% (使用此值)
    'kelly_aggressive': 0.26,              # 激进模式×1.5 → 26.3% (现金>95%时)
    'kelly_conservative': 0.09,            # 保守模式×0.25 → 8.75% (现金<70%时)
    'win_rate': 0.60,                      # 胜率 60%
    'avg_win': 0.015,                      # 平均赢 1.5%
    'avg_loss': 0.008,                     # 平均亏 0.8%
    'position_size_limit': 0.08,           # 单仓最多8%
    'description': '基于历史回测数据的Kelly优化'
}

# v5.100: 多层止损设计
STOP_LOSS_V100 = {
    'enabled': True,
    'initial_stops': {                     # 第1层: 初始止损 (距买入价)
        '科技成长': 0.05,                   # 5% (-5%)
        '新能源': 0.04,                     # 4% (-4%)
        '白马消费': 0.03                    # 3% (-3%)
    },
    'trailing_stop_pct': 0.08,             # 第2层: 追踪止损 8% (从高点)
    'time_stops': {                        # 第3层: 时间止损 (持仓天数)
        '科技成长': 25,                     # 25天无利润→考虑止损
        '新能源': 20,                       # 20天
        '白马消费': 30                      # 30天
    },
    'description': '多层递进式止损,保护本金+保留收益'
}

# v5.100: 资金分层配置
# 四层模式: 激进40% + 平衡35% + 保守15% + 现金储备10%
FUND_LAYERING_V100 = {
    'enabled': True,
    'layers': {
        'aggressive': {
            'ratio': 0.40,                  # 基础40% (现金>95%时→50%)
            'min_quality': 25,              # 最低入场质量 25分
            'max_single': 0.08,             # 单仓最多8%
            'strategy': 'MACD+RSI',
            'description': '强技术信号,激进建仓'
        },
        'balanced': {
            'ratio': 0.35,                  # 35%
            'min_quality': 45,              # 最低入场质量 45分
            'max_single': 0.06,             # 单仓最多6%
            'strategy': 'MULTI_FACTOR',
            'description': '基本面+技术面平衡'
        },
        'conservative': {
            'ratio': 0.15,                  # 15%
            'min_quality': 60,              # 最低入场质量 60分
            'max_single': 0.05,             # 单仓最多5%
            'strategy': 'WHITE_HORSE',
            'description': '优质标的,防守为主'
        },
        'cash_reserve': {
            'ratio': 0.10,                  # 10% 现金储备
            'description': '应对突发机会或风险'
        }
    },
    'extreme_mode': {
        'condition': 'cash_ratio > 0.95',
        'allocation': {
            'aggressive': 0.50,             # +10%
            'balanced': 0.30,               # -5%
            'conservative': 0.10,
            'cash_reserve': 0.10
        },
        'description': '现金极多时的激进配置'
    }
}

# v5.100: 入场质量动态评分
ENTRY_QUALITY_V100 = {
    'enabled': True,
    'scoring_weights': {                   # 入场质量权重
        'macd_signal': 0.35,                # MACD信号强度 (35%)
        'rsi_oversold': 0.25,               # RSI超卖程度 (25%)
        'breakout': 0.20,                   # 突破确认 (20%)
        'volume': 0.15,                     # 量能配合 (15%)
        'margin': 0.05                      # 融资融券 (5%)
    },
    'thresholds': {                        # 现金占比 → 质量门槛
        0.95: {
            'MACD+RSI': 20,
            'MULTI_FACTOR': 30,
            'WHITE_HORSE': 40
        },
        0.85: {
            'MACD+RSI': 25,
            'MULTI_FACTOR': 35,
            'WHITE_HORSE': 45
        },
        0.70: {
            'MACD+RSI': 35,
            'MULTI_FACTOR': 45,
            'WHITE_HORSE': 55
        },
        0.00: {
            'MACD+RSI': 45,
            'MULTI_FACTOR': 55,
            'WHITE_HORSE': 65
        }
    },
    'scoring_max': 100,
    'description': '现金越多→阈值越低(更激进)'
}

# v5.100: 选股超时保护
SELECTION_TIMEOUT_V100 = {
    'enabled': True,
    'max_candidates': 60,                  # 最多候选数
    'max_picks': 12,                       # 最多选中数 (从45中选12)
    'safe_pool_sizes': {                   # 超时风险 → 候选池大小
        0.8: 25,                           # 高风险
        0.6: 35,                           # 中高风险
        0.4: 45,                           # 中等风险 (v5.96)
        0.0: 60                            # 低风险
    },
    'timeout_threshold_seconds': 120,      # 选股超时 >120s时触发保护
    'description': '智能降级机制,防止候选池过大导致超时'
}

# v5.100: 预期改进
V5_100_EXPECTED_IMPROVEMENTS = {
    'capital_efficiency': (0.035, 0.25),   # 3.5% → 25%
    'daily_picks': (2, 10),                # 2只 → 10只
    'sharpe_ratio': (2.30, 2.35),          # 保持2.35+
    'win_rate': (0.58, 0.62),              # 58% → 62%
    'max_drawdown': (0.05, 0.04),          # 从5% → 4%
}

# v5.100: 快速参考
V5_100_QUICK_REFERENCE = {
    'MACD参数': '科技成长: 11/26/9, 其他: 12/26/9',
    'Kelly仓位': '17.5% (安全) / 26.3% (激进)',
    '初始止损': '5-3% (按赛道)',
    '追踪止损': '8% (从高点)',
    '时间止损': '20-30天 (按赛道)',
    '资金分层': '激进40% + 平衡35% + 保守15% + 现金10%',
    '入场阈值': '20-45分 (按现金占比)',
    '超时保护': '45候选 → 12选中'
}

if __name__ == '__main__':
    print("✅ v5.100配置附加模块已加载")
    print("\n📊 关键参数:")
    print(f"  Kelly (安全): {KELLY_V100['kelly_half']:.1%}")
    print(f"  初始止损 (科技): {STOP_LOSS_V100['initial_stops']['科技成长']:.1%}")
    print(f"  追踪止损: {STOP_LOSS_V100['trailing_stop_pct']:.1%}")
    print(f"  激进仓配比: {FUND_LAYERING_V100['layers']['aggressive']['ratio']:.0%}")
    print(f"  最低入场质量 (激进): {FUND_LAYERING_V100['layers']['aggressive']['min_quality']}分")
