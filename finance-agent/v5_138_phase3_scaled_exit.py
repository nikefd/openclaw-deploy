
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
    print(f"初始持仓: 600股 @ ¥9.23\n")
    
    for price in prices:
        result = execute_scaled_exit(pos, price)
        print(f"当前价格: ¥{price:.2f} | 收益率: {result['profit_pct']*100:.2f}% | "
              f"出场: {result['exit_phase']} | 已止盈: ¥{result['realized_profit']:.0f} | "
              f"剩余: {result['remaining_qty']}股")
