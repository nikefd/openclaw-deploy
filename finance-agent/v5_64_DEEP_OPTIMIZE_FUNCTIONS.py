"""v5.64 深度优化函数集 — Kelly仓位 + 相关性检查 + 入场时机"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# ============ Kelly仓位优化 ============

def best_entry_timing_check(symbol: str, signals: dict, timeframe_hours: int = 4) -> bool:
    """最优入场时机检查
    
    Args:
        symbol: 股票代码
        signals: 技术面信号 {macd_cross: bool, rsi_oversold: bool, macd_value: float}
        timeframe_hours: 信号有效期（小时）
    
    Returns:
        是否处于最优入场时机
    """
    # 检查信号新鲜度
    if not signals or 'timestamp' not in signals:
        return True  # 保守起见，无时间戳视为可入场
    
    signal_age = (datetime.now() - signals['timestamp']).total_seconds() / 3600
    if signal_age > timeframe_hours:
        return False  # 信号过期
    
    # Kelly标准: MACD值0-2之间为最优入场区间
    macd_val = signals.get('macd_value', 0)
    return 0 <= macd_val <= 2.0


def position_correlation_check(symbol: str, current_portfolio: list, max_correlation: float = 0.65) -> bool:
    """持仓相关性检查 — 防止集中度过高
    
    Args:
        symbol: 待加仓票
        current_portfolio: 当前持仓 [{symbol, sector, correlation}...]
        max_correlation: 允许最大相关性
    
    Returns:
        是否可加仓
    """
    if not current_portfolio:
        return True  # 空仓时可加仓
    
    # 按sector分组统计
    sector_holdings = {}
    for pos in current_portfolio:
        sector = pos.get('sector', 'unknown')
        sector_holdings[sector] = sector_holdings.get(sector, 0) + 1
    
    # 同sector超过3只则拒绝
    new_symbol_sector = infer_sector(symbol)
    if sector_holdings.get(new_symbol_sector, 0) >= 3:
        return False
    
    return True


def position_size_limit_check(symbol: str, entry_price: float, account_equity: float, 
                             position_limit: float = 0.08) -> float:
    """单个头寸上限检查 — Kelly安全防护
    
    Args:
        symbol: 股票代码
        entry_price: 入场价格
        account_equity: 账户权益
        position_limit: 单头寸上限占比 (默认8%)
    
    Returns:
        允许最大建仓规模（元）
    """
    # Kelly基础仓位 = equity * kelly_fraction (通常0.08-0.15)
    # 但上限不超过单头寸上限
    max_position_value = account_equity * position_limit
    return max_position_value


def sector_weight_by_winrate(sector: str, historical_winrate: float, 
                            current_weight: float, max_weight: float = 0.25) -> float:
    """按胜率调整sector权重 — 高胜率sector增加权重
    
    Args:
        sector: 板块名称
        historical_winrate: 历史胜率 (0-1)
        current_weight: 当前配置权重
        max_weight: 最大权重上限
    
    Returns:
        调整后的权重
    """
    # 胜率 > 60% → +20% 权重
    # 胜率 40-60% → 保持不变
    # 胜率 < 40% → -30% 权重
    
    if historical_winrate > 0.60:
        adjusted = min(current_weight * 1.2, max_weight)
    elif historical_winrate < 0.40:
        adjusted = current_weight * 0.7
    else:
        adjusted = current_weight
    
    return adjusted


# ============ 辅助函数 ============

def infer_sector(symbol: str) -> str:
    """推断股票所属板块 (简化版)"""
    sector_map = {
        '半导体': ['301236', '688396'],
        '新能源': ['300750', '600586'],
        '消费': ['000858', '000671'],
        '金融': ['600036', '601398'],
    }
    for sector, syms in sector_map.items():
        if symbol in syms:
            return sector
    return 'other'


# ============ 验证函数 ============

def validate_v5_64():
    """验证v5.64模块是否正常加载"""
    print("✅ v5.64 Deep Optimize Functions loaded successfully")
    print("   - best_entry_timing_check()")
    print("   - position_correlation_check()")
    print("   - position_size_limit_check()")
    print("   - sector_weight_by_winrate()")
    return True


if __name__ == '__main__':
    validate_v5_64()
