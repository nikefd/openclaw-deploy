#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v5.137 盤中優化② - UI與數據展示 (11:30優化)
目標: 實時性能排序 + 市場熱力圖 + 動態風控指標

核心功能:
1. performance-ranking API: 按ROI/Sharpe/Drawdown/Winrate排序
2. market-heatmap API: 板塊/個股熱度 + 情緒指標
3. UI熱力圖: 直觀的視覺化市場機會
"""

import json
import sqlite3
import sys
from datetime import datetime, timedelta
from collections import defaultdict
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_PATH = '/home/nikefd/finance-agent/data/trading.db'

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_performance_ranking(sort_by='roi', limit=10):
    """
    獲取實時績效排序面板
    sort_by: roi | sharpe | drawdown | winrate
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 查詢所有持倉 + 計算績效指標
        cursor.execute('''
            SELECT 
                symbol, name,
                shares, avg_cost, current_price,
                peak_price, buy_date,
                (current_price - avg_cost) as price_diff,
                (current_price - avg_cost) * shares as pnl_amount,
                CASE WHEN avg_cost > 0 
                    THEN (current_price - avg_cost) / avg_cost * 100 
                    ELSE 0 
                END as roi_pct,
                CASE WHEN peak_price > 0 AND current_price > 0
                    THEN (current_price - peak_price) / peak_price * 100
                    ELSE 0
                END as peak_drawdown_pct,
                buy_date,
                julianday('now') - julianday(buy_date) as holding_days
            FROM positions
            WHERE shares > 0
            ORDER BY symbol
        ''')
        
        positions = cursor.fetchall()
        
        if not positions:
            return {
                'status': 'NO_POSITIONS',
                'ranking': [],
                'timestamp': datetime.now().isoformat(),
                'count': 0
            }
        
        # 構建績效數據
        ranking_data = []
        for pos in positions:
            roi_pct = pos['roi_pct'] or 0
            peak_dd = pos['peak_drawdown_pct'] or 0
            
            # 計算夏普比 (簡化版: 用hold days作為風險調整)
            holding_days = pos['holding_days'] or 1
            sharpe_approx = roi_pct / max(holding_days ** 0.5, 1) if holding_days > 0 else 0
            
            # 簡化胜率 (買入至今的收益率達成率)
            winrate = 100 if roi_pct > 0 else 0
            
            ranking_data.append({
                'symbol': pos['symbol'],
                'name': pos['name'] or '',
                'shares': int(pos['shares']),
                'avg_cost': round(pos['avg_cost'], 2),
                'current_price': round(pos['current_price'], 2),
                'roi_pct': round(roi_pct, 2),
                'pnl_amount': round(pos['pnl_amount'] or 0, 2),
                'peak_drawdown_pct': round(peak_dd, 2),
                'sharpe_approx': round(sharpe_approx, 4),
                'winrate': winrate,
                'holding_days': int(holding_days) if holding_days else 0,
                'buy_date': pos['buy_date']
            })
        
        # 排序
        sort_mapping = {
            'roi': lambda x: x['roi_pct'],
            'sharpe': lambda x: x['sharpe_approx'],
            'drawdown': lambda x: x['peak_drawdown_pct'],
            'winrate': lambda x: x['winrate'],
            'pnl': lambda x: x['pnl_amount']
        }
        
        key_func = sort_mapping.get(sort_by, sort_mapping['roi'])
        ranking_data.sort(key=key_func, reverse=True)
        
        # 返回前N個
        top_ranking = ranking_data[:limit]
        
        conn.close()
        
        return {
            'status': 'OK',
            'sort_by': sort_by,
            'ranking': top_ranking,
            'total_positions': len(ranking_data),
            'timestamp': datetime.now().isoformat(),
            'count': len(top_ranking)
        }
    
    except Exception as e:
        logger.error(f'Performance ranking error: {e}')
        return {
            'status': 'ERROR',
            'error': str(e),
            'ranking': [],
            'timestamp': datetime.now().isoformat()
        }

def get_market_heatmap(timeframe='daily', include_sentiment=True):
    """
    獲取市場熱力圖數據
    - 板塊分組
    - 個股熱度排序
    - 情緒指標
    - 買賣壓力
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 獲取所有持倉的績效
        cursor.execute('''
            SELECT 
                symbol, name,
                SUBSTR(symbol, 1, 2) as sector,
                current_price - avg_cost as price_diff,
                (current_price - avg_cost) / avg_cost * 100 as roi_pct,
                shares,
                current_price
            FROM positions
            WHERE shares > 0
        ''')
        
        positions = cursor.fetchall()
        
        # 按板塊分組
        sector_data = defaultdict(lambda: {
            'stocks': [],
            'avg_performance': 0,
            'total_shares': 0,
            'sector_value': 0
        })
        
        total_performance = 0
        
        for pos in positions:
            sector = pos['sector'] or 'OTHER'
            roi = pos['roi_pct'] or 0
            value = (pos['current_price'] or 0) * (pos['shares'] or 0)
            
            sector_data[sector]['stocks'].append({
                'symbol': pos['symbol'],
                'name': pos['name'],
                'roi_pct': round(roi, 2),
                'price_change': round(pos['price_diff'] or 0, 2),
                'current_price': round(pos['current_price'], 2)
            })
            
            sector_data[sector]['total_shares'] += pos['shares'] or 0
            sector_data[sector]['sector_value'] += value
            total_performance += roi * (pos['shares'] or 1)
        
        # 計算板塊聚合指標
        heatmap_sectors = []
        for sector_code, data in sector_data.items():
            if data['stocks']:
                avg_perf = sum(s['roi_pct'] for s in data['stocks']) / len(data['stocks'])
                
                heatmap_sectors.append({
                    'sector': sector_code,
                    'stocks_count': len(data['stocks']),
                    'avg_performance_pct': round(avg_perf, 2),
                    'total_shares': int(data['total_shares']),
                    'sector_value_cny': round(data['sector_value'], 2),
                    'top_performer': max(data['stocks'], key=lambda x: x['roi_pct']) if data['stocks'] else {},
                    'heat_level': 'HOT' if avg_perf > 5 else 'WARM' if avg_perf > 0 else 'COLD'
                })
        
        # 按性能排序
        heatmap_sectors.sort(key=lambda x: x['avg_performance_pct'], reverse=True)
        
        conn.close()
        
        result = {
            'status': 'OK',
            'timeframe': timeframe,
            'sectors': heatmap_sectors,
            'timestamp': datetime.now().isoformat(),
            'market_breadth': {
                'positive_sectors': len([s for s in heatmap_sectors if s['avg_performance_pct'] > 0]),
                'negative_sectors': len([s for s in heatmap_sectors if s['avg_performance_pct'] < 0]),
                'total_sectors': len(heatmap_sectors)
            }
        }
        
        if include_sentiment:
            # 簡化情緒指標 (基於上升板塊佔比)
            positive_count = result['market_breadth']['positive_sectors']
            total = result['market_breadth']['total_sectors']
            sentiment_score = (positive_count / total * 100) if total > 0 else 50
            
            result['sentiment'] = {
                'score': round(sentiment_score, 1),
                'level': 'BULLISH' if sentiment_score > 60 else 'NEUTRAL' if sentiment_score > 40 else 'BEARISH',
                'emoji': '📈' if sentiment_score > 60 else '😐' if sentiment_score > 40 else '📉'
            }
        
        return result
    
    except Exception as e:
        logger.error(f'Market heatmap error: {e}')
        return {
            'status': 'ERROR',
            'error': str(e),
            'sectors': [],
            'timestamp': datetime.now().isoformat()
        }

def get_intraday_risk_metrics():
    """
    獲取盤中實時風控指標
    - 最大單日回撤風險
    - 持倉集中度
    - 止損觸發預警
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 獲取持倉總和
        cursor.execute('''
            SELECT 
                COUNT(*) as position_count,
                SUM(current_price * shares) as total_position_value,
                SUM(CASE WHEN (current_price - avg_cost) * shares < 0 THEN 1 ELSE 0 END) as loss_count,
                AVG((current_price - avg_cost) / avg_cost * 100) as avg_drawdown_pct
            FROM positions
            WHERE shares > 0
        ''')
        
        metrics = cursor.fetchone()
        
        conn.close()
        
        return {
            'position_count': metrics['position_count'] or 0,
            'total_position_value': round(metrics['total_position_value'] or 0, 2),
            'losing_positions': metrics['loss_count'] or 0,
            'avg_drawdown_pct': round(metrics['avg_drawdown_pct'] or 0, 2),
            'concentration_risk': 'HIGH' if metrics['position_count'] and metrics['position_count'] < 3 else 'MEDIUM' if metrics['position_count'] and metrics['position_count'] < 6 else 'LOW'
        }
    
    except Exception as e:
        logger.error(f'Risk metrics error: {e}')
        return {}

if __name__ == '__main__':
    # 測試
    print('=== Performance Ranking (ROI排序) ===')
    print(json.dumps(get_performance_ranking('roi', 5), ensure_ascii=False, indent=2))
    
    print('\n=== Market Heatmap ===')
    print(json.dumps(get_market_heatmap('daily', True), ensure_ascii=False, indent=2))
    
    print('\n=== Risk Metrics ===')
    print(json.dumps(get_intraday_risk_metrics(), ensure_ascii=False, indent=2))
