#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v5.73 持倉組合散佈圖 + 賽道集中度檢查
盤中UI增強：可視化持倉分佈、風險提示

Features:
- 按賽道+市值生成散佈圖數據 (Bubble Chart)
- 計算持倉集中度指數 (HHI)
- 風險等級評估 (GREEN/YELLOW/RED)
- 建議分散動作
"""

import sqlite3
import json
import math
from datetime import datetime
from pathlib import Path

DB_PATH = '/home/nikefd/finance-agent/data/trading.db'
SECTOR_MAPPING = {
    '001367': '醫藥',
    '001308': '新能源',
    '600958': '主板',
    # 默認映射
}

def get_portfolio_distribution():
    """獲取持倉按賽道分佈 + 濃度指數"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    # 獲取所有持倉
    positions = conn.execute('SELECT * FROM positions WHERE shares > 0').fetchall()
    conn.close()
    
    if not positions:
        return {
            'positions': [],
            'sectors': {},
            'concentration_index': 0,
            'risk_level': 'GREEN',
            'warning': None,
            'recommendation': '現金待命'
        }
    
    # 計算各賽道總市值
    total_market_value = sum(p['current_price'] * p['shares'] for p in positions)
    sector_distribution = {}
    
    for p in positions:
        sector = SECTOR_MAPPING.get(p['symbol'], '其他')
        market_value = p['current_price'] * p['shares']
        
        if sector not in sector_distribution:
            sector_distribution[sector] = {
                'market_value': 0,
                'positions': [],
                'count': 0
            }
        
        name_str = (p['name'] or '').strip() if p['name'] else ''
        sector_distribution[sector]['positions'].append({
            'code': p['symbol'],
            'name': name_str,
            'shares': p['shares'],
            'current_price': p['current_price'],
            'market_value': market_value,
            'pnl_pct': round((p['current_price'] - p['avg_cost']) / p['avg_cost'] * 100, 2) if p['avg_cost'] else 0,
            'holding_days': _calc_holding_days(p['buy_date'])
        })
        sector_distribution[sector]['market_value'] += market_value
        sector_distribution[sector]['count'] += 1
    
    # 計算持倉集中度指數 (HHI)
    # HHI = Σ(市值占比 %)^2 / 10000
    # 0-2500: 競爭; 2500-1500: 中等; >1500: 高度集中
    sector_weights = []
    for sector, data in sector_distribution.items():
        weight = data['market_value'] / total_market_value if total_market_value > 0 else 0
        sector_weights.append(weight * 100)
    
    hhi = sum(w**2 for w in sector_weights) / 10000
    
    # 風險等級
    if hhi > 3500:
        risk_level = 'RED'
        warning = f'⚠️ 持倉高度集中！HHI={hhi:.1f} | 最大賽道占比 {max(sector_weights):.1f}%'
        recommendation = '建議: 分散到其他賽道或降低持倉規模'
    elif hhi > 2000:
        risk_level = 'YELLOW'
        warning = f'⚠️ 持倉中等集中 | HHI={hhi:.1f}'
        recommendation = '建議: 適度增加賽道多樣性'
    else:
        risk_level = 'GREEN'
        warning = None
        recommendation = '持倉結構良好'
    
    # 構造散佈圖數據
    bubbles = []
    for sector, data in sector_distribution.items():
        for pos in data['positions']:
            bubbles.append({
                'code': pos['code'],
                'name': pos['name'],
                'sector': sector,
                'market_value': pos['market_value'],
                'weight_pct': round(pos['market_value'] / total_market_value * 100, 2) if total_market_value > 0 else 0,
                'pnl_pct': pos['pnl_pct'],
                'holding_days': pos['holding_days'],
                'current_price': pos['current_price'],
                'shares': pos['shares']
            })
    
    return {
        'timestamp': datetime.now().isoformat(),
        'total_positions': len(positions),
        'total_market_value': round(total_market_value, 2),
        'sector_count': len(sector_distribution),
        'bubbles': bubbles,
        'sectors': {
            sector: {
                'market_value': round(data['market_value'], 2),
                'weight_pct': round(data['market_value'] / total_market_value * 100, 2) if total_market_value > 0 else 0,
                'position_count': data['count'],
                'positions': [p for p in data['positions']]
            }
            for sector, data in sector_distribution.items()
        },
        'concentration_metrics': {
            'hhi': round(hhi, 2),
            'max_sector_weight': round(max(sector_weights), 2) if sector_weights else 0,
            'sector_entropy': _calc_entropy(sector_weights)
        },
        'risk_level': risk_level,
        'warning': warning,
        'recommendation': recommendation
    }


def _calc_holding_days(buy_date):
    """計算持倉天數"""
    if not buy_date:
        return None
    try:
        from datetime import datetime as dt
        buy = dt.fromisoformat(buy_date)
        now = dt.now()
        return (now - buy).days
    except:
        return None


def _calc_entropy(weights):
    """計算持倉多樣性 (信息熵) [0-1]
    higher = more diverse"""
    if not weights or sum(weights) == 0:
        return 0
    p = [w / 100 for w in weights if w > 0]
    max_entropy = math.log(len(weights)) if len(weights) > 1 else 1
    entropy = -sum(pi * math.log(pi) for pi in p if pi > 0)
    return round(entropy / max_entropy, 3) if max_entropy > 0 else 0


if __name__ == '__main__':
    data = get_portfolio_distribution()
    print(json.dumps(data, ensure_ascii=False, indent=2))
