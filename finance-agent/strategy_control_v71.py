"""v5.71: 策略启用控制 — 禁用低效策略，强化高效策略"""

# =================== v5.71 策略启用状态控制 ===================
# 基于回测数据的策略效果评级，动态启用/禁用策略

STRATEGY_ENABLED = {
    # TOP 3: 启用
    'MACD_RSI': {
        'enabled': True,
        'reason': '17.1% 收益率，2.35 Sharpe (TOP1)',
        'sectors': ['科技成长', '新能源', '主板', '混合池'],
        'boost_multiplier': 1.3,  # +30% 权重加成
    },
    
    'MULTI_FACTOR': {
        'enabled': True,
        'reason': '6.45% 稳定收益，风险管理完善',
        'sectors': ['新能源', '消费白马'],
        'boost_multiplier': 1.0,
    },
    
    'TREND_FOLLOW': {
        'enabled': True,
        'reason': '3.93% 稳定收益，低回撤',
        'sectors': ['消费白马', '新能源'],
        'boost_multiplier': 0.9,
    },
    
    'MA_CROSS': {
        'enabled': True,
        'reason': '5.3% 收益率，可靠性较高',
        'sectors': ['科技成长', '主板'],
        'boost_multiplier': 1.0,
    },
    
    # DISABLED: 低效或亏损策略
    'BOLL_REVERT': {
        'enabled': False,  # 禁用
        'reason': '负收益(-0.2% ~ -1.08%), 低胜率',
        'backtest_results': {
            '科技成长': {'return': 0.0, 'sharpe': 0.0},
            '新能源': {'return': -0.43, 'sharpe': -0.25},
            '消费白马': {'return': -0.2, 'sharpe': -0.15},
            '混合池': {'return': -1.08, 'sharpe': -0.55},
        }
    },
    
    'VOLUME_BREAKOUT': {
        'enabled': False,  # 当前禁用，待优化
        'reason': '回测结果为0(未投入使用)',
        'note': 'v5.72 计划: 添加量价突破核心逻辑后重启',
    },
}

# v5.71: 策略权重调整规则
def get_strategy_weight_multiplier(strategy: str, sector: str = '') -> float:
    """根据策略启用状态和板块获取权重乘数
    
    Args:
        strategy: 策略名称
        sector: 板块名称(可选)
    
    Returns: 权重乘数 (0.0 = 禁用, >1.0 = 加强)
    """
    if strategy not in STRATEGY_ENABLED:
        return 1.0  # 未知策略，保持原权重
    
    config = STRATEGY_ENABLED[strategy]
    
    # 禁用策略: 权重乘以 0
    if not config.get('enabled', False):
        return 0.0
    
    # 启用策略: 基础权重乘数
    base_multiplier = config.get('boost_multiplier', 1.0)
    
    # 如果指定了板块，检查是否在该策略的优先板块中
    if sector and 'sectors' in config:
        if sector in config['sectors']:
            return base_multiplier * 1.15  # +15% 补偿
        else:
            return base_multiplier * 0.8   # -20% 弱化
    
    return base_multiplier


def validate_strategy_in_picker(strategy: str, sector: str = '') -> tuple:
    """检查策略是否应在选股时应用
    
    Returns: (should_apply: bool, reason: str, weight: float)
    """
    if strategy not in STRATEGY_ENABLED:
        return True, 'unknown_strategy', 1.0
    
    config = STRATEGY_ENABLED[strategy]
    
    if not config.get('enabled', False):
        return False, config.get('reason', 'disabled'), 0.0
    
    weight = get_strategy_weight_multiplier(strategy, sector)
    return True, f"{strategy} enabled for {sector or 'all'}", weight


# =================== 性能基准对标 (v5.71) ===================
STRATEGY_PERFORMANCE_BASELINE = {
    'MACD_RSI': {
        'target_return': 0.15,      # 目标 15% 收益率
        'target_sharpe': 2.0,       # 目标 2.0 Sharpe 比率
        'max_drawdown': 0.06,       # 最大回撤 6%
    },
    'MULTI_FACTOR': {
        'target_return': 0.07,
        'target_sharpe': 1.3,
        'max_drawdown': 0.05,
    },
    'TREND_FOLLOW': {
        'target_return': 0.05,
        'target_sharpe': 0.9,
        'max_drawdown': 0.04,
    },
    'MA_CROSS': {
        'target_return': 0.06,
        'target_sharpe': 1.0,
        'max_drawdown': 0.04,
    },
}

# =================== 监控逻辑 (v5.72 待实施) ===================
# 如果实盘效果与回测相差 > 30%, 自动降权或禁用该策略
# 如果某策略连续 5 天无有效信号，自动降权
