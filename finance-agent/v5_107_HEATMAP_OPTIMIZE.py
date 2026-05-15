#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v5.107 盤前優化④ - 實時熱力圖引擎 (UI增強)
功能: 情感/勝率/持倉多維熱力圖 + 即時數據聚合
時間: 2026-05-15 03:30
"""

import sqlite3
import json
from datetime import datetime, timedelta
from collections import defaultdict

DB_PATH = '/home/nikefd/finance-agent/data/trading.db'

def query_db(sql):
    """執行SQL查詢"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(sql)
        return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        print(f'DB Error: {e}')
        return []
    finally:
        conn.close()

def get_sentiment_heatmap_v107():
    """
    獲取情感熱力圖
    - 過去30天情感評分 (0-100)
    - 情感分級統計
    - 情感變化趨勢
    """
    snapshots = query_db("""
        SELECT date, sentiment_score
        FROM daily_snapshots
        WHERE date >= date('now', '-30 days')
        ORDER BY date ASC
    """)
    
    # 構建熱力圖數據
    heatmap_data = []
    sentiment_counts = defaultdict(int)
    
    for snap in snapshots:
        score = snap['sentiment_score'] or 50
        # 根據score確定label
        if score >= 75:
            label = '極貪婪'
            color_level = 5
        elif score >= 60:
            label = '貪婪'
            color_level = 4
        elif score >= 45:
            label = '中性'
            color_level = 3
        elif score >= 30:
            label = '謹慎'
            color_level = 2
        else:
            label = '極恐慌'
            color_level = 1
        
        heatmap_data.append({
            'date': snap['date'],
            'score': round(score, 1),
            'level': label,
            'color_level': color_level,
            'label': label
        })
        
        sentiment_counts[label] += 1
    
    # 計算分佈統計
    total_days = len(heatmap_data)
    distribution = {
        '極貪婪': round(sentiment_counts['極貪婪'] / total_days * 100 if total_days > 0 else 0, 1),
        '貪婪': round(sentiment_counts['貪婪'] / total_days * 100 if total_days > 0 else 0, 1),
        '中性': round(sentiment_counts['中性'] / total_days * 100 if total_days > 0 else 0, 1),
        '謹慎': round(sentiment_counts['謹慎'] / total_days * 100 if total_days > 0 else 0, 1),
        '極恐慌': round(sentiment_counts['極恐慌'] / total_days * 100 if total_days > 0 else 0, 1),
    }
    
    # 計算7日trend
    if len(heatmap_data) >= 7:
        week_avg = sum(h['score'] for h in heatmap_data[-7:]) / 7
        prev_week_avg = sum(h['score'] for h in heatmap_data[-14:-7]) / 7 if len(heatmap_data) >= 14 else week_avg
        trend = '↑ 升溫' if week_avg > prev_week_avg else '↓ 降溫' if week_avg < prev_week_avg else '→ 平穩'
    else:
        trend = '→ 平穩'
    
    return {
        'heatmap': heatmap_data,
        'distribution': distribution,
        'trend': trend,
        'current_score': heatmap_data[-1]['score'] if heatmap_data else 50,
        'current_level': heatmap_data[-1]['level'] if heatmap_data else '中性'
    }

def get_winrate_heatmap_v107():
    """
    獲取勝率熱力圖
    - 按策略分組統計勝率
    - 週期性勝率變化
    """
    trades = query_db("""
        SELECT symbol, direction, price, trade_date
        FROM trades
        ORDER BY trade_date ASC
    """)
    
    if not trades:
        return {'strategies': {'overall': {'winrate': 0, 'trades': 0, 'wins': 0, 'color_level': 0}}, 'weekly': [], 'overall_winrate': 0}
    
    # 按symbol分組計算勝率
    strategy_stats = defaultdict(lambda: {'buys': 0, 'sells': 0, 'wins': 0})
    
    buy_prices = {}  # symbol -> [prices]
    
    for trade in trades:
        symbol = trade['symbol']
        
        if trade['direction'] == 'BUY':
            strategy_stats['overall']['buys'] += 1
            if symbol not in buy_prices:
                buy_prices[symbol] = []
            buy_prices[symbol].append(trade['price'])
        else:  # SELL
            strategy_stats['overall']['sells'] += 1
            if symbol in buy_prices:
                avg_buy = sum(buy_prices[symbol]) / len(buy_prices[symbol])
                if trade['price'] > avg_buy:
                    strategy_stats['overall']['wins'] += 1
    
    # 構建策略熱力
    strategy_heatmap = {}
    total_wins = 0
    total_sells = 0
    
    for strategy, stats in strategy_stats.items():
        if stats['sells'] > 0:
            winrate = (stats['wins'] / stats['sells']) * 100
            color_level = 5 if winrate >= 60 else 4 if winrate >= 50 else 3 if winrate >= 40 else 2 if winrate >= 30 else 1
        else:
            winrate = 0
            color_level = 0
        
        strategy_heatmap[strategy] = {
            'winrate': round(winrate, 1),
            'trades': stats['sells'],
            'wins': stats['wins'],
            'color_level': color_level
        }
        total_wins += stats['wins']
        total_sells += stats['sells']
    
    overall_winrate = (total_wins / total_sells * 100) if total_sells > 0 else 0
    
    # 週期性勝率 (過去30天按週分組)
    weekly_data = []
    now = datetime.now()
    for week_offset in range(5):
        week_start = now - timedelta(days=7 * (week_offset + 1))
        week_end = now - timedelta(days=7 * week_offset)
        
        week_trades = [t for t in trades 
                      if datetime.fromisoformat(t['trade_date']) >= week_start 
                      and datetime.fromisoformat(t['trade_date']) < week_end]
        
        sell_trades = [t for t in week_trades if t['direction'] == 'SELL']
        if sell_trades:
            # 計算該週的勝率
            week_wins = 0
            for t in sell_trades:
                if t['symbol'] in buy_prices:
                    avg_buy = sum(buy_prices[t['symbol']]) / len(buy_prices[t['symbol']])
                    if t['price'] > avg_buy:
                        week_wins += 1
            week_wr = (week_wins / len(sell_trades)) * 100
        else:
            week_wr = 0
        
        weekly_data.insert(0, {
            'week': f"W{week_offset + 1}",
            'winrate': round(week_wr, 1),
            'color_level': 5 if week_wr >= 60 else 4 if week_wr >= 50 else 3 if week_wr >= 40 else 2 if week_wr >= 30 else 1
        })
    
    return {
        'strategies': strategy_heatmap,
        'weekly': weekly_data,
        'overall_winrate': round(overall_winrate, 1)
    }

def get_position_heatmap_v107():
    """
    獲取持倉熱力圖
    - 按股票分佈視覺化
    - 按漲跌分佈
    - 集中度指標
    """
    positions = query_db("SELECT symbol, name, shares, avg_cost, current_price FROM positions WHERE shares > 0")
    
    if not positions:
        return {'stocks': {}, 'pnl_distribution': {'up': 0, 'down': 0, 'up_ratio': 0}, 'concentration': 0, 'total_positions': 0}
    
    # 計算持倉分佈
    stock_dist = {}
    total_value = 0
    up_count = 0
    down_count = 0
    
    for pos in positions:
        symbol = pos['symbol']
        pos_value = pos['current_price'] * pos['shares']
        
        stock_dist[symbol] = {
            'name': pos['name'],
            'shares': pos['shares'],
            'total_value': pos_value
        }
        total_value += pos_value
        
        pnl_pct = ((pos['current_price'] - pos['avg_cost']) / pos['avg_cost'] * 100) if pos['avg_cost'] > 0 else 0
        if pnl_pct > 0:
            up_count += 1
        else:
            down_count += 1
    
    # 構建heatmap
    stock_heatmap = {}
    for symbol, data in stock_dist.items():
        pct = (data['total_value'] / total_value * 100) if total_value > 0 else 0
        color_level = 5 if pct >= 20 else 4 if pct >= 15 else 3 if pct >= 10 else 2 if pct >= 5 else 1
        stock_heatmap[symbol] = {
            'name': data['name'],
            'percentage': round(pct, 1),
            'shares': data['shares'],
            'color_level': color_level
        }
    
    # PnL分佈
    pnl_dist = {
        'up': up_count,
        'down': down_count,
        'up_ratio': round(up_count / (up_count + down_count) * 100 if (up_count + down_count) > 0 else 0, 1)
    }
    
    # 集中度 (Herfindahl指數)
    concentration = sum((data['total_value'] / total_value) ** 2 for data in stock_dist.values()) * 100 if total_value > 0 else 0
    
    return {
        'stocks': stock_heatmap,
        'pnl_distribution': pnl_dist,
        'concentration': round(concentration, 1),
        'total_positions': len(positions)
    }

def get_dashboard_aggregate_v107():
    """
    聚合API - 一次請求獲取所有熱力圖數據
    減少前端API調用次數，提升頁面加載速度
    """
    return {
        'sentiment_heatmap': get_sentiment_heatmap_v107(),
        'winrate_heatmap': get_winrate_heatmap_v107(),
        'position_heatmap': get_position_heatmap_v107(),
        'timestamp': datetime.now().isoformat()
    }

if __name__ == '__main__':
    # 測試
    print(json.dumps(get_dashboard_aggregate_v107(), ensure_ascii=False, indent=2, default=str))
