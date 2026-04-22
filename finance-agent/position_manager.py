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
STOP_LOSS_BLACKLIST_DAYS = 5  # 止损后5个交易日内不买回(v5.41: 从8缩短,98%现金闲置说明太保守)


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


def get_recent_strategy_performance() -> dict:
    """获取最近策略性能数据 (胜率、Sharpe等)
    
    Returns: {'strategy': {...}, 'sector': {...}}
    """
    try:
        import sqlite3
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        cutoff = (date.today() - timedelta(days=30)).isoformat()
        c.execute("""SELECT strategy, AVG(pnl) as avg_pnl, COUNT(*) as trades
                     FROM trades WHERE direction='SELL' AND trade_date >= ? GROUP BY strategy""", (cutoff,))
        results = {'strategy': {}, 'sector': {}}
        for strat, avg_pnl, cnt in c.fetchall():
            if cnt >= 2:
                results['strategy'][strat] = {'hit_rate': 50 + (avg_pnl * 5)}  # 简化计算
        conn.close()
        return results
    except:
        return {'strategy': {}, 'sector': {}}


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
    
    # v5.49: 胜率高时敢加仓(max 30%)
    # 逻辑: 胜率>60%时，根据胜率提升30%
    try:
        from config import KELLY_MAX_POSITION, KELLY_WIN_RATE_BOOST
        # 尝试获取板块最近性胜率
        perf = get_recent_strategy_performance().get('sector', {}).get(sector, {})
        hit_rate_pct = perf.get('hit_rate', 50)
        win_rate = hit_rate_pct / 100
        
        if win_rate > 0.6:
            # 敢加仓：基于(胜率-50%) * 0.05系数提升
            boost_pct = (win_rate - 0.5) * KELLY_WIN_RATE_BOOST
            adjusted = min(adjusted * (1 + boost_pct), KELLY_MAX_POSITION)
    except:
        pass  # 性能数据不可用时省略
    
    # v5.50 新增: 现金闲置激进模式
    # 当现金>90% 且不是极端熊市 时，Kelly上限上提2.5%(0.25→0.35)
    # 逻辑: 现金过剩说明选股过于保守，应激进消耗闲置
    try:
        from trading_engine import get_account
        acc = get_account()
        if acc:
            total_value = acc.get('total_value', 1e6)
            cash = acc.get('cash', total_value)
            cash_ratio = cash / total_value if total_value > 0 else 1.0
            
            # 简单熊市检测：最近10天亏损>50%次数
            is_extreme_bear = False
            try:
                import sqlite3
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                cutoff = (date.today() - timedelta(days=10)).isoformat()
                c.execute("""SELECT COUNT(*) FROM trades WHERE direction='SELL' AND reason LIKE '%止损%' AND trade_date >= ?""", (cutoff,))
                sl_count = c.fetchone()[0] or 0
                conn.close()
                if sl_count > 5:  # 10天内止损>5次说明是熊市
                    is_extreme_bear = True
            except:
                pass
            
            # 激进激励: 现金>90% + 不是极端熊市
            if cash_ratio > 0.90 and not is_extreme_bear:
                # Kelly上限从0.25/0.15/0.10等提升2.5%
                params['max_kelly'] = min(params['max_kelly'] + 0.025, 0.35)
                # v5.52优化: 激进系数从1.06→1.10 (+4% → +10%资金效率提升)
                adjusted = min(adjusted * (1 + 0.10), params['max_kelly'])
    except:
        pass  # 账户查询失败时保持默认
    
    # 限制在合理范围
    return min(adjusted, params['max_kelly'])


def check_high_sharpe_holdings() -> None:
    """v5.49: 对历史高Sharpe比的持仓加强保护，止损容错放宽
    
    逻辑: 如果某持仓历史Sharpe>1.5，提高其止损容错(放宽2%)
    
    Returns: None (更新内部状态)
    """
    try:
        import sqlite3
        from datetime import date as _date
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # 查询所有历史持仓的Sharpe比
        c.execute("""SELECT symbol, SUM(pnl) as total_pnl, COUNT(*) as trades 
                     FROM trades WHERE direction='SELL' GROUP BY symbol HAVING trades >= 3""")
        high_sharpe = {}
        for symbol, total_pnl, trades in c.fetchall():
            if total_pnl is not None and trades >= 3:
                avg_ret = total_pnl / trades
                # 简化Sharpe估计: 平均收益 / 风险(这里用交易数代理)
                # 真实应该用std, 但数据库中没有, 先用近似
                sharpe_est = avg_ret * (trades ** 0.5)  # 粗略Sharpe估计
                if sharpe_est > 1.5:
                    high_sharpe[symbol] = sharpe_est
        
        # 对高Sharpe持仓更新记录 (可在check_dynamic_stop中使用)
        # 这里只记录, 不修改DB, 由调用方在check_dynamic_stop中应用
        if high_sharpe:
            print(f"  ✨ 高Sharpe持仓检测: {len(high_sharpe)}只(Sharpe>1.5)，加强保护")
        
        conn.close()
        return high_sharpe
    except:
        return {}


def get_low_win_rate_blacklist() -> set:
    """v5.49: 统计最近30天胜率<40%的信号，加入黑名单
    
    逻辑: 查询trading.db的trades表，统计各信号的胜率
    Returns: {signal_name} 集合，选股时需检查
    """
    try:
        import sqlite3
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        cutoff = (date.today() - timedelta(days=30)).isoformat()
        
        # 统计各信号的止损/止盈比例
        c.execute("""SELECT reason, COUNT(*) as cnt FROM trades 
                     WHERE direction='SELL' AND trade_date >= ? 
                     GROUP BY reason""", (cutoff,))
        signal_stats = {}
        for reason, cnt in c.fetchall():
            # 从reason中提取信号名 (e.g., "止损: 信号名...")
            if '止损' in reason or '止盈' in reason:
                # 简化处理：按reason分类
                signal_name = reason.split(':')[0] if ':' in reason else reason
                signal_stats[signal_name] = signal_stats.get(signal_name, 0) + (1 if '止损' in reason else -1)
        
        # 识别低胜率信号(止损多于止盈)
        blacklist = set()
        for signal, score in signal_stats.items():
            if score > 0:  # 止损多于止盈
                # 计算胜率
                total = 0
                wins = 0
                # 重新查询准确的胜率
                c.execute("""SELECT reason FROM trades WHERE reason LIKE ? AND trade_date >= ?""",
                          (f"%{signal}%", cutoff))
                for (r,) in c.fetchall():
                    total += 1
                    if '止盈' in r:
                        wins += 1
                
                win_rate = wins / total if total > 0 else 0.5
                if win_rate < 0.40:  # 胜率<40%
                    blacklist.add(signal)
                    print(f"  ☠️ 低胜率黑名单: {signal} (胜率{win_rate*100:.0f}%<40%)")
        
        conn.close()
        return blacklist
    except Exception as e:
        print(f"  ⚠️ 黑名单检查失败: {e}")
        return set()


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
            # OBV量价背离 + 盈利 → 减半仓（需盈利15%+才触发，避免过早减仓）
            if (pnl_pct >= 0.15 and pos_tech.get('obv_price_diverge')):
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
                actions.append({
                    "action": "SELL",
                    "symbol": pos['symbol'],
                    "name": pos['name'],
                    "reason": f"支撑破位止损: 跌破支撑{broken_sup:.2f}, 亏损{pnl_pct*100:+.1f}%",
                    "shares": pos['shares'],
                    "price": pos['current_price']
                })
                continue
            
            # === 阴跌主动减仓 (v5.48) ===
            # 持仓超过7天 + 浮亏 + 阴跌模式(10天中7天跌) → 主动减半仓
            if pos_tech.get('slow_bleed') and pnl_pct < 0 and pos['shares'] >= 200:
                _hold_sb = _trading_days_since(buy_date) if buy_date else 0
                if _hold_sb >= 7:
                    half = (pos['shares'] // 200) * 100
                    if half >= 100:
                        actions.append({
                            "action": "SELL",
                            "symbol": pos['symbol'],
                            "name": pos['name'],
                            "reason": f"阴跌减仓: 持{_hold_sb}天亏{pnl_pct*100:.1f}%+10天中{int(pos_tech.get('down_day_ratio_10d',0)*10)}天下跌,主动减半仓",
                            "shares": half,
                            "price": pos['current_price']
                        })
                        continue
        
        # === 时间止损 (Time Stop) ===
        # 持仓天数阈值根据市场状态自适应: 牛市宽松(25天)，熊市收紧(12天)
        time_stop_days = 20  # 默认震荡市
        if regime == 'bull':
            time_stop_days = 25  # 牛市给更多时间发酵
        elif regime == 'bear':
            time_stop_days = 12  # 熊市快速止损换票（加速换仓）
        
        # v5.48: PnL轨迹自适应时间止损
        # 如果持仓期间PnL持续下降(每天都比前一天差)，提前触发时间止损
        if pos_tech and buy_date:
            _hold_d = _trading_days_since(buy_date)
            if _hold_d >= 7 and pnl_pct < 0.01:
                # 检查近5日收盘价是否持续下降
                try:
                    from data_collector import get_stock_daily
                    _df = get_stock_daily(pos['symbol'], 30)
                    _closes = _df['收盘'].astype(float) if _df is not None else None
                    if _closes is not None and len(_closes) >= 5:
                        _recent5 = _closes.tail(5).tolist()
                        _declining = all(_recent5[i] <= _recent5[i-1] for i in range(1, len(_recent5)))
                        if _declining:
                            time_stop_days = min(time_stop_days, _hold_d)  # 立即触发
                            print(f"  ⚠️ {pos['name']} 连续5日下行轨迹，提前时间止损")
                except:
                    pass
        
        # 熊市时间止损扩大亏损容忍: 小亏(-5%以内)也清掉，别死扛
        time_stop_loss_floor = -0.05 if regime == 'bear' else -0.03
        
        # 时间止损盈利上限: 牛市只清微利(<1.5%)，震荡/熊市清<3%
        time_stop_profit_cap = 0.015 if regime == 'bull' else 0.03
        
        # v5.50 新增: 市场暴跌日止损容错机制
        # 当市场跌停>5只或指数日跌>3% 时，整日不触发时间止损（保护风险资产度过回调）
        from datetime import datetime as dt
        today_market_crash = False
        try:
            from data_collector import get_market_sentiment, get_stock_daily
            sentiment = get_market_sentiment()
            limit_down_count = sentiment.get('limit_down_count', 0) or 0
            
            if limit_down_count > 5:
                today_market_crash = True
            else:
                # 检查指数跌幅
                idx_df = get_stock_daily('000001', 10)
                if idx_df is not None and len(idx_df) >= 2:
                    today_close = float(idx_df.iloc[-1]['收盘'])
                    yest_close = float(idx_df.iloc[-2]['收盘'])
                    idx_chg = (today_close - yest_close) / yest_close
                    if idx_chg < -0.03:
                        today_market_crash = True
        except:
            pass
        
        if buy_date:
            hold_days_ts = _trading_days_since(buy_date)
            # v5.50: 暴跌日容错 - 跳过时间止损检查
            if not today_market_crash and hold_days_ts >= 0 and hold_days_ts >= time_stop_days and time_stop_loss_floor <= pnl_pct <= time_stop_profit_cap:
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
                # v5.43: 动量确认追踪止损 — 只有动量也转弱才触发
                # 避免"强势股正常回调"被误止损(历史60%错误止损的主因)
                momentum_weak = True  # 默认触发
                if pos_tech and trail_drawdown < trail_threshold * 1.5:
                    # 回撤不太大时检查动量:MACD仍看多且RSI>40说明只是正常回调
                    _m = pos_tech.get('macd_signal', '')
                    _r = pos_tech.get('rsi14', 50)
                    if _m in ('bullish', 'golden_cross') and _r > 40:
                        momentum_weak = False
                        # 不触发追踪止损,但记录观察
                        print(f"  👀 {pos['name']} 回撤{trail_drawdown*100:.1f}%但动量仍强(MACD={_m},RSI={_r:.0f}),暂缓止损")
                
                if momentum_weak:
                    actions.append({
                        "action": "SELL",
                        "symbol": pos['symbol'],
                        "name": pos['name'],
                        "reason": f"追踪止损: 高点{peak_price:.2f}回撤{trail_drawdown*100:.1f}%+动量确认转弱",
                        "shares": pos['shares'],
                        "price": pos['current_price']
                    })
                    continue
                else:
                    continue  # 动量仍强,暂不止损
        
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
        # 如果历史止损多数是"错误止损"(止损后股价反弹), 则适当放宽
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
        
        # === 趋势恶化预警减仓 v5.47 ===
        # 持仓超5天+浮亏+多个技术面恶化信号 → 主动减半仓,不等止损线
        if pos_tech and pnl_pct < 0 and pnl_pct > stop_loss:
            _bad_signals = 0
            if pos_tech.get('weekly_trend') == 'down':
                _bad_signals += 2
            if pos_tech.get('macd_signal') in ('death_cross', 'bearish'):
                _bad_signals += 1
            if pos_tech.get('lower_low'):
                _bad_signals += 1
            if pos_tech.get('cmf_20', 0) < -0.1:
                _bad_signals += 1
            if pos_tech.get('obv_price_diverge'):
                _bad_signals += 1
            
            _hold = _trading_days_since(buy_date) if buy_date else 0
            if _bad_signals >= 3 and _hold >= 5 and pos['shares'] >= 200:
                half = (pos['shares'] // 200) * 100
                if half >= 100:
                    actions.append({
                        "action": "SELL",
                        "symbol": pos['symbol'],
                        "name": pos['name'],
                        "reason": f"趋势恶化减仓: 亏损{pnl_pct*100:+.1f}%+{_bad_signals}个恶化信号,主动减半仓",
                        "shares": half,
                        "price": pos['current_price']
                    })
                    continue
        
        # === 梯度止损 v5.39 ===
        # 接近止损线时先减半仓(预警区), 真正触发才清仓
        # 避免一次性全卖后股价反弹的"错误止损"问题
        stop_warning_zone = stop_loss * 0.7  # 预警区=止损线的70% (如止损-8%,预警-5.6%)
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
        elif pnl_pct <= stop_warning_zone and pos['shares'] >= 200:
            # 预警区: 先减半仓, 降低风险但保留反弹机会
            half = (pos['shares'] // 200) * 100
            if half >= 100:
                actions.append({
                    "action": "SELL",
                    "symbol": pos['symbol'],
                    "name": pos['name'],
                    "reason": f"止损预警减仓: 亏损{pnl_pct*100:.1f}%接近止损线{stop_loss*100:.0f}%,先减半仓",
                    "shares": half,
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
    
    # === 资金闲置告警 ===
    # 96%现金是大问题，提醒用户/系统
    if total_value > 0:
        cash_pct = 1.0 - sum(p['current_price'] * p['shares'] for p in positions) / total_value
        if cash_pct > 0.90 and len(positions) <= 2:
            warnings.append(f"💤 现金{cash_pct*100:.0f}%闲置过多(仅{len(positions)}只持仓),建议适度建仓")
    
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


# ============================================================
# v5.56 新增: 赛道级策略路由 + Sharpe风险权重
# ============================================================

def get_sector_optimal_strategy(sector: str) -> dict:
    """
    获取特定赛道的最优策略组合 (基于回测数据)
    
    Args:
        sector: 赛道名称 (例: '科技成长', '新能源', '白马消费')
    
    Returns: {'primary': (strategy, weight), 'secondary': ..., 'hedge': ...}
    """
    try:
        from config import SECTOR_STRATEGY_ROUTING
        return SECTOR_STRATEGY_ROUTING.get(sector, {
            'primary': ('MACD_RSI', 0.65),
            'secondary': ('MULTI_FACTOR', 0.20),
            'hedge': ('MA_CROSS', 0.15)
        })
    except:
        # 默认返回科技成长策略
        return {
            'primary': ('MACD_RSI', 0.65),
            'secondary': ('MULTI_FACTOR', 0.20),
            'hedge': ('MA_CROSS', 0.15)
        }


def get_realtime_sharpe_ratio(lookback_days: int = 30) -> dict:
    """
    计算当前实盘的Sharpe比率 (用于动态风险调权)
    
    Returns: {'sharpe': float, 'quality': str, 'weight_multiplier': float}
             quality: 'high'(Sharpe>=1.5) | 'medium'(1.0-1.5) | 'low'(<1.0)
    """
    try:
        import sqlite3
        from config import DB_PATH
        from datetime import datetime, timedelta
        import math
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # 获取近30天的日收益
        cutoff = (datetime.now() - timedelta(days=lookback_days)).isoformat()
        c.execute("""
            SELECT DATE(trade_date) as d, SUM(CASE WHEN direction='SELL' THEN profit ELSE 0 END) as daily_pnl
            FROM trades
            WHERE trade_date >= ?
            GROUP BY DATE(trade_date)
            ORDER BY d
        """, (cutoff,))
        
        daily_returns = []
        for row in c.fetchall():
            if row[1] is not None:
                daily_returns.append(row[1])
        
        conn.close()
        
        if len(daily_returns) < 5:
            return {'sharpe': 0.0, 'quality': 'unknown', 'weight_multiplier': 1.0}
        
        # 计算Sharpe比率 (简化: 假设无风险利率为0)
        mean_ret = sum(daily_returns) / len(daily_returns)
        variance = sum((r - mean_ret) ** 2 for r in daily_returns) / len(daily_returns)
        std_dev = math.sqrt(variance) if variance > 0 else 0.001
        
        sharpe = (mean_ret / std_dev) * math.sqrt(252) if std_dev > 0 else 0
        
        # 风险等级判定
        if sharpe >= 1.5:
            quality = 'high'
            multiplier = 1.0  # 100%权重
        elif sharpe >= 1.0:
            quality = 'medium'
            multiplier = 0.5  # 50%权重
        elif sharpe >= 0.5:
            quality = 'low'
            multiplier = 0.25  # 25%权重
        else:
            quality = 'very_low'
            multiplier = 0.0  # 黑名单
        
        return {'sharpe': round(sharpe, 2), 'quality': quality, 'weight_multiplier': multiplier}
    
    except Exception as e:
        print(f"⚠️ 无法计算实时Sharpe: {e}")
        return {'sharpe': 0.0, 'quality': 'unknown', 'weight_multiplier': 1.0}


def get_strategy_risk_weight(strategy_name: str, sector: str = '') -> float:
    """
    获取策略的风险权重 (基于Sharpe和历史表现)
    
    v5.56: 只推荐 Sharpe>1.5的策略输出
    - Sharpe >= 1.5: 100% 权重 (推荐)
    - Sharpe 1.0-1.5: 50% 权重 (谨慎)
    - Sharpe 0.5-1.0: 25% 权重 (保守)
    - Sharpe < 0.5: 0% 权重 (黑名单)
    """
    try:
        import sqlite3
        conn = sqlite3.connect("/home/nikefd/finance-agent/data/backtest.db")
        c = conn.cursor()
        
        # 查策略的最新回测Sharpe
        c.execute("""
            SELECT sharpe_ratio FROM backtest_runs
            WHERE strategy LIKE ?
            ORDER BY created_at DESC LIMIT 1
        """, (f"%{strategy_name}%",))
        
        result = c.fetchone()
        conn.close()
        
        if not result:
            return 1.0  # 默认权重
        
        sharpe = result[0]
        
        from config import SHARPE_RISK_THRESHOLDS
        
        if sharpe >= SHARPE_RISK_THRESHOLDS['high_quality']:
            return 1.0   # 100%
        elif sharpe >= SHARPE_RISK_THRESHOLDS['medium_quality']:
            return 0.5   # 50%
        elif sharpe >= SHARPE_RISK_THRESHOLDS['low_quality']:
            return 0.25  # 25%
        else:
            return 0.0   # 黑名单
    
    except:
        return 1.0  # 异常时返回默认权重



# =================== v5.59 新增函数: 加仓/追踪止损/现金利用率 ===================

def get_cash_utilization_rate() -> float:
    """计算当前现金占比 (v5.59: 用于超激进模式判断)
    
    Returns: 现金占总资产的比例 (0.0-1.0)
    """
    try:
        import sqlite3
        from config import DB_PATH
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # 获取最新的账户快照
        c.execute('SELECT cash, total_value FROM daily_snapshots ORDER BY date DESC LIMIT 1')
        row = c.fetchone()
        conn.close()
        
        if not row or row[1] <= 0:
            return 0.98  # 默认高现金占比
        
        cash, total_value = row
        return cash / total_value
    except:
        return 0.95  # 异常时返回保守估计


def check_position_adding_condition(pos: dict, current_price: float) -> dict:
    """检查是否满足加仓条件 (v5.59)
    
    条件:
    - 持仓至少3天
    - 浮盈 > 2%
    - 技术面仍然强势
    
    Returns: {should_add: bool, reason: str, add_quantity: int, add_amount: float}
    """
    from config import POSITION_ADDING_CONDITIONS
    from data_collector import get_stock_daily, calculate_technical_indicators
    
    should_add = False
    reason = ""
    add_quantity = 0
    add_amount = 0.0
    
    try:
        # 条件1: 持仓天数
        hold_days = _trading_days_since(pos['buy_date'])
        if hold_days < POSITION_ADDING_CONDITIONS['min_hold_days']:
            reason = f"持仓仅{hold_days}天,需≥{POSITION_ADDING_CONDITIONS['min_hold_days']}"
            return {'should_add': False, 'reason': reason, 'add_quantity': 0, 'add_amount': 0}
        
        # 条件2: 浮盈百分比
        pnl_pct = (current_price - pos['avg_cost']) / pos['avg_cost']
        if pnl_pct < POSITION_ADDING_CONDITIONS['min_profit_pct']:
            reason = f"浮盈{pnl_pct*100:.1f}%,需≥{POSITION_ADDING_CONDITIONS['min_profit_pct']*100:.1f}%"
            return {'should_add': False, 'reason': reason, 'add_quantity': 0, 'add_amount': 0}
        
        # 条件3: 技术面强势检查
        df = get_stock_daily(pos['symbol'], 30)
        if df is None or df.empty:
            reason = "数据获取失败"
            return {'should_add': False, 'reason': reason, 'add_quantity': 0, 'add_amount': 0}
        
        tech = calculate_technical_indicators(df)
        if not tech:
            reason = "指标计算失败"
            return {'should_add': False, 'reason': reason, 'add_quantity': 0, 'add_amount': 0}
        
        # 检查技术面信号
        strong_signals = 0
        if tech.get('trend') in ['多头', '强势']:
            strong_signals += 1
        if tech.get('macd_signal') in ['bullish', 'golden_cross']:
            strong_signals += 1
        if tech.get('rsi14', 50) < 60:
            strong_signals += 1
        if tech.get('obv_trend', 0) > 5:
            strong_signals += 1
        
        if strong_signals < 2:
            reason = f"技术面信号仅{strong_signals}个,需≥2个"
            return {'should_add': False, 'reason': reason, 'add_quantity': 0, 'add_amount': 0}
        
        # 计算加仓数量
        kelly_ratio = kelly_position_size(pos['symbol']) / pos.get('expected_kelly_size', 1000)
        kelly_ratio = min(kelly_ratio, POSITION_ADDING_CONDITIONS['max_add_pct'])
        
        add_quantity = int(pos['shares'] * kelly_ratio * POSITION_ADDING_CONDITIONS['kelly_add_ratio'])
        add_amount = add_quantity * current_price
        
        if add_quantity > 0:
            should_add = True
            reason = f"满足加仓条件: 持{hold_days}d+浮盈{pnl_pct*100:.1f}%+{strong_signals}个强信号"
        else:
            reason = "加仓数量为0"
        
        return {
            'should_add': should_add,
            'reason': reason,
            'add_quantity': add_quantity,
            'add_amount': add_amount,
            'hold_days': hold_days,
            'pnl_pct': pnl_pct,
            'tech_signals': strong_signals
        }
    except Exception as e:
        return {
            'should_add': False,
            'reason': f"检查异常: {str(e)}",
            'add_quantity': 0,
            'add_amount': 0
        }


def check_trailing_stop_loss(pos: dict, current_price: float, peak_price: float = None) -> dict:
    """追踪止损检查 (v5.59)
    
    追踪止损逻辑:
    - 从峰值回撤 > 5% 触发止损
    - 或 8小时无新高 触发止损
    - 锁定95%的峰值收益
    
    Returns: {should_stop: bool, reason: str, stop_price: float}
    """
    from config import TRAILING_STOP_LOSS
    
    if not TRAILING_STOP_LOSS.get('enabled', False):
        return {'should_stop': False, 'reason': '追踪止损未启用', 'stop_price': None}
    
    try:
        if peak_price is None:
            peak_price = pos.get('peak_price', current_price)
        
        # 条件1: 从峰值回撤
        retracement = (peak_price - current_price) / peak_price
        if retracement > TRAILING_STOP_LOSS['peak_retracement_pct']:
            stop_price = peak_price * (1 - TRAILING_STOP_LOSS['peak_retracement_pct'])
            return {
                'should_stop': True,
                'reason': f"从峰值{peak_price:.2f}回撤{retracement*100:.1f}%>5%",
                'stop_price': stop_price,
                'peak_price': peak_price,
                'retracement_pct': retracement
            }
        
        # 条件2: 时间止损 (8小时无新高)
        last_update = pos.get('updated_at')
        if last_update:
            try:
                from datetime import datetime as dt_parser
                last_time = dt_parser.fromisoformat(last_update)
                hours_since = (datetime.now() - last_time).total_seconds() / 3600
                if hours_since > TRAILING_STOP_LOSS['time_stop_hours']:
                    return {
                        'should_stop': True,
                        'reason': f"{hours_since:.1f}小时无新高",
                        'stop_price': current_price,
                        'hours_since_update': hours_since
                    }
            except:
                pass
        
        return {'should_stop': False, 'reason': '未触发追踪止损', 'stop_price': None}
    except Exception as e:
        return {'should_stop': False, 'reason': f"检查异常: {str(e)}", 'stop_price': None}


def get_extreme_cash_mode_boost() -> dict:
    """获取超激进模式下的权重加成 (v5.59)
    
    返回每个策略在超激进模式下的权重倍数
    现金占比 > 98% 时激活
    
    Returns: {'MACD_RSI': 2.2, 'MULTI_FACTOR': 1.4, ...}
    """
    from config import EXTREME_CASH_RATIO, EXTREME_CASH_SIGNAL_BOOST
    
    cash_util = get_cash_utilization_rate()
    
    if cash_util > EXTREME_CASH_RATIO:
        return EXTREME_CASH_SIGNAL_BOOST  # 返回超激进权重
    else:
        # 返回正常权重 (都是1.0)
        return {
            'MACD_RSI': 1.0,
            'MULTI_FACTOR': 1.0,
            'TREND_FOLLOW': 1.0,
            'MA_CROSS': 1.0,
        }
