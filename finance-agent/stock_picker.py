"""多策略选股引擎 — 综合技术面+资金面+消息面+新闻舆情+AI研判"""

import akshare as ak
import pandas as pd
import json
import time
from datetime import datetime, timedelta
from data_collector import (
    get_stock_daily, get_realtime_quotes, get_market_sentiment,
    get_hot_stocks, get_stock_research_reports, get_stock_news,
    get_market_indices, get_sector_fund_flow, calculate_technical_indicators
)
from performance_tracker import classify_sector, record_recommendation
from position_manager import SECTOR_STRATEGY_WEIGHTS, get_sector_score_multiplier, kelly_position_size, get_stop_loss_blacklist, get_sector_stop_loss_penalty
from entry_quality import enrich_candidates_with_entry_quality, adjust_score_by_entry_quality


# === 信号持续性数据库 (Signal Persistence) ===
# 保存每日候选股快照，只有连续出现2+天的信号才可信
def save_candidate_snapshot(candidates: list):
    """保存今日候选股快照到数据库，供信号持续性检查使用"""
    try:
        import sqlite3
        from datetime import date as _date
        conn = sqlite3.connect('/home/nikefd/finance-agent/data/trading.db')
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS candidate_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_date TEXT,
            symbol TEXT,
            score INTEGER,
            signals TEXT,
            UNIQUE(snapshot_date, symbol)
        )''')
        today = _date.today().isoformat()
        for cand in candidates[:30]:  # 保存top 30
            code = cand.get('code', cand.get('symbol', ''))
            if not code:
                continue
            sigs = '+'.join(cand.get('signals', []))
            score = cand.get('score', 0)
            c.execute('INSERT OR REPLACE INTO candidate_snapshots (snapshot_date, symbol, score, signals) VALUES (?,?,?,?)',
                      (today, code, score, sigs))
        # 清理30天前的旧数据
        cutoff = (_date.today() - timedelta(days=30)).isoformat()
        c.execute('DELETE FROM candidate_snapshots WHERE snapshot_date < ?', (cutoff,))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"  ⚠️ 保存候选快照失败: {e}")


def get_signal_persistence(symbol: str) -> dict:
    """检查一只股票在过去几天是否持续出现在候选池中
    
    Returns: {days_appeared: int, consecutive: int, avg_score: float, persistent: bool}
    """
    try:
        import sqlite3
        from datetime import date as _date
        conn = sqlite3.connect('/home/nikefd/finance-agent/data/trading.db')
        c = conn.cursor()
        cutoff = (_date.today() - timedelta(days=7)).isoformat()
        c.execute('SELECT snapshot_date, score FROM candidate_snapshots WHERE symbol=? AND snapshot_date >= ? ORDER BY snapshot_date DESC',
                  (symbol, cutoff))
        rows = c.fetchall()
        conn.close()
        
        if not rows:
            return {'days_appeared': 0, 'consecutive': 0, 'avg_score': 0, 'persistent': False}
        
        days_appeared = len(rows)
        avg_score = sum(r[1] for r in rows) / len(rows)
        
        # 计算连续出现天数(从今天往前数)
        from datetime import datetime as _dt
        dates = sorted([r[0] for r in rows], reverse=True)
        consecutive = 1
        for i in range(1, len(dates)):
            d1 = _dt.strptime(dates[i-1], '%Y-%m-%d').date()
            d2 = _dt.strptime(dates[i], '%Y-%m-%d').date()
            # 允许跳过周末(差1-3天都算连续)
            if (d1 - d2).days <= 3:
                consecutive += 1
            else:
                break
        
        return {
            'days_appeared': days_appeared,
            'consecutive': consecutive,
            'avg_score': round(avg_score, 1),
            'persistent': consecutive >= 3  # v5.49: 从2升级到3天 - 提高信号可靠性
        }
    except:
        return {'days_appeared': 0, 'consecutive': 0, 'avg_score': 0, 'persistent': False}


# 各信号源对应的策略key（用于市场状态调节权重）
SIGNAL_STRATEGY_MAP = {
    '量价齐升': 'momentum',
    '创新高': 'momentum',
    '大笔买入': 'money_flow',
    '火箭发射': 'money_flow',
    '强势股': 'strong',
    '机构买入': 'institution',
    '机构增持': 'institution',
    '机构强烈推荐': 'institution',
}

# 信号历史胜率权重(基于回测和实盘经验)
SIGNAL_QUALITY_WEIGHTS = {
    '量价齐升': 1.2,     # 量价配合信号可靠
    '创新高': 0.9,       # 追高有风险
    '大笔买入': 1.1,     # 资金流入有效
    '火箭发射': 0.7,     # 短线信号容易反转
    '强势股': 0.8,       # 可能已到顶
    '机构买入': 1.3,     # 机构买入最可靠
    '机构增持': 1.2,
    '机构强烈推荐': 1.4,
}


def get_learned_signal_weights() -> dict:
    """从实际交易结果动态学习信号可靠性权重
    
    使用指数衰减加权: 近期交易权重更大，快速适应市场变化
    """
    try:
        import sqlite3
        from datetime import datetime as dt
        conn = sqlite3.connect('/home/nikefd/finance-agent/data/trading.db')
        c = conn.cursor()
        # 获取最近45天的买入交易及其最近一次卖出结果
        c.execute("""
            SELECT b.reason, b.trade_date,
                   CASE WHEN s.reason LIKE '%止损%' THEN 'loss'
                        WHEN s.reason LIKE '%止盈%' THEN 'win'
                        ELSE 'unknown' END as outcome
            FROM trades b
            LEFT JOIN trades s ON b.symbol = s.symbol AND s.direction = 'SELL' 
                AND s.id = (SELECT MIN(s2.id) FROM trades s2 WHERE s2.symbol = b.symbol AND s2.direction = 'SELL' AND s2.id > b.id)
            WHERE b.direction = 'BUY' AND b.trade_date >= date('now', '-45 days')
        """)
        rows = c.fetchall()
        conn.close()
        
        if len(rows) < 5:
            return {}  # 样本太少不学习
        
        today = dt.now()
        signal_stats = {}  # signal -> {weighted_wins, weighted_losses, total_weight}
        for reason, trade_date, outcome in rows:
            if not reason:
                continue
            # 指数衰减: 半衰期7天，越近的交易权重越大
            try:
                td = dt.strptime(trade_date, '%Y-%m-%d')
                days_ago = (today - td).days
                weight = 0.5 ** (days_ago / 7)  # 7天前权重0.5，14天前权重0.25
            except:
                weight = 0.1
            
            for sig_name in SIGNAL_QUALITY_WEIGHTS:
                if sig_name in reason:
                    if sig_name not in signal_stats:
                        signal_stats[sig_name] = {'weighted_wins': 0, 'weighted_losses': 0, 'total_weight': 0}
                    signal_stats[sig_name]['total_weight'] += weight
                    if outcome == 'win':
                        signal_stats[sig_name]['weighted_wins'] += weight
                    elif outcome == 'loss':
                        signal_stats[sig_name]['weighted_losses'] += weight
        
        # 计算学习后的权重调节
        adjustments = {}
        for sig, stats in signal_stats.items():
            total = stats['weighted_wins'] + stats['weighted_losses']
            if total >= 1.5:  # 加权总量够
                win_rate = stats['weighted_wins'] / total
                if win_rate < 0.25:
                    adjustments[sig] = 0.4   # 近期胜率极低，大幅降权
                elif win_rate < 0.4:
                    adjustments[sig] = 0.65  # 近期胜率低，适度降权
                elif win_rate > 0.6:
                    adjustments[sig] = 1.35  # 近期胜率高，提权
        return adjustments
    except:
        return {}


# 信号类别分组 — 用于共识门槛检查
SIGNAL_CATEGORIES = {
    '量价齐升': 'momentum',
    '创新高': 'momentum',
    '大笔买入': 'money_flow',
    '火箭发射': 'money_flow',
    '强势股': 'strong',
    '机构买入': 'institution',
    '机构增持': 'institution',
    '机构强烈推荐': 'institution',
    '新闻利好': 'news',
    '机构龙虎榜买入': 'lhb',
    '北向增持': 'northbound',
    '缩量企稳': 'technical',
    '均线收敛突破': 'technical',
    '底部放量': 'technical',
    '主力净流入': 'money_flow',
}


def get_trade_review_insights() -> dict:
    """交易复盘学习 — 分析历史赢/亏交易的技术条件，学习什么情况买入更容易赢
    
    Returns: {
        'win_patterns': {'near_support': 0.7, 'rsi_low': 0.6, ...},  # 赢的交易中该信号出现率
        'loss_patterns': {'near_resistance': 0.8, 'rsi_high': 0.5, ...},
        'score_adjustments': {'near_support': +8, 'near_resistance': -6, ...}
    }
    """
    try:
        import sqlite3
        conn = sqlite3.connect('/home/nikefd/finance-agent/data/trading.db')
        c = conn.cursor()
        # 获取近60天所有完整交易(买入+卖出)
        c.execute("""
            SELECT b.symbol, b.price as buy_price, b.trade_date as buy_date,
                   s.price as sell_price, s.reason as sell_reason
            FROM trades b
            JOIN trades s ON b.symbol = s.symbol AND s.direction = 'SELL'
                AND s.id = (SELECT MIN(s2.id) FROM trades s2 WHERE s2.symbol = b.symbol AND s2.direction = 'SELL' AND s2.id > b.id)
            WHERE b.direction = 'BUY' AND b.trade_date >= date('now', '-60 days')
        """)
        trades = c.fetchall()
        conn.close()
        
        if len(trades) < 5:
            return {}
        
        from data_collector import get_stock_daily, calculate_technical_indicators
        
        win_conditions = {'near_support': 0, 'strong_support': 0, 'z_under_neg1': 0, 
                         'higher_low': 0, 'volume_dryup': 0, 'weekly_up': 0, 'adx_strong': 0,
                         'near_vp_support': 0, 'below_poc': 0}
        loss_conditions = dict(win_conditions)
        win_count = 0
        loss_count = 0
        
        for symbol, buy_price, buy_date, sell_price, sell_reason in trades:
            is_win = sell_price > buy_price or '止盈' in (sell_reason or '')
            is_loss = '止损' in (sell_reason or '')
            
            if not is_win and not is_loss:
                continue
            
            # 回溯买入时的技术条件(用买入日前60天数据)
            try:
                df = get_stock_daily(symbol, 80)
                if df is None or df.empty:
                    continue
                # 截取到买入日附近的数据
                if '日期' in df.columns:
                    mask = df['日期'] <= buy_date
                    df_before = df[mask]
                    if len(df_before) < 20:
                        continue
                    tech = calculate_technical_indicators(df_before)
                else:
                    tech = calculate_technical_indicators(df)
                
                if not tech:
                    continue
                
                conds = win_conditions if is_win else loss_conditions
                if is_win:
                    win_count += 1
                else:
                    loss_count += 1
                
                if tech.get('near_support'):
                    conds['near_support'] += 1
                if tech.get('strong_support'):
                    conds['strong_support'] += 1
                if tech.get('price_z_score', 0) < -1:
                    conds['z_under_neg1'] += 1
                if tech.get('higher_low'):
                    conds['higher_low'] += 1
                if tech.get('volume_dryup'):
                    conds['volume_dryup'] += 1
                if tech.get('weekly_trend') == 'up':
                    conds['weekly_up'] += 1
                if tech.get('trend_strength') == 'strong':
                    conds['adx_strong'] += 1
                if tech.get('near_vp_support'):
                    conds['near_vp_support'] += 1
                if tech.get('below_poc'):
                    conds['below_poc'] += 1
            except:
                continue
        
        if win_count < 2 and loss_count < 2:
            return {}
        
        # 计算分数调整: 赢家交易中高频出现的条件加分，输家交易中高频的条件扣分
        adjustments = {}
        for cond in win_conditions:
            win_rate = win_conditions[cond] / max(win_count, 1)
            loss_rate = loss_conditions[cond] / max(loss_count, 1)
            diff = win_rate - loss_rate
            if diff > 0.2:
                adjustments[cond] = int(diff * 15)  # 赢家信号，加分
            elif diff < -0.2:
                adjustments[cond] = int(diff * 12)  # 输家信号，扣分
        
        return {
            'win_count': win_count,
            'loss_count': loss_count,
            'adjustments': adjustments,
        }
    except:
        return {}


def get_toxic_signal_combos() -> dict:
    """信号毒性检测 — 分析近期亏损交易的信号组合模式
    
    找出哪些信号组合总是亏钱(毒信号)，自动扣分
    Returns: {signal_combo_key: penalty_score}
    """
    try:
        import sqlite3
        conn = sqlite3.connect('/home/nikefd/finance-agent/data/trading.db')
        c = conn.cursor()
        # 获取近30天买入→止损的交易对
        c.execute("""
            SELECT b.reason, b.trade_date, s.reason as sell_reason,
                   (s.price - b.price) / b.price * 100 as loss_pct
            FROM trades b
            JOIN trades s ON b.symbol = s.symbol AND s.direction = 'SELL'
                AND s.id = (SELECT MIN(s2.id) FROM trades s2 WHERE s2.symbol = b.symbol AND s2.direction = 'SELL' AND s2.id > b.id)
            WHERE b.direction = 'BUY' AND b.trade_date >= date('now', '-30 days')
                AND s.reason LIKE '%止损%'
        """)
        losses = c.fetchall()
        
        # 统计买入→赢的交易作为对照
        c.execute("""
            SELECT b.reason
            FROM trades b
            JOIN trades s ON b.symbol = s.symbol AND s.direction = 'SELL'
                AND s.id = (SELECT MIN(s2.id) FROM trades s2 WHERE s2.symbol = b.symbol AND s2.direction = 'SELL' AND s2.id > b.id)
            WHERE b.direction = 'BUY' AND b.trade_date >= date('now', '-30 days')
                AND s.reason LIKE '%止盈%'
        """)
        wins = c.fetchall()
        conn.close()
        
        if len(losses) < 3:
            return {}
        
        # 提取亏损交易中频繁出现的信号关键词
        loss_signals = {}
        for reason, _, _, loss_pct in losses:
            if not reason:
                continue
            for keyword in ['量价齐升', '创新高', '大笔买入', '火箭', '强势股', '机构', 
                           '超跌', '北向', '龙虎榜', '新闻利好']:
                if keyword in reason:
                    loss_signals[keyword] = loss_signals.get(keyword, 0) + 1
        
        # 赢的交易中的信号
        win_signals = {}
        for (reason,) in wins:
            if not reason:
                continue
            for keyword in loss_signals:
                if keyword in reason:
                    win_signals[keyword] = win_signals.get(keyword, 0) + 1
        
        # 计算毒性: 亏损出现率 >> 盈利出现率 的信号
        toxic = {}
        total_losses = len(losses)
        total_wins = max(len(wins), 1)
        for sig, loss_count in loss_signals.items():
            loss_rate = loss_count / total_losses
            win_rate = win_signals.get(sig, 0) / total_wins
            # 亏损交易中出现率>50%且盈利交易中出现率<20% = 毒信号
            if loss_rate > 0.5 and win_rate < 0.2:
                toxic[sig] = -15  # 重扣
            elif loss_rate > 0.4 and loss_rate > win_rate * 2:
                toxic[sig] = -8   # 中扣
        
        return toxic
    except:
        return {}


def get_dynamic_score_threshold(regime: str = "", loss_streak: int = 0) -> int:
    """基于近期胜率动态调节最低买入分数门槛
    
    连亏越多、胜率越低 → 门槛越高，只买最强信号
    v5.25: 连亏加码进一步减弱，避免永远空仓
    """
    base = 25  # 正常市场下的最低分数
    
    # 近期胜率调节 — v5.30: 样本量<10时惩罚减半，避免小样本过拟合导致永远空仓
    try:
        from performance_tracker import get_performance_summary
        perf = get_performance_summary()
        hr = perf.get('hit_rate', 50)
        total = perf.get('total_recommendations', 0)
        # 样本量不足时惩罚减半
        penalty_mult = 0.5 if total < 10 else 1.0
        if hr < 20:
            base += int(5 * penalty_mult)  # 小样本: +2~3, 大样本: +5
        elif hr < 35:
            base += int(3 * penalty_mult)
    except:
        pass
    
    # 连亏调节 — 进一步放宽，让系统有机会交易
    if loss_streak >= 5:
        base += 3   # 从5降到3
    elif loss_streak >= 3:
        base += 2   # 从3降到2
    
    # 熊市调节
    if regime == 'bear':
        base += 3
    
    # v5.30: 门槛上限30分，防止永远空仓的死循环
    threshold = min(base, 30)
    
    # v5.39: 转换期降低门槛20% — bear→sideways是最佳布局时机
    try:
        from market_regime import detect_market_regime
        _regime_info = detect_market_regime()
        _transition = _regime_info.get('transition', 'none')
        if _transition in ('bear_to_sideways', 'sideways_to_bull'):
            threshold = int(threshold * 0.8)  # 降低20%
    except:
        pass
    
    # v5.35: 闲置资金递减门槛——连续无交易时逐步降低要求
    try:
        from indicator_attribution import get_idle_threshold_adjustment
        idle_adj = get_idle_threshold_adjustment()
        if idle_adj < 0:
            threshold = max(18, threshold + idle_adj)  # 最低18分
    except:
        pass
    
    # v5.41: 牛市+高现金闲置(>90%)时额外降低门槛，避免踏空
    try:
        from trading_engine import get_account
        acct = get_account()
        cash_ratio = acct['cash'] / max(acct['total_value'], 1)
        if cash_ratio > 0.90 and regime == 'bull':
            threshold = max(18, threshold - 5)  # 牛市98%闲置太离谱，再降5分
    except:
        pass
    
    return threshold


def check_risk_reward_ratio(tech: dict, regime: str = "") -> dict:
    """风险回报比门控 (Risk-Reward Ratio Gate)
    
    计算买入后的预期回报 vs 预期风险:
    - 回报 = 距最近阻力位/Fib阻力位的距离
    - 风险 = 距止损位(ATR止损或支撑破位)的距离
    - R:R >= 2.0 才值得买入
    
    Returns: {rr_ratio, reward_pct, risk_pct, pass}
    """
    if not tech:
        return {'rr_ratio': 0, 'pass': False}
    
    current = tech.get('current_price', 0)
    if current <= 0:
        return {'rr_ratio': 0, 'pass': False}
    
    # 预期风险: ATR止损距离 + 交易成本
    # v5.39: 纳入佣金(万三×2)+印花税(千一)+滑点(0.2%)≈ 0.22%单程→来回0.44%
    atr_pct = tech.get('atr_pct', 3)
    trading_cost_pct = 0.44  # 买卖一次的总交易成本
    risk_pct = max(atr_pct * 2 + trading_cost_pct, 3.0)  # 至少3%风险
    risk_pct = min(risk_pct, 10.0)    # 最多10%风险
    
    # 预期回报: 多种方式估算，取最保守
    reward_estimates = []
    
    # 方法1: 距最近阻力位
    res_dist = tech.get('resistance_distance_pct', 99)
    if res_dist < 30:
        reward_estimates.append(res_dist)
    
    # 方法2: 距Fib阻力位
    fib_res_dist = tech.get('fib_resistance_dist_pct', 99)
    if fib_res_dist < 30:
        reward_estimates.append(fib_res_dist)
    
    # 方法3: 基于ATR的合理目标(3x ATR)
    reward_estimates.append(atr_pct * 3)
    
    # 取最保守的回报估算
    reward_pct = min(reward_estimates) if reward_estimates else atr_pct * 2
    
    rr_ratio = reward_pct / risk_pct if risk_pct > 0 else 0
    
    # v5.39: 转换期降低R:R要求，熊市要求更高
    if regime == 'bear':
        min_rr = 2.5
    elif regime == 'transition':  # bear→sideways转换期
        min_rr = 1.5
    else:
        min_rr = 1.8
    
    return {
        'rr_ratio': round(rr_ratio, 2),
        'reward_pct': round(reward_pct, 2),
        'risk_pct': round(risk_pct, 2),
        'pass': rr_ratio >= min_rr,
        'min_rr': min_rr,
    }


def check_pullback_entry(tech: dict) -> dict:
    """回调入场过滤 (Pullback Entry Filter)
    
    避免在连涨后追高。理想入场:
    - 近期趋势向上(10日涨) + 近1-2日回调(当日跌或收在日内低位)
    - 或处于支撑位附近
    
    Returns: {is_pullback, entry_quality, reason}
    """
    if not tech:
        return {'is_pullback': True, 'entry_quality': 'neutral', 'reason': '无数据'}
    
    daily_chg = tech.get('daily_change_pct', 0)
    ret_10d = tech.get('stock_ret_10d', 0)
    rsi = tech.get('rsi14', 50)
    near_support = tech.get('near_support', False)
    near_fib_support = tech.get('near_fib_support', False)
    pct_b = tech.get('boll_pct_b', 0.5)
    z_score = tech.get('price_z_score', 0)
    
    # 最佳入场: 上升趋势中的回调
    if ret_10d > 2 and daily_chg < 0:
        return {'is_pullback': True, 'entry_quality': 'excellent', 
                'reason': f'上升趋势回调(10d+{ret_10d:.1f}%,今日{daily_chg:.1f}%)', 'bonus': 8}
    
    # 好的入场: 在支撑位附近
    if near_support or near_fib_support:
        return {'is_pullback': True, 'entry_quality': 'good',
                'reason': '支撑位入场', 'bonus': 5}
    
    # 好的入场: 超卖区域
    if z_score < -1.5 or pct_b < 0.1 or rsi < 35:
        return {'is_pullback': True, 'entry_quality': 'good',
                'reason': f'超卖区(Z={z_score:.1f},RSI={rsi:.0f})', 'bonus': 5}
    
    # 中性: 横盘或微涨
    if -1 < daily_chg < 2 and ret_10d < 5:
        return {'is_pullback': True, 'entry_quality': 'neutral',
                'reason': '常规入场', 'bonus': 0}
    
    # 差的入场: 连涨后追高
    if daily_chg > 3 or (ret_10d > 8 and daily_chg > 0):
        return {'is_pullback': False, 'entry_quality': 'poor',
                'reason': f'追涨入场(10d+{ret_10d:.1f}%,今日+{daily_chg:.1f}%)', 'bonus': -10}
    
    return {'is_pullback': True, 'entry_quality': 'neutral', 'reason': '一般', 'bonus': 0}


def calculate_entry_quality_score(tech: dict, signals: list, regime: str = "") -> int:
    """入场质量综合评分 (Entry Quality Score)
    
    独立于现有score系统，评估"这个入场时机好不好"(而非"这个股票好不好")
    满分100，低于40不入场
    
    维度:
    - 趋势对齐(0-25): 日线/周线/MACD方向一致
    - 位置优势(0-25): 在支撑位/超卖区/回调中
    - 量价确认(0-25): OBV/CMF/量比配合
    - 风险回报(0-25): R:R比合理
    """
    if not tech:
        return 0
    
    score = 0
    
    # === 趋势对齐 (0-25) ===
    trend_score = 0
    weekly = tech.get('weekly_trend', 'neutral')
    macd_sig = tech.get('macd_signal', '')
    trend = tech.get('trend', '')
    adx = tech.get('adx', 0)
    
    if weekly == 'up':
        trend_score += 8
    elif weekly == 'neutral':
        trend_score += 4
    
    if macd_sig in ('golden_cross', 'bullish'):
        trend_score += 8
    elif macd_sig == 'golden_cross':
        trend_score += 10
    
    if '多头' in trend:
        trend_score += 5
    elif '震荡' in trend:
        trend_score += 2
    
    if adx > 25:
        trend_score += 4  # 强趋势确认
    
    score += min(trend_score, 25)
    
    # === 位置优势 (0-25) ===
    pos_score = 0
    if tech.get('near_support'):
        pos_score += 8
    if tech.get('near_fib_support'):
        pos_score += 6
    if tech.get('strong_support'):
        pos_score += 5
    
    z = tech.get('price_z_score', 0)
    if z < -2:
        pos_score += 8
    elif z < -1:
        pos_score += 5
    elif z > 1.5:
        pos_score -= 5
    
    pct_b = tech.get('boll_pct_b', 0.5)
    if pct_b < 0.1:
        pos_score += 6
    elif pct_b < 0.3:
        pos_score += 3
    
    score += max(min(pos_score, 25), 0)
    
    # === 量价确认 (0-25) ===
    vol_score = 0
    obv_trend = tech.get('obv_trend', 0)
    if obv_trend > 0.1:
        vol_score += 8
    elif obv_trend < -0.1:
        vol_score -= 5
    
    cmf = tech.get('cmf_20', 0)
    if cmf > 0.1:
        vol_score += 8
    elif cmf > 0:
        vol_score += 4
    elif cmf < -0.1:
        vol_score -= 5
    
    vol_ratio = tech.get('volume_ratio', 1)
    if 1.0 < vol_ratio < 2.5:  # 温和放量最好
        vol_score += 6
    elif vol_ratio > 3:
        vol_score -= 3  # 异常放量不好
    
    if tech.get('volume_dryup'):
        vol_score += 5  # 缩量企稳
    
    score += max(min(vol_score, 25), 0)
    
    # === 风险回报 (0-25) ===
    rr_info = check_risk_reward_ratio(tech, regime)
    rr = rr_info['rr_ratio']
    if rr >= 3:
        score += 25
    elif rr >= 2.5:
        score += 20
    elif rr >= 2:
        score += 15
    elif rr >= 1.5:
        score += 8
    else:
        score += 0
    
    return score


def check_signal_consensus(signals: list, regime: str = "") -> tuple:
    """检查信号共识: 至少2个不同类别的信号同意才通过
    
    v5.27: 熊市反转信号豁免 — 超跌反弹/技术面底部信号本身就是独立策略,
    不需要多类别共识(因为反转信号很少同时出现在多个类别)
    
    Returns: (pass: bool, categories: set, category_count: int)
    """
    categories = set()
    has_reversal = False
    for sig in signals:
        sig_base = sig.split('×')[0].split('+')[0].split(':')[0]
        cat = SIGNAL_CATEGORIES.get(sig_base, 'other')
        categories.add(cat)
        # 检测是否含反转类信号
        if any(kw in sig for kw in ['超跌', '缩量企稳', '均线收敛', '看涨', '锤子', '早晨之星', '底部抬升']):
            has_reversal = True
    
    # 熊市反转信号豁免: 反转信号天然单类别,不要求多类别共识
    if regime == 'bear' and has_reversal and len(categories) >= 1:
        return True, categories, len(categories)
    
    return len(categories) >= 2, categories, len(categories)


def get_recent_strategy_performance() -> dict:
    """读取近期推荐绩效，动态调节策略可信度
    
    如果某策略近期命中率低于30%，降低其权重
    如果某板块近期表现好，提升其权重
    """
    try:
        from performance_tracker import get_performance_summary
        perf = get_performance_summary()
        
        strategy_mult = {}
        for s in perf.get('by_strategy', []):
            if s['total'] >= 3:  # 至少3次推荐才有统计意义
                hr = s['hit_rate']
                if hr >= 50:
                    strategy_mult[s['strategy']] = 1.2
                elif hr >= 30:
                    strategy_mult[s['strategy']] = 1.0
                else:
                    strategy_mult[s['strategy']] = 0.7  # 近期表现差，降权
        
        sector_mult = {}
        for s in perf.get('by_sector', []):
            if s['total'] >= 3:
                hr = s['hit_rate']
                if hr >= 50:
                    sector_mult[s['sector']] = 1.15
                elif hr < 25:
                    sector_mult[s['sector']] = 0.8
        
        return {'strategy': strategy_mult, 'sector': sector_mult}
    except:
        return {'strategy': {}, 'sector': {}}


def get_smart_money_candidates() -> list:
    """策略9: 主力资金异动扫描 (Smart Money Scanner)
    
    追踪当日主力大单净流入排行 + 技术面筛选:
    - 主力净流入为正且排名靠前
    - RSI不超买(< 70)
    - 非ST/退市
    - 结合技术面企稳信号(支撑位/MACD/底部抬升)给加分
    
    核心价值: 直接跟踪"聪明钱"的流向，比追涨/机构研报更实时
    """
    candidates = []
    try:
        try:
            df = ak.stock_individual_fund_flow_rank(indicator="今日")
            if df is not None and not df.empty:
                flow_col = None
                for col in df.columns:
                    if '主力净流入' in str(col) and '占比' not in str(col):
                        flow_col = col
                        break
                if flow_col is None:
                    for col in df.columns:
                        if '净额' in str(col) or '净流入' in str(col):
                            flow_col = col
                            break
                if flow_col:
                    df[flow_col] = pd.to_numeric(df[flow_col], errors='coerce')
                    df = df.dropna(subset=[flow_col])
                    df = df.sort_values(flow_col, ascending=False)
                    for _, row in df.head(40).iterrows():
                        code = str(row.get('代码', row.get('股票代码', '')))
                        name = str(row.get('名称', row.get('股票简称', '')))
                        net_flow = float(row.get(flow_col, 0) or 0)
                        if not code or len(code) < 6 or 'ST' in name or net_flow <= 0:
                            continue
                        net_flow_yi = net_flow / 1e8 if abs(net_flow) > 1e8 else (net_flow / 1e4 if abs(net_flow) > 1e4 else net_flow)
                        candidates.append({'code': code, 'name': name, 'signal': f'主力净流入{net_flow_yi:.1f}亿', 'score': min(int(abs(net_flow_yi) * 5), 15), 'net_flow': net_flow})
        except Exception as e:
            print(f"  主力资金排行获取失败: {e}")
        if not candidates:
            return []
        filtered = []
        for c in candidates[:20]:
            try:
                df_k = get_stock_daily(c['code'], 30)
                if df_k is None or df_k.empty or len(df_k) < 20:
                    continue
                tech = calculate_technical_indicators(df_k)
                if not tech:
                    continue
                rsi = tech.get('rsi14', 50)
                if rsi > 70 or tech.get('weekly_trend') == 'down' or tech.get('atr_pct', 3) > 6:
                    continue
                bonus = 0
                reasons = []
                if tech.get('near_support') or tech.get('near_fib_support'):
                    bonus += 6; reasons.append('支撑位')
                macd = tech.get('macd_signal', '')
                if macd in ('golden_cross', 'fresh_golden', 'bullish'):
                    bonus += 5; reasons.append(f'MACD{macd}')
                if tech.get('higher_low'):
                    bonus += 4; reasons.append('底部抬升')
                if tech.get('cmf_20', 0) > 0.05:
                    bonus += 4; reasons.append('CMF正')
                if tech.get('obv_trend', 0) > 0.1:
                    bonus += 3; reasons.append('OBV↑')
                if tech.get('volume_dryup'):
                    bonus += 5; reasons.append('缩量企稳')
                z = tech.get('price_z_score', 0)
                if z < -1:
                    bonus += 4; reasons.append(f'Z{z:.1f}')
                c['score'] += bonus
                if reasons:
                    c['signal'] += '+' + '+'.join(reasons[:3])
                filtered.append(c)
                time.sleep(0.2)
            except:
                continue
        return sorted(filtered, key=lambda x: -x['score'])[:10]
    except Exception as e:
        print(f"  主力资金扫描失败: {e}")
        return []



def get_rsi_extreme_reversal_candidates() -> list:
    """v5.50 新增 策略7.5: RSI极端超卖反弹信号 — 全市场
    
    核心逐辑：
    1. RSI(14)<20 且最近。2日RSI都<30 → 极端超卖信号
    2. 不要超跌股（跌幅>-15%）、不要已体量储力为负(cumulative volume < -20%)
    3. 按RSI极低整序，取top30
    
    权重: 0.8x (保守)
    """
    candidates = []
    try:
        from data_collector import get_stock_daily, calculate_technical_indicators
        import pandas as pd
        
        # 取两市所有A股
        all_stocks = []
        try:
            import akshare as ak
            # 根据RSI排厨找极端超卖股
            # 我们自己扫描手技股池，不RSI排基本不存在，使用旅游頎豆剪提供的笋广捷提取散户股
            all_stocks = ak.stock_zh_a_spot_em()[['代码', '名称']].head(200).values.tolist()
        except Exception as e:
            print(f"    ⚠️ 下载A股清单失败: {e}")
            return []
        
        # 扫描每一只股的RSI
        import sqlite3
        from datetime import date as _date, timedelta
        
        for code, name in all_stocks:
            try:
                # 取近日12日数据
                df = get_stock_daily(str(code), 14)
                if df is None or len(df) < 12:
                    continue
                
                # 计算技术指标
                tech = calculate_technical_indicators(df)
                if not tech:
                    continue
                
                rsi_today = tech.get('rsi14', 50)
                
                # 极端超卖探测: 今日RSI<20
                if rsi_today >= 20:
                    continue
                
                # 执二天RSI检查（执亊一天）
                if len(df) >= 2:
                    # 厚一元数据是最新的，执亊一天是候选
                    df_yesterday = df.iloc[:-1].reset_index(drop=True)
                    tech_yesterday = calculate_technical_indicators(df_yesterday)
                    rsi_yesterday = tech_yesterday.get('rsi14', 50) if tech_yesterday else 50
                else:
                    rsi_yesterday = rsi_today
                
                # 执亊RSI也需要<30 (探测持续超卖)
                if rsi_yesterday >= 30:
                    continue
                
                # 优化: 字体不超跌、不是趋新股、不是ST股
                if isinstance(name, str):
                    if '*ST' in name or 'ST' == name[:2]:
                        continue
                
                # 检查跌幅（最近月线）
                if len(df) >= 20:
                    price_low_20d = df['低'].astype(float).min()
                    price_close_today = float(df.iloc[-1]['收盘'])
                    drop_from_high = (price_close_today - price_low_20d) / price_low_20d
                    if drop_from_high < -0.15:  # 超跌15%+稍保守
                        continue
                
                candidates.append({
                    'code': str(code),
                    'name': name,
                    'signal': f'RSI极端超卖({rsi_today:.0f}/{rsi_yesterday:.0f})',
                    'score': min(80 - rsi_today, 15),  # RSI越低分数越高(上限15分)
                    'rsi_today': rsi_today,
                    'rsi_yesterday': rsi_yesterday,
                    'weight_multiplier': 0.8,  # 权重0.8x(保守)
                })
            except Exception as e:
                continue
        
        # 按RSI杰晴序，取top30
        candidates = sorted(candidates, key=lambda x: x.get('rsi_today', 50))
        return candidates[:30]
    except Exception as e:
        print(f"  RSI超卖扫描失败: {e}")
        return []


def get_bottom_breakout_candidates() -> list:
    """策略8: 底部放量突破扫描 — 全市场
    
    扫描近20日横盘缩量整理后突然放量上涨的股票:
    - 近10-20日振幅<10%(横盘整理)
    - 近5日成交量<20日均量的60%(缩量)
    - 今日放量(量比>1.5)且收阳线(涨>1%)
    - RSI 40-65(不超买不超卖,启动区)
    
    这种形态是经典的"缩量蓄力→放量启动",比追涨更安全
    """
    candidates = []
    try:
        # 获取两市活跃股票列表
        from data_collector import get_stock_daily, calculate_technical_indicators
        import akshare as ak
        
        # 用量比排行找今日放量的股票
        try:
            df = ak.stock_rank_lbsz_ths()
            if df is not None and not df.empty:
                for _, row in df.head(50).iterrows():
                    code = str(row.get('股票代码', ''))
                    lb = float(row.get('量比', 0) or 0)
                    chg = float(row.get('涨跌幅', 0) or 0)
                    
                    # 今日放量(量比>1.5)且上涨(>1%)
                    if lb < 1.5 or chg < 1.0 or chg > 8.0:
                        continue
                    # 排除ST
                    name = str(row.get('股票简称', ''))
                    if 'ST' in name:
                        continue
                    
                    candidates.append({
                        'code': code,
                        'name': name,
                        'signal': f'底部放量(量比{lb:.1f}+涨{chg:.1f}%)',
                        'score': 10,
                        'volume_ratio': lb,
                    })
        except Exception as e:
            print(f"  量比排行获取失败: {e}")
        
        if not candidates:
            return []
        
        # 二次筛选: 确认是底部整理后的突破,不是高位放量
        filtered = []
        for c in candidates[:25]:
            try:
                df_k = get_stock_daily(c['code'], 30)
                if df_k is None or df_k.empty or len(df_k) < 20:
                    continue
                tech = calculate_technical_indicators(df_k)
                if not tech:
                    continue
                
                rsi = tech.get('rsi14', 50)
                z_score = tech.get('price_z_score', 0)
                weekly = tech.get('weekly_trend', 'neutral')
                atr_pct = tech.get('atr_pct', 3)
                
                # 过滤条件: RSI适中(不超买)、不在下降通道
                if rsi > 65 or rsi < 25:
                    continue
                if weekly == 'down':
                    continue
                if z_score > 1.5:  # 已在高位
                    continue
                if atr_pct > 5:  # 波动太大的妖股
                    continue
                
                # 检查是否真的是底部整理: 近10日振幅<15%
                try:
                    closes = df_k['收盘'].astype(float).tail(10)
                    range_pct = (closes.max() - closes.min()) / closes.min() * 100
                    if range_pct > 15:  # 近10日振幅太大,不算底部整理
                        continue
                except:
                    continue
                
                # 加分项
                bonus = 0
                reasons = []
                if tech.get('ma_converge_breakout'):
                    bonus += 8
                    reasons.append('均线收敛')
                if tech.get('nr7') or tech.get('nr4'):
                    bonus += 5
                    reasons.append('NR7蓄力')
                if tech.get('near_support') or tech.get('near_fib_support'):
                    bonus += 5
                    reasons.append('支撑位')
                macd = tech.get('macd_signal', '')
                if macd in ('golden_cross', 'fresh_golden', 'bullish'):
                    bonus += 6
                    reasons.append(f'MACD{macd}')
                if tech.get('higher_low'):
                    bonus += 4
                    reasons.append('底部抬升')
                cmf = tech.get('cmf_20', 0)
                if cmf > 0.05:
                    bonus += 3
                    reasons.append('资金流入')
                
                c['score'] += bonus
                if reasons:
                    c['signal'] += '+' + '+'.join(reasons[:3])
                
                filtered.append(c)
                time.sleep(0.2)
            except:
                continue
        
        return sorted(filtered, key=lambda x: -x['score'])[:10]
    except Exception as e:
        print(f"  底部突破扫描失败: {e}")
        return []


def get_oversold_reversal_candidates() -> list:
    """策略7: 超跌反弹候选池 — 熊市专用
    
    主动扫描近期跌幅大但技术面出现企稳信号的股票
    不依赖动量/突破信号，而是寻找卖方耗尽+底部形态
    """
    candidates = []
    try:
        # 获取连续下跌的股票(同花顺连续下跌排行)
        try:
            df = ak.stock_rank_ljqd_ths()
            for _, row in df.head(40).iterrows():
                code = str(row.get('股票代码', ''))
                days_down = int(row.get('连续下跌天数', 0) or 0)
                cum_drop = float(row.get('累计跌幅', 0) or 0)
                # 筛选: 连跌5-15天、累计跌幅-8%~-25%(不要跌太多的雷股)
                if 5 <= days_down <= 15 and -25 <= cum_drop <= -8:
                    candidates.append({
                        'code': code,
                        'name': row.get('股票简称', ''),
                        'signal': f'超跌{days_down}天跌{cum_drop:.1f}%',
                        'score': min(abs(cum_drop), 20),  # 跌得越多基础分越高(有限度)
                        'days_down': days_down,
                        'cum_drop': cum_drop,
                    })
        except Exception as e:
            print(f"  超跌排行获取失败: {e}")
        
        # 二次筛选: 加载技术指标，只保留有企稳信号的
        filtered = []
        for c in candidates[:20]:
            try:
                df_k = get_stock_daily(c['code'], 60)
                if df_k is None or df_k.empty or len(df_k) < 20:
                    continue
                tech = calculate_technical_indicators(df_k)
                if not tech:
                    continue
                
                # 企稳信号检查: 至少满足2个
                reversal_signals = 0
                reasons = []
                
                rsi = tech.get('rsi14', 50)
                if rsi < 30:
                    reversal_signals += 1
                    reasons.append(f'RSI{rsi:.0f}')
                
                if tech.get('volume_dryup'):
                    reversal_signals += 1
                    reasons.append('缩量企稳')
                
                if tech.get('higher_low'):
                    reversal_signals += 1
                    reasons.append('底部抬升')
                
                if tech.get('bullish_candle'):
                    reversal_signals += 1
                    reasons.append('看涨K线')
                
                z = tech.get('price_z_score', 0)
                if z < -1.5:
                    reversal_signals += 1
                    reasons.append(f'Z{z:.1f}')
                
                wr = tech.get('williams_r', -50)
                if tech.get('wr_reversal'):
                    reversal_signals += 1
                    reasons.append('WR回升')
                
                if tech.get('near_fib_support'):
                    reversal_signals += 1
                    reasons.append('Fib支撑')
                
                if tech.get('macd_zero_cross_up') or tech.get('macd_signal') == 'golden_cross':
                    reversal_signals += 1
                    reasons.append('MACD转多')
                
                if tech.get('nr7') and tech.get('range_compression', 1.0) < 0.5:
                    reversal_signals += 1
                    reasons.append('NR7蓄力')
                
                if tech.get('macd_hist_bull_div'):
                    reversal_signals += 1
                    reasons.append('MACD柱背离')
                
                if reversal_signals >= 2:
                    c['signal'] += '+' + '+'.join(reasons[:3])
                    c['score'] += reversal_signals * 5
                    c['reversal_count'] = reversal_signals
                    filtered.append(c)
                
                time.sleep(0.2)
            except:
                continue
        
        return sorted(filtered, key=lambda x: -x['score'])[:15]
    except Exception as e:
        print(f"  超跌反弹扫描失败: {e}")
        return []


def get_momentum_candidates() -> list:
    """策略1: 动量策略 — 量价齐升+创新高"""
    candidates = []

    # 量价齐升 (v5.52优化: 从30改为45, +50%)
    try:
        df = ak.stock_rank_ljqs_ths()
        for _, row in df.head(45).iterrows():
            code = str(row.get('股票代码', ''))
            candidates.append({
                'code': code,
                'name': row.get('股票简称', ''),
                'signal': '量价齐升',
                'days': int(row.get('量价齐升天数', 0)),
                'score': min(int(row.get('量价齐升天数', 0)) * 3, 15),
            })
    except Exception as e:
        print(f"量价齐升获取失败: {e}")

    # 创新高 (v5.52优化: 从20改为28, +40%)
    try:
        time.sleep(0.5)
        df = ak.stock_rank_cxg_ths()
        for _, row in df.head(28).iterrows():
            code = str(row.get('股票代码', ''))
            existing = next((c for c in candidates if c['code'] == code), None)
            if existing:
                existing['signal'] += '+创新高'
                existing['score'] += 10
            else:
                candidates.append({
                    'code': code,
                    'name': row.get('股票简称', ''),
                    'signal': '创新高',
                    'score': 10,
                })
    except Exception as e:
        print(f"创新高获取失败: {e}")

    return candidates


def get_money_flow_candidates() -> list:
    """策略2: 资金流入 — 大笔买入+火箭发射"""
    candidates = []
    buy_counts = {}

    # 大笔买入统计（同一只股票出现多次=资金持续流入）
    try:
        df = ak.stock_changes_em(symbol='大笔买入')
        for _, row in df.iterrows():
            code = str(row.get('代码', ''))
            name = str(row.get('名称', ''))
            if code not in buy_counts:
                buy_counts[code] = {'name': name, 'count': 0}
            buy_counts[code]['count'] += 1

        # 多次大笔买入的股票
        for code, info in sorted(buy_counts.items(), key=lambda x: -x[1]['count']):
            if info['count'] >= 3:  # 至少3次大笔买入
                candidates.append({
                    'code': code,
                    'name': info['name'],
                    'signal': f'大笔买入×{info["count"]}',
                    'score': min(info['count'] * 3, 15),
                })
            if len(candidates) >= 25:  # v5.52优化: 从20改为25, +25%
                break
    except Exception as e:
        print(f"大笔买入获取失败: {e}")

    # 火箭发射（快速拉升信号）
    try:
        time.sleep(0.5)
        df = ak.stock_changes_em(symbol='火箭发射')
        rocket_counts = {}
        for _, row in df.iterrows():
            code = str(row.get('代码', ''))
            if code not in rocket_counts:
                rocket_counts[code] = {'name': str(row.get('名称', '')), 'count': 0}
            rocket_counts[code]['count'] += 1

        for code, info in sorted(rocket_counts.items(), key=lambda x: -x[1]['count']):
            existing = next((c for c in candidates if c['code'] == code), None)
            if existing:
                existing['signal'] += f'+火箭×{info["count"]}'
                existing['score'] += min(info['count'] * 4, 12)
            elif info['count'] >= 2:
                candidates.append({
                    'code': code,
                    'name': info['name'],
                    'signal': f'火箭发射×{info["count"]}',
                    'score': min(info['count'] * 4, 12),
                })
            if len(candidates) >= 35:  # v5.52优化: 从30改为35, +17%
                break  # v5.52: 超过35个候选就停止
    except Exception as e:
        print(f"火箭发射获取失败: {e}")

    return candidates


def get_strong_candidates() -> list:
    """策略3: 强势股 — 涨停板+强势连板"""
    candidates = []
    today = datetime.now().strftime('%Y%m%d')

    # 强势股池
    try:
        df = ak.stock_zt_pool_strong_em(date=today)
        for _, row in df.head(20).iterrows():
            code = str(row.get('代码', ''))
            candidates.append({
                'code': code,
                'name': row.get('名称', ''),
                'signal': '强势股',
                'change': row.get('涨跌幅', 0),
                'score': 8,
            })
    except Exception as e:
        print(f"强势股获取失败: {e}")

    return candidates


def get_institution_candidates() -> list:
    """策略4: 机构推荐 — 研报买入/增持评级"""
    candidates = []
    reports = get_stock_research_reports()
    if reports is not None and not reports.empty:
        for _, row in reports.iterrows():
            rating = str(row.get('评级', ''))
            if rating in ['买入', '增持', '强烈推荐']:
                code = str(row.get('股票代码', ''))
                if code:
                    candidates.append({
                        'code': code,
                        'name': row.get('股票名称', ''),
                        'signal': f'机构{rating}',
                        'institution': row.get('机构', ''),
                        'score': 12 if rating == '买入' else 8,
                    })
    return candidates[:20]


def get_sector_momentum() -> dict:
    """板块动量轮动 — 追踪近期板块资金流入方向，倾斜选股权重
    
    Returns: {sector_name: momentum_score} 正=资金流入，负=流出
    """
    try:
        from data_collector import get_sector_fund_flow
        sectors = get_sector_fund_flow()
        if sectors is None or sectors.empty:
            return {}
        
        result = {}
        for _, row in sectors.iterrows():
            name = str(row.get('板块名称', ''))
            change = float(row.get('涨跌幅', 0) or 0)
            net_flow = float(row.get('主力净流入', 0) or 0)
            # 正向动量: 涨幅+资金流入
            momentum = 0
            if change > 3:
                momentum += 3  # 大涨板块加更多分
            elif change > 2:
                momentum += 2
            elif change > 0:
                momentum += 1
            elif change < -2:
                momentum -= 2
            if net_flow > 5e8:  # 超5亿流入
                momentum += 2
            elif net_flow > 0:
                momentum += 1
            elif net_flow < -5e8:  # 超5亿流出
                momentum -= 2
            elif net_flow < -1e8:
                momentum -= 1
            result[name] = momentum
        return result
    except:
        return {}


def score_and_rank(all_candidates: list, regime: str = "") -> list:
    """综合打分+技术面验证+板块策略路由+市场状态调节+排名"""
    # 合并同一股票的信号（按信号质量加权 + 动态学习调整）
    learned_adj = get_learned_signal_weights()
    merged = {}
    for c in all_candidates:
        code = c['code']
        if not code or len(code) < 6:
            continue
        sig_base = c['signal'].split('×')[0].split('+')[0]
        quality_w = SIGNAL_QUALITY_WEIGHTS.get(sig_base, 1.0)
        # 应用学习调整: 实盘验证后的信号权重覆盖默认值
        if sig_base in learned_adj:
            quality_w *= learned_adj[sig_base]
        
        # v5.53: MACD+RSI信号加权逻辑 — 激进权重提升
        # 回测TOP1: 17.1% 收益, 2.35 Sharpe, 60% 胜率, 4.08%回撤 → 权重提升到1.5x
        # 新增: MACD金叉+RSI上升 = 双信号 → 额外+15%权重
        if 'MACD' in c['signal'] or 'RSI' in c['signal']:
            from config import MACD_RSI_SIGNAL_BOOST
            quality_w *= MACD_RSI_SIGNAL_BOOST  # 1.5x激进提升
            # 如果同时包含MACD和RSI双重信号,额外加强
            if 'MACD' in c['signal'] and 'RSI' in c['signal']:
                quality_w *= 1.15  # MACD+RSI双信号 +15%额外权重
        weighted_score = int(c['score'] * quality_w)
        if code in merged:
            merged[code]['signals'].append(c['signal'])
            merged[code]['score'] += weighted_score
        else:
            merged[code] = {
                'code': code,
                'name': c.get('name', ''),
                'signals': [c['signal']],
                'score': weighted_score,
            }

    # 排序取top
    ranked = sorted(merged.values(), key=lambda x: -x['score'])[:15]
    
    # v5.56: 应用Sharpe风险权重 (策略级别滤波)
    # 只推荐Sharpe>=1.5的策略,<1.0的黑名单
    try:
        from position_manager import get_strategy_risk_weight
        for cand in ranked:
            # 提取候选的主要策略
            signals = cand.get('signals', [])
            strategy = 'MULTI_FACTOR'  # 默认
            if signals:
                if 'MACD' in signals[0]:
                    strategy = 'MACD_RSI'
                elif 'RSI' in signals[0]:
                    strategy = 'MACD_RSI'
                elif 'MA' in signals[0]:
                    strategy = 'MA_CROSS'
            
            risk_weight = get_strategy_risk_weight(strategy)
            
            if risk_weight == 0.0:
                cand['score'] = 0  # 黑名单
                cand['_risk_status'] = 'blacklist'
            else:
                cand['score'] = int(cand.get('score', 0) * risk_weight)
                cand['_strategy_risk_weight'] = risk_weight
                if risk_weight < 1.0:
                    cand['_risk_status'] = 'caution'
    except Exception as e:
        pass  # Sharpe风险过滤异常时忽略

    # v5.53: 科技成长赛道权重激进优化 (+30%)
    # 逻辑: 科技相关板块持续表现优异，基于回测数据提升权重
    try:
        from config import TECH_GROWTH_SECTORS, TECH_GROWTH_WEIGHT_BOOST
        for stock in ranked:
            # 尝试分类股票所属板块
            sector = classify_sector(stock['code'], stock.get('name', ''))
            if sector in TECH_GROWTH_SECTORS:
                original_score = stock['score']
                stock['score'] = int(stock['score'] * (1 + TECH_GROWTH_WEIGHT_BOOST))
                # 记录优化: score从xx升级到yy(+20%权重加成)
    except Exception as e:
        pass  # 如果分类失败则忽略，不影响后续逻辑

    # 市场状态调节信号源权重
    if regime:
        from market_regime import get_regime_strategy_multiplier
        for stock in ranked:
            adjusted_score = 0
            for sig in stock['signals']:
                sig_base = sig.split('×')[0].split('+')[0]  # 取信号基础名
                strategy_key = SIGNAL_STRATEGY_MAP.get(sig_base, 'multi_factor')
                multiplier = get_regime_strategy_multiplier(regime, strategy_key)
                adjusted_score += stock['score'] / max(len(stock['signals']), 1) * multiplier
            stock['score'] = int(adjusted_score)

    # === 熊市均值回归模式 ===
    # 熊市下追涨策略命中率低,切换为超跌反弹逻辑
    bear_mode = (regime == 'bear')

    # === v5.39 指标分级权重 ===
    # A级: 回测+实盘验证有效的指标, 权重2x
    # B级: 回测验证但实盘样本不足, 权重1x
    # C级: 未验证/实盘表现中性, 权重0.5x
    # 基于指标归因数据自动分级
    _indicator_tiers = {'A': 2.0, 'B': 1.0, 'C': 0.5}
    _tier_map = {}  # indicator -> tier
    try:
        from indicator_attribution import compute_indicator_effectiveness
        _eff = compute_indicator_effectiveness()
        for ind, stats in _eff.items():
            if stats.get('sample_size', 0) >= 5 and stats.get('win_rate', 0) >= 0.6:
                _tier_map[ind] = 'A'  # 胜率≥60%+样本足够
            elif stats.get('sample_size', 0) >= 3:
                _tier_map[ind] = 'B'
            else:
                _tier_map[ind] = 'C'
    except:
        pass
    
    def _tier_mult(indicator_name: str) -> float:
        tier = _tier_map.get(indicator_name, 'B')
        return _indicator_tiers.get(tier, 1.0)

    # === 预计算: 循环外一次性获取，避免每只股票重复调用 ===
    _review_insights = None
    try:
        _review_insights = get_trade_review_insights()
    except:
        pass
    
    _perf_mult = {'strategy': {}, 'sector': {}}
    try:
        _perf_mult = get_recent_strategy_performance()
    except:
        pass
    
    _sector_mom = {}
    try:
        _sector_mom = get_sector_momentum()
    except:
        pass

    # === 板块级止损冷却: 同板块近期多次止损扣分 ===
    _sector_penalties = {}
    try:
        _sector_penalties = get_sector_stop_loss_penalty()
    except:
        pass

    # === 信号毒性检测: 近期总亏钱的信号组合自动扣分 ===
    _toxic_signals = {}
    try:
        _toxic_signals = get_toxic_signal_combos()
        if _toxic_signals:
            print(f"  ☠️ 毒信号检测: {_toxic_signals}")
    except:
        pass

    # 加技术面验证 + 板块策略路由
    print(f"  📊 验证{len(ranked)}只候选股技术面...")
    for i, stock in enumerate(ranked):
        try:
            # 板块分类
            sector = classify_sector(stock['code'], stock.get('name', ''))
            stock['sector'] = sector
            weights = SECTOR_STRATEGY_WEIGHTS.get(sector, {})

            df = get_stock_daily(stock['code'], 60)
            if df is not None and not df.empty:
                tech = calculate_technical_indicators(df)
                stock['technical'] = tech

                # 技术面加减分 — 按板块策略权重调节
                trend = tech.get('trend', '')
                if '多头' in trend or '强势' in trend:
                    stock['score'] += int(10 * weights.get('trend_follow', 1.0))
                elif '空头' in trend or '弱势' in trend:
                    stock['score'] -= 10

                rsi = tech.get('rsi14', 50)
                if 40 < rsi < 70:  # RSI适中，安全区
                    stock['score'] += 5
                elif rsi > 80:  # 超买风险
                    stock['score'] -= 8
                elif rsi < 30 and bear_mode:  # 熊市超跌反弹加分
                    stock['score'] += 12  # 熊市下RSI<30是抄底机会
                elif rsi < 30:
                    stock['score'] += 5

                macd_sig = tech.get('macd_signal', '')
                macd_weight = weights.get('macd_rsi', 1.0)
                if macd_sig == 'golden_cross':
                    stock['score'] += int(12 * macd_weight)  # 已确认金叉(2日)
                elif macd_sig == 'fresh_golden':
                    stock['score'] += int(7 * macd_weight)  # 未确认金叉(仅1日),权重降低
                elif macd_sig == 'bullish':
                    stock['score'] += int(5 * macd_weight)
                elif macd_sig == 'death_cross':
                    stock['score'] -= 12
                elif macd_sig == 'fresh_death':
                    stock['score'] -= 7  # 未确认死叉

                # === MACD零轴突破: DIF上穿零轴=趋势空翻多，比金叉更强 ===
                if tech.get('macd_zero_cross_up'):
                    stock['score'] += int(10 * macd_weight)  # 强趋势反转信号
                elif tech.get('macd_zero_cross_down'):
                    stock['score'] -= 8  # DIF跌穿零轴=趋势转空

                vol_ratio = tech.get('volume_ratio', 1)
                if vol_ratio > 1.5:  # 放量
                    stock['score'] += 5
                elif vol_ratio < 0.5:  # 缩量
                    stock['score'] -= 3

                # KDJ信号加减分
                kdj_sig = tech.get('kdj_signal', '')
                if kdj_sig == 'golden_cross':
                    stock['score'] += 8
                elif kdj_sig == 'oversold':
                    stock['score'] += 5
                elif kdj_sig == 'death_cross':
                    stock['score'] -= 8
                elif kdj_sig == 'overbought':
                    stock['score'] -= 5
                
                # KDJ J值极端区域 — J<0极度超卖, J>100极度超买
                # J值比K/D更灵敏，极端值是强反转信号
                kdj_j = tech.get('kdj_j', 50)
                if kdj_j < 0:  # J<0: 统计极度超卖
                    j_bonus = 10 if regime == 'bear' else 6
                    stock['score'] += j_bonus
                elif kdj_j < 10:  # J<10: 超卖区
                    stock['score'] += 3
                elif kdj_j > 100:  # J>100: 极度超买
                    stock['score'] -= 8
                elif kdj_j > 90:  # J>90: 超买区
                    stock['score'] -= 3

                # RSI背离信号 — 强反转信号
                rsi_div = tech.get('rsi_divergence', 'none')
                if rsi_div == 'bullish':
                    stock['score'] += 10  # 底背离是强买入信号
                elif rsi_div == 'bearish':
                    stock['score'] -= 10  # 顶背离是强卖出信号

                # === MACD柱状图背离 — 比RSI背离更灵敏的动量反转信号 ===
                # 看涨背离: 价格新低但MACD柱线低点抬升 → 空方衰竭
                # 看跌背离: 价格新高但MACD柱线高点下降 → 多方衰竭
                if tech.get('macd_hist_bull_div'):
                    bonus = 12 if regime == 'bear' else 7
                    stock['score'] += bonus
                if tech.get('macd_hist_bear_div'):
                    stock['score'] -= 8  # 看跌背离警告

                # === 动量衰减检测 — 避免追高 ===
                if tech.get('momentum_decay'):
                    stock['score'] -= 8  # MACD柱线递减，动力不足
                if tech.get('volume_price_diverge'):
                    stock['score'] -= 6  # 量价背离，上涨不可持续

                # === VWAP入场时机 ===
                price_vs_vwap = tech.get('price_vs_vwap', 0)
                if price_vs_vwap < -3:  # 低于VWAP 3%+，折价买入好时机
                    stock['score'] += 8
                elif price_vs_vwap < -1:
                    stock['score'] += 4
                elif price_vs_vwap > 5:  # 远超VWAP，溢价追高风险大
                    stock['score'] -= 5

                # === 跳空缺口信号 ===
                if tech.get('gap_up'):
                    stock['score'] += 6  # 向上跳空缺口=强势突破
                if tech.get('gap_down'):
                    stock['score'] -= 8  # 向下跳空缺口=破位风险

                # === CMF (Chaikin Money Flow) 资金流向 ===
                cmf = tech.get('cmf_20', 0)
                if cmf > 0.15:  # 强资金流入
                    stock['score'] += 8
                elif cmf > 0.05:
                    stock['score'] += 4
                elif cmf < -0.15:  # 强资金流出
                    stock['score'] -= 8
                elif cmf < -0.05:
                    stock['score'] -= 4
                # CMF趋势变化
                if tech.get('cmf_rising'):
                    stock['score'] += 3  # 资金流入趋势加速
                if tech.get('cmf_falling'):
                    stock['score'] -= 3  # 资金流出趋势加速

                # === OBV能量潮确认 ===
                obv_trend = tech.get('obv_trend', 0)
                if obv_trend > 0.15:  # OBV明显上升，量价配合
                    stock['score'] += 6
                elif obv_trend < -0.15:  # OBV下降，上涨可能是假突破
                    stock['score'] -= 5
                if tech.get('obv_price_diverge'):  # 价涨量缩的OBV背离
                    stock['score'] -= 7

                # === Williams %R 信号 ===
                wr = tech.get('williams_r', -50)
                if tech.get('wr_reversal'):
                    stock['score'] += 8  # 从超卖回升=强买入信号
                elif wr > -20:  # 超买区
                    stock['score'] -= 6
                elif tech.get('wr_overbought_exit'):
                    stock['score'] -= 4  # 从超买回落=减弱信号

                # === 周线趋势过滤器 ===
                # 日线信号必须有周线趋势确认，否则打折
                weekly_trend = tech.get('weekly_trend', 'neutral')
                if weekly_trend == 'down':
                    stock['score'] = int(stock['score'] * 0.6)  # 周线下降趋势，信号大幅打折
                    stock['weekly_downtrend'] = True
                elif weekly_trend == 'up':
                    stock['score'] = int(stock['score'] * 1.15)  # 周线上升趋势，加分
                # neutral不调整

                # === 换手率过滤 ===
                # 用volume_ratio近似判断异常换手: 量比>3说明换手极高,可能是游资炒作
                if vol_ratio > 3.0:
                    stock['score'] -= 6  # 异常高换手,游资出货风险
                    stock['high_turnover'] = True

                # === ATR波动率过滤 ===
                atr_pct = tech.get('atr_pct', 0)
                if atr_pct > 6:  # 日均波动>6%，风险太大
                    stock['score'] -= 8
                elif atr_pct > 4:  # 较高波动
                    stock['score'] -= 3
                stock['atr_pct'] = atr_pct

                # === ADX趋势强度调节 ===
                # ADX>25=强趋势: 趋势信号可信; ADX<20=弱趋势: 趋势信号打折
                adx = tech.get('adx', 0)
                trend_strength = tech.get('trend_strength', 'unknown')
                if trend_strength == 'strong':
                    # 强趋势下，多头排列/MACD金叉更可信，额外加分
                    if '多头' in trend or macd_sig in ('golden_cross', 'bullish'):
                        stock['score'] += 6
                elif trend_strength == 'weak':
                    # 无方向市场，趋势信号不可信，扣分避免假突破
                    if '多头' in trend or macd_sig in ('golden_cross', 'bullish'):
                        stock['score'] -= 4
                stock['adx'] = adx

                # === 布林带 %B 超卖/超买 ===
                pct_b = tech.get('boll_pct_b', 0.5)
                if pct_b < 0:  # 跌破下轨，极度超卖
                    stock['score'] += 10 if bear_mode else 6
                elif pct_b < 0.2:  # 接近下轨
                    stock['score'] += 5 if bear_mode else 3
                elif pct_b > 1.0:  # 突破上轨，超买
                    stock['score'] -= 6
                
                # 布林带收窄(squeeze) = 即将变盘，观望
                if tech.get('boll_squeeze'):
                    stock['score'] -= 3  # 方向不明，不急着进场
                
                # === 成交量高潮 ===
                if tech.get('sell_climax') and bear_mode:
                    stock['score'] += 10  # 恐慌抛售尾声，熊市抄底好机会
                elif tech.get('sell_climax'):
                    stock['score'] += 5
                if tech.get('buy_climax'):
                    stock['score'] -= 10  # 追高巨量，获利盘回吐风险极大

                # === 相对强度评级 (RS vs 大盘) ===
                # 比大盘弱的股票不买，只选强于大盘的
                stock_ret_10d = tech.get('stock_ret_10d', 0)
                stock_ret_20d = tech.get('stock_ret_20d', 0)
                rs_10d = stock_ret_10d  # 绝对收益当RS
                if rs_10d < -5:
                    stock['score'] -= 8  # 近10日大跌>5%，弱势
                elif rs_10d > 5:
                    stock['score'] += 5  # 近10日涨>5%，强势
                stock['rs_10d'] = rs_10d

                # === 缩量企稳(Volume Dry-up) ===
                if tech.get('volume_dryup'):
                    stock['score'] += int((10 if bear_mode else 6) * _tier_mult('volume_dryup'))
                    stock['volume_dryup'] = True

                # === 均线密集收敛突破 ===
                if tech.get('ma_converge_breakout'):
                    stock['score'] += 12  # MA收敛后突破=强启动信号
                    stock['ma_breakout'] = True

                # === 价格结构: Higher Low 确认底部 ===
                if tech.get('higher_low'):
                    stock['score'] += 8 if bear_mode else 5  # 底部抬升=筑底成功
                if tech.get('lower_low'):
                    stock['score'] -= 8  # 下降通道，不抄底

                # === 支撑阻力位评分 ===
                if tech.get('near_support'):
                    stock['score'] += int(8 * _tier_mult('near_support'))  # 接近支撑位
                    if tech.get('strong_support'):
                        stock['score'] += int(5 * _tier_mult('strong_support'))
                if tech.get('near_resistance'):
                    stock['score'] -= 6  # 接近阻力位，上涨空间有限

                # === Fibonacci 回撤位评分 ===
                if tech.get('near_fib_support'):
                    stock['score'] += 7  # 接近Fib支撑位=关键价位买入
                fib_res_dist = tech.get('fib_resistance_dist_pct', 99)
                if fib_res_dist < 1.5:
                    stock['score'] -= 5  # 接近Fib阻力位,上涨空间有限

                # === 价格Z-Score均值回归 ===
                z_score = tech.get('price_z_score', 0)
                if z_score < -2:
                    stock['score'] += 10 if bear_mode else 6  # 统计极度超卖
                elif z_score < -1:
                    stock['score'] += 5 if bear_mode else 3
                elif z_score > 2:
                    stock['score'] -= 8  # 统计极度超买
                elif z_score > 1.5:
                    stock['score'] -= 4

                # === 成交密集区 (Volume Profile) 评分 ===
                # v5.27新增: 比局部极值支撑更可靠
                if tech.get('near_vp_support'):
                    stock['score'] += int(8 * _tier_mult('near_vp_support'))
                    stock['near_vp_support'] = True
                if tech.get('below_poc'):
                    stock['score'] += 5 if bear_mode else 3  # 低于成交量中心,有回归动力

                # === K线形态信号 ===
                if tech.get('bullish_candle'):
                    candle_bonus = 10 if bear_mode else 6
                    stock['score'] += candle_bonus
                    stock['bullish_candle'] = True
                    if tech.get('hammer'):
                        stock['candle_pattern'] = '锤子线'
                    elif tech.get('bullish_engulf'):
                        stock['candle_pattern'] = '看涨吞没'
                    elif tech.get('morning_star'):
                        stock['candle_pattern'] = '早晨之星'
                if tech.get('bearish_candle'):
                    stock['score'] -= 8
                    stock['bearish_candle'] = True

                # === 连续阳线/阴线信号 ===
                consec_bull = tech.get('consec_bull_candles', 0)
                consec_bear = tech.get('consec_bear_candles', 0)
                if consec_bull >= 3 and rsi < 45:  # 超卖区连续阳线=强反转
                    stock['score'] += 8 if bear_mode else 5
                elif consec_bull >= 3 and rsi > 65:  # 高位连续阳线=可能见顶
                    stock['score'] -= 3
                if consec_bear >= 3:
                    stock['score'] -= 6  # 连续阴线=趋势衰弱

                # === 阴跌检测 (v5.48) ===
                # 10天中7天跌且累计>3%→温水煮蛙式下跌，重扣
                if tech.get('slow_bleed'):
                    stock['score'] -= 10
                    stock['slow_bleed'] = True

                # === NR7窄幅整理评分 ===
                # NR7=7天内最窄振幅,多空极度压缩即将突破
                # 配合趋势方向:上升趋势中NR7=低风险做多入场
                if tech.get('nr7'):
                    weekly_up = tech.get('weekly_trend') == 'up'
                    macd_bull = tech.get('macd_signal') in ('bullish', 'golden_cross')
                    if weekly_up or macd_bull:
                        stock['score'] += 8  # 上升趋势中的窄幅整理=强蓄力
                    else:
                        stock['score'] += 3  # 方向不明的窄幅整理
                elif tech.get('nr4') and tech.get('range_compression', 1.0) < 0.5:
                    # NR4+振幅压缩到均值50%以下,也是较好信号
                    stock['score'] += 4

                # === 抛物线拉升过滤 ===
                # 5日涨幅>15%的票大概率要回调，不追
                if df is not None and len(df) >= 5:
                    try:
                        close_5 = df['收盘'].astype(float)
                        ret_5d = (close_5.iloc[-1] - close_5.iloc[-5]) / close_5.iloc[-5] * 100
                        if ret_5d > 15:
                            stock['score'] -= 12  # 重扣: 抛物线拉升回调风险极大
                            stock['parabolic'] = True
                        elif ret_5d > 10:
                            stock['score'] -= 5   # 轻扣: 短期涨幅较大
                    except:
                        pass

                # === 信号毒性扣分 ===
                if _toxic_signals:
                    for sig in stock['signals']:
                        for toxic_kw, penalty in _toxic_signals.items():
                            if toxic_kw in sig:
                                stock['score'] += penalty
                                stock['toxic_signal'] = True

                # 板块整体乘数（回测验证好的板块加成）
                stock['score'] = int(stock['score'] * get_sector_score_multiplier(sector))

                # === 近期绩效自适应 ===
                try:
                    sector_adj = _perf_mult.get('sector', {}).get(sector, 1.0)
                    stock['score'] = int(stock['score'] * sector_adj)
                except:
                    pass

                # === 交易复盘学习调整 ===
                try:
                    review = _review_insights
                    if review and review.get('adjustments'):
                        adj = review['adjustments']
                        if 'near_support' in adj and tech.get('near_support'):
                            stock['score'] += adj['near_support']
                        if 'strong_support' in adj and tech.get('strong_support'):
                            stock['score'] += adj.get('strong_support', 0)
                        if 'z_under_neg1' in adj and tech.get('price_z_score', 0) < -1:
                            stock['score'] += adj['z_under_neg1']
                        if 'higher_low' in adj and tech.get('higher_low'):
                            stock['score'] += adj.get('higher_low', 0)
                        if 'volume_dryup' in adj and tech.get('volume_dryup'):
                            stock['score'] += adj.get('volume_dryup', 0)
                        if 'weekly_up' in adj and tech.get('weekly_trend') == 'up':
                            stock['score'] += adj.get('weekly_up', 0)
                        if 'adx_strong' in adj and tech.get('trend_strength') == 'strong':
                            stock['score'] += adj.get('adx_strong', 0)
                        if 'near_vp_support' in adj and tech.get('near_vp_support'):
                            stock['score'] += adj.get('near_vp_support', 0)
                        if 'below_poc' in adj and tech.get('below_poc'):
                            stock['score'] += adj.get('below_poc', 0)
                except:
                    pass

                # === 指标归因评分调整 (v5.35) ===
                # 基于实盘归因数据，自动调整各指标分数
                try:
                    from indicator_attribution import get_attribution_score_adjustments
                    attr_adj = get_attribution_score_adjustments(tech)
                    if attr_adj != 0:
                        stock['score'] += attr_adj
                        stock['attribution_adj'] = attr_adj
                except:
                    pass

                # === 板块动量轮动加分 ===
                try:
                    sector_mom = _sector_mom
                    # 用板块名称关键词匹配: 科技→半导体/软件/芯片, 新能源→光伏/锂电/风电 等
                    SECTOR_KEYWORDS = {
                        '科技成长': ['半导体', '软件', '芯片', '计算机', '电子', '通信', '互联网', '人工智能', 'AI'],
                        '新能源': ['光伏', '锂电', '风电', '新能源', '储能', '太阳能', '电池'],
                        '消费白马': ['白酒', '食品', '家电', '医药', '消费', '零售'],
                    }
                    keywords = SECTOR_KEYWORDS.get(sector, [])
                    best_mom = 0
                    for sec_name, mom_score in sector_mom.items():
                        for kw in keywords:
                            if kw in sec_name:
                                if abs(mom_score) > abs(best_mom):
                                    best_mom = mom_score
                                break
                    if best_mom >= 2:
                        stock['score'] += 6  # 强势板块加分
                    elif best_mom <= -2:
                        stock['score'] -= 4  # 弱势板块扣分
                except:
                    pass

                # === 板块级止损冷却惩罚 ===
                if sector in _sector_penalties:
                    stock['score'] += _sector_penalties[sector]
                    stock['sector_cooldown'] = True

            time.sleep(0.3)
        except Exception as e:
            print(f"  ⚠️ {stock['code']}技术面验证失败: {e}")

    # 重新排序
    ranked = sorted(ranked, key=lambda x: -x['score'])
    
    # === 过滤器全局松绑率 (v5.48) ===
    # 现金闲置越高，过滤器越应该松绑，避免"永远空仓"
    _filter_relax = 1.0  # 1.0=不松绑, 0.7=松30%
    try:
        from trading_engine import get_account as _ga2
        _acct2 = _ga2()
        _cash_ratio = _acct2['cash'] / max(_acct2['total_value'], 1)
        if _cash_ratio > 0.95:
            _filter_relax = 0.6  # 95%以上闲置，大幅松绑
        elif _cash_ratio > 0.85:
            _filter_relax = 0.8  # 85%以上闲置，适度松绑
    except:
        pass

    # === 信号共识过滤 ===
    # 只保留至少2个独立信号类别支持的候选,减少假信号
    # 但极高分候选(>=60)可绕过共识门槛(高确信度旁路)
    # v5.47: 高现金闲置(>90%)时放宽共识要求到1类
    _high_idle = False
    try:
        from trading_engine import get_account as _ga
        _acct = _ga()
        _high_idle = _acct['cash'] / max(_acct['total_value'], 1) > 0.90
    except:
        pass
    consensus_min = 1 if _high_idle else 2
    # v5.48: 应用全局松绑率到共识门槛
    if _filter_relax < 0.8:
        consensus_min = 1  # 重度闲置时放宽到单类别即可
    consensus_filtered = []
    for stock in ranked:
        passed, cats, cat_count = check_signal_consensus(stock['signals'], regime=regime)
        stock['signal_categories'] = list(cats)
        stock['consensus_count'] = cat_count
        if passed or (_high_idle and cat_count >= 1):
            # 多类别共识加分: 3类别+6, 4类别+10
            if cat_count >= 4:
                stock['score'] += 10
            elif cat_count >= 3:
                stock['score'] += 6
            consensus_filtered.append(stock)
        elif stock['score'] >= 60:
            # 高确信度旁路: 极高分即使单类别也保留(仅打9折)
            stock['score'] = int(stock['score'] * 0.9)
            stock['bypass_consensus'] = True
            consensus_filtered.append(stock)
        else:
            # 单类别但分数极高(>50)的也保留(可能是强机构推荐)
            if stock['score'] >= 50:
                stock['score'] = int(stock['score'] * 0.8)  # 打折但保留
                consensus_filtered.append(stock)
    
    # 如果共识过滤后太少,放宽到原列表(避免空选)
    if len(consensus_filtered) < 3:
        consensus_filtered = ranked
    
    # === 评分质量归一化 ===
    # 防止多信号堆叠导致分数膨胀 — 计算每个信号类别的平均分
    for stock in consensus_filtered:
        n_cats = max(stock.get('consensus_count', 1), 1)
        n_sigs = max(len(stock.get('signals', [])), 1)
        # 质量分 = 总分 × (1 + log2(信号类别数)) / sqrt(信号总数)
        # 多类别加成(质量好)，但单纯多信号不等比膨胀
        import math
        quality_mult = (1 + math.log2(n_cats)) / math.sqrt(n_sigs) if n_sigs > 1 else 1.0
        stock['raw_score'] = stock['score']
        stock['score'] = int(stock['score'] * min(quality_mult, 1.5))
    
    return sorted(consensus_filtered, key=lambda x: -x['score'])


def filter_tradeable(candidates: list) -> list:
    """过滤：排除ST、停牌、涨跌停（无法买入）"""
    filtered = []
    codes = [c['code'] for c in candidates[:10]]
    quotes = get_realtime_quotes(codes)

    for c in candidates[:10]:
        name = c.get('name', '')
        if 'ST' in name or '*ST' in name:
            continue
        code = c['code']
        if code in quotes:
            price = quotes[code]['price']
            change = quotes[code].get('change_pct', 0)
            if price <= 0:  # 停牌
                continue
            if abs(change) >= 9.8:  # 涨跌停，大概率买不进
                c['at_limit'] = True
            # 盘中已涨>5%不追高: 早上选出来评分高，但盘中已大涨就别追了
            if change >= 5.0:
                c['score'] = int(c.get('score', 0) * 0.6)  # 打6折
                c['intraday_chase'] = True
            c['realtime_price'] = price
            c['change_pct'] = change
        filtered.append(c)

    return filtered


def analyze_stop_loss_effectiveness() -> dict:
    """止损效果分析器 — 分析历史止损是太紧还是太松
    
    检查止损卖出后股价的表现:
    - 如果多数止损后继续跌 → 止损正确，保持或更紧
    - 如果多数止损后反弹 → 止损太紧，应放宽
    - 计算最优止损阈值建议
    
    Returns: {correct_stops, wrong_stops, optimal_threshold, recommendation}
    """
    try:
        import sqlite3
        from data_collector import get_stock_daily
        conn = sqlite3.connect('/home/nikefd/finance-agent/data/trading.db')
        c = conn.cursor()
        c.execute("""SELECT symbol, price, trade_date, reason FROM trades 
                     WHERE direction='SELL' AND reason LIKE '%止损%' 
                     AND trade_date >= date('now', '-45 days') ORDER BY id DESC""")
        stops = c.fetchall()
        conn.close()
        
        if len(stops) < 3:
            return {}
        
        correct = 0  # 止损后继续跌
        wrong = 0    # 止损后反弹
        loss_at_stop = []  # 止损时的亏损幅度
        
        for symbol, stop_price, stop_date, reason in stops[:12]:
            try:
                df = get_stock_daily(symbol, 30)
                if df is None or df.empty:
                    continue
                # 找止损日之后的价格走势
                if '日期' in df.columns:
                    after = df[df['日期'] > stop_date]
                    if len(after) < 3:
                        continue
                    # 止损后5天的最高价 vs 止损价
                    max_after = after['最高'].astype(float).head(5).max()
                    min_after = after['最低'].astype(float).head(5).min()
                    
                    if max_after > stop_price * 1.03:  # 止损后涨了3%+
                        wrong += 1
                    elif min_after < stop_price * 0.97:  # 止损后继续跌3%+
                        correct += 1
                    else:
                        correct += 0.5  # 横盘，止损不算错
                        wrong += 0.5
                
                # 提取止损时的亏损幅度
                import re
                m = re.search(r'亏损([\-\d.]+)%', reason)
                if m:
                    loss_at_stop.append(float(m.group(1)))
                time.sleep(0.2)
            except:
                continue
        
        total = correct + wrong
        if total < 2:
            return {}
        
        accuracy = correct / total
        avg_loss = sum(loss_at_stop) / len(loss_at_stop) if loss_at_stop else -8
        
        # 建议
        if accuracy > 0.7:
            rec = 'keep'  # 止损正确率高，保持
            adj = 0
        elif accuracy > 0.5:
            rec = 'slightly_loosen'  # 稍微放宽
            adj = 1  # 放宽1个百分点
        else:
            rec = 'loosen'  # 太紧，放宽
            adj = 2  # 放宽2个百分点
        
        return {
            'total_stops': len(stops),
            'analyzed': int(total),
            'correct': int(correct),
            'wrong': int(wrong),
            'accuracy': round(accuracy * 100, 1),
            'avg_loss_at_stop': round(avg_loss, 1),
            'recommendation': rec,
            'stop_adjustment': adj,
        }
    except Exception as e:
        print(f"  ⚠️ 止损分析失败: {e}")
        return {}


def multi_strategy_pick(regime: str = "", use_news: bool = True, loss_streak: int = 0) -> dict:
    """多策略综合选股主流程（含新闻/舆情数据源）"""
    print("  🔍 策略1: 动量选股(量价齐升+创新高)...")
    momentum = get_momentum_candidates()
    print(f"    → {len(momentum)}只候选")

    print("  💰 策略2: 资金流入(大笔买入+火箭发射)...")
    money = get_money_flow_candidates()
    print(f"    → {len(money)}只候选")

    print("  🔥 策略3: 强势股池...")
    strong = get_strong_candidates()
    print(f"    → {len(strong)}只候选")

    print("  📋 策略4: 机构推荐...")
    institution = get_institution_candidates()
    print(f"    → {len(institution)}只候选")

    # === 策略5: 新闻/舆情驱动 ===
    news_signals = None
    news_candidates = []
    if use_news:
        try:
            from news_collector import collect_and_analyze, get_news_score_for_stock
            print("  📰 策略5: 新闻/舆情信号...")
            news_result = collect_and_analyze()
            news_signals = news_result.get('signals', {})
            
            # 从新闻信号中提取个股候选
            for sig in news_signals.get('stock_signals', []):
                code = sig.get('code', '')
                if code and len(code) == 6 and sig.get('signal') == '利好':
                    news_candidates.append({
                        'code': code,
                        'name': sig.get('name', ''),
                        'signal': f"新闻利好:{sig.get('reason', '')[:20]}",
                        'score': 15,
                    })
            print(f"    → {len(news_signals.get('stock_signals', []))}条个股信号, "
                  f"{len(news_signals.get('sector_signals', []))}条板块信号")
        except Exception as e:
            print(f"  ⚠️ 新闻采集失败(不影响其他策略): {e}")

    # === 策略6: 资金面数据(北向+龙虎榜+融资融券+宏观) ===
    money_overview = None
    money_candidates = []
    try:
        from market_data_ext import get_money_flow_overview, get_stock_money_signals, save_money_flow_snapshot
        print("  💰 策略6: 资金面数据(北向/龙虎榜/融资融券/宏观)...")
        money_overview = get_money_flow_overview()
        save_money_flow_snapshot(money_overview)
        
        # 从龙虎榜机构买入中提取候选
        for stock in money_overview.get('lhb', {}).get('institution_buys', []):
            code = stock.get('code', '')
            if code and len(code) == 6:
                money_candidates.append({
                    'code': code,
                    'name': stock.get('name', ''),
                    'signal': f"机构龙虎榜买入",
                    'score': 15,
                })
        # 北向大额增持
        for stock in money_overview.get('northbound', {}).get('top_buys', [])[:5]:
            code = stock.get('code', '')
            if code and len(code) == 6 and stock.get('increase_value', 0) > 1:
                money_candidates.append({
                    'code': code,
                    'name': stock.get('name', ''),
                    'signal': f"北向增持{stock['increase_value']}亿",
                    'score': 12,
                })
        print(f"    → 资金面评分: {money_overview.get('money_flow_score', '?')}/100 "
              f"({money_overview.get('money_flow_label', '?')}), "
              f"{len(money_candidates)}只资金面候选")
    except Exception as e:
        print(f"  ⚠️ 资金面数据采集失败(不影响其他策略): {e}")

    # === 策略7: 超跌反弹(熊市专用) ===
    oversold_candidates = []
    if regime == 'bear':
        print("  🐻 策略7: 超跌反弹扫描(熊市专用)...")
        oversold_candidates = get_oversold_reversal_candidates()
        print(f"    → {len(oversold_candidates)}只超跌企稳候选")

    # === 策略7.5 (新增 v5.50): RSI超卖反向信号(全市场) ===
    # v5.50 新增：当RSI极端超卖(<20)且持续时，生成自动反弹信号
    # 权重保守(0.8x)确保安全性，只在极端情况触发
    rsi_reversal_candidates = []
    print("  📉 策略7.5 (新): RSI超卖反向信号扫描...")
    try:
        rsi_reversal_candidates = get_rsi_extreme_reversal_candidates()
        print(f"    → {len(rsi_reversal_candidates)}只RSI极端超卖反弹候选")
    except Exception as e:
        print(f"  ⚠️ RSI超卖扫描失败: {e}")

    # === 策略8: 底部放量突破(全市场) ===
    breakout_candidates = []
    print("  🔥 策略8: 底部放量突破扫描...")
    try:
        breakout_candidates = get_bottom_breakout_candidates()
        print(f"    → {len(breakout_candidates)}只底部突破候选")
    except Exception as e:
        print(f"  ⚠️ 底部突破扫描失败: {e}")

    # === 策略9: 主力资金异动(全市场) ===
    smart_money_candidates = []
    print("  💎 策略9: 主力资金异动扫描...")
    try:
        smart_money_candidates = get_smart_money_candidates()
        print(f"    → {len(smart_money_candidates)}只主力资金候选")
    except Exception as e:
        print(f"  ⚠️ 主力资金扫描失败: {e}")

    # 合并所有候选
    all_candidates = momentum + money + strong + institution + news_candidates + money_candidates + oversold_candidates + rsi_reversal_candidates + breakout_candidates + smart_money_candidates
    print(f"  📊 共{len(all_candidates)}条信号，开始综合打分...")

    # 打分排名（含市场状态调节）
    ranked = score_and_rank(all_candidates, regime=regime)

    # ========== v5.56 深度优化: 入场质量5维评分集成 ==========
    # 新增维度: 机构持仓稳定性,预防踩坑,提高连板准确率
    try:
        from entry_quality import enrich_candidates_with_entry_quality, get_dynamic_entry_quality_threshold
        ranked = enrich_candidates_with_entry_quality(ranked)
        
        # 获取动态阈值并过滤
        dynamic_threshold = get_dynamic_entry_quality_threshold()
        ranked_filtered = [c for c in ranked if c.get('entry_quality_score', 0) >= dynamic_threshold]
        
        if len(ranked_filtered) > 0:
            ranked = ranked_filtered
            print(f"  ✅ 入场质量过滤: {len(ranked_filtered)}/{len(ranked)}只符合条件(阈值{dynamic_threshold}分)")
        else:
            print(f"  ⚠️ 入场质量严格,所有候选都低于{dynamic_threshold}分,保留全部但标记低质")
    except Exception as e:
        print(f"  ⚠️ 入场质量评分异常: {e}")

    # === 波动率环境自适应 ===
    # 高波动环境: 偏好均值回归(超跌/支撑位买入), 压缩趋势追涨权重
    # 低波动环境: 偏好趋势突破(均线收敛/MACD金叉), 压缩超跌反弹权重
    try:
        from data_collector import get_stock_daily, calculate_technical_indicators
        _idx_df = get_stock_daily('000001', 30)  # 上证指数
        if _idx_df is not None and len(_idx_df) >= 14:
            _idx_tech = calculate_technical_indicators(_idx_df)
            market_atr_pct = _idx_tech.get('atr_pct', 1.5)
            if market_atr_pct > 2.5:  # 高波动环境
                print(f"  📈 高波动环境(ATR%={market_atr_pct:.1f}%), 偏重均值回归信号")
                for s in ranked:
                    tech = s.get('technical', {})
                    # 加重超跌/支撑信号
                    if tech.get('near_support') or tech.get('near_fib_support'):
                        s['score'] += 5
                    if tech.get('price_z_score', 0) < -1.5:
                        s['score'] += 5
                    # 压缩趋势追涨
                    if tech.get('ma_converge_breakout'):
                        s['score'] -= 3
            elif market_atr_pct < 1.0:  # 低波动环境
                print(f"  📉 低波动环境(ATR%={market_atr_pct:.1f}%), 偏重趋势突破信号")
                for s in ranked:
                    tech = s.get('technical', {})
                    if tech.get('ma_converge_breakout'):
                        s['score'] += 5
                    if '多头' in tech.get('trend', ''):
                        s['score'] += 3
            ranked = sorted(ranked, key=lambda x: -x['score'])
    except Exception as e:
        print(f"  ⚠️ 波动率环境检测失败: {e}")

    # === 新闻信号叠加到候选股分数 ===
    if news_signals and use_news:
        try:
            from news_collector import get_news_score_for_stock
            print("  📰 叠加新闻信号到候选股...")
            for stock in ranked:
                news_score = get_news_score_for_stock(
                    stock['code'], stock.get('name', ''), news_signals)
                if news_score['has_news']:
                    stock['score'] += news_score['score_delta']
                    stock['news_reasons'] = news_score['reasons']
                    print(f"    {stock.get('name','')}({stock['code']}): "
                          f"新闻{'+' if news_score['score_delta']>=0 else ''}{news_score['score_delta']}分")
            # 重新排序
            ranked = sorted(ranked, key=lambda x: -x['score'])
        except Exception as e:
            print(f"  ⚠️ 新闻信号叠加失败: {e}")

    # === 资金面信号叠加到候选股分数 ===
    if money_overview:
        try:
            from market_data_ext import get_stock_money_signals
            print("  💰 叠加资金面信号到候选股...")
            for stock in ranked:
                money_sig = get_stock_money_signals(
                    stock['code'], stock.get('name', ''), money_overview)
                if money_sig['score_delta'] != 0:
                    stock['score'] += money_sig['score_delta']
                    stock['money_reasons'] = money_sig['reasons']
                    stock['northbound_hold'] = money_sig.get('northbound_hold', False)
                    stock['institution_buy'] = money_sig.get('institution_buy', False)
                    print(f"    {stock.get('name','')}({stock['code']}): "
                          f"资金面{'+' if money_sig['score_delta']>=0 else ''}{money_sig['score_delta']}分")
            ranked = sorted(ranked, key=lambda x: -x['score'])
        except Exception as e:
            print(f"  ⚠️ 资金面信号叠加失败: {e}")

    # === 入场质量评分 + 回调入场过滤 + 风险回报比 ===
    for stock in ranked:
        tech = stock.get('technical', {})
        # 入场质量评分(0-100)
        eq_score = calculate_entry_quality_score(tech, stock.get('signals', []), regime)
        stock['entry_quality'] = eq_score
        
        # v5.27: 入场质量作为连续乘数而非二元过滤
        # entry_quality 50→1.0x, 80→1.3x, 20→0.7x
        eq_mult = 0.7 + (eq_score / 100) * 0.6  # 范围[0.7, 1.3]
        stock['score'] = int(stock['score'] * eq_mult)
        
        # 回调入场过滤
        pullback = check_pullback_entry(tech)
        stock['pullback_info'] = pullback
        stock['score'] += pullback.get('bonus', 0)
        
        # 风险回报比
        rr = check_risk_reward_ratio(tech, regime)
        stock['rr_info'] = rr
        if not rr['pass']:
            stock['score'] = int(stock['score'] * 0.8)  # R:R不够打8折
            stock['rr_fail'] = True
        elif rr['rr_ratio'] >= 3.0:
            stock['score'] = int(stock['score'] * 1.1)  # 高R:R加分
    
    # 按综合分重排
    ranked = sorted(ranked, key=lambda x: -x['score'])
    
    # v5.27: 入场质量过滤门槛降到15(从20), 低质量入场已经通过乘数惩罚了
    # v5.48: 应用全局松绑率
    _eq_threshold = int(15 * _filter_relax)
    before_eq = len(ranked)
    ranked = [s for s in ranked if s.get('entry_quality', 0) >= _eq_threshold]
    if before_eq > len(ranked):
        print(f"  🎯 入场质量过滤: {before_eq - len(ranked)}只入场质量<{_eq_threshold}被淘汰")

    # === 信号持续性检查 (Signal Persistence) ===
    # 只有连续2+天出现在候选池的股票才可信,过滤一日游假信号
    # 熊市时更严格: 必须连续2天; 牛市时放宽到1天也可以
    for stock in ranked:
        code = stock.get('code', '')
        persistence = get_signal_persistence(code)
        stock['persistence'] = persistence
        if persistence.get('persistent'):
            stock['score'] += 8  # 连续2+天出现,信号可靠加分
            stock['signal_persistent'] = True
        elif persistence.get('days_appeared', 0) == 0:
            # 首次出现,不扣分但标记
            stock['signal_persistent'] = False
        else:
            # 出现过但不连续,信号可能已衰退
            stock['score'] -= 3
            stock['signal_persistent'] = False
    
    # 熊市+连亏期: 强制要求信号持续性(首次出现的不买)
    if regime == 'bear' and loss_streak >= 3:
        before_persist = len(ranked)
        # 不直接过滤,而是非持续性信号大幅打折
        for stock in ranked:
            if not stock.get('signal_persistent') and stock.get('persistence', {}).get('days_appeared', 0) == 0:
                stock['score'] = int(stock['score'] * 0.6)  # 首次出现打6折
        ranked = sorted(ranked, key=lambda x: -x['score'])
        print(f"  🔄 信号持续性: 熊市连亏期,首次出现的候选打6折")
    
    # 保存今日候选快照(供明天持续性检查)
    save_candidate_snapshot(ranked)

    # === 动态分数门槛: 根据近期胜率+连亏情况自动提高门槛 ===
    score_threshold = get_dynamic_score_threshold(regime=regime, loss_streak=loss_streak)
    ranked = [s for s in ranked if s['score'] >= score_threshold]
    print(f"  🎯 动态分数门槛: {score_threshold}分, 通过{len(ranked)}只")

    # === 止损黑名单: 近期止损过的股票不再买回 ===
    blacklist = get_stop_loss_blacklist()
    if blacklist:
        before = len(ranked)
        ranked = [s for s in ranked if s['code'] not in blacklist]
        blocked = before - len(ranked)
        if blocked > 0:
            print(f"  🚫 止损黑名单过滤: 排除{blocked}只近期止损股")

    # === 市场宽度检查: 普跌行情进一步提高门槛 ===
    # v5.39: 转换期放宽市场宽度限制
    breadth_info = {}
    try:
        from market_regime import get_market_breadth
        breadth_info = get_market_breadth()
        breadth_sig = breadth_info.get('breadth_signal', 'neutral')
        print(f"  📊 市场宽度: 涨{breadth_info.get('advance',0)}跌{breadth_info.get('decline',0)} "
              f"({breadth_info.get('breadth_ratio',0.5):.1%}) → {breadth_sig}")
        # 检查是否在转换期
        _in_transition = False
        try:
            _ri = detect_market_regime() if 'detect_market_regime' in dir() else {}
            _in_transition = _ri.get('transition', 'none') not in ('none', None)
        except:
            pass
        if breadth_sig == 'very_weak' and not _in_transition:
            # 普跌行情，只保留最强的2只
            ranked = ranked[:2]
            print(f"  ⚠️ 市场普跌，候选缩减至{len(ranked)}只")
        elif breadth_sig == 'weak':
            ranked = ranked[:4]
    except Exception as e:
        print(f"  ⚠️ 市场宽度检查失败: {e}")

    # === 强制最低交易保障 (v5.43) ===
    # 连续7+交易日无新建仓且现金>85%: 强制放宽所有过滤器
    # 核心问题: 系统42+层过滤叠加导致永远无法交易，97%现金闲置是机会成本
    try:
        from indicator_attribution import get_idle_days_since_last_trade
        idle_days = get_idle_days_since_last_trade()
        if idle_days >= 7 and len(ranked) == 0:
            # 重新从全部候选中选择，只要分数>15就保留
            emergency_threshold = 15
            all_merged = score_and_rank(all_candidates, regime=regime)
            ranked = [s for s in all_merged if s['score'] >= emergency_threshold][:5]
            if ranked:
                print(f"  🚨 最低交易保障触发: 已{idle_days}交易日未建仓，放宽门槛到{emergency_threshold}分，{len(ranked)}只候选")
    except Exception as e:
        print(f"  ⚠️ 最低交易保障检查失败: {e}")

    # 过滤
    tradeable = filter_tradeable(ranked)
    
    # v5.53: 入场质量评分系统集成
    try:
        tradeable = enrich_candidates_with_entry_quality(tradeable)  # 计算入场质量分
        tradeable = adjust_score_by_entry_quality(tradeable, (0.8, 1.3))  # 权重调整0.8x-1.3x
        high_quality_count = sum(1 for c in tradeable if c.get('entry_quality_score', 0) >= 65)
        print(f"  ✅ v5.53入场质量评分: {len(tradeable)}只候选, {high_quality_count}只达到优质(≥65分)")
    except Exception as e:
        print(f"  ⚠️ 入场质量评分失败: {e}")

    return {
        'candidates': tradeable,
        'news_signals': news_signals,
        'money_overview': money_overview,
        'breadth': breadth_info,
        'stats': {
            'momentum_count': len(momentum),
            'money_flow_count': len(money),
            'strong_count': len(strong),
            'institution_count': len(institution),
            'news_count': len(news_candidates),
            'money_data_count': len(money_candidates),
            'oversold_count': len(oversold_candidates),
            'breakout_count': len(breakout_candidates),
            'smart_money_count': len(smart_money_candidates),
            'total_signals': len(all_candidates),
            'final_count': len(tradeable),
            'money_flow_score': money_overview.get('money_flow_score', 0) if money_overview else 0,
            'money_flow_label': money_overview.get('money_flow_label', '') if money_overview else '',
        }
    }


if __name__ == "__main__":
    print("=== 多策略选股测试 ===")
    result = multi_strategy_pick()
    print(f"\n📊 统计: {json.dumps(result['stats'], ensure_ascii=False)}")
    print(f"\n🎯 Top候选股:")
    for i, c in enumerate(result['candidates'][:8]):
        print(f"  {i+1}. {c['name']}({c['code']}) 分数:{c['score']} 信号:{'+'.join(c['signals'])} "
              f"价格:{c.get('realtime_price','?')} 涨跌:{c.get('change_pct','?')}%")
        tech = c.get('technical', {})
        if tech:
            print(f"     趋势:{tech.get('trend','')} RSI:{tech.get('rsi14','')} MACD:{tech.get('macd_signal','')}")
