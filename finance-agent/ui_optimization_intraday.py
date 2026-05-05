#!/usr/bin/env python3
"""
金融Agent 盤中UI优化②
- 新增：Kelly仓位实时调整图表
- 新增：市场情绪波动热力图
- 新增：回测性能对标表
"""

import json
import sqlite3
from pathlib import Path

DB_PATH = '/home/nikefd/finance-agent/data/trading.db'

def get_kelly_positions_data():
    """Kelly仓位实时数据"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # 当前持仓
        c.execute('SELECT COUNT(*) as cnt, SUM(shares * current_price) as val FROM positions WHERE shares > 0')
        pos_count, pos_value = c.fetchone()
        pos_value = pos_value or 0
        
        # 账户
        c.execute('SELECT total_value FROM account ORDER BY id DESC LIMIT 1')
        account_val = c.fetchone()
        total_value = account_val[0] if account_val else 1000000
        
        # 计算资金利用率
        fund_util = (pos_value / total_value * 100) if total_value else 0
        kelly_efficiency = min(100, (fund_util / 15 * 100)) if total_value else 0
        
        # 30天历史
        c.execute('''
            SELECT DATE(trade_date) as d, COUNT(*) as cnt
            FROM trades WHERE DATE(trade_date) >= date('now', '-30 days')
            GROUP BY DATE(trade_date)
        ''')
        history = [{'date': row[0], 'trade_count': row[1]} for row in c.fetchall()]
        
        conn.close()
        return {
            'current_positions': pos_count or 0,
            'current_allocation': round(fund_util, 1),
            'target_kelly': 15,
            'kelly_efficiency': round(kelly_efficiency, 1),
            'history': history
        }
    except Exception as e:
        print(f"[ERROR] kelly: {e}")
        return {'current_positions': 0, 'current_allocation': 0, 'target_kelly': 15, 'kelly_efficiency': 0, 'history': []}

def get_sentiment_heatmap():
    """市场情绪数据"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # 最新5条
        c.execute('SELECT date, sentiment_score FROM daily_snapshots ORDER BY date DESC LIMIT 5')
        rows = c.fetchall()
        
        current_score = rows[0][1] if rows else 50
        if current_score >= 70:
            current_label = '乐观'
        elif current_score >= 40:
            current_label = '中性'
        else:
            current_label = '悲观'
        
        # 趋势
        trend = []
        for i, (date, score) in enumerate(rows):
            score = score or 50
            if i > 0:
                prev = rows[i-1][1] or 50
                change = score - prev
                trend_lbl = '↑升温' if change > 10 else '↓降温' if change < -10 else '→平稳'
            else:
                change = 0
                trend_lbl = '当前'
            
            trend.append({'date': date, 'score': score, 'change': change, 'trend': trend_lbl})
        
        # 30天分布
        c.execute('''
            SELECT CASE 
                WHEN sentiment_score >= 70 THEN '乐观' 
                WHEN sentiment_score >= 40 THEN '中性'
                ELSE '悲观' END as lbl, COUNT(*) as cnt
            FROM daily_snapshots WHERE date >= date('now', '-30 days')
            GROUP BY lbl
        ''')
        dist = {row[0]: row[1] for row in c.fetchall()}
        
        conn.close()
        return {
            'current_score': current_score,
            'current_label': current_label,
            'trend': trend,
            'distribution': dist
        }
    except Exception as e:
        print(f"[ERROR] sentiment: {e}")
        return {'current_score': 50, 'current_label': '中性', 'trend': [], 'distribution': {}}

def get_backtest_comparison():
    """v5.85性能对标"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # 胜率
        c.execute('SELECT COUNT(*) FROM trades WHERE direction="SELL"')
        sell_cnt = c.fetchone()[0]
        
        c.execute('''
            SELECT COUNT(*) FROM trades t1
            WHERE direction="SELL" AND EXISTS (
                SELECT 1 FROM trades t2 
                WHERE t2.symbol=t1.symbol AND t2.direction="BUY" 
                AND t2.price < t1.price AND datetime(t2.created_at) < datetime(t1.created_at)
            )
        ''')
        win_cnt = c.fetchone()[0]
        win_rate = (win_cnt / sell_cnt * 100) if sell_cnt > 0 else 0
        
        # 最大回撤
        c.execute('SELECT total_value FROM daily_snapshots ORDER BY date DESC LIMIT 30')
        values = [row[0] for row in c.fetchall()]
        max_dd = 0
        if values:
            peak = max(values)
            for v in values:
                dd = ((peak - v) / peak * 100) if peak else 0
                max_dd = max(max_dd, dd)
        
        # Sharpe (简化)
        returns = []
        for i in range(len(values)-1):
            if values[i+1] > 0:
                ret = ((values[i] - values[i+1]) / values[i+1]) * 100
                returns.append(ret)
        
        avg_ret = sum(returns) / len(returns) if returns else 0
        std = (sum((r - avg_ret)**2 for r in returns) / len(returns))**0.5 if returns else 0
        sharpe = (avg_ret / std * (252**0.5)) if std > 0 else 0
        
        # 资金利用率
        c.execute('SELECT total_value FROM account ORDER BY id DESC LIMIT 1')
        total_val = c.fetchone()[0] if c.fetchone() else 1000000
        c.execute('SELECT SUM(shares * current_price) FROM positions WHERE shares > 0')
        pos_val = c.fetchone()[0] or 0
        fund_util = (pos_val / total_val * 100) if total_val else 0
        
        # 赛道
        c.execute('SELECT sector, COUNT(*) FROM positions WHERE shares > 0 GROUP BY sector')
        sectors = {row[0] or '其他': row[1] for row in c.fetchall()}
        
        conn.close()
        
        return {
            'current_metrics': {
                'win_rate': round(win_rate, 1),
                'max_drawdown': round(max_dd, 2),
                'sharpe_ratio': round(sharpe, 2),
                'fund_utilization': round(fund_util, 1),
                'positions_count': len(sectors),
                'total_trades': len(values)
            },
            'v585_targets': {
                'win_rate': 65,
                'max_drawdown': 3.5,
                'sharpe_ratio': 2.5,
                'fund_utilization': 95,
                'positions_count': 8,
                'expected_return': 18
            },
            'achievement_rate': {
                'win_rate': min(100, round((win_rate / 65) * 100, 1)) if win_rate > 0 else 0,
                'max_drawdown': min(100, round((3.5 / max_dd) * 100, 1)) if max_dd > 0 else 0,
                'sharpe_ratio': min(100, round((sharpe / 2.5) * 100, 1)) if sharpe > 0 else 0,
                'fund_utilization': min(100, round((fund_util / 95) * 100, 1)) if fund_util > 0 else 0
            },
            'sector_distribution': sectors
        }
    except Exception as e:
        print(f"[ERROR] backtest: {e}")
        return {'current_metrics': {}, 'v585_targets': {}, 'achievement_rate': {}, 'sector_distribution': {}}

if __name__ == '__main__':
    print("=== UI优化②数据生成 ===")
    
    kelly = get_kelly_positions_data()
    print(f"\n✅ Kelly仓位:")
    print(f"  持仓: {kelly.get('current_positions')} | 利用率: {kelly.get('current_allocation', 0):.1f}% (目标15%)")
    
    sentiment = get_sentiment_heatmap()
    print(f"\n✅ 情绪波动:")
    print(f"  当前: {sentiment.get('current_label')} (评分{sentiment.get('current_score')})")
    
    backtest = get_backtest_comparison()
    print(f"\n✅ 回测对标:")
    print(f"  胜率: {backtest['current_metrics'].get('win_rate', 0):.1f}% | 目标65%")
