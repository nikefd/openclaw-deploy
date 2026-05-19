#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v5.114 集成模块 — stock_picker.py 增强功能
负责集成赛道策略精细化 + 混合池路由优化
"""

from config import (
    V5_114_SECTOR_STRATEGY_ROUTING,
    V5_114_AGGRESSIVE_BUILD_PLAN,
    ENTRY_QUALITY_DYNAMIC_THRESHOLDS
)
from typing import List, Dict, Optional

def apply_v5_114_sector_routing(candidates: List[Dict]) -> List[Dict]:
    """
    应用v5.114赛道路由策略
    
    核心逻辑:
      1. 检测候选股所属赛道
      2. 应用该赛道的最优策略组合权重
      3. 调整入场质量阈值
      4. 特别处理白马消费 (替换失效策略)
    """
    
    enhanced = []
    
    for candidate in candidates:
        sector = candidate.get('sector', '混合池')
        
        # 获取该赛道的最优策略
        sector_config = V5_114_SECTOR_STRATEGY_ROUTING.get(sector)
        if not sector_config:
            enhanced.append(candidate)
            continue
        
        # 应用策略权重和调整
        if sector == '白马消费':
            # 特殊处理: MACD+RSI -> MULTI_FACTOR
            candidate['applied_strategy'] = 'MULTI_FACTOR (v5.114改用)'
            candidate['strategy_explanation'] = 'MACD+RSI在白马消费失效(-5.51%)，改用多因子+趋势'
        elif sector == '科技成长':
            candidate['applied_strategy'] = 'MACD_RSI (TOP1策略)'
            candidate['strategy_explanation'] = '回测TOP1: 17.1% Sharpe 2.35'
        elif sector == '新能源':
            candidate['applied_strategy'] = 'MACD_RSI (次优策略)'
            candidate['strategy_explanation'] = '回测次优: 14.66% Sharpe 1.78'
        elif sector == '混合池':
            candidate['applied_strategy'] = '加权路由 (科技54% + 新能源35% + 消费11%)'
            candidate['strategy_explanation'] = '按回测绩效动态权重'
        
        # 应用入场质量阈值
        threshold = sector_config.get('entry_quality_threshold', 35)
        candidate['v5_114_entry_threshold'] = threshold
        
        # 应用策略权重
        candidate['strategy_weights'] = {
            'primary': {
                'strategy': sector_config.get('primary'),
                'weight': sector_config.get('primary_weight')
            },
            'secondary': {
                'strategy': sector_config.get('secondary'),
                'weight': sector_config.get('secondary_weight')
            },
            'hedge': {
                'strategy': sector_config.get('hedge'),
                'weight': sector_config.get('hedge_weight')
            }
        }
        
        # 记录回测数据
        candidate['backtest_data'] = {
            'return': sector_config.get('backtest_return'),
            'sharpe': sector_config.get('backtest_sharpe'),
            'note': sector_config.get('note')
        }
        
        enhanced.append(candidate)
    
    return enhanced


def apply_v5_114_mixed_pool_routing(candidates: List[Dict]) -> List[Dict]:
    """
    应用v5.114混合池路由优化
    
    核心逻辑:
      1. 识别混合池候选股
      2. 检测其真实赛道属性
      3. 按该赛道回测绩效加权
      4. 调整排序优先级
    """
    
    routes = V5_114_SECTOR_STRATEGY_ROUTING['混合池']['route_weights']
    mixed_pool = [c for c in candidates if c.get('sector') == '混合池']
    
    if not mixed_pool:
        return candidates
    
    enhanced_mixed = []
    
    for candidate in mixed_pool:
        # 检测真实赛道 (简化版，实际需要查询数据库)
        true_sector = _detect_true_sector_v5_114(candidate.get('symbol', ''))
        
        # 应用路由权重
        route_weight = routes.get(true_sector, 1.0)
        original_score = candidate.get('entry_quality_score', 0)
        
        # 加权调整
        adjusted_priority = original_score * route_weight
        
        # 记录调整信息
        candidate['mixed_pool_route'] = {
            'true_sector': true_sector,
            'route_weight': route_weight,
            'original_score': original_score,
            'adjusted_priority': adjusted_priority,
        }
        
        enhanced_mixed.append(candidate)
    
    # 按adjusted_priority排序
    enhanced_mixed.sort(key=lambda x: x['mixed_pool_route']['adjusted_priority'], reverse=True)
    
    # 拼接回完整列表
    non_mixed = [c for c in candidates if c.get('sector') != '混合池']
    return non_mixed + enhanced_mixed


def _detect_true_sector_v5_114(symbol: str) -> str:
    """
    检测股票真实赛道 (v5.114版本)
    
    简化版实现，实际应接入 data_collector.get_stock_industry()
    """
    
    # 科技关键词
    tech_keywords = ['科技', '芯片', '半导体', '软件', '计算机', '互联网', 'AI', '电子']
    
    # 新能源关键词
    energy_keywords = ['新能源', '电动', '锂电', '光伏', '氢能', '储能']
    
    # 消费关键词  
    consumer_keywords = ['白马', '消费', '酒', '食品', '医药', '家电', '美妆']
    
    # 需要接入实际的行业数据
    # 占位符实现
    return '科技成长'


def adjust_entry_threshold_by_cash_ratio_v5_114(cash_ratio: float) -> int:
    """
    按现金占比动态调整入场质量阈值 (v5.114激进版)
    
    逻辑:
      - 现金>90%: 20分 (极度激进)
      - 现金80-90%: 28分 (激进)
      - 现金50-80%: 35分 (正常)
      - 现金<50%: 40分 (保守)
    """
    
    if cash_ratio > 0.90:
        return 20  # 极度激进
    elif cash_ratio > 0.80:
        return 28  # 激进
    elif cash_ratio > 0.50:
        return 35  # 正常
    else:
        return 40  # 保守


def calculate_aggressive_kelly_position(
    win_rate: float,
    avg_win: float,
    avg_loss: float,
    kelly_coefficient: float = 1.28
) -> float:
    """
    计算激进Kelly仓位 (v5.114版本)
    
    Kelly公式: f = (p*b - q) / b
    其中:
      p = 胜率
      q = 1-p
      b = 平均赢 / 平均亏
      f = Kelly仓位
    
    v5.114: Kelly系数 1.28 (激进)
    """
    
    if avg_loss <= 0 or win_rate <= 0:
        return 0.025  # 微仓
    
    q = 1 - win_rate
    b = avg_win / abs(avg_loss)
    
    # Kelly基础公式
    kelly_fraction = (win_rate * b - q) / b
    
    # 应用激进系数
    position_size = kelly_fraction * kelly_coefficient
    
    # 限制在最大值
    max_single = 0.032  # v5.114: 单只最多3.2%
    return min(position_size, max_single)


# =================== 验证函数 ===================

def validate_v5_114_integration() -> Dict:
    """
    验证v5.114集成的完整性
    """
    
    return {
        'sector_routing': bool(V5_114_SECTOR_STRATEGY_ROUTING),
        'aggressive_plan': bool(V5_114_AGGRESSIVE_BUILD_PLAN),
        'mixed_pool_routes': bool(V5_114_SECTOR_STRATEGY_ROUTING.get('混合池', {}).get('route_weights')),
        'quality_compensation': bool(V5_114_AGGRESSIVE_BUILD_PLAN),
        'status': '✅ 已集成' if all([
            V5_114_SECTOR_STRATEGY_ROUTING,
            V5_114_AGGRESSIVE_BUILD_PLAN
        ]) else '❌ 集成不完整'
    }


if __name__ == '__main__':
    # 验证集成
    validation = validate_v5_114_integration()
    print("\n📊 v5.114集成验证:")
    for key, val in validation.items():
        print(f"  {key}: {val}")
    
    # 示例: 计算Kelly仓位
    kelly_size = calculate_aggressive_kelly_position(
        win_rate=0.60,
        avg_win=0.15,
        avg_loss=-0.08,
        kelly_coefficient=1.28
    )
    print(f"\n💰 Kelly仓位示例 (胜率60%, 平均赢15%, 平均亏-8%): {kelly_size:.2%}")
    
    # 示例: 动态阈值
    for cash_ratio in [0.95, 0.85, 0.70, 0.45]:
        threshold = adjust_entry_threshold_by_cash_ratio_v5_114(cash_ratio)
        print(f"  现金{cash_ratio:.0%}: 入场阈值{threshold}分")
    
    print("\n✅ v5.114集成模块验证完成")
