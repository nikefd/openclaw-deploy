#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v5.132 盤中實時熱力圖儀表板 (Intraday Heatmap Dashboard)
盤中優化②: 新增熱力圖可視化,實時展示持倉和交易對象的分鐘級活躍度
"""

import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any
import sqlite3
from pathlib import Path

DB_PATH = Path('/home/nikefd/finance-agent/data/trading.db')

def get_intraday_heatmap_v132() -> Dict[str, Any]:
    """主入口: 获取完整热力图数据"""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        
        # 获取持仓数据
        cursor = conn.cursor()
        positions = cursor.execute('SELECT * FROM positions WHERE shares > 0').fetchall()
        
        # 计算持仓热度
        positions_heatmap = []
        for p in positions:
            heat = min(100, max(0, (p['current_price'] * p['shares'] / 10000)))  # 简单权重
            positions_heatmap.append({
                'symbol': p['symbol'],
                'name': p['name'] or 'N/A',
                'heat_score': round(heat, 1),
                'shares': p['shares'],
                'current_price': p['current_price'],
                'pnl_pct': round((p['current_price'] - p['avg_cost']) / p['avg_cost'] * 100, 2) if p['avg_cost'] > 0 else 0,
            })
        positions_heatmap = sorted(positions_heatmap, key=lambda x: x['heat_score'], reverse=True)[:10]
        
        # 获取信号数据
        signals = cursor.execute('SELECT * FROM signals WHERE direction = "BUY" ORDER BY created_at DESC LIMIT 15').fetchall()
        signals_heatmap = []
        for s in signals:
            heat = min(100, max(0, s['strength'] if s['strength'] else 50))
            signals_heatmap.append({
                'symbol': s['symbol'],
                'name': s['name'] or 'N/A',
                'heat_score': round(heat, 1),
                'strength': s['strength'],
                'direction': s.get('direction', 'BUY'),
                'reason': (s['reason'] or '')[:50],
            })
        signals_heatmap = sorted(signals_heatmap, key=lambda x: x['heat_score'], reverse=True)
        
        # 集中度计算
        total_heat = sum(p['heat_score'] for p in positions_heatmap) + sum(s['heat_score'] for s in signals_heatmap)
        
        result = {
            'timestamp': datetime.now().isoformat(),
            'positions_heatmap': positions_heatmap,
            'signals_heatmap': signals_heatmap,
            'sector_heatmap': {},
            'time_distribution': {},
            'summary': {
                'total_heat': round(total_heat, 1),
                'hottest_position': positions_heatmap[0]['symbol'] if positions_heatmap else 'N/A',
                'hottest_signal': signals_heatmap[0]['symbol'] if signals_heatmap else 'N/A',
                'concentration': {
                    'concentration_score': min(100, (sum((p['heat_score']/total_heat)**2 for p in positions_heatmap) if total_heat > 0 else 0) * 100),
                    'risk_level': 'HIGH' if (sum((p['heat_score']/total_heat)**2 for p in positions_heatmap) if total_heat > 0 else 0) > 0.3 else 'LOW',
                },
            }
        }
        
        conn.close()
        return result
        
    except Exception as e:
        print(f"Heatmap error: {e}")
        return {
            'timestamp': datetime.now().isoformat(),
            'positions_heatmap': [],
            'signals_heatmap': [],
            'sector_heatmap': {},
            'time_distribution': {},
            'summary': {'total_heat': 0, 'concentration': {'concentration_score': 0, 'risk_level': 'LOW'}},
            'error': str(e)
        }


if __name__ == '__main__':
    import sys
    result = get_intraday_heatmap_v132()
    print(json.dumps(result, indent=2, ensure_ascii=False))
