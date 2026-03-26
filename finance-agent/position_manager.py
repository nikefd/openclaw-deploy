"""仓位管理器 — 动态仓位+风控+止盈止损优化"""

from datetime import datetime, date
from config import *


def calculate_position_size(confidence: int, sentiment_score: float, 
                            current_positions: int, available_cash: float) -> float:
    """动态计算仓位大小"""
    # 基础仓位：根据信心评分
    base_pct = {10: 0.15, 9: 0.13, 8: 0.12, 7: 0.10, 6: 0.08}.get(confidence, 0.05)
    
    # 情绪调节：市场过热时减仓，恐慌时加仓（逆向思维）
    if sentiment_score > 85:  # 极度贪婪 → 减仓
        base_pct *= 0.6
    elif sentiment_score > 70:  # 乐观 → 微减
        base_pct *= 0.85
    elif sentiment_score < 30:  # 恐慌 → 加仓（抄底）
        base_pct *= 1.3
    elif sentiment_score < 45:  # 谨慎 → 微加
        base_pct *= 1.1
    
    # 持仓数量调节：已有很多仓位时降低新仓比例
    if current_positions >= 8:
        base_pct *= 0.5
    elif current_positions >= 5:
        base_pct *= 0.7
    
    # 绝对限制
    base_pct = min(base_pct, MAX_SINGLE_POSITION)
    
    # 确保不超过可用资金的30%
    max_from_cash = 0.3
    base_pct = min(base_pct, max_from_cash)
    
    return round(base_pct, 4)


def check_dynamic_stop(positions: list, sentiment_score: float) -> list:
    """动态止损止盈 — 根据市场情绪和个股走势调整"""
    actions = []
    for pos in positions:
        if not pos.get('current_price') or not pos.get('avg_cost'):
            continue
        
        pnl_pct = (pos['current_price'] - pos['avg_cost']) / pos['avg_cost']
        buy_date = pos.get('buy_date', '')
        
        # T+1检查
        if buy_date == date.today().isoformat():
            continue
        
        # 动态止损
        stop_loss = STOP_LOSS  # 默认-8%
        if sentiment_score < 35:  # 市场恐慌时收紧止损
            stop_loss = -0.05
        elif sentiment_score > 75:  # 市场乐观时放宽
            stop_loss = -0.10
        
        if pnl_pct <= stop_loss:
            actions.append({
                "action": "SELL",
                "symbol": pos['symbol'],
                "name": pos['name'],
                "reason": f"动态止损: 亏损{pnl_pct*100:.1f}% (阈值{stop_loss*100:.0f}%)",
                "shares": pos['shares'],
                "price": pos['current_price']
            })
            continue
        
        # 阶梯止盈
        if pnl_pct >= 0.30:  # 赚30%+，止盈全部
            actions.append({
                "action": "SELL",
                "symbol": pos['symbol'],
                "name": pos['name'],
                "reason": f"止盈: 盈利{pnl_pct*100:.1f}% ≥30%",
                "shares": pos['shares'],
                "price": pos['current_price']
            })
        elif pnl_pct >= 0.20:  # 赚20%+，止盈一半
            half = (pos['shares'] // 200) * 100  # 取整到100
            if half >= 100:
                actions.append({
                    "action": "SELL",
                    "symbol": pos['symbol'],
                    "name": pos['name'],
                    "reason": f"阶梯止盈: 盈利{pnl_pct*100:.1f}% ≥20%, 卖出一半",
                    "shares": half,
                    "price": pos['current_price']
                })
    
    return actions


def portfolio_risk_check(positions: list, total_value: float) -> dict:
    """组合风险检查"""
    if not positions:
        return {"healthy": True, "warnings": []}
    
    warnings = []
    
    # 单一持仓占比检查
    for pos in positions:
        pos_value = pos['current_price'] * pos['shares']
        pct = pos_value / total_value if total_value > 0 else 0
        if pct > 0.20:
            warnings.append(f"{pos['name']}仓位过重: {pct*100:.1f}%")
    
    # 总亏损检查
    total_pnl = sum((p['current_price'] - p['avg_cost']) * p['shares'] for p in positions)
    total_cost = sum(p['avg_cost'] * p['shares'] for p in positions)
    if total_cost > 0 and total_pnl / total_cost < -0.10:
        warnings.append(f"组合总亏损超10%: {total_pnl/total_cost*100:.1f}%")
    
    # 持仓过于集中（同一行业）
    # TODO: 加行业分散度检查
    
    return {"healthy": len(warnings) == 0, "warnings": warnings}
