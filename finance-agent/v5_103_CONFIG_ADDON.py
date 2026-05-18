"""v5.103 配置集成模块 — 将深度融合引擎参数集成到config.py"""

# ================================================================================
# v5.103: 新增Kelly凯利配置参数
# ================================================================================

# Kelly凯利仓位配置 (基于MACD+RSI回测数据: 60%胜率)
KELLY_CONFIG_V103 = {
    'enabled': True,
    'win_rate': 0.60,              # 胜率 (来自MACD+RSI回测)
    'avg_win_pct': 0.015,          # 平均赢1.5%
    'avg_loss_pct': 0.008,         # 平均亏0.8%
    'kelly_full': 0.30,            # 完整Kelly比例 (理论值)
    'kelly_conservative': 0.15,    # 保守Kelly (Kelly/2)
    'kelly_max_position_pct': 0.08, # 单仓最大8%
    'kelly_min_position_pct': 0.02, # 单仓最小2%
    'deployment_modes': {
        'aggressive': {
            'kelly_multiplier': 1.5,
            'target_positions': 12,
            'cash_trigger': 0.95,
            'description': '激进模式: 高现金+快速建仓'
        },
        'balanced': {
            'kelly_multiplier': 1.0,
            'target_positions': 8,
            'cash_trigger': 0.80,
            'description': '平衡模式: 正常操作'
        },
        'conservative': {
            'kelly_multiplier': 0.5,
            'target_positions': 5,
            'cash_trigger': 0.20,
            'description': '保守模式: 低现金或高风险'
        }
    }
}

# ================================================================================
# v5.103: 多层风险分级配置
# ================================================================================

RISK_ALLOCATION_V103 = {
    'aggressive': {
        'description': '激进配置 (现金>95%, 快速建仓)',
        'defensive': 0.15,     # 消费白马/医药 (稳定器)
        'offensive': 0.55,     # 科技成长/新能源 (获利主力)
        'tactical': 0.15,      # 低位补涨
        'cash': 0.15,          # 保留现金
        'trigger_condition': 'cash_ratio > 0.95 and market_regime != "bear"'
    },
    'balanced': {
        'description': '平衡配置 (正常操作)',
        'defensive': 0.25,
        'offensive': 0.45,
        'tactical': 0.15,
        'cash': 0.15,
        'trigger_condition': 'default mode'
    },
    'conservative': {
        'description': '保守配置 (市场风险高或现金<20%)',
        'defensive': 0.40,
        'offensive': 0.25,
        'tactical': 0.10,
        'cash': 0.25,
        'trigger_condition': 'cash_ratio < 0.20 or market_regime == "bear"'
    },
    'crisis': {
        'description': '危机配置 (大幅下跌或极端风险)',
        'defensive': 0.50,
        'offensive': 0.10,
        'tactical': 0.05,
        'cash': 0.35,
        'trigger_condition': 'max_drawdown < -0.10 or market_regime == "crisis"'
    }
}

# ================================================================================
# v5.103: 赛道级MACD参数差异化 (基于回测TOP1数据)
# ================================================================================

MACD_PARAMS_SECTOR_V103 = {
    '科技成长': {
        'macd_fast': 11,           # 优化参数
        'macd_slow': 26,
        'macd_signal': 9,
        'rsi_period': 13,          # 更敏感
        'rsi_oversold': 28,        # 更激进的超卖
        'rsi_overbought': 72,      # 减少误杀
        'macd_threshold': 0.0015,  # DIF-DEF差值阈值
        'entry_score_boost': 3.5,  # 入场评分加成
        'expected_return': 17.1,
        'expected_sharpe': 2.35,
        'expected_drawdown': 4.08,
        'confidence': 'VERY_HIGH',
        'description': 'TOP1 from backtest'
    },
    '新能源': {
        'macd_fast': 12,
        'macd_slow': 26,
        'macd_signal': 9,
        'rsi_period': 14,
        'rsi_oversold': 30,
        'rsi_overbought': 70,
        'macd_threshold': 0.002,
        'entry_score_boost': 2.8,
        'expected_return': 14.66,
        'expected_sharpe': 1.78,
        'expected_drawdown': 6.93,
        'confidence': 'HIGH',
        'description': 'TOP2 from backtest'
    },
    '白马消费': {
        'macd_fast': 12,
        'macd_slow': 28,           # 更长周期,防噪声
        'macd_signal': 10,
        'rsi_period': 15,
        'rsi_oversold': 35,        # 更高阈值,更保守
        'rsi_overbought': 68,
        'macd_threshold': 0.003,
        'entry_score_boost': 2.5,
        'expected_return': 8.0,
        'expected_sharpe': 1.4,
        'expected_drawdown': 5.0,
        'confidence': 'MEDIUM',
        'description': 'Conservative sector params'
    },
    '混合池': {
        'macd_fast': 12,
        'macd_slow': 26,
        'macd_signal': 9,
        'rsi_period': 14,
        'rsi_oversold': 30,
        'rsi_overbought': 70,
        'macd_threshold': 0.0025,
        'entry_score_boost': 2.8,
        'expected_return': 12.0,
        'expected_sharpe': 1.8,
        'expected_drawdown': 5.5,
        'confidence': 'MEDIUM_HIGH',
        'description': 'Mixed pool fallback params'
    }
}

# ================================================================================
# v5.103: 动态入场质量阈值 (现金占比联动)
# ================================================================================

ENTRY_QUALITY_DYNAMIC_V103 = {
    'thresholds': {
        'normal': 65,            # 正常: ≥65分 (严格标准)
        'high_cash': 55,         # 现金75-95%: ≥55分 (放宽10分)
        'extreme_cash': 45,      # 现金>95%: ≥45分 (放宽20分,激进建仓)
        'crisis': 75             # 危机: ≥75分 (超严格)
    },
    'trigger_conditions': {
        'normal': 'cash_ratio <= 0.75 and max_drawdown > -0.10',
        'high_cash': '0.75 < cash_ratio <= 0.95',
        'extreme_cash': 'cash_ratio > 0.95 and market_regime != "bear"',
        'crisis': 'max_drawdown < -0.10 or market_regime == "crisis"'
    },
    'allowed_entry_categories': {
        'extreme_cash': ['底部挖掘', '成长性个股', '低位补涨', '机构关注'],
        'high_cash': ['优质成长股', '低位补涨', '主力参与', '机构支持'],
        'normal': ['确认趋势', '主力参与', '机构支持', '量价配合'],
        'crisis': ['龙头品种', '机构持股', '防守反弹', '安全边际>30%']
    }
}

# ================================================================================
# v5.103: 选股超时防护配置
# ================================================================================

STOCK_PICKING_TIMEOUT_V103 = {
    'modes': {
        'ultra_fast': {
            'candidates_limit': 20,
            'timeout_seconds': 5,
            'trigger': 'cash_ratio > 0.95 and current_positions < 3',
            'filtering_aggressiveness': 'aggressive',
            'estimated_completion_ms': 1000,
            'description': '超快速模式: 极高现金'
        },
        'fast': {
            'candidates_limit': 40,
            'timeout_seconds': 12,
            'trigger': 'cash_ratio > 0.90 and current_positions < 5',
            'filtering_aggressiveness': 'normal',
            'estimated_completion_ms': 1500,
            'description': '快速模式: 激进建仓'
        },
        'normal': {
            'candidates_limit': 100,
            'timeout_seconds': 45,
            'trigger': 'default',
            'filtering_aggressiveness': 'normal',
            'estimated_completion_ms': 3000,
            'description': '正常模式'
        }
    }
}

# ================================================================================
# v5.103: 赛道权重 (基于Sharpe比率)
# ================================================================================

SECTOR_WEIGHTS_FROM_BACKTEST_V103 = {
    '科技成长': 0.621,      # Sharpe 2.35权重占比最高
    '新能源': 0.379,        # Sharpe 1.78权重次之
    '白马消费': 0.0,        # 不在TOP回测中,用多因子替代
    '混合池': 0.0           # 用通用参数
}

# ================================================================================
# v5.103: 赛道策略路由 (基于回测最优表现)
# ================================================================================

SECTOR_STRATEGIES_V103 = {
    '科技成长': {
        'primary_strategy': 'MACD_RSI',
        'primary_weight': 0.70,
        'secondary_strategy': 'MULTI_FACTOR',
        'secondary_weight': 0.20,
        'hedge_strategy': 'MA_CROSS',
        'hedge_weight': 0.10,
        'expected_return': 17.1,
        'expected_sharpe': 2.35,
        'expected_drawdown': 4.08,
        'confidence_level': 'VERY_HIGH'
    },
    '新能源': {
        'primary_strategy': 'MACD_RSI',
        'primary_weight': 0.65,
        'secondary_strategy': 'MULTI_FACTOR',
        'secondary_weight': 0.25,
        'hedge_strategy': 'TREND_FOLLOW',
        'hedge_weight': 0.10,
        'expected_return': 14.66,
        'expected_sharpe': 1.78,
        'expected_drawdown': 6.93,
        'confidence_level': 'HIGH'
    },
    '白马消费': {
        'primary_strategy': 'MULTI_FACTOR',
        'primary_weight': 0.50,
        'secondary_strategy': 'TREND_FOLLOW',
        'secondary_weight': 0.30,
        'hedge_strategy': 'MA_CROSS',
        'hedge_weight': 0.20,
        'expected_return': 8.0,
        'expected_sharpe': 1.4,
        'expected_drawdown': 5.0,
        'confidence_level': 'MEDIUM'
    },
    '混合池': {
        'primary_strategy': 'MACD_RSI',
        'primary_weight': 0.60,
        'secondary_strategy': 'MULTI_FACTOR',
        'secondary_weight': 0.25,
        'hedge_strategy': 'MA_CROSS',
        'hedge_weight': 0.15,
        'expected_return': 12.0,
        'expected_sharpe': 1.8,
        'expected_drawdown': 5.5,
        'confidence_level': 'MEDIUM_HIGH'
    }
}

# ================================================================================
# v5.103: 启用标志
# ================================================================================

V5_103_ENABLED = True                           # 启用v5.103优化
KELLY_POSITION_SIZING_ENABLED = True            # 启用Kelly仓位
MULTI_LAYER_RISK_ALLOCATION_ENABLED = True      # 启用多层风险分级
SECTOR_STRATEGY_ROUTING_ENABLED = True          # 启用赛道策略路由
DYNAMIC_ENTRY_QUALITY_ENABLED = True            # 启用动态入场阈值
STOCK_PICKING_TIMEOUT_PROTECTION_ENABLED = True # 启用超时防护

# ================================================================================
# v5.103: 优化参数预期
# ================================================================================

V5_103_EXPECTED_IMPROVEMENTS = {
    'capital_utilization': {
        'before': '3.4%',
        'after': '25-30%',
        'improvement_factor': '8倍'
    },
    'positions_count': {
        'before': '2-3只',
        'after': '8-12只',
        'improvement_pct': '+300-500%'
    },
    'sharpe_ratio': {
        'before': '≈2.30',
        'after': '≥2.35',
        'status': '保持/改善'
    },
    'annual_return': {
        'before': '~10-15%',
        'after': '17%+',
        'improvement_pct': '+15-70%'
    },
    'max_drawdown': {
        'before': '4-6%',
        'after': '4-5%',
        'status': '控制/改善'
    },
    'selection_timeout': {
        'before': '45秒',
        'after': '1.5秒 (快速模式)',
        'reliability': '99%+一致性'
    }
}
