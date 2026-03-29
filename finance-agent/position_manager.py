"""仓位管理器 — 动态仓位+风控+止盈止损+追踪止损+板块策略路由+时间止损+市场状态"""

from datetime import datetime, date, timedelta
from config import *


# 板块策略权重 — 来自回测数据验证
# MACD+RSI在科技+新能源最强，TREND_FOLLOW在消费白马最稳
SECTOR_STRATEGY_WEIGHTS = {
    '科技成长': {'macd_rsi': 1.5, 'multi_factor': 1.2, 'trend_follow': 0.8, 'ma_cross': 1.0},
    '新能源':   {'macd_rsi': 1.4, 'multi_factor': 1.2, 'trend_follow': 1.1, 'ma_cross': 0.9},
    '消费白马': {'macd_rsi': 0.5, 'multi_factor': 0.8, 'trend_follow': 1.5, 'ma_cross': 1.2},
    '主板':     {'macd_rsi': 1.0, 'multi_factor': 1.1, 'trend_follow': 1.0, 'ma_cross': 1.0},
    '其他':     {'macd_rsi': 1.0, 'multi_factor': 1.0, 'trend_follow': 1.0, 'ma_cross': 1.0},
}


def get_sector_score_multiplier(sector: str) -> float:
    """根据板块返回评分乘数 — 回测表现好的板块给更高权重"""
    # 科技和新能源回测收益最高，给予加成
    sector_bonus = {
        '科技成长': 1.15,
        '新能源': 1.10,
        '消费白马': 0.85,  # 消费白马不适合短线技术策略
        '主板': 1.0,
        '其他': 0.95,
    }
    return sector_bonus.get(sector, 1.0)


def calculate_position_size(confidence: int, sentiment_score: float, 
                            current_positions: int, available_cash: float,
                            sector: str = "", regime: str = "") -> float:
    """动态计算仓位大小（板块+市场状态调节）"""
    # 基础仓位：根据信心评分
    base_pct = {10: 0.15, 9: 0.13, 8: 0.12, 7: 0.10, 6: 0.08}.get(confidence, 0.05)
    
    # 板块调节 — 回测验证过的板块给更大仓位
    if sector:
        base_pct *= get_sector_score_multiplier(sector)
    
    # 市场状态调节
    if regime:
        from market_regime import get_regime_position_cap
        cap = get_regime_position_cap(regime)
        # 熊市整体压低仓位
        if regime == 'bear':
            base_pct *= 0.6
        elif regime == 'bull':
            base_pct *= 1.1
    
    # 情绪调节：市场过热时减仓，恐慌时加仓（逆向思维）
    if sentiment_score > 90:  # 极度贪婪 → 禁止新开仓
        return 0.0
    elif sentiment_score > 85:  # 贪婪 → 大幅减仓
        base_pct *= 0.4
    elif sentiment_score > 70:  # 乐观 → 微减
        base_pct *= 0.85
    elif sentiment_score < 30:  # 恐慌 → 加仓（抄底）
        base_pct *= 1.3
    elif sentiment_score < 45:  # 谨慎 → 微加
        base_pct *= 1.1
    
    # 持仓数量调节：限制最大持仓数，分散风险
    if current_positions >= 10:  # 硬上限
        return 0.0
    elif current_positions >= 8:
        base_pct *= 0.4
    elif current_positions >= 5:
        base_pct *= 0.7
    
    # 绝对限制
    base_pct = min(base_pct, MAX_SINGLE_POSITION)
    
    # 确保不超过可用资金的30%
    max_from_cash = 0.3
    base_pct = min(base_pct, max_from_cash)
    
    return round(base_pct, 4)


def check_dynamic_stop(positions: list, sentiment_score: float, regime: str = "") -> list:
    """动态止损止盈 — 追踪止损+情绪调节+阶梯止盈+时间止损"""
    actions = []
    for pos in positions:
        if not pos.get('current_price') or not pos.get('avg_cost'):
            continue
        
        pnl_pct = (pos['current_price'] - pos['avg_cost']) / pos['avg_cost']
        buy_date = pos.get('buy_date', '')
        
        # T+1检查
        if buy_date == date.today().isoformat():
            continue
        
        # === 时间止损 (Time Stop) ===
        # 持仓超过15个交易日且收益在-3%~+3%之间 → 说明选错了，清掉换票
        if buy_date:
            try:
                buy_dt = datetime.strptime(buy_date, '%Y-%m-%d').date()
                hold_days = (date.today() - buy_dt).days
                if hold_days >= 20 and -0.03 <= pnl_pct <= 0.03:
                    actions.append({
                        "action": "SELL",
                        "symbol": pos['symbol'],
                        "name": pos['name'],
                        "reason": f"时间止损: 持仓{hold_days}天无明显盈亏({pnl_pct*100:+.1f}%)",
                        "shares": pos['shares'],
                        "price": pos['current_price']
                    })
                    continue
            except:
                pass
        
        # === 追踪止损 (Trailing Stop) ===
        # 当盈利超过10%后，启用追踪止损：从最高点回撤5%即卖出
        # 这能锁住大部分利润，避免"坐过山车"
        peak_price = pos.get('peak_price', pos['avg_cost'])
        if pos['current_price'] > peak_price:
            peak_price = pos['current_price']
        
        if peak_price > pos['avg_cost'] * 1.10:  # 曾经盈利超10%
            trail_drawdown = (peak_price - pos['current_price']) / peak_price
            if trail_drawdown >= 0.05:  # 从高点回撤5%
                actions.append({
                    "action": "SELL",
                    "symbol": pos['symbol'],
                    "name": pos['name'],
                    "reason": f"追踪止损: 高点{peak_price:.2f}回撤{trail_drawdown*100:.1f}%",
                    "shares": pos['shares'],
                    "price": pos['current_price']
                })
                continue
        
        # === 动态止损（情绪+市场状态调节）===
        stop_loss = STOP_LOSS  # 默认-8%
        
        # 市场状态调节
        if regime:
            from market_regime import get_regime_stop_loss
            stop_loss = get_regime_stop_loss(regime)
        
        # 情绪再调节
        if sentiment_score < 35:  # 市场恐慌时收紧止损
            stop_loss = max(stop_loss, -0.05)  # 不低于-5%
        elif sentiment_score > 75:  # 市场乐观时放宽
            stop_loss = min(stop_loss, -0.10)
        
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
        
        # === 阶梯止盈 ===
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
    
    # 持仓过于集中（同一板块检查）
    from performance_tracker import classify_sector
    sector_counts = {}
    for pos in positions:
        sector = classify_sector(pos['symbol'], pos.get('name', ''))
        sector_counts[sector] = sector_counts.get(sector, 0) + 1
    for sector, count in sector_counts.items():
        if count >= 4:
            warnings.append(f"板块过于集中: {sector}有{count}只持仓，建议分散")
    
    return {"healthy": len(warnings) == 0, "warnings": warnings}
