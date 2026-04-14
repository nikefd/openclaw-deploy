"""指标归因系统 — 记录每次买入时的指标快照，分析哪些指标真正预测成功

核心思路:
1. 买入时: 记录所有技术指标的值到DB
2. 卖出时: 自动匹配买入记录，标记交易结果(win/loss)
3. 分析: 计算每个指标在赢/亏交易中的分布差异
4. 输出: 数据驱动的指标权重，替代硬编码的+8/-6评分

v5.35 新增
"""

import sqlite3
import json
from datetime import datetime, date, timedelta
from config import DB_PATH

# 追踪的关键指标列表 — 这些是score_and_rank中使用的全部指标
TRACKED_INDICATORS = [
    # 趋势类
    'trend', 'weekly_trend', 'macd_signal', 'macd_zero_cross_up', 'macd_zero_cross_down',
    'ma_converge_breakout', 'adx', 'trend_strength',
    # 动量类
    'rsi14', 'williams_r', 'wr_reversal', 'momentum_decay', 'volume_price_diverge',
    'rsi_divergence', 'macd_hist_bull_div', 'macd_hist_bear_div',
    # 量价类
    'volume_ratio', 'obv_trend', 'obv_price_diverge', 'cmf_20', 'cmf_rising', 'cmf_falling',
    'volume_dryup', 'sell_climax', 'buy_climax',
    # 位置类
    'near_support', 'strong_support', 'near_resistance', 'near_fib_support',
    'near_vp_support', 'below_poc', 'price_z_score', 'boll_pct_b', 'price_vs_vwap',
    # 形态类
    'higher_low', 'lower_low', 'bullish_candle', 'bearish_candle',
    'nr7', 'range_compression', 'gap_up', 'gap_down',
    'consec_bull_candles', 'consec_bear_candles',
    # 波动类
    'atr_pct', 'daily_change_pct', 'stock_ret_10d', 'stock_ret_20d',
    # KDJ
    'kdj_signal',
]


def init_attribution_tables():
    """初始化归因数据库表"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS indicator_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT NOT NULL,
        trade_date TEXT NOT NULL,
        direction TEXT NOT NULL,
        indicators_json TEXT,
        outcome TEXT DEFAULT 'pending',
        outcome_pnl_pct REAL DEFAULT 0,
        matched_sell_id INTEGER DEFAULT 0,
        created_at TEXT,
        UNIQUE(symbol, trade_date, direction)
    )''')
    c.execute('''CREATE INDEX IF NOT EXISTS idx_snap_symbol ON indicator_snapshots(symbol)''')
    c.execute('''CREATE INDEX IF NOT EXISTS idx_snap_outcome ON indicator_snapshots(outcome)''')
    conn.commit()
    conn.close()


def record_entry_indicators(symbol: str, tech: dict):
    """在买入时记录所有指标快照
    
    调用时机: execute_buys() 成功买入后
    """
    if not tech:
        return
    
    try:
        init_attribution_tables()
        
        # 提取关键指标值
        snapshot = {}
        for ind in TRACKED_INDICATORS:
            val = tech.get(ind)
            if val is not None:
                # 布尔值转0/1，字符串保留
                if isinstance(val, bool):
                    snapshot[ind] = 1 if val else 0
                elif isinstance(val, (int, float)):
                    snapshot[ind] = round(float(val), 4)
                else:
                    snapshot[ind] = str(val)
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        today = date.today().isoformat()
        c.execute('''INSERT OR REPLACE INTO indicator_snapshots 
                     (symbol, trade_date, direction, indicators_json, created_at)
                     VALUES (?, ?, 'BUY', ?, ?)''',
                  (symbol, today, json.dumps(snapshot, ensure_ascii=False),
                   datetime.now().isoformat()))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"  ⚠️ 指标归因记录失败: {e}")


def update_attribution_outcomes():
    """更新归因记录的交易结果
    
    调用时机: 每日运行开始时（和update_recommendation_outcomes一起）
    查找所有pending的买入快照，匹配后续的卖出交易，标记outcome
    """
    try:
        init_attribution_tables()
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # 找到所有pending的买入快照
        c.execute('''SELECT id, symbol, trade_date FROM indicator_snapshots 
                     WHERE outcome='pending' AND direction='BUY' ''')
        pending = c.fetchall()
        
        updated = 0
        for snap_id, symbol, buy_date in pending:
            # 查找该股票在买入日期之后的第一次卖出
            c.execute('''SELECT id, price, reason FROM trades 
                        WHERE symbol=? AND direction='SELL' AND trade_date > ?
                        ORDER BY id ASC LIMIT 1''', (symbol, buy_date))
            sell = c.fetchone()
            
            if not sell:
                continue  # 尚未卖出
            
            sell_id, sell_price, sell_reason = sell
            
            # 获取买入价格
            c.execute('''SELECT price FROM trades 
                        WHERE symbol=? AND direction='BUY' AND trade_date=?
                        ORDER BY id DESC LIMIT 1''', (symbol, buy_date))
            buy = c.fetchone()
            if not buy:
                continue
            
            buy_price = buy[0]
            pnl_pct = (sell_price - buy_price) / buy_price * 100
            
            # 判断结果
            if '止盈' in (sell_reason or '') or pnl_pct > 1:
                outcome = 'win'
            elif '止损' in (sell_reason or '') or pnl_pct < -1:
                outcome = 'loss'
            else:
                outcome = 'neutral'
            
            c.execute('''UPDATE indicator_snapshots 
                        SET outcome=?, outcome_pnl_pct=?, matched_sell_id=?
                        WHERE id=?''', (outcome, round(pnl_pct, 2), sell_id, snap_id))
            updated += 1
        
        conn.commit()
        conn.close()
        return updated
    except Exception as e:
        print(f"  ⚠️ 归因结果更新失败: {e}")
        return 0


def compute_indicator_effectiveness() -> dict:
    """计算每个指标的实战有效性
    
    Returns: {
        indicator_name: {
            'win_rate': float,      # 该指标为正时的交易胜率
            'avg_pnl': float,       # 该指标为正时的平均盈亏%
            'sample_size': int,     # 样本数
            'effectiveness': float, # 综合效果分(-1到+1)
            'optimal_weight': float # 建议权重乘数
        }
    }
    """
    try:
        init_attribution_tables()
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # 获取所有已完成的归因记录
        c.execute('''SELECT indicators_json, outcome, outcome_pnl_pct 
                     FROM indicator_snapshots 
                     WHERE outcome IN ('win', 'loss') AND direction='BUY'
                     ORDER BY trade_date DESC LIMIT 100''')
        records = c.fetchall()
        conn.close()
        
        if len(records) < 5:
            return {}
        
        # 统计每个指标在win/loss中的分布
        indicator_stats = {}
        
        for ind_json, outcome, pnl in records:
            try:
                indicators = json.loads(ind_json)
            except:
                continue
            
            for ind_name, ind_val in indicators.items():
                if ind_name not in indicator_stats:
                    indicator_stats[ind_name] = {
                        'positive_wins': 0, 'positive_losses': 0, 'positive_total_pnl': 0,
                        'negative_wins': 0, 'negative_losses': 0, 'negative_total_pnl': 0,
                        'positive_count': 0, 'negative_count': 0,
                    }
                
                stats = indicator_stats[ind_name]
                
                # 判断指标是否"正面"（看涨信号）
                is_positive = _is_positive_signal(ind_name, ind_val)
                
                if is_positive:
                    stats['positive_count'] += 1
                    stats['positive_total_pnl'] += pnl
                    if outcome == 'win':
                        stats['positive_wins'] += 1
                    else:
                        stats['positive_losses'] += 1
                else:
                    stats['negative_count'] += 1
                    stats['negative_total_pnl'] += pnl
                    if outcome == 'win':
                        stats['negative_wins'] += 1
                    else:
                        stats['negative_losses'] += 1
        
        # 计算效果
        results = {}
        for ind_name, stats in indicator_stats.items():
            pos_total = stats['positive_wins'] + stats['positive_losses']
            if pos_total < 3:
                continue  # 样本太少
            
            win_rate = stats['positive_wins'] / pos_total
            avg_pnl = stats['positive_total_pnl'] / stats['positive_count'] if stats['positive_count'] else 0
            
            # 对照组: 该指标为负时的胜率
            neg_total = stats['negative_wins'] + stats['negative_losses']
            neg_win_rate = stats['negative_wins'] / neg_total if neg_total >= 2 else 0.5
            
            # 效果 = 指标为正时胜率 - 指标为负时胜率
            effectiveness = win_rate - neg_win_rate
            
            # 建议权重: 效果好的放大，效果差的缩小
            if effectiveness > 0.2:
                optimal_weight = 1.0 + min(effectiveness, 0.5)  # 1.2~1.5
            elif effectiveness < -0.2:
                optimal_weight = max(0.3, 1.0 + effectiveness)  # 0.3~0.8
            else:
                optimal_weight = 1.0  # 不显著，保持原样
            
            results[ind_name] = {
                'win_rate': round(win_rate * 100, 1),
                'avg_pnl': round(avg_pnl, 2),
                'sample_size': pos_total,
                'effectiveness': round(effectiveness, 3),
                'optimal_weight': round(optimal_weight, 2),
            }
        
        return results
    except Exception as e:
        print(f"  ⚠️ 指标效果计算失败: {e}")
        return {}


def get_attribution_score_adjustments(tech: dict) -> int:
    """基于归因数据，为当前候选股计算额外分数调整
    
    替代 get_trade_review_insights() 的功能（更快，因为不需要重新获取历史K线）
    """
    if not tech:
        return 0
    
    effectiveness = compute_indicator_effectiveness()
    if not effectiveness:
        return 0
    
    adjustment = 0
    for ind_name, ind_val in tech.items():
        if ind_name not in effectiveness:
            continue
        
        eff = effectiveness[ind_name]
        if eff['sample_size'] < 5:
            continue
        
        is_positive = _is_positive_signal(ind_name, ind_val)
        
        if is_positive:
            if eff['effectiveness'] > 0.15:
                # 指标有效: 额外加分(按效果大小)
                adjustment += int(eff['effectiveness'] * 10)
            elif eff['effectiveness'] < -0.15:
                # 指标反效果: 扣分
                adjustment += int(eff['effectiveness'] * 8)
    
    # 限制总调整幅度
    return max(-15, min(15, adjustment))


def get_idle_days_since_last_trade() -> int:
    """计算距离上次交易(买入或卖出)过了多少个交易日
    
    用于闲置资金递减门槛
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT trade_date FROM trades ORDER BY id DESC LIMIT 1")
        row = c.fetchone()
        conn.close()
        
        if not row:
            return 30  # 无交易记录，视为30天
        
        last_date = datetime.strptime(row[0], '%Y-%m-%d').date()
        cal_days = (date.today() - last_date).days
        # 粗算交易日
        weeks = cal_days // 7
        return cal_days - weeks * 2
    except:
        return 0


def get_idle_threshold_adjustment() -> int:
    """闲置资金递减门槛 — 长期无交易时逐步降低选股门槛
    
    原理: 88%现金闲置本身就是一种成本（机会成本）。
    如果连续多天没有任何交易，说明门槛可能太高。
    
    Returns: 负数 = 门槛降低的分数
    """
    idle_days = get_idle_days_since_last_trade()
    
    if idle_days >= 10:
        return -8  # 10天无交易，大幅降低门槛
    elif idle_days >= 7:
        return -5  # 7天无交易
    elif idle_days >= 5:
        return -3  # 5天无交易
    else:
        return 0


def _is_positive_signal(ind_name: str, ind_val) -> bool:
    """判断某个指标值是否代表"看涨信号"
    
    用于区分指标的正面/负面状态
    """
    # 布尔型指标
    bool_positive = {
        'near_support', 'strong_support', 'near_fib_support', 'near_vp_support',
        'below_poc', 'higher_low', 'bullish_candle', 'volume_dryup',
        'ma_converge_breakout', 'wr_reversal', 'macd_zero_cross_up', 'gap_up',
        'sell_climax', 'nr7', 'macd_hist_bull_div', 'cmf_rising',
    }
    bool_negative = {
        'near_resistance', 'lower_low', 'bearish_candle', 'momentum_decay',
        'volume_price_diverge', 'obv_price_diverge', 'macd_zero_cross_down',
        'gap_down', 'buy_climax', 'macd_hist_bear_div', 'cmf_falling',
    }
    
    if ind_name in bool_positive:
        return bool(ind_val) and ind_val not in (0, '0', 'False', False)
    if ind_name in bool_negative:
        return not ind_val or ind_val in (0, '0', 'False', False)
    
    # 数值型指标
    try:
        val = float(ind_val)
    except (TypeError, ValueError):
        # 字符串型
        if ind_name == 'trend':
            return '多头' in str(ind_val) or '强势' in str(ind_val)
        if ind_name == 'weekly_trend':
            return str(ind_val) == 'up'
        if ind_name == 'macd_signal':
            return str(ind_val) in ('golden_cross', 'bullish')
        if ind_name == 'rsi_divergence':
            return str(ind_val) == 'bullish'
        if ind_name == 'trend_strength':
            return str(ind_val) == 'strong'
        if ind_name == 'kdj_signal':
            return str(ind_val) in ('golden_cross', 'oversold')
        return False
    
    # 数值型判断
    thresholds = {
        'rsi14': lambda v: 30 < v < 65,
        'williams_r': lambda v: v < -60,
        'volume_ratio': lambda v: 1.0 < v < 3.0,
        'obv_trend': lambda v: v > 0.05,
        'cmf_20': lambda v: v > 0.05,
        'price_z_score': lambda v: v < -0.5,
        'boll_pct_b': lambda v: v < 0.4,
        'price_vs_vwap': lambda v: v < -1,
        'atr_pct': lambda v: v < 4,
        'daily_change_pct': lambda v: -2 < v < 3,
        'stock_ret_10d': lambda v: v > -3,
        'stock_ret_20d': lambda v: v > -5,
        'adx': lambda v: v > 25,
        'range_compression': lambda v: v < 0.6,
        'consec_bull_candles': lambda v: v >= 2,
        'consec_bear_candles': lambda v: v < 2,
    }
    
    if ind_name in thresholds:
        return thresholds[ind_name](val)
    
    return val > 0


def get_indicator_summary_for_api() -> dict:
    """为前端API提供指标效果摘要
    
    Returns: {indicators: [...], total_attributed: int, win_count: int, loss_count: int}
    """
    try:
        init_attribution_tables()
        effectiveness = compute_indicator_effectiveness()
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT outcome, COUNT(*) FROM indicator_snapshots WHERE direction='BUY' GROUP BY outcome")
        counts = dict(c.fetchall())
        conn.close()
        
        indicators = []
        for name, eff in sorted(effectiveness.items(), key=lambda x: -x[1]['effectiveness']):
            indicators.append({
                'name': name,
                'win_rate': eff['win_rate'],
                'avg_pnl': eff['avg_pnl'],
                'sample_size': eff['sample_size'],
                'effectiveness': eff['effectiveness'],
                'optimal_weight': eff['optimal_weight'],
                'category': _get_indicator_category(name),
            })
        
        return {
            'indicators': indicators,
            'total_attributed': counts.get('win', 0) + counts.get('loss', 0) + counts.get('pending', 0),
            'win_count': counts.get('win', 0),
            'loss_count': counts.get('loss', 0),
            'pending_count': counts.get('pending', 0),
        }
    except Exception as e:
        return {'indicators': [], 'total_attributed': 0, 'error': str(e)}


def _get_indicator_category(name: str) -> str:
    """指标分类"""
    cats = {
        'trend': '趋势', 'weekly_trend': '趋势', 'macd_signal': '趋势', 
        'macd_zero_cross_up': '趋势', 'macd_zero_cross_down': '趋势',
        'ma_converge_breakout': '趋势', 'adx': '趋势', 'trend_strength': '趋势',
        'rsi14': '动量', 'williams_r': '动量', 'wr_reversal': '动量',
        'momentum_decay': '动量', 'volume_price_diverge': '动量',
        'rsi_divergence': '动量', 'macd_hist_bull_div': '动量', 'macd_hist_bear_div': '动量',
        'volume_ratio': '量价', 'obv_trend': '量价', 'obv_price_diverge': '量价',
        'cmf_20': '量价', 'cmf_rising': '量价', 'cmf_falling': '量价',
        'volume_dryup': '量价', 'sell_climax': '量价', 'buy_climax': '量价',
        'near_support': '位置', 'strong_support': '位置', 'near_resistance': '位置',
        'near_fib_support': '位置', 'near_vp_support': '位置', 'below_poc': '位置',
        'price_z_score': '位置', 'boll_pct_b': '位置', 'price_vs_vwap': '位置',
        'higher_low': '形态', 'lower_low': '形态', 'bullish_candle': '形态',
        'bearish_candle': '形态', 'nr7': '形态', 'range_compression': '形态',
        'gap_up': '形态', 'gap_down': '形态',
        'consec_bull_candles': '形态', 'consec_bear_candles': '形态',
        'atr_pct': '波动', 'daily_change_pct': '波动',
        'stock_ret_10d': '波动', 'stock_ret_20d': '波动',
        'kdj_signal': '动量',
    }
    return cats.get(name, '其他')
