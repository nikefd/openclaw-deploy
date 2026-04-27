"""
【v5.64 配置参数更新】
基于深度优化结果的新参数集合
"""

# ============================================================================
# 【v5.64 新增配置】止损/止盈精细化参数
# ============================================================================

# ATR-based动态止损参数 (方向1)
DYNAMIC_STOP_LOSS_ENABLED = True
DYNAMIC_STOP_LOSS_BY_SECTOR = {
    '科技成长': {
        'atr_multiplier': 1.5,      # ATR × 1.5 (高波动)
        'liquidity_penalty': -0.01,  # 低流动性额外-1%
        'take_profit_boost': 0.02,   # 止盈+2% (22%而非20%)
    },
    '新能源': {
        'atr_multiplier': 1.0,
        'liquidity_penalty': -0.01,
        'take_profit_boost': 0.0,
    },
    '白马消费': {
        'atr_multiplier': 0.8,       # ATR × 0.8 (低波动)
        'liquidity_penalty': -0.005,
        'take_profit_boost': 0.0,
    }
}

# 融资杠杆检测阈值 (方向3)
LEVERAGE_DETECTION_ENABLED = True
LEVERAGE_HIGH_THRESHOLD = 500_000_000_000  # 融资余额>5000亿标记为高杠杆
LEVERAGE_AGGRESSIVENESS_PENALTY = -0.10    # 激进度-10%
LEVERAGE_STOP_LOSS_PENALTY = -0.01         # 止损-1% (更严格)

# ============================================================================
# 【v5.64 新增配置】入场点优化参数
# ============================================================================

BEST_ENTRY_TIMING_ENABLED = True
ENTRY_TIMING_BONUSES = {
    'rsi_oversold': 15,          # RSI<30超卖反弹 +15分
    'rsi_low': 8,                # RSI<35低位 +8分
    'macd_golden_cross': 10,     # MACD金叉 +10分
    'volume_confirm': 8,         # 成交量>5日均×120% +8分
    'high_position_penalty': -5, # 高位(>MA20×120%) -5分
}

# ============================================================================
# 【v5.64 新增配置】风控增强参数
# ============================================================================

# 持仓数限制 (方向3)
POSITION_COUNT_LIMITS = {
    'ultra_high_cash': 20,  # 超激进模式最多20只 (防过度分散)
    'high_cash': 15,
    'normal': 10
}

# 单只头寸上限 (方向3)
SINGLE_POSITION_LIMIT_PCT = 0.10  # 不超过总资金10%

# 赛道相关性检测 (方向3)
SECTOR_CORRELATION_CHECK_ENABLED = True
SECTOR_MAX_HOLDINGS = {
    '科技成长': 3,      # 同赛道最多3只 (防同向坍塌)
    '新能源': 3,
    '白马消费': 2,
    '其他': 3
}

# 相关性阈值 (>0.70认为高度相关)
CORRELATION_THRESHOLD = 0.70

# ============================================================================
# 【v5.64 新增配置】赛道权重微调参数
# ============================================================================

# 基于Sharpe和30天胜率的赛道权重 (方向4)
SECTOR_WEIGHT_DYNAMIC = {
    '科技成长': {
        'base_weight': 1.0,         # Sharpe 2.35最高 → 基础权重1.0
        'sharpe': 2.35,
        'winrate_threshold_high': 0.60,     # 胜率>60% → 1.2x
        'winrate_threshold_medium': 0.50,   # 胜率50-60% → 1.0x
        'winrate_threshold_low': 0.40,      # 胜率<40% → 0.5x
    },
    '新能源': {
        'base_weight': 0.80,        # Sharpe 1.78 → 权重降20%
        'sharpe': 1.78,
        'winrate_threshold_high': 0.60,
        'winrate_threshold_medium': 0.50,
        'winrate_threshold_low': 0.40,
    },
    '白马消费': {
        'base_weight': 0.70,        # Sharpe <1.0 → 权重降30%
        'sharpe': 0.85,
        'winrate_threshold_high': 0.60,
        'winrate_threshold_medium': 0.50,
        'winrate_threshold_low': 0.40,
    }
}

# 反向权重应用 (胜率<40% → -50%)
SECTOR_WEIGHT_REVERSE_PENALTY = 0.50  # 权重打5折

# ============================================================================
# 【预期效果】v5.64 优化目标
# ============================================================================

EXPECTED_IMPROVEMENTS_V5_64 = {
    '1. 止损更智能': {
        'metric': '最大回撤',
        'before': '4.08%',
        'after': '3.2%',
        'improvement': '-20%',
        'driver': 'ATR-based动态止损 + 赛道差异化'
    },
    '2. 入场更精准': {
        'metric': '成功率',
        'before': '60%',
        'after': '65%',
        'improvement': '+5%',
        'driver': 'RSI超卖检测 + MACD金叉时机 + 高位避免'
    },
    '3. 风控更强': {
        'metric': '持仓集中度 & 回撤',
        'before': '5只/4.08%',
        'after': '15-20只/3.0%',
        'improvement': '分散+降回撤',
        'driver': '持仓数限制 + 相关性检测 + 融资识别'
    },
    '4. 赛道权重优化': {
        'metric': 'Sharpe稳定性',
        'before': '2.35 (主要靠TOP1)',
        'after': '2.35+ (多赛道配合)',
        'improvement': '收益更稳定',
        'driver': '基于实际胜率动态调整赛道权重'
    }
}

# ============================================================================
# 【集成指南】如何在stock_picker.py中调用新函数
# ============================================================================

"""
# 在 stock_picker.py 的 score_and_rank() 中添加:

from v5_64_deep_optimize_functions import (
    dynamic_stop_loss_by_sector,
    best_entry_timing_check,
    position_correlation_check,
    leverage_market_detection,
    position_size_limit_check,
    sector_weight_by_winrate
)

# 示例集成点 (在rank排序后，应用这些优化)

# ===== 点1: 赛道权重微调 (方向4) =====
sector_weights = sector_weight_by_winrate()  # 获取动态权重
for stock in ranked:
    sector = stock.get('sector', '科技成长')
    weight_info = sector_weights.get(sector, {})
    final_weight = weight_info.get('final_weight', 1.0)
    stock['score'] = int(stock['score'] * final_weight)
    stock['_sector_weight_v64'] = final_weight

# ===== 点2: 市场杠杆检测 (方向3) =====
leverage = leverage_market_detection()
if leverage['leverage_level'] == 'HIGH':
    # 整体激进度下调10%
    for stock in ranked:
        stock['score'] = int(stock['score'] * 0.90)

# ===== 点3: 头寸限制检查 (方向3) =====
for stock in ranked:
    size_check = position_size_limit_check(
        total_capital=1_000_000,
        existing_positions=current_holdings,
        new_position_size=stock['position_size'],
        num_positions=len(current_holdings)
    )
    if not size_check['can_add']:
        stock['score'] = 0  # 禁止加仓

# ===== 点4: 相关性检测 (方向3) =====
for stock in ranked:
    corr_check = position_correlation_check(
        holdings=current_holdings,
        new_candidate=stock
    )
    if corr_check['risk_level'] == 'HIGH':
        stock['score'] = int(stock['score'] * 0.5)  # 风险高 -50%

# ===== 点5: 入场时机优化 (方向2) =====
for stock in ranked:
    timing = best_entry_timing_check(stock['code'], {...})
    stock['score'] += timing['entry_score_bonus']
    stock['_entry_timing'] = timing['entry_timing']

"""

# ============================================================================
# 【兼容性保障】向后兼容措施
# ============================================================================

# 所有新配置都有默认值，旧代码无需修改
# 新逻辑使用 try-except 保护
BACKWARD_COMPATIBILITY_MODE = True

# v5.64优化可关闭开关 (便于回滚)
V5_64_OPTIMIZATIONS_ENABLED = {
    'dynamic_stop_loss': True,
    'entry_timing_check': True,
    'position_correlation': True,
    'leverage_detection': True,
    'sector_weight_dynamic': True
}
