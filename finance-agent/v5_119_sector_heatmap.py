#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v5.119 盤中UI優化②: 賽道熱力圖 (視覺化績效對比)
功能:
  - 5賽道實時熱力圖 (顏色/大小表達績效)
  - 股票個體表現排序
  - 風險熱度警告 (紅/黃/綠)
  - 實時更新API
"""

import json
import sqlite3
from datetime import datetime

def get_sector_heatmap_data():
    """生成賽道熱力圖數據"""
    conn = sqlite3.connect('/home/nikefd/finance-agent/data/trading.db')
    conn.row_factory = sqlite3.Row
    
    # 獲取所有位置
    positions = conn.execute("SELECT * FROM positions").fetchall()
    
    # 賽道配置 (基於v5.117)
    sector_config = {
        'tech': {
            'name': '科技成長',
            'symbols': ['300124', '300750', '300760', '300059', '002460'],
            'weight': 0.20,
            'strategy': 'MACD+RSI',
            'target_sharpe': 2.35,
        },
        'energy': {
            'name': '新能源',
            'symbols': ['600690', '601888', '000591', '300274'],
            'weight': 0.15,
            'strategy': 'MOMENTUM_SENTIMENT',
            'target_sharpe': 2.0,
        },
        'consumer': {
            'name': '消費白馬',
            'symbols': ['600519', '600887', '603589', '002415'],
            'weight': 0.25,
            'strategy': 'MA_REVERT_VOL',
            'target_sharpe': 1.8,
        },
        'finance': {
            'name': '金融週期',
            'symbols': ['601398', '000333', '601012', '601988'],
            'weight': 0.20,
            'strategy': 'IV_ARBITRAGE',
            'target_sharpe': 2.1,
        },
        'estate': {
            'name': '地產及其他',
            'symbols': ['601939', '000651', '600606'],
            'weight': 0.20,
            'strategy': 'MULTI_FACTOR',
            'target_sharpe': 1.5,
        },
    }
    
    heatmap_data = {
        'timestamp': datetime.now().isoformat(),
        'sectors': {},
        'stocks': [],
        'summary': {},
    }
    
    # 計算賽道數據
    for sector_key, config in sector_config.items():
        sector_positions = [p for p in positions if p['symbol'] in config['symbols']]
        
        if not sector_positions:
            heatmap_data['sectors'][sector_key] = {
                'name': config['name'],
                'count': 0,
                'total_pnl': 0,
                'avg_return': 0,
                'heat': 'neutral',
                'heat_value': 0,
            }
            continue
        
        # 計算賽道績效
        total_pnl = sum((p['current_price'] - p['avg_cost']) * p['shares'] for p in sector_positions if p['avg_cost'])
        avg_return = sum(((p['current_price'] - p['avg_cost']) / p['avg_cost'] * 100) for p in sector_positions if p['avg_cost']) / len(sector_positions)
        
        # 熱度評分 (0-100)
        heat_value = min(100, max(0, 50 + avg_return * 3))  # 基於收益率
        
        if heat_value >= 70:
            heat = 'hot'  # 紅
        elif heat_value >= 50:
            heat = 'warm'  # 黃
        else:
            heat = 'cold'  # 藍
        
        heatmap_data['sectors'][sector_key] = {
            'name': config['name'],
            'strategy': config['strategy'],
            'count': len(sector_positions),
            'weight': config['weight'],
            'total_pnl': round(total_pnl, 2),
            'avg_return': round(avg_return, 2),
            'target_sharpe': config['target_sharpe'],
            'heat': heat,
            'heat_value': round(heat_value, 1),
        }
    
    # 收集所有股票績效
    for pos in positions:
        pnl = (pos['current_price'] - pos['avg_cost']) * pos['shares'] if pos['avg_cost'] else 0
        pnl_pct = ((pos['current_price'] - pos['avg_cost']) / pos['avg_cost'] * 100) if pos['avg_cost'] else 0
        
        # 判斷熱度
        if pnl_pct >= 5:
            heat = 'hot'
        elif pnl_pct >= 2:
            heat = 'warm'
        elif pnl_pct >= -2:
            heat = 'neutral'
        elif pnl_pct >= -5:
            heat = 'cool'
        else:
            heat = 'cold'
        
        heatmap_data['stocks'].append({
            'symbol': pos['symbol'],
            'name': pos['name'],
            'pnl': round(pnl, 2),
            'pnl_pct': round(pnl_pct, 2),
            'price': pos['current_price'],
            'avg_cost': pos['avg_cost'],
            'shares': pos['shares'],
            'heat': heat,
        })
    
    # 排序
    heatmap_data['stocks'].sort(key=lambda x: x['pnl_pct'], reverse=True)
    
    # 摘要
    total_positions = len(positions)
    hot_count = sum(1 for p in heatmap_data['stocks'] if p['heat'] in ['hot', 'warm'])
    cold_count = sum(1 for p in heatmap_data['stocks'] if p['heat'] in ['cold', 'cool'])
    
    heatmap_data['summary'] = {
        'total_positions': total_positions,
        'hot_positions': hot_count,
        'cold_positions': cold_count,
        'neutral_positions': total_positions - hot_count - cold_count,
        'sector_count': len([s for s in heatmap_data['sectors'].values() if s['count'] > 0]),
    }
    
    conn.close()
    return heatmap_data

def generate_heatmap_html(heatmap_data):
    """生成HTML熱力圖"""
    sectors = heatmap_data['sectors']
    
    # 熱度顏色映射
    color_map = {
        'hot': '#e63946',      # 紅
        'warm': '#f1faee',     # 黃
        'cold': '#1d3557',     # 藍
        'cool': '#457b9d',     # 淡藍
        'neutral': '#a8dadc',  # 灰
    }
    
    html = '<div class="heatmap-container">\n'
    html += '<div class="heatmap-sectors">\n'
    
    for sector_key, data in sorted(sectors.items(), key=lambda x: x[1]['heat_value'], reverse=True):
        if data['count'] == 0:
            continue
        
        color = color_map.get(data['heat'], '#a8dadc')
        html += f'''
        <div class="heatmap-sector" style="border-left:4px solid {color}; background: rgba(166,214,220,0.1);">
            <div class="heat-sector-title">{data['name']}</div>
            <div class="heat-sector-metrics">
                <span>持倉: {data['count']}個</span>
                <span>P&L: <span style="color:{color}">${data['total_pnl']:.0f}</span></span>
                <span>Return: <span style="color:{color}">{data['avg_return']:.1f}%</span></span>
                <span>Sharpe: {data['target_sharpe']}</span>
            </div>
            <div class="heat-meter" style="background: linear-gradient(90deg, #1d3557 0%, #457b9d 25%, #a8dadc 50%, #f1faee 75%, #e63946 100%); height: 4px; border-radius: 2px; margin-top: 6px;"></div>
        </div>
        '''
    
    html += '</div>\n'
    html += '</div>\n'
    return html

if __name__ == '__main__':
    heatmap = get_sector_heatmap_data()
    heatmap['html'] = generate_heatmap_html(heatmap)
    print(json.dumps(heatmap, indent=2, ensure_ascii=False))
