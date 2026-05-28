#!/usr/bin/env python3
"""
v5.138 Phase 2-3: 小盘股适配 + 多级止盈策略实现
优化目标:
  - 东方证券(600958): 9.23 → 多级止盈, 锁定更多收益
  - 华映科技(000536): 4.26 → 动态止损, 避免虚假止损
"""

import json
from datetime import datetime

# =================== Phase 2: 市值分层函数 ===================

PHASE_2_CODE = '''
# v5.138 Phase 2: 市值分层的参数自适应

def get_market_cap_tier(stock_market_cap_yuan):
    """
    根据市值确定参数等级
    
    参数:
        stock_market_cap_yuan: 股票总市值(元)
    
    返回:
        'large_cap' | 'mid_cap' | 'small_cap'
    """
    # 转换为亿元
    market_cap_billion = stock_market_cap_yuan / 1_000_000_000
    
    if market_cap_billion >= 2000:
        return 'large_cap'
    elif market_cap_billion >= 500:
        return 'mid_cap'
    else:
        return 'small_cap'

def get_adaptive_macd_params(stock_market_cap_yuan, base_params=None):
    """
    根据市值返回自适应的MACD参数
    
    例:
        蓝筹: (12, 26, 9)   - 平稳, 信号稳定
        中盘: (9, 21, 7)    - 敏感, 科技成长
        小盘: (7, 17, 5)    - 快速, 新能源/创新
    """
    from config import MACD_PARAMS_BY_MARKET_CAP
    
    tier = get_market_cap_tier(stock_market_cap_yuan)
    return MACD_PARAMS_BY_MARKET_CAP.get(tier, MACD_PARAMS_BY_MARKET_CAP['mid_cap'])

def get_adaptive_rsi_period(stock_market_cap_yuan):
    """
    根据市值返回自适应的RSI周期
    """
    from config import RSI_PERIOD_BY_MARKET_CAP
    
    tier = get_market_cap_tier(stock_market_cap_yuan)
    return RSI_PERIOD_BY_MARKET_CAP.get(tier, 12)

def calculate_adaptive_signals(symbol, price_series, volume_series, market_cap):
    """
    使用自适应参数计算MACD+RSI信号
    
    参数:
        symbol: 股票代码
        price_series: 价格序列 (numpy array)
        volume_series: 成交量序列
        market_cap: 市值(元)
    
    返回:
        {
            'macd': {...},
            'rsi': {...},
            'tier': 'large_cap' | 'mid_cap' | 'small_cap',
            'adapted_params': {...}
        }
    """
    import numpy as np
    from ta.momentum import macd, rsi
    
    tier = get_market_cap_tier(market_cap)
    macd_params = get_adaptive_macd_params(market_cap)
    rsi_period = get_adaptive_rsi_period(market_cap)
    
    # 计算MACD
    macd_line = macd(
        close=price_series,
        window_fast=macd_params['fast'],
        window_slow=macd_params['slow'],
        window_sign=macd_params['signal']
    )
    
    # 计算RSI
    rsi_line = rsi(price_series, window=rsi_period)
    
    return {
        'symbol': symbol,
        'tier': tier,
        'macd_params': macd_params,
        'rsi_period': rsi_period,
        'macd': {
            'value': macd_line.iloc[-1],
            'signal': macd_line.iloc[-1],  # 简化版
        },
        'rsi': {
            'value': rsi_line.iloc[-1],
            'oversold': rsi_line.iloc[-1] < 30,
            'overbought': rsi_line.iloc[-1] > 70
        }
    }

# 测试案例
if __name__ == '__main__':
    # 东方证券: 600958, 市值约180亿 (mid_cap)
    cap_east_securities = 180_000_000_000
    print(f"东方证券(600958): {get_market_cap_tier(cap_east_securities)}")
    print(f"  MACD参数: {get_adaptive_macd_params(cap_east_securities)}")
    print(f"  RSI周期: {get_adaptive_rsi_period(cap_east_securities)}")
    
    # 华映科技: 000536, 市值约20亿 (small_cap)
    cap_huaying = 20_000_000_000
    print(f"\\n华映科技(000536): {get_market_cap_tier(cap_huaying)}")
    print(f"  MACD参数: {get_adaptive_macd_params(cap_huaying)}")
    print(f"  RSI周期: {get_adaptive_rsi_period(cap_huaying)}")
'''

# =================== Phase 3: 多级止盈函数 ===================

PHASE_3_CODE = '''
# v5.138 Phase 3: 多级止盈策略 (Scaled Exit)

from dataclasses import dataclass
from typing import List, Dict
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class ExitPhase(Enum):
    PHASE_1 = "phase_1"  # 3%收益 卖17%
    PHASE_2 = "phase_2"  # 8%收益 卖33%
    PHASE_3 = "phase_3"  # 15%收益 卖25%
    HOLD = "hold"        # 持有25%

@dataclass
class ScaledExitConfig:
    """多级止盈配置"""
    phase_1_profit: float = 0.03    # 3%
    phase_1_qty: float = 0.17       # 卖17%
    phase_2_profit: float = 0.08    # 8%
    phase_2_qty: float = 0.33       # 卖33%
    phase_3_profit: float = 0.15    # 15%
    phase_3_qty: float = 0.25       # 卖25%
    hold_qty: float = 0.25          # 持有25%

class Position:
    def __init__(self, symbol, entry_price, qty, entry_date):
        self.symbol = symbol
        self.entry_price = entry_price
        self.qty = qty
        self.entry_date = entry_date
        self.sold_qty = 0  # 已卖出数量
        self.realized_profit = 0  # 已实现收益
        self.exit_phases_completed = set()

def execute_scaled_exit(position: Position, current_price: float, config: ScaledExitConfig = None):
    """
    执行多级止盈策略
    
    参数:
        position: 持仓对象
        current_price: 当前价格
        config: 止盈配置
    
    返回:
        {
            'exit_signal': True/False,
            'exit_qty': 卖出数量,
            'exit_phase': 'phase_1'|'phase_2'|'phase_3'|'hold',
            'profit_pct': 当前收益率,
            'realized_profit': 已实现收益,
            'remaining_qty': 剩余持仓
        }
    """
    if config is None:
        config = ScaledExitConfig()
    
    # 计算收益率
    profit_pct = (current_price - position.entry_price) / position.entry_price
    current_qty = position.qty - position.sold_qty
    
    result = {
        'exit_signal': False,
        'exit_qty': 0,
        'exit_phase': None,
        'profit_pct': profit_pct,
        'realized_profit': position.realized_profit,
        'remaining_qty': current_qty
    }
    
    # Phase 1: 3% → 卖17%
    if (profit_pct >= config.phase_1_profit and 
        ExitPhase.PHASE_1 not in position.exit_phases_completed):
        
        exit_qty = int(position.qty * config.phase_1_qty)
        profit = exit_qty * (current_price - position.entry_price)
        
        position.sold_qty += exit_qty
        position.realized_profit += profit
        position.exit_phases_completed.add(ExitPhase.PHASE_1)
        
        result['exit_signal'] = True
        result['exit_qty'] = exit_qty
        result['exit_phase'] = 'phase_1'
        result['realized_profit'] = position.realized_profit
        result['remaining_qty'] = position.qty - position.sold_qty
        
        logger.info(f"{position.symbol}: Phase 1 止盈 | 卖出{exit_qty}股 @ ¥{current_price:.2f} | "
                   f"收益¥{profit:.0f} | 剩余{result['remaining_qty']}股")
        return result
    
    # Phase 2: 8% → 卖33%
    if (profit_pct >= config.phase_2_profit and 
        ExitPhase.PHASE_2 not in position.exit_phases_completed):
        
        exit_qty = int((position.qty - position.sold_qty) * (config.phase_2_qty / (1 - config.phase_1_qty)))
        profit = exit_qty * (current_price - position.entry_price)
        
        position.sold_qty += exit_qty
        position.realized_profit += profit
        position.exit_phases_completed.add(ExitPhase.PHASE_2)
        
        result['exit_signal'] = True
        result['exit_qty'] = exit_qty
        result['exit_phase'] = 'phase_2'
        result['realized_profit'] = position.realized_profit
        result['remaining_qty'] = position.qty - position.sold_qty
        
        logger.info(f"{position.symbol}: Phase 2 止盈 | 卖出{exit_qty}股 @ ¥{current_price:.2f} | "
                   f"收益¥{profit:.0f} | 剩余{result['remaining_qty']}股")
        return result
    
    # Phase 3: 15% → 卖25%
    if (profit_pct >= config.phase_3_profit and 
        ExitPhase.PHASE_3 not in position.exit_phases_completed):
        
        exit_qty = int((position.qty - position.sold_qty) * (config.phase_3_qty / (1 - config.phase_1_qty - config.phase_2_qty)))
        profit = exit_qty * (current_price - position.entry_price)
        
        position.sold_qty += exit_qty
        position.realized_profit += profit
        position.exit_phases_completed.add(ExitPhase.PHASE_3)
        
        result['exit_signal'] = True
        result['exit_qty'] = exit_qty
        result['exit_phase'] = 'phase_3'
        result['realized_profit'] = position.realized_profit
        result['remaining_qty'] = position.qty - position.sold_qty
        
        logger.info(f"{position.symbol}: Phase 3 止盈 | 卖出{exit_qty}股 @ ¥{current_price:.2f} | "
                   f"收益¥{profit:.0f} | 剩余{result['remaining_qty']}股")
        return result
    
    # Hold: 继续持有25%
    result['exit_phase'] = 'hold'
    return result

# 测试案例: 东方证券 (600958)
if __name__ == '__main__':
    # 初始持仓: 600股 @ 9.23元
    pos = Position(
        symbol='600958',
        entry_price=9.23,
        qty=600,
        entry_date='2026-05-28'
    )
    
    # 模拟价格变化
    prices = [9.35, 9.50, 10.00, 10.50, 11.00, 11.50]
    
    print(f"东方证券(600958) 多级止盈测试")
    print(f"初始持仓: 600股 @ ¥9.23\\n")
    
    for price in prices:
        result = execute_scaled_exit(pos, price)
        print(f"当前价格: ¥{price:.2f} | 收益率: {result['profit_pct']*100:.2f}% | "
              f"出场: {result['exit_phase']} | 已止盈: ¥{result['realized_profit']:.0f} | "
              f"剩余: {result['remaining_qty']}股")
'''

# =================== Phase 4: 资金面增强 ===================

PHASE_4_CODE = '''
# v5.138 Phase 4: 龙虎榜缺失补偿 + 资金面增强

def calculate_volume_signal(symbol, volume_series, volume_ma5):
    """
    成交量突增信号 (0-25分)
    
    条件:
        - 当日成交量 > 日均(5天) × 1.5
        - 返回20分 (基础) + 额外5分 (如果 > 2倍)
    """
    current_vol = volume_series[-1]
    threshold = volume_ma5 * 1.5
    
    if current_vol < threshold:
        return 0
    
    # 基础分: 20分
    score = 20
    
    # 额外分: 成交量越大越多
    if current_vol > volume_ma5 * 2.0:
        score += 5
    
    return min(score, 25)

def calculate_institutional_signal(large_order_count, avg_order_size):
    """
    机构参与信号 (0-20分)
    
    条件:
        - 单日大单数(>100万) 多于往日平均 × 1.2
        - 返回15分 (基础) + 额外5分 (如果异常活跃)
    """
    # 简化版: 假设large_order_count为当日大单数
    threshold = avg_order_size * 1.2
    
    if large_order_count < threshold:
        return 0
    
    score = 15
    if large_order_count > avg_order_size * 1.5:
        score += 5
    
    return min(score, 20)

def calculate_margin_signal(margin_balance_change_pct):
    """
    融资净买入信号 (0-5分)
    
    条件:
        - 融资余额日增 > 3%
        - 返回5分
    """
    if margin_balance_change_pct >= 0.03:
        return 5
    elif margin_balance_change_pct >= 0.01:
        return 3
    return 0

def calculate_enhanced_funding_score(symbol, volume_data, order_data, margin_data):
    """
    增强的资金面评分 (0-100)
    
    = 基础50分 (无龙虎榜时) 
      + 成交量突增(0-25)
      + 机构参与(0-20)
      + 融资净买(0-5)
    
    龙虎榜有数据时, 则使用龙虎榜数据替代
    """
    
    base_score = 50  # 无龙虎榜时的基础分
    
    # 成交量信号
    vol_signal = calculate_volume_signal(
        symbol,
        volume_data['current'],
        volume_data['ma5']
    )
    
    # 机构信号
    inst_signal = calculate_institutional_signal(
        order_data['large_order_count'],
        order_data['avg_large_order_size']
    )
    
    # 融资信号
    margin_signal = calculate_margin_signal(
        margin_data['balance_change_pct']
    )
    
    total = base_score + vol_signal + inst_signal + margin_signal
    
    return min(total, 100), {
        'base': base_score,
        'volume': vol_signal,
        'institutional': inst_signal,
        'margin': margin_signal
    }

# 测试案例
if __name__ == '__main__':
    # 华映科技: 小盘股, 龙虎榜常缺失
    symbol = '000536'
    
    volume_data = {'current': 5000000, 'ma5': 3000000}
    order_data = {'large_order_count': 15, 'avg_large_order_size': 10}
    margin_data = {'balance_change_pct': 0.05}
    
    score, breakdown = calculate_enhanced_funding_score(
        symbol, volume_data, order_data, margin_data
    )
    
    print(f"华映科技({symbol}) 资金面评分")
    print(f"总分: {score:.0f}/100")
    print(f"分项:")
    print(f"  基础: {breakdown['base']}")
    print(f"  成交量突增: {breakdown['volume']}")
    print(f"  机构参与: {breakdown['institutional']}")
    print(f"  融资净买: {breakdown['margin']}")
'''

def main():
    print("🌙 v5.138 Phase 2-4: 核心优化代码生成")
    print("=" * 60)
    
    # 生成文件
    files = {
        '/home/nikefd/finance-agent/v5_138_phase2_market_cap_adaptive.py': PHASE_2_CODE,
        '/home/nikefd/finance-agent/v5_138_phase3_scaled_exit.py': PHASE_3_CODE,
        '/home/nikefd/finance-agent/v5_138_phase4_funding_enhance.py': PHASE_4_CODE,
    }
    
    for filepath, code in files.items():
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(code)
        print(f"✅ {filepath.split('/')[-1]}")
    
    # 生成集成测试
    test_code = '''#!/usr/bin/env python3
"""v5.138 集成测试: 市值分层 + 多级止盈 + 资金面增强"""

import sys
sys.path.insert(0, '/home/nikefd/finance-agent')

from v5_138_phase2_market_cap_adaptive import *
from v5_138_phase3_scaled_exit import *
from v5_138_phase4_funding_enhance import *

def test_all():
    print("🧪 v5.138 集成测试")
    print("=" * 60)
    
    # Test Phase 2
    print("\\n📊 Phase 2: 市值分层参数自适应")
    print("-" * 40)
    
    # 东方证券
    cap_east = 180_000_000_000
    print(f"东方证券(600958): {get_market_cap_tier(cap_east)}")
    print(f"  MACD: {get_adaptive_macd_params(cap_east)}")
    print(f"  RSI周期: {get_adaptive_rsi_period(cap_east)}")
    
    # 华映科技
    cap_huaying = 20_000_000_000
    print(f"\\n华映科技(000536): {get_market_cap_tier(cap_huaying)}")
    print(f"  MACD: {get_adaptive_macd_params(cap_huaying)}")
    print(f"  RSI周期: {get_adaptive_rsi_period(cap_huaying)}")
    
    # Test Phase 3
    print("\\n\\n📈 Phase 3: 多级止盈策略")
    print("-" * 40)
    
    pos = Position('600958', 9.23, 600, '2026-05-28')
    prices = [9.50, 10.00, 10.50, 11.00]
    
    for price in prices:
        result = execute_scaled_exit(pos, price)
        if result['exit_signal']:
            print(f"✅ ¥{price:.2f}: {result['exit_phase']} | 卖{result['exit_qty']}股 | 已止盈¥{result['realized_profit']:.0f}")
        else:
            print(f"⏳ ¥{price:.2f}: 持有 | 收益{result['profit_pct']*100:.1f}%")
    
    # Test Phase 4
    print("\\n\\n💰 Phase 4: 资金面增强信号")
    print("-" * 40)
    
    vol_data = {'current': 5000000, 'ma5': 3000000}
    order_data = {'large_order_count': 15, 'avg_large_order_size': 10}
    margin_data = {'balance_change_pct': 0.05}
    
    score, breakdown = calculate_enhanced_funding_score(
        '000536', vol_data, order_data, margin_data
    )
    
    print(f"华映科技(000536) 资金面评分: {score:.0f}/100")
    print(f"  基础(无龙虎榜): {breakdown['base']}")
    print(f"  成交量突增: +{breakdown['volume']}")
    print(f"  机构参与: +{breakdown['institutional']}")
    print(f"  融资净买: +{breakdown['margin']}")
    
    print("\\n✨ 集成测试完成！")

if __name__ == '__main__':
    test_all()
'''
    
    test_file = '/home/nikefd/finance-agent/v5_138_integration_test.py'
    with open(test_file, 'w', encoding='utf-8') as f:
        f.write(test_code)
    print(f"✅ v5_138_integration_test.py")
    
    print("\n" + "=" * 60)
    print("✨ Phase 2-4 代码生成完成！")
    print("\n📋 文件清单:")
    print("  1. v5_138_phase2_market_cap_adaptive.py - 市值分层参数")
    print("  2. v5_138_phase3_scaled_exit.py - 多级止盈")
    print("  3. v5_138_phase4_funding_enhance.py - 资金面增强")
    print("  4. v5_138_integration_test.py - 集成测试")

if __name__ == '__main__':
    main()
