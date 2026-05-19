#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v5.112 盤中實時性能儀表板 (11:30優化)
===========================================
盤中數據視覺化強化：交易計數器、資金流向、策略信號強度

功能：
  1. 實時交易統計 (今日/週/月)
  2. 近3小時資金流向分析
  3. 策略信號強度儀表
  4. 持倉情緒關聯熱力圖
  
作者: Finance Agent v5.112
時間: 2026-05-19 03:30
"""

import json
import sqlite3
from datetime import datetime, timedelta

DB_PATH = '/home/nikefd/finance-agent/data/trading.db'

def query_sqlite(sql):
    """Query database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(sql)
        return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        print(f"[ERROR] SQL: {e}")
        return []

def get_intraday_trade_stats():
    """獲取盤中交易統計"""
    now = datetime.now()
    today = now.strftime('%Y-%m-%d')
    
    # 今日交易
    today_trades = query_sqlite(f"""
        SELECT direction, COUNT(*) as cnt, SUM(shares) as total_shares
        FROM trades
        WHERE DATE(trade_date) = '{today}'
        GROUP BY direction
    """)
    
    buy_count = sum(t['cnt'] for t in today_trades if t['direction'] == 'BUY')
    sell_count = sum(t['cnt'] for t in today_trades if t['direction'] == 'SELL')
    
    # 週交易
    week_start = (now - timedelta(days=now.weekday())).strftime('%Y-%m-%d')
    week_trades = query_sqlite(f"""
        SELECT COUNT(*) as cnt FROM trades
        WHERE DATE(trade_date) >= '{week_start}'
    """)
    week_count = week_trades[0]['cnt'] if week_trades else 0
    
    # 月交易
    month_start = now.strftime('%Y-%m-01')
    month_trades = query_sqlite(f"""
        SELECT COUNT(*) as cnt FROM trades
        WHERE DATE(trade_date) >= '{month_start}'
    """)
    month_count = month_trades[0]['cnt'] if month_trades else 0
    
    return {
        'today': {'buys': buy_count, 'sells': sell_count, 'total': buy_count + sell_count},
        'week': {'total': week_count},
        'month': {'total': month_count},
        'target_daily_trades': 3,  # 目標每日交易3次
        'achievement_rate': min(100, (buy_count + sell_count) / 3 * 100)
    }

def get_capital_flow_3h():
    """獲取近3小時資金流向"""
    now = datetime.now()
    three_hours_ago = (now - timedelta(hours=3)).strftime('%Y-%m-%d %H:%M:%S')
    
    # 近3小時現金變化
    snapshots = query_sqlite(f"""
        SELECT 
            strftime('%H:00', trade_date) as hour,
            COUNT(*) as trade_count,
            SUM(CASE WHEN direction='BUY' THEN shares ELSE 0 END) as buy_volume,
            SUM(CASE WHEN direction='SELL' THEN shares ELSE 0 END) as sell_volume
        FROM trades
        WHERE trade_date >= '{three_hours_ago}'
        GROUP BY hour
        ORDER BY hour DESC
        LIMIT 3
    """)
    
    # 計算現金淨流出
    account = query_sqlite("SELECT cash, total_value FROM account ORDER BY id DESC LIMIT 1")
    if account:
        cash_ratio = account[0]['cash'] / account[0]['total_value'] * 100 if account[0]['total_value'] > 0 else 0
    else:
        cash_ratio = 100
    
    return {
        'hourly_activity': snapshots,
        'current_cash_ratio': round(cash_ratio, 2),
        'capital_utilization': round(100 - cash_ratio, 2),
        'flow_direction': '淨流入' if len(snapshots) > 1 and snapshots[0]['buy_volume'] > snapshots[1]['sell_volume'] else '淨流出'
    }

def get_strategy_signal_strength():
    """獲取策略信號強度"""
    # 從最新報告獲取信號品質
    signals = query_sqlite("""
        SELECT 
            strategy,
            COUNT(*) as signal_count,
            AVG(strength) as avg_strength
        FROM signals
        WHERE created_at >= datetime('now', '-24 hours')
        GROUP BY strategy
        ORDER BY avg_strength DESC
    """)
    
    result = []
    for sig in signals:
        strength = sig['avg_strength'] or 50
        intensity = '🔴 弱' if strength < 40 else '🟡 中' if strength < 70 else '🟢 強'
        result.append({
            'strategy': sig['strategy'],
            'signal_count': sig['signal_count'],
            'strength': round(strength, 1),
            'intensity': intensity,
            'bar': '█' * int(strength / 10) + '░' * (10 - int(strength / 10))
        })
    
    return {
        'strategies': result,
        'overall_strength': round(sum(s['strength'] for s in result) / len(result), 1) if result else 50,
        'recommendation': '建議持倉' if (result and sum(s['strength'] for s in result) / len(result) > 60) else '風險管理'
    }

def get_sentiment_position_correlation():
    """獲取市場情緒與持倉關聯分析"""
    # 當前持倉
    positions = query_sqlite("""
        SELECT symbol, current_price, avg_cost, shares
        FROM positions
        WHERE shares > 0
        ORDER BY shares DESC
    """)
    
    # 當前情緒
    snapshot = query_sqlite("""
        SELECT sentiment_score, sentiment_label
        FROM daily_snapshots
        ORDER BY date DESC
        LIMIT 1
    """)
    
    sentiment_score = snapshot[0]['sentiment_score'] if snapshot else 50
    sentiment_label = snapshot[0]['sentiment_label'] if snapshot else '中性'
    
    # 情緒與持倉權重建議
    correlation = []
    for pos in positions:
        pnl_pct = ((pos['current_price'] - pos['avg_cost']) / pos['avg_cost'] * 100) if pos['avg_cost'] > 0 else 0
        
        # 根據情緒調整權重建議
        if sentiment_score > 70:  # 樂觀
            weight_adjust = 'UP' if pnl_pct > 0 else 'HOLD'
        elif sentiment_score < 40:  # 悲觀
            weight_adjust = 'DOWN' if pnl_pct < 0 else 'HOLD'
        else:  # 中性
            weight_adjust = 'HOLD'
        
        correlation.append({
            'symbol': pos['symbol'],
            'pnl_pct': round(pnl_pct, 2),
            'weight_adjust': weight_adjust,
            'emoji': '📈' if pnl_pct > 0 else '📉' if pnl_pct < 0 else '➡️'
        })
    
    return {
        'current_sentiment': sentiment_label,
        'sentiment_score': sentiment_score,
        'positions_correlation': correlation,
        'action_plan': '逐步減倉管理風險' if sentiment_score < 40 else '保持持倉' if sentiment_score < 70 else '適度加倉'
    }

def get_dashboard_aggregate():
    """聚合所有盤中性能指標"""
    return {
        'timestamp': datetime.now().isoformat(),
        'trade_stats': get_intraday_trade_stats(),
        'capital_flow': get_capital_flow_3h(),
        'strategy_signals': get_strategy_signal_strength(),
        'sentiment_correlation': get_sentiment_position_correlation(),
        'version': 'v5.112',
        'last_update_time': datetime.now().strftime('%H:%M:%S')
    }

if __name__ == '__main__':
    data = get_dashboard_aggregate()
    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))
