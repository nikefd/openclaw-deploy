"""仓位管理器 — 动态仓位+风控+止盈止损+追踪止损+板块策略路由+时间止损+市场状态+回撤熔断+风险平价+止损黑名单"""

from datetime import datetime, date, timedelta
from config import *


def _trading_days_since(buy_date_str: str) -> int:
    """计算从买入日期到今天的交易日天数(排除周末)
    
    统一工具函数，避免早期止损和时间止损各自重复计算
    """
    try:
        buy_dt = datetime.strptime(buy_date_str, '%Y-%m-%d').date()
        cal_days = (date.today() - buy_dt).days
        weekends = sum(1 for d in range(cal_days) if (buy_dt + timedelta(days=d+1)).weekday() >= 5)
        return cal_days - weekends
    except:
        return -1  # 解析失败返回-1


def check_correlation_with_portfolio(symbol: str, positions: list) -> float:
    """检查候选股与现有持仓的价格相关性
    
    避免买入高度相关的股票(同涨同跌=没有分散风险)
    Returns: 与现有持仓的最大相关系数 (0~1)
    """
    if not positions:
        return 0.0
    try:
        from data_collector import get_stock_daily
        import pandas as pd
        
        # 获取候选股近20日收益率
        df_new = get_stock_daily(symbol, 25)
        if df_new is None or len(df_new) < 15:
            return 0.0
        ret_new = df_new['收盘'].astype(float).pct_change().dropna()
        
        max_corr = 0.0
        for pos in positions[:5]:  # 只查前5只避免太慢
            try:
                df_pos = get_stock_daily(pos['symbol'], 25)
                if df_pos is None or len(df_pos) < 15:
                    continue
                ret_pos = df_pos['收盘'].astype(float).pct_change().dropna()
                # 对齐长度
                min_len = min(len(ret_new), len(ret_pos))
                if min_len < 10:
                    continue
                corr = ret_new.tail(min_len).reset_index(drop=True).corr(
                    ret_pos.tail(min_len).reset_index(drop=True))
                if abs(corr) > max_corr:
                    max_corr = abs(corr)
            except:
                continue
        return round(max_corr, 3)
    except:
        return 0.0


# === 止损黑名单: 近期止损过的股票短期内不再买入 ===
STOP_LOSS_BLACKLIST_DAYS = 15  # 止损后15个交易日内不买回(从10提高,连亏期更长冷却)


def get_stop_loss_blacklist() -> set:
    """获取近期止损过的股票代码集合
    
    动态冷却: 小亏(-3%以内)冷却7天, 中亏(-3%~-8%)冷却10天, 大亏(-8%+)冷却15天
    """
    try:
        import sqlite3
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        # 获取近15天所有止损卖出记录(含价格和成本信息)
        cutoff = (date.today() - timedelta(days=15)).isoformat()
        c.execute("""SELECT symbol, trade_date, price FROM trades 
                     WHERE direction='SELL' AND reason LIKE '%止损%' AND trade_date >= ?""", (cutoff,))
        blacklist = set()
        for symbol, trade_date, sell_price in c.fetchall():
            # 查这只股票的买入成本
            c.execute("""SELECT price FROM trades WHERE symbol=? AND direction='BUY' AND id < 
                        (SELECT id FROM trades WHERE symbol=? AND direction='SELL' AND trade_date=? LIMIT 1)
                        ORDER BY id DESC LIMIT 1""", (symbol, symbol, trade_date))
            buy_row = c.fetchone()
            loss_pct = 0
            if buy_row and buy_row[0] > 0:
                loss_pct = (sell_price - buy_row[0]) / buy_row[0] * 100
            
            # 根据亏损幅度决定冷却天数
            if loss_pct <= -8:
                cool_days = 15  # 大亏冷却15天
            elif loss_pct <= -3:
                cool_days = 10  # 中亏冷却10天
            else:
                cool_days = 7   # 小亏冷却7天
            
            try:
                stop_date = datetime.strptime(trade_date, '%Y-%m-%d').date()
                if (date.today() - stop_date).days < cool_days:
                    blacklist.add(symbol)
            except:
                blacklist.add(symbol)  # 解析失败保守处理
        conn.close()
        return blacklist
    except:
        return set()


def get_sector_stop_loss_penalty() -> dict:
    """板块级止损冷却 — 同板块近期多次止损则整体扣分
    
    Returns: {sector: penalty_score} 负数=扣分
    """
    try:
        import sqlite3
        from performance_tracker import classify_sector
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        cutoff = (date.today() - timedelta(days=20)).isoformat()
        c.execute("""SELECT b.symbol, b.reason as buy_reason
                     FROM trades s
                     JOIN trades b ON b.symbol = s.symbol AND b.direction = 'BUY'
                         AND b.id = (SELECT MAX(b2.id) FROM trades b2 WHERE b2.symbol = s.symbol AND b2.direction = 'BUY' AND b2.id < s.id)
                     WHERE s.direction='SELL' AND s.reason LIKE '%止损%' AND s.trade_date >= ?""", (cutoff,))
        sector_stops = {}
        for symbol, buy_reason in c.fetchall():
            sec = classify_sector(symbol, buy_reason or '')
            sector_stops[sec] = sector_stops.get(sec, 0) + 1
        conn.close()
        
        penalties = {}
        for sec, count in sector_stops.items():
            if count >= 3:
                penalties[sec] = -12  # 同板块3次止损，大扣
            elif count >= 2:
                penalties[sec] = -6   # 2次止损，中扣
        return penalties
    except:
        return {}


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
    elif sentiment_score > 80 and regime == 'bear':  # 熊市+贪婪 → 大幅减仓(不完全禁止)
        base_pct *= 0.2
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
    
    # === 连亏8+次: 狙击手模式 — 不完全停手,但极度保守 ===
    # v5.27: 连亏3-7次也打开狙击手模式,而不是只缩仓
    # 原因: 缩仓后的微仓让交易毫无意义,不如用固定小仓位快速试探
    if loss_streak >= 8:
        base_pct = 0.025  # 固定2.5%微仓
    elif loss_streak >= 5:
        base_pct = 0.04   # 固定4%小仓(v5.27: 从50%缩仓改为固定小仓)
    
    # === 连亏冷却期: 连亏6+次强制冷却，不只是缩仓 ===
    if loss_streak >= 6:
        # 检查最后一次止损距今是否超过冷却天数
        try:
            import sqlite3
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT trade_date FROM trades WHERE direction='SELL' AND reason LIKE '%止损%' ORDER BY id DESC LIMIT 1")
            row = c.fetchone()
            conn.close()
            if row:
                last_stop = datetime.strptime(row[0], '%Y-%m-%d').date()
                cool_days = min(loss_streak - 3, 5)  # 连亏6=冷却3天, 连亏7=冷却4天, 最多5天
                if (date.today() - last_stop).days < cool_days:
                    return 0.0  # 冷却期内完全不买
        except:
            pass
    
    # === 连亏保护: 连续止损后自动收缩仓位 ===
    # v5.27: 连亏5+已在上方固定为小仓位, 这里只处理连亏2-4
    if loss_streak >= 3 and loss_streak < 5:
        base_pct *= 0.6  # 连亏3-4次，仓位降40%
    elif loss_streak >= 2:
        base_pct *= 0.7  # 连亏2次，仓位降30%
    
    # 最低仓位地板: 低于2%不开仓，避免100股微仓
    if base_pct > 0 and base_pct < 0.02:
        return 0.0
    
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


def check_dynamic_stop(positions: list, sentiment_score: float, regime: str = "", loss_streak: int = 0) -> list:
    """动态止损止盈 — 早期止损+追踪止损+情绪调节+阶梯止盈+时间止损+动量衰减卖出"""
    actions = []
    for pos in positions:
        if not pos.get('current_price') or not pos.get('avg_cost'):
            continue
        
        pnl_pct = (pos['current_price'] - pos['avg_cost']) / pos['avg_cost']
        buy_date = pos.get('buy_date', '')
        
        # T+1检查
        if buy_date == date.today().isoformat():
            continue
        
        # === 早期止损 (Early Exit) ===
        # 买入后2个交易日内亏>2%说明入场时机错误，快速认错比等-8%好
        # 买入后3个交易日内亏>1%也止损(连亏期间更严格)
        # 注意: 用交易日而非日历天数，避免周五买入→周一=3天的误判
        if buy_date:
            try:
                hold_days = _trading_days_since(buy_date)
                if hold_days <= 2 and pnl_pct <= -0.02:
                    actions.append({
                        "action": "SELL",
                        "symbol": pos['symbol'],
                        "name": pos['name'],
                        "reason": f"早期止损: 持仓{hold_days}天亏{pnl_pct*100:.1f}%,入场时机错误",
                        "shares": pos['shares'],
                        "price": pos['current_price']
                    })
                    continue
                if hold_days <= 3 and pnl_pct <= -0.01 and loss_streak >= 5:
                    actions.append({
                        "action": "SELL",
                        "symbol": pos['symbol'],
                        "name": pos['name'],
                        "reason": f"连亏早期止损: 持仓{hold_days}天亏{pnl_pct*100:.1f}%,连亏{loss_streak}次加严",
                        "shares": pos['shares'],
                        "price": pos['current_price']
                    })
                    continue
            except:
                pass
        
        # === 连亏锁利润 (Loss Streak Profit Lock) ===
        # v5.36: 优先级提升 — 移到动量衰减减仓之前，确保连亏锁利不被半仓减仓截获
        # 连亏>=3次时，动态锁利帮助重置连亏计数器
        if loss_streak >= 3 and pnl_pct > 0:
            # 连亏8+: +2%即锁; 连亏5-7: +3%锁; 连亏3-4: +5%锁
            if loss_streak >= 8:
                lock_threshold = 0.02
            elif loss_streak >= 5:
                lock_threshold = 0.03
            else:
                lock_threshold = 0.05
            
            if pnl_pct >= lock_threshold:
                half = (pos['shares'] // 200) * 100
                sell_shares = half if half >= 100 else pos['shares']
                actions.append({
                    "action": "SELL",
                    "symbol": pos['symbol'],
                    "name": pos['name'],
                    "reason": f"连亏锁利润: 连亏{loss_streak}次,盈利{pnl_pct*100:+.1f}%≥{lock_threshold*100:.0f}%主动锁利",
                    "shares": sell_shares,
                    "price": pos['current_price']
                })
                continue
        
        # === 预取技术指标(一次获取，多处复用) ===
        pos_tech = None
        try:
            from data_collector import get_stock_daily, calculate_technical_indicators
            _df = get_stock_daily(pos['symbol'], 30)
            if _df is not None and not _df.empty:
                pos_tech = calculate_technical_indicators(_df)
        except:
            pass
        
        # === 动量衰减卖出 ===
        # 持仓盈利但动量正在衰减时，主动减仓保利润
        if pos_tech:
            # 盈利5%+且动量衰减+量价背离 → 减半仓
            if (pnl_pct >= 0.05 and 
                pos_tech.get('momentum_decay') and 
                pos_tech.get('volume_price_diverge')):
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
            # OBV量价背离 + 盈利 → 减半仓（新增）
            if (pnl_pct >= 0.05 and pos_tech.get('obv_price_diverge')):
                half = (pos['shares'] // 200) * 100
                if half >= 100:
                    actions.append({
                        "action": "SELL",
                        "symbol": pos['symbol'],
                        "name": pos['name'],
                        "reason": f"OBV量价背离减仓: 盈利{pnl_pct*100:+.1f}%但OBV下降",
                        "shares": half,
                        "price": pos['current_price']
                    })
                    continue
            # RSI顶背离 + 盈利 → 卖出
            if (pnl_pct >= 0.03 and 
                pos_tech.get('rsi_divergence') == 'bearish'):
                actions.append({
                    "action": "SELL",
                    "symbol": pos['symbol'],
                    "name": pos['name'],
                    "reason": f"RSI顶背离卖出: 盈利{pnl_pct*100:+.1f}%+顶背离信号",
                    "shares": pos['shares'],
                    "price": pos['current_price']
                })
                continue
            # MACD柱状图看跌背离 + 盈利 → 减半仓
            if (pnl_pct >= 0.04 and pos_tech.get('macd_hist_bear_div')):
                half = (pos['shares'] // 200) * 100
                if half >= 100:
                    actions.append({
                        "action": "SELL",
                        "symbol": pos['symbol'],
                        "name": pos['name'],
                        "reason": f"MACD柱背离减仓: 盈利{pnl_pct*100:+.1f}%+柱线高点下降",
                        "shares": half,
                        "price": pos['current_price']
                    })
                    continue
            # Williams %R 从超买回落 + 盈利 → 减仓
            if (pnl_pct >= 0.05 and pos_tech.get('wr_overbought_exit')):
                half = (pos['shares'] // 200) * 100
                if half >= 100:
                    actions.append({
                        "action": "SELL",
                        "symbol": pos['symbol'],
                        "name": pos['name'],
                        "reason": f"Williams%R超买回落: 盈利{pnl_pct*100:+.1f}%+%R离开超买区",
                        "shares": half,
                        "price": pos['current_price']
                    })
                    continue
            # 布林带%B > 1.0回落 + 盈利 → 减仓 (超买回落)
            pct_b = pos_tech.get('boll_pct_b', 0.5)
            if pnl_pct >= 0.05 and pos_tech.get('buy_climax'):
                # 巨量追高后立即减仓
                half = (pos['shares'] // 200) * 100
                if half >= 100:
                    actions.append({
                        "action": "SELL",
                        "symbol": pos['symbol'],
                        "name": pos['name'],
                        "reason": f"巨量追高减仓: 盈利{pnl_pct*100:+.1f}%+成交量高潮",
                        "shares": half,
                        "price": pos['current_price']
                    })
                    continue
            
            # === 单日暴涨冲高减仓 ===
            # 持仓盈利5%+且单日涨幅>5%，冲高回落概率极大，主动减半仓锁利
            daily_chg = pos_tech.get('daily_change_pct', 0)
            if pnl_pct >= 0.05 and daily_chg > 5:
                half = (pos['shares'] // 200) * 100
                if half >= 100:
                    actions.append({
                        "action": "SELL",
                        "symbol": pos['symbol'],
                        "name": pos['name'],
                        "reason": f"单日暴涨减仓: 盈利{pnl_pct*100:+.1f}%+今日涨{daily_chg:.1f}%冲高风险",
                        "shares": half,
                        "price": pos['current_price']
                    })
                    continue
            
            # === 支撑位跌破加速止损 ===
            # 跌破关键支撑位 = 技术面破位，不等止损线直接卖
            broken_sup = pos_tech.get('broken_support', 0)
            if pnl_pct < -0.02 and broken_sup > 0:
                # broken_support > 0 说明有刚跌破的支撑位
                actions.append({
                    "action": "SELL",
                    "symbol": pos['symbol'],
                    "name": pos['name'],
                    "reason": f"支撑破位止损: 跌破支撑{broken_sup:.2f}, 亏损{pnl_pct*100:+.1f}%",
                    "shares": pos['shares'],
                    "price": pos['current_price']
                })
                continue
        
        # === 时间止损 (Time Stop) ===
        # 持仓天数阈值根据市场状态自适应: 牛市宽松(25天)，熊市收紧(15天)
        time_stop_days = 20  # 默认震荡市
        if regime == 'bull':
            time_stop_days = 25  # 牛市给更多时间发酵
        elif regime == 'bear':
            time_stop_days = 12  # 熊市快速止损换票（加速换仓）
        
        # 熊市时间止损扩大亏损容忍: 小亏(-5%以内)也清掉，别死扛
        time_stop_loss_floor = -0.05 if regime == 'bear' else -0.03
        
        # 时间止损盈利上限: 牛市只清微利(<1.5%)，震荡/熊市清<3%
        time_stop_profit_cap = 0.015 if regime == 'bull' else 0.03
        
        if buy_date:
            hold_days_ts = _trading_days_since(buy_date)
            if hold_days_ts >= 0 and hold_days_ts >= time_stop_days and time_stop_loss_floor <= pnl_pct <= time_stop_profit_cap:
                    actions.append({
                        "action": "SELL",
                        "symbol": pos['symbol'],
                        "name": pos['name'],
                        "reason": f"时间止损: 持仓{hold_days_ts}天无明显盈亏({pnl_pct*100:+.1f}%)",
                        "shares": pos['shares'],
                        "price": pos['current_price']
                    })
                    continue
        
        # === 追踪止损 (Trailing Stop) ===
        # 当盈利超过一定比例后，启用追踪止损：从最高点回撤即卖出
        peak_price = pos.get('peak_price', pos['avg_cost'])
        if pos['current_price'] > peak_price:
            peak_price = pos['current_price']
        
        trail_activation = 1.04 if regime == 'bear' else 1.10  # 熊市4%即激活追踪止损
        if peak_price > pos['avg_cost'] * trail_activation:
            trail_drawdown = (peak_price - pos['current_price']) / peak_price
            # ATR自适应追踪止损: 用1.5×ATR%代替固定百分比
            # 上限从10%降到7%，避免高波动股利润大幅回吐
            trail_threshold = 0.05  # 默认5%
            if pos_tech:
                pos_atr_pct = pos_tech.get('atr_pct', 0)
                if pos_atr_pct > 0:
                    trail_threshold = max(0.03, min(pos_atr_pct * 1.5 / 100, 0.07))
            if regime == 'bear':
                trail_threshold = min(trail_threshold, 0.04)  # 熊市上限4%
            
            # === 阶梯利润底线 (Profit Floor Lock) ===
            # 利润达到每个里程碑后, 止损线永久提升到该里程碑的一定比例
            # 例: 峰值+12% → 底线+6%, 峰值+8% → 底线+3%, 峰值+5% → 底线+1%
            peak_gain = (peak_price - pos['avg_cost']) / pos['avg_cost']
            profit_floor = None
            if peak_gain >= 0.15:
                profit_floor = 0.08  # 峰值>=15%, 利润底线8%
            elif peak_gain >= 0.12:
                profit_floor = 0.06  # 峰值>=12%, 利润底线6%
            elif peak_gain >= 0.08:
                profit_floor = 0.03  # 峰值>=8%, 利润底线3%
            elif peak_gain >= 0.05:
                profit_floor = 0.01  # 峰值>=5%, 利润底线1%
            
            if profit_floor is not None and pnl_pct < profit_floor:
                actions.append({
                    "action": "SELL",
                    "symbol": pos['symbol'],
                    "name": pos['name'],
                    "reason": f"利润底线止损: 峰值{peak_gain*100:+.1f}%→底线{profit_floor*100:.0f}%, 当前{pnl_pct*100:+.1f}%跌破",
                    "shares": pos['shares'],
                    "price": pos['current_price']
                })
                continue
            
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
        
        # === ATR自适应止损 + 情绪/市场状态调节 + 止损自学习 ===
        stop_loss = STOP_LOSS  # 默认-8%
        atr_stop = None
        if pos_tech:
            atr_pct = pos_tech.get('atr_pct', 0)
            if atr_pct > 0:
                atr_stop = -(atr_pct * 2) / 100
                atr_stop = max(min(atr_stop, -0.03), -0.15)
        
        # 市场状态调节基准
        if regime:
            from market_regime import get_regime_stop_loss
            stop_loss = get_regime_stop_loss(regime)
        
        # 如果有ATR数据，取ATR止损和市场止损中更保守的（更紧的）
        if atr_stop is not None:
            stop_loss = max(stop_loss, atr_stop)  # max because both are negative
        
        # === 止损自学习: 根据历史止损效果微调 ===
        # 如果历史止损多数是“错误止损”(止损后股价反弹), 则适当放宽
        try:
            from stock_picker import analyze_stop_loss_effectiveness
            sl_analysis = analyze_stop_loss_effectiveness()
            if sl_analysis and sl_analysis.get('stop_adjustment', 0) > 0:
                adj = sl_analysis['stop_adjustment'] / 100  # 1% or 2%
                stop_loss = stop_loss - adj  # 放宽(e.g. -5% → -7%)
                stop_loss = max(stop_loss, -0.15)  # 最宽不超过-15%
        except:
            pass
        
        # 情绪再调节（注意: 贪婪+熊市是陷阱信号，不放宽止损）
        if sentiment_score < 35:  # 市场恐慌时收紧止损
            stop_loss = max(stop_loss, -0.05)  # 不低于-5%
        elif sentiment_score > 75 and regime != 'bear':  # 乐观+非熊市才放宽
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
        
        # === 阶梯止盈 (ATR自适应) ===
        # 根据个股波动率动态设定止盈档位，而非固定12%/20%/30%
        tp1, tp2, tp3 = 0.12, 0.20, 0.30  # 默认档位
        if pos_tech:
            pos_atr = pos_tech.get('atr_pct', 0)
            if pos_atr > 0:
                # 低波股(ATR<2%): 8%/15%/25% — 更早锁利
                # 高波股(ATR>4%): 15%/25%/40% — 给更多空间
                tp1 = max(0.06, min(pos_atr * 4 / 100, 0.15))
                tp2 = max(0.12, min(pos_atr * 7 / 100, 0.30))
                tp3 = max(0.20, min(pos_atr * 10 / 100, 0.45))
        
        if pnl_pct >= tp3:  # 最高档，止盈全部
            actions.append({
                "action": "SELL",
                "symbol": pos['symbol'],
                "name": pos['name'],
                "reason": f"止盈: 盈利{pnl_pct*100:.1f}% ≥{tp3*100:.0f}%",
                "shares": pos['shares'],
                "price": pos['current_price']
            })
        elif pnl_pct >= tp2:  # 中档，止盈一半
            half = (pos['shares'] // 200) * 100
            if half >= 100:
                actions.append({
                    "action": "SELL",
                    "symbol": pos['symbol'],
                    "name": pos['name'],
                    "reason": f"阶梯止盈: 盈利{pnl_pct*100:.1f}% ≥{tp2*100:.0f}%, 卖出一半",
                    "shares": half,
                    "price": pos['current_price']
                })
        elif pnl_pct >= tp1:  # 低档，止盈1/3
            third = (pos['shares'] // 300) * 100
            if third >= 100:
                actions.append({
                    "action": "SELL",
                    "symbol": pos['symbol'],
                    "name": pos['name'],
                    "reason": f"阶梯止盈: 盈利{pnl_pct*100:.1f}% ≥{tp1*100:.0f}%, 卖出1/3",
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
    
    # === 连亏检测 — 含时间衰减 ===
    # 连亏不是永久的: 最后一次止损距今越久, 连亏的惩罚效果越弱
    # 超过5个交易日无止损, 连亏计数每多1天减1次(最低0)
    loss_streak = 0
    try:
        import sqlite3
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT direction, reason, trade_date FROM trades ORDER BY id DESC LIMIT 15")
        recent_sells = []
        last_stop_date = None
        for row in c.fetchall():
            if row[0] == 'SELL':
                recent_sells.append(row[1] or '')
                if last_stop_date is None and '止损' in (row[1] or ''):
                    last_stop_date = row[2]
        conn.close()
        # 统计连续止损次数
        for reason in recent_sells:
            if '止损' in reason:
                loss_streak += 1
            else:
                break
        
        # 时间衰减: 最后一次止损距今>5个交易日, 连亏感知减弱
        if loss_streak >= 3 and last_stop_date:
            try:
                from datetime import datetime as _dt
                last_dt = _dt.strptime(last_stop_date, '%Y-%m-%d').date()
                days_since = (date.today() - last_dt).days
                # 排除周末粗算交易日
                _wk = days_since // 7
                trading_days_since = days_since - _wk * 2
                if trading_days_since > 5:
                    decay = trading_days_since - 5  # 每多1个交易日减1
                    loss_streak = max(0, loss_streak - decay)
            except:
                pass
        
        if loss_streak >= 3:
            warnings.append(f"⚠️ 连续{loss_streak}次止损! 建议降低仓位+提高选股门槛")
    except:
        pass
    
    return {"healthy": len(warnings) == 0, "warnings": warnings, "loss_streak": loss_streak}
