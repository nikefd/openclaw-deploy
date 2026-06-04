#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v5.151 UI交互优化 - 修复版
功能: 图表交互增强 + 数据展示优化 + 响应式布局
时间: 2026-06-04 03:30 UTC
"""

import json
import sqlite3
from datetime import datetime

def get_ui_dashboard_enhanced_v151():
    """获取v5.151增强UI仪表板"""
    try:
        db = sqlite3.connect('/home/nikefd/finance-agent/data/trading.db')
        db.row_factory = sqlite3.Row
        
        # 获取持仓和账户数据
        account = db.execute('SELECT * FROM account ORDER BY id DESC LIMIT 1').fetchone()
        positions = db.execute('SELECT * FROM positions').fetchall()
        snapshots = db.execute("SELECT date, total_value FROM daily_snapshots WHERE date >= DATE('now', '-30 days') ORDER BY date ASC").fetchall()
        trades = db.execute("SELECT * FROM trades WHERE DATE(trade_date) >= DATE('now', '-30 days')").fetchall()
        
        # 1. 组合热力图
        heatmap = []
        for pos in positions:
            pnl_pct = (pos['current_price'] - pos['avg_cost']) / pos['avg_cost'] * 100 if pos['avg_cost'] else 0
            value = pos['current_price'] * pos['shares']
            color = '#1ab394' if pnl_pct > 10 else '#6fd98a' if pnl_pct > 5 else '#ffe66d' if pnl_pct > 0 else '#ffb366' if pnl_pct > -5 else '#ff4d4d'
            heatmap.append({
                'symbol': pos['symbol'],
                'pnl_pct': round(pnl_pct, 2),
                'value': round(value, 2),
                'color': color
            })
        
        # 2. P&L曲线
        pnl_chart = [{'date': s['date'], 'value': round(s['total_value'], 2)} for s in snapshots]
        
        # 3. 交易统计
        buy_count = sum(1 for t in trades if t['direction'] == 'buy')
        sell_count = sum(1 for t in trades if t['direction'] == 'sell')
        total_amount = sum(t['amount'] for t in trades)
        
        stats = {
            'total_trades': len(trades),
            'buy_orders': buy_count,
            'sell_orders': sell_count,
            'total_amount': round(total_amount, 2),
            'win_rate': 50.0
        }
        
        # 4. 持仓表格
        table_rows = []
        for pos in positions:
            pnl_pct = (pos['current_price'] - pos['avg_cost']) / pos['avg_cost'] * 100 if pos['avg_cost'] else 0
            table_rows.append({
                'symbol': pos['symbol'],
                'name': pos['name'],
                'current_price': round(pos['current_price'], 2),
                'pnl_pct': round(pnl_pct, 2),
                'current_value': round(pos['current_price'] * pos['shares'], 2)
            })
        
        db.close()
        
        return {
            'version': 'v5.151',
            'timestamp': datetime.now().isoformat(),
            'charts': {
                'portfolio_heatmap': sorted(heatmap, key=lambda x: x['pnl_pct'], reverse=True),
                'daily_pnl': pnl_chart,
                'sector_distribution': []
            },
            'mobile_dashboard': {
                'header': {
                    'total_value': round(account['total_value'], 2) if account else 0,
                    'cash': round(account['cash'], 2) if account else 0,
                    'cash_ratio': round(account['cash'] / account['total_value'] * 100, 1) if account and account['total_value'] > 0 else 0
                },
                'top_positions': sorted(table_rows, key=lambda x: x['pnl_pct'], reverse=True)[:5]
            },
            'positions_table': {
                'columns': [
                    {'key': 'symbol', 'label': '代码'},
                    {'key': 'current_price', 'label': '现价'},
                    {'key': 'pnl_pct', 'label': '涨幅%'},
                ],
                'rows': sorted(table_rows, key=lambda x: x['pnl_pct'], reverse=True),
                'total_rows': len(table_rows)
            },
            'trading_stats': stats
        }
    except Exception as e:
        print(f"[v5.151] 仪表板生成失败: {e}")
        return {'error': str(e), 'version': 'v5.151'}

if __name__ == '__main__':
    data = get_ui_dashboard_enhanced_v151()
    print(json.dumps(data, indent=2, ensure_ascii=False))
