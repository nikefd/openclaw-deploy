"""仓位管理器 — 动态仓位+风控+止盈止损+追踪止损+板块策略路由+时间止损+市场状态+回撤熔断+风险平价"""

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
    sector_bonus = {
        '科技成长': 1.15,
        '新能源': 1.10,
        '消费白马': 0.85,
        '主板': 1.0,
        '其他': 0.95,
    }
    return sector_bonus.get(sector, 1.0)


# === Kelly Criterion 仓位优化 ===
# 基于回测验证的各板块策略胜率和盈亏比
KELLY_PARAMS = {
    '科技成长': {'win_rate': 0.60, 'profit_factor': 2.35, 'max_kelly': 0.25},
    '新能源':   {'win_rate': 0.70, 'profit_factor': 1.78, 'max_kelly': 0.25},
    '消费白马': {'win_rate': 0.40, 'profit_factor': 0.80, 'max_kelly': 0.10},
    '主板':     {'win_rate': 0.50, 'profit_factor': 1.20, 'max_kelly': 0.15},
    '其他':     {'win_rate': 0.45, 'profit_factor': 1.00, 'max_kelly': 0.12},
}


def kelly_position_size(sector: str, confidence: int) -> float:
    """Kelly Criterion计算最优仓位比例
    
    Kelly% = W - (1-W)/R
    W = 胜率, R = 盈亏比
    实际使用半Kelly(更保守)
    """
    params = KELLY_PARAMS.get(sector, KELLY_PARAMS['其他'])
    w = params['win_rate']
    r = params['profit_factor']
    
    if r <= 0:
        return 0.05
    
    kelly = w - (1 - w) / r
    kelly = max(kelly, 0)  # 负Kelly = 不下注
    
    # 半Kelly更保守
    half_kelly = kelly / 2
    
    # 信心度调节: confidence 6-10 映射到 0.6-1.0
    conf_mult = max(0.6, min(confidence / 10, 1.0))
    adjusted = half_kelly * conf_mult
    
    # 限制在合理范围
    return min(adjusted, params['max_kelly'])


# === 组合回撤熔断器 ===
# 总组合从峰值回撤超过阈值时，暂停新买入
DRAWDOWN_CIRCUIT_BREAKER = {
    'threshold': -0.08,      # 总回撤>8%触发熔断
    'cooldown_days': 3,      # 熔断后冷却3天不买入
    'reduce_threshold': -0.05,  # 回撤>5%仓位减半
}


def check_portfolio_drawdown() -> dict:
    """检查组合回撤状态，返回熔断信息
    
    Returns: {drawdown_pct, from_peak, is_circuit_break, reduce_position}
    """
    try:
        import sqlite3
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT total_value, date FROM daily_snapshots ORDER BY date DESC LIMIT 30")
        rows = c.fetchall()
        conn.close()
        
        if len(rows) < 2:
            return {'drawdown_pct': 0, 'is_circuit_break': False, 'reduce_position': False}
        
        values = [(r[1], r[0]) for r in rows]
        values.reverse()
        
        peak = max(v for _, v in values)
        current = values[-1][1]
        drawdown = (current - peak) / peak
        
        is_break = drawdown <= DRAWDOWN_CIRCUIT_BREAKER['threshold']
        reduce = drawdown <= DRAWDOWN_CIRCUIT_BREAKER['reduce_threshold']
        
        return {
            'drawdown_pct': round(drawdown * 100, 2),
            'peak_value': peak,
            'current_value': current,
            'is_circuit_break': is_break,
            'reduce_position': reduce,
        }
    except:
        return {'drawdown_pct': 0, 'is_circuit_break': False, 'reduce_position': False}


def risk_parity_weight(atr_pct: float, target_vol: float = 3.0) -> float:
    """风险平价仓位权重 — ATR反比调仓
    
    低波动股给更大仓位，高波动股给更小仓位
    目标: 每只股票对组合贡献相同的风险
    
    target_vol: 目标每只股票日波动贡献(%)
    """
    if atr_pct <= 0:
        return 1.0
    # weight ∝ 1/ATR，归一化到[0.5, 2.0]范围
    raw_weight = target_vol / atr_pct
    return max(0.5, min(raw_weight, 2.0))


def calculate_position_size(confidence: int, sentiment_score: float, 
                            current_positions: int, available_cash: float,
                            sector: str = "", regime: str = "",
                            loss_streak: int = 0, atr_pct: float = 0) -> float:
    """动态计算仓位大小（板块+市场状态+连亏保护+回撤熔断+风险平价）"""
    # === 回撤熔断检查 ===
    dd_info = check_portfolio_drawdown()
    if dd_info['is_circuit_break']:
        return 0.0  # 熔断: 完全停止买入
    
    # 基础仓位：使用Kelly Criterion（有回测数据支撑）
    if sector:
        kelly = kelly_position_size(sector, confidence)
        # Kelly仓位 vs 经验仓位取加权平均 (Kelly 60% + 经验 40%)
        exp_pct = {10: 0.15, 9: 0.13, 8: 0.12, 7: 0.10, 6: 0.08}.get(confidence, 0.05)
        base_pct = kelly * 0.6 + exp_pct * 0.4
    else:
        base_pct = {10: 0.15, 9: 0.13, 8: 0.12, 7: 0.10, 6: 0.08}.get(confidence, 0.05)
    
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
    
    # === 连亏保护: 连续止损后自动收缩仓位 ===
    if loss_streak >= 5:
        base_pct *= 0.3  # 连亏5次，仓位降到30%
    elif loss_streak >= 3:
        base_pct *= 0.5  # 连亏3次，仓位减半
    elif loss_streak >= 2:
        base_pct *= 0.7  # 连亏2次，仓位降30%
    
    # === 回撤减仓: 组合回撤>5%时仓位减半 ===
    if dd_info.get('reduce_position'):
        base_pct *= 0.5
    
    # === 风险平价: 低波动股给更大仓位 ===
    if atr_pct > 0:
        rp_weight = risk_parity_weight(atr_pct)
        base_pct *= rp_weight
    
    # 绝对限制
    base_pct = min(base_pct, MAX_SINGLE_POSITION)
    
    # 确保不超过可用资金的30%
    max_from_cash = 0.3
    base_pct = min(base_pct, max_from_cash)
    
    return round(base_pct, 4)


def check_dynamic_stop(positions: list, sentiment_score: float, regime: str = "") -> list:
    """动态止损止盈 — 追踪止损+情绪调节+阶梯止盈+时间止损+动量衰减卖出"""
    actions = []
    for pos in positions:
        if not pos.get('current_price') or not pos.get('avg_cost'):
            continue
        
        pnl_pct = (pos['current_price'] - pos['avg_cost']) / pos['avg_cost']
        buy_date = pos.get('buy_date', '')
        
        # T+1检查
        if buy_date == date.today().isoformat():
            continue
        
        # === 动量衰减卖出 ===
        # 持仓盈利但动量正在衰减时，主动减仓保利润
        try:
            from data_collector import get_stock_daily, calculate_technical_indicators
            df = get_stock_daily(pos['symbol'], 30)
            if df is not None and not df.empty:
                tech = calculate_technical_indicators(df)
                if tech:
                    # 盈利5%+且动量衰减+量价背离 → 减半仓
                    if (pnl_pct >= 0.05 and 
                        tech.get('momentum_decay') and 
                        tech.get('volume_price_diverge')):
                        half = (pos['shares'] // 200) * 100
                        if half >= 100:
                            actions.append({
                                "action": "SELL",
                                "symbol": pos['symbol'],
                                "name": pos['name'],
                                "reason": f"动量衰减减仓: 盈利{pnl_pct*100:+.1f}%但MACD递减+量价背离",
                                "shares": half,
                                "price": pos['current_price']
                            })
                            continue
                    # RSI顶背离 + 盈利 → 卖出
                    if (pnl_pct >= 0.03 and 
                        tech.get('rsi_divergence') == 'bearish'):
                        actions.append({
                            "action": "SELL",
                            "symbol": pos['symbol'],
                            "name": pos['name'],
                            "reason": f"RSI顶背离卖出: 盈利{pnl_pct*100:+.1f}%+顶背离信号",
                            "shares": pos['shares'],
                            "price": pos['current_price']
                        })
                        continue
        except:
            pass
        
        # === 时间止损 (Time Stop) ===
        # 持仓天数阈值根据市场状态自适应: 牛市宽松(25天)，熊市收紧(15天)
        time_stop_days = 20  # 默认震荡市
        if regime == 'bull':
            time_stop_days = 25  # 牛市给更多时间发酵
        elif regime == 'bear':
            time_stop_days = 12  # 熊市快速止损换票（加速换仓）
        
        if buy_date:
            try:
                buy_dt = datetime.strptime(buy_date, '%Y-%m-%d').date()
                hold_days = (date.today() - buy_dt).days
                if hold_days >= time_stop_days and -0.03 <= pnl_pct <= 0.03:
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
        
        trail_activation = 1.06 if regime == 'bear' else 1.10  # 熊市6%即激活追踪止损
        if peak_price > pos['avg_cost'] * trail_activation:
            trail_drawdown = (peak_price - pos['current_price']) / peak_price
            # 熊市收紧追踪止损：4%回撤即卖出（默认5%）
            trail_threshold = 0.04 if regime == 'bear' else 0.05
            if trail_drawdown >= trail_threshold:  # 从高点回撤
                actions.append({
                    "action": "SELL",
                    "symbol": pos['symbol'],
                    "name": pos['name'],
                    "reason": f"追踪止损: 高点{peak_price:.2f}回撤{trail_drawdown*100:.1f}%",
                    "shares": pos['shares'],
                    "price": pos['current_price']
                })
                continue
        
        # === ATR自适应止损 + 情绪/市场状态调节 ===
        # 先计算该股票的ATR止损线（基于个股波动率）
        stop_loss = STOP_LOSS  # 默认-8%
        atr_stop = None
        try:
            from data_collector import get_stock_daily as _gsd, calculate_technical_indicators as _cti
            _df = _gsd(pos['symbol'], 30)
            if _df is not None and not _df.empty:
                _tech = _cti(_df)
                atr_pct = _tech.get('atr_pct', 0)
                if atr_pct > 0:
                    # ATR止损 = 2倍ATR百分比（给正常波动留空间）
                    atr_stop = -(atr_pct * 2) / 100
                    # 限制在合理范围 [-3%, -15%]
                    atr_stop = max(min(atr_stop, -0.03), -0.15)
        except:
            pass
        
        # 市场状态调节基准
        if regime:
            from market_regime import get_regime_stop_loss
            stop_loss = get_regime_stop_loss(regime)
        
        # 如果有ATR数据，取ATR止损和市场止损中更保守的（更紧的）
        if atr_stop is not None:
            stop_loss = max(stop_loss, atr_stop)  # max because both are negative
        
        # 情绪再调节
        if sentiment_score < 35:  # 市场恐慌时收紧止损
            stop_loss = max(stop_loss, -0.05)  # 不低于-5%
        elif sentiment_score > 75:  # 市场乐观时放宽
            stop_loss = min(stop_loss, -0.10)
        
        if pnl_pct <= stop_loss:
            atr_info = f" ATR止损{atr_stop*100:.1f}%" if atr_stop else ""
            actions.append({
                "action": "SELL",
                "symbol": pos['symbol'],
                "name": pos['name'],
                "reason": f"动态止损: 亏损{pnl_pct*100:.1f}% (阈值{stop_loss*100:.0f}%{atr_info})",
                "shares": pos['shares'],
                "price": pos['current_price']
            })
            continue
        
        # === 阶梯止盈 (三档渐进) ===
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
        elif pnl_pct >= 0.12:  # 赚12%+，止盈1/3
            third = (pos['shares'] // 300) * 100
            if third >= 100:
                actions.append({
                    "action": "SELL",
                    "symbol": pos['symbol'],
                    "name": pos['name'],
                    "reason": f"阶梯止盈: 盈利{pnl_pct*100:.1f}% ≥12%, 卖出1/3",
                    "shares": third,
                    "price": pos['current_price']
                })
    
    return actions


def portfolio_risk_check(positions: list, total_value: float) -> dict:
    """组合风险检查 — 含连亏保护+板块集中度+相关性"""
    if not positions:
        return {"healthy": True, "warnings": [], "loss_streak": 0}
    
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
    
    # === 连亏检测 — 查最近交易记录 ===
    loss_streak = 0
    try:
        import sqlite3
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT direction, reason FROM trades ORDER BY id DESC LIMIT 10")
        recent_sells = []
        for row in c.fetchall():
            if row[0] == 'SELL':
                recent_sells.append(row[1] or '')
        conn.close()
        # 统计连续止损次数
        for reason in recent_sells:
            if '止损' in reason:
                loss_streak += 1
            else:
                break
        if loss_streak >= 3:
            warnings.append(f"⚠️ 连续{loss_streak}次止损! 建议降低仓位+提高选股门槛")
    except:
        pass
    
    return {"healthy": len(warnings) == 0, "warnings": warnings, "loss_streak": loss_streak}
