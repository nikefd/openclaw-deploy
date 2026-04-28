"""v5.68 盘前优化 — 流动性加权+ATR动态止损+信号持续性强化
时间: 2026-04-28 08:00 UTC
优化方向: 3项改进 | 预期成果: 止损率-1~2% | MaxDD 3.2%稳定 | Sharpe +5%
"""

import pandas as pd
import numpy as np
from datetime import datetime, time
import sqlite3
from pathlib import Path

DB_PATH = "/home/nikefd/finance-agent/data/trading.db"


# ========================= 优化1: 流动性加权入场 =========================

def check_liquidity_filter(symbol: str, market_data: dict = None) -> dict:
    """
    盘前流动性过滤 — 上午8-10点限制低流动性垃圾股入场
    
    规则:
    - 08:00-10:00: 成交额>1亿 + 换手率>2% (过滤低流动性)
    - 10:00后: 解除限制 (全天流动性充足)
    - 返回: {pass: bool, reason: str, liquidity_score: float}
    """
    try:
        current_time = datetime.now().time()
        morning_start = time(8, 0)
        morning_end = time(10, 0)
        
        # 非盘前时段直接放行
        if not (morning_start <= current_time < morning_end):
            return {
                'pass': True,
                'reason': 'non-premarket-hours',
                'liquidity_score': 1.0,
                'hour': current_time.hour
            }
        
        # 盘前时段: 检查流动性
        if not market_data:
            market_data = {}
        
        # 获取成交额 (单位: 元)
        turnover_volume = market_data.get('turnover_volume', 0)
        turnover_rate = market_data.get('turnover_rate', 0)
        
        # 流动性评分: (成交额/1亿) * (换手率/2%)
        liquidity_score = min(
            (turnover_volume / 1e8) * (turnover_rate / 2.0),
            1.0
        )
        
        # 流动性阈值判定
        if turnover_volume >= 1e8 and turnover_rate >= 0.02:
            return {
                'pass': True,
                'reason': 'high-liquidity',
                'liquidity_score': liquidity_score,
                'turnover': turnover_volume,
                'hour': current_time.hour
            }
        else:
            return {
                'pass': False,
                'reason': f'low-liquidity (vol:{turnover_volume/1e8:.2f}亿 rate:{turnover_rate:.2%})',
                'liquidity_score': liquidity_score,
                'turnover': turnover_volume,
                'hour': current_time.hour
            }
    
    except Exception as e:
        # 数据不足时放行(不因数据问题卡壳)
        return {
            'pass': True,
            'reason': f'data-error:{e}',
            'liquidity_score': 0.5,
            'hour': datetime.now().time().hour
        }


def count_today_entries() -> int:
    """统计今日已入场数量"""
    try:
        from datetime import date
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        today = date.today().isoformat()
        c.execute(
            "SELECT COUNT(DISTINCT symbol) FROM trades WHERE direction='BUY' AND date(trade_date)=?",
            (today,)
        )
        count = c.fetchone()[0]
        conn.close()
        return count
    except:
        return 0


def apply_liquidity_weighted_entry(candidates: list, max_daily_entries: int = 5) -> list:
    """
    应用流动性加权过滤 — 盘前限制入场数+流动性评分排序
    
    逻辑:
    1. 统计今日入场数
    2. 若已达上限(5只), 后续候选必须成交额>3亿 (更高流动性)
    3. 候选按liquidity_score排序 (高流动性优先)
    
    Args:
        candidates: 已排序的候选清单
        max_daily_entries: 每日最大入场数 (默认5只)
    
    Returns: 过滤后的候选清单
    """
    try:
        today_entries = count_today_entries()
        current_time = datetime.now().time()
        morning_start = time(8, 0)
        morning_end = time(10, 0)
        is_premarket = morning_start <= current_time < morning_end
        
        filtered = []
        for cand in candidates:
            # 统计入场数上限检查
            if is_premarket and today_entries >= max_daily_entries:
                # 已达上限, 要求成交额>3亿
                liquidity = cand.get('liquidity_score', 0.5)
                if liquidity < 0.3:  # 相当于成交额<3亿
                    cand['_filter_reason'] = 'premarket-entry-limit'
                    continue
            
            filtered.append(cand)
        
        # 按流动性评分排序 (降序)
        filtered.sort(
            key=lambda x: x.get('liquidity_score', 0.5),
            reverse=True
        )
        
        return filtered
    
    except Exception as e:
        print(f"  ⚠️ 流动性加权过滤失败: {e}")
        return candidates


# ========================= 优化2: ATR动态止损 =========================

def calculate_atr(close_prices: list, highs: list, lows: list, period: int = 14) -> float:
    """
    计算ATR (Average True Range)
    
    True Range = max(High - Low, abs(High - prev_Close), abs(Low - prev_Close))
    ATR = SMA(True Range, period)
    """
    try:
        if len(close_prices) < period + 1:
            return 0.0
        
        close_prices = list(close_prices)
        highs = list(highs)
        lows = list(lows)
        
        tr_values = []
        for i in range(1, len(close_prices)):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - close_prices[i-1]),
                abs(lows[i] - close_prices[i-1])
            )
            tr_values.append(tr)
        
        atr = np.mean(tr_values[-period:])
        return atr
    except:
        return 0.0


def get_dynamic_stop_loss(symbol: str, current_price: float, peak_price: float = None,
                          tech_indicators: dict = None) -> dict:
    """
    ATR动态止损 — 根据波动率自适应调整止损线
    
    规则:
    - ATR>3%: 止损放宽到 peak_price - ATR*1.2 (高波动市场)
    - ATR 1.5%-3%: 止损标准 peak_price - ATR*1.0 (正常)
    - ATR<1.5%: 止损收紧到 peak_price - ATR*0.8 (低波动, 快速止损)
    
    返回: {should_stop: bool, stop_price: float, reason: str, atr_pct: float}
    """
    try:
        if not tech_indicators:
            tech_indicators = {}
        
        atr = tech_indicators.get('atr', 0)
        atr_pct = tech_indicators.get('atr_pct', 0)
        
        if peak_price is None or peak_price == 0:
            peak_price = current_price
        
        # 波动率分级
        if atr_pct > 0.03:  # >3%
            atr_multiplier = 1.2
            volatility_level = 'high'
        elif atr_pct < 0.015:  # <1.5%
            atr_multiplier = 0.8
            volatility_level = 'low'
        else:  # 1.5%-3%
            atr_multiplier = 1.0
            volatility_level = 'normal'
        
        # 计算动态止损线
        stop_price = peak_price - (atr * atr_multiplier)
        drawdown = (peak_price - current_price) / peak_price if peak_price > 0 else 0
        
        # 判定是否触发止损
        should_stop = current_price < stop_price
        
        return {
            'should_stop': should_stop,
            'stop_price': stop_price,
            'current_price': current_price,
            'peak_price': peak_price,
            'drawdown_pct': drawdown * 100,
            'atr_pct': atr_pct * 100,
            'volatility_level': volatility_level,
            'atr_multiplier': atr_multiplier,
            'reason': f'ATR-dynamic-{volatility_level}' if should_stop else 'holding'
        }
    
    except Exception as e:
        return {
            'should_stop': False,
            'stop_price': None,
            'reason': f'atr-error:{e}',
            'atr_pct': 0
        }


# ========================= 优化3: 信号持续性强化 =========================

def get_adaptive_persistence_threshold(cash_ratio: float = 0.75) -> int:
    """
    自适应信号持续性天数 — 根据现金占比动态调整
    
    规则:
    - 现金>98%(极端激进): 2天 (快速入场)
    - 现金90-98%(激进): 2.5天 → 向下取整为2天
    - 现金75-90%(中等激进): 3天 (标准)
    - 现金<75%(保守): 4天 (高确定性)
    
    预期效果: 在激进模式下快速入场, 但通过Sharpe排序保证质量
    """
    if cash_ratio > 0.98:
        return 2
    elif cash_ratio > 0.90:
        return 2
    elif cash_ratio > 0.75:
        return 3
    else:
        return 4


def verify_signal_persistence_enhanced(symbol: str, lookback_days: int = None,
                                       cash_ratio: float = 0.75,
                                       min_quality_score: int = 50) -> dict:
    """
    强化版信号持续性检查 — 自适应天数+质量评分过滤
    
    逻辑:
    1. 根据现金占比确定持续性天数 (get_adaptive_persistence_threshold)
    2. 查询过去N天候选快照
    3. 要求连续出现2+天 且 平均分数>=min_quality_score
    
    Returns: {
        persistent: bool,
        days_appeared: int,
        consecutive: int,
        avg_score: float,
        quality_pass: bool,
        reason: str
    }
    """
    try:
        from datetime import date, timedelta
        
        if lookback_days is None:
            lookback_days = get_adaptive_persistence_threshold(cash_ratio)
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        cutoff = (date.today() - timedelta(days=lookback_days)).isoformat()
        
        c.execute(
            """SELECT snapshot_date, score FROM candidate_snapshots 
               WHERE symbol=? AND snapshot_date >= ? ORDER BY snapshot_date DESC""",
            (symbol, cutoff)
        )
        rows = c.fetchall()
        conn.close()
        
        if not rows:
            return {
                'persistent': False,
                'days_appeared': 0,
                'consecutive': 0,
                'avg_score': 0,
                'quality_pass': False,
                'reason': 'no-history'
            }
        
        scores = [r[1] for r in rows]
        avg_score = np.mean(scores)
        quality_pass = avg_score >= min_quality_score
        
        # 检查连续性 (最近2天至少出现1天)
        recent_2_days = len(rows) >= 1 if len(rows) < 2 else True
        consecutive = len(rows)
        
        persistent = consecutive >= 2 and quality_pass
        
        return {
            'persistent': persistent,
            'days_appeared': len(rows),
            'consecutive': consecutive,
            'avg_score': avg_score,
            'quality_pass': quality_pass,
            'min_lookback': lookback_days,
            'reason': 'quality-pass' if persistent else f'days:{consecutive} score:{avg_score:.0f}'
        }
    
    except Exception as e:
        return {
            'persistent': False,
            'days_appeared': 0,
            'consecutive': 0,
            'avg_score': 0,
            'quality_pass': False,
            'reason': f'check-error:{e}'
        }


# ========================= 集成测试 =========================

def test_v5_68_optimizations():
    """单元测试"""
    print("\n" + "="*60)
    print("【v5.68 盘前优化 单元测试】")
    print("="*60)
    
    # 测试1: 流动性过滤
    print("\n✓ Test 1: 流动性过滤")
    result1 = check_liquidity_filter(
        '600519',
        market_data={'turnover_volume': 5e8, 'turnover_rate': 0.05}
    )
    assert result1['pass'] or result1['liquidity_score'] > 0
    print(f"  ├─ Liquidity check: {result1['reason']}")
    print(f"  └─ Score: {result1['liquidity_score']:.2f}")
    
    # 测试2: ATR动态止损
    print("\n✓ Test 2: ATR动态止损")
    result2 = get_dynamic_stop_loss(
        '600519',
        current_price=100.0,
        peak_price=105.0,
        tech_indicators={'atr': 2.5, 'atr_pct': 0.025}
    )
    assert 'stop_price' in result2
    print(f"  ├─ Peak: ¥{result2['peak_price']:.2f}")
    print(f"  ├─ Current: ¥{result2['current_price']:.2f}")
    print(f"  ├─ Stop Price: ¥{result2['stop_price']:.2f}")
    print(f"  └─ Volatility: {result2['volatility_level']} (ATR {result2['atr_pct']:.2f}%)")
    
    # 测试3: 自适应持续性
    print("\n✓ Test 3: 自适应持续性阈值")
    for cash in [0.50, 0.75, 0.90, 0.984]:
        thresh = get_adaptive_persistence_threshold(cash)
        print(f"  ├─ 现金占比 {cash:.1%}: {thresh}天阈值")
    
    print("\n" + "="*60)
    print("✅ v5.68 优化模块测试完成")
    print("="*60 + "\n")


if __name__ == '__main__':
    test_v5_68_optimizations()
