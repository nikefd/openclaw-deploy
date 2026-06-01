"""
v5.141 盘中优化② - UI和数据展示增强
时间: 2026-06-01 11:30 (盘中)
目标: 改进性能排序、风险监控、资金利用率展示
新增API: 绩效统计、资金分配热力图、风险指数
"""

import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = '/home/nikefd/finance-agent/data/trading.db'
INITIAL_CAPITAL = 1000000

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_performance_metrics():
    """增强版性能指标 - 包含多维度排序"""
    conn = get_db()
    c = conn.cursor()
    
    # 获取今日交易和持仓
    c.execute("""
        SELECT 
            symbol, 
            SUM(CASE WHEN direction='BUY' THEN shares ELSE -shares END) as net_shares,
            AVG(CASE WHEN direction='BUY' THEN price ELSE NULL END) as avg_buy_price,
            MAX(price) as peak_price
        FROM trades 
        WHERE DATE(trade_date) = DATE('now', 'localtime')
        GROUP BY symbol
    """)
    trades = c.fetchall()
    
    # 获取最新价格和持仓
    c.execute("SELECT symbol, shares, avg_cost, current_price, peak_price FROM positions")
    positions = {p['symbol']: p for p in c.fetchall()}
    
    metrics = []
    for trade in trades:
        sym = trade['symbol']
        pos = positions.get(sym, {})
        
        # 计算多维度指标
        current_price = pos.get('current_price', 0) or 0
        avg_cost = pos.get('avg_cost', 0) or 0
        peak_price = pos.get('peak_price', 0) or 0
        
        pnl_pct = ((current_price - avg_cost) / avg_cost * 100) if avg_cost > 0 else 0
        peak_dd = ((current_price - peak_price) / peak_price * 100) if peak_price > 0 else 0
        
        # 风险调整收益 (Sharpe代理)
        risk_adjusted = pnl_pct - abs(peak_dd) * 0.5 if peak_dd else pnl_pct
        
        # 效率评分 (0-100)
        efficiency = min(100, max(0, 50 + pnl_pct * 2 + risk_adjusted))
        
        metrics.append({
            'symbol': sym,
            'pnl_pct': round(pnl_pct, 2),
            'peak_drawdown': round(peak_dd, 2),
            'risk_adjusted_return': round(risk_adjusted, 2),
            'efficiency_score': round(efficiency, 1),
            'net_shares': trade['net_shares'],
            'entry_price': round(trade['avg_buy_price'], 2) if trade['avg_buy_price'] else 0,
            'current_price': round(current_price, 2)
        })
    
    conn.close()
    return sorted(metrics, key=lambda x: x['risk_adjusted_return'], reverse=True)

def get_capital_allocation_heatmap():
    """资金分配热力图 - 按赛道和持仓规模"""
    conn = get_db()
    c = conn.cursor()
    
    c.execute("""
        SELECT symbol, shares, avg_cost, current_price,
               shares * current_price as position_value
        FROM positions
        WHERE shares > 0
    """, ())
    positions = c.fetchall()
    
    # 赛道分类 (简化版)
    sector_map = {
        '000001': '指数', '000333': '新能源', '000858': '五粮液',
        '600000': '浦发银行', '600009': '上海机场',
        '301750': '实益达', '688981': '中芯国际'
    }
    
    sectors = {}
    total_value = sum(p['position_value'] for p in positions)
    
    for pos in positions:
        sector = sector_map.get(pos['symbol'], '其他')
        if sector not in sectors:
            sectors[sector] = {'value': 0, 'count': 0, 'positions': []}
        
        sectors[sector]['value'] += pos['position_value']
        sectors[sector]['count'] += 1
        sectors[sector]['positions'].append({
            'symbol': pos['symbol'],
            'shares': pos['shares'],
            'value': round(pos['position_value'], 2)
        })
    
    # 计算热力强度 (0-100)
    heatmap = []
    for sector_name, data in sorted(sectors.items(), 
                                     key=lambda x: x[1]['value'], 
                                     reverse=True):
        allocation_pct = (data['value'] / total_value * 100) if total_value > 0 else 0
        heat_intensity = min(100, allocation_pct * 1.5)  # 放大显示
        
        heatmap.append({
            'sector': sector_name,
            'allocation_pct': round(allocation_pct, 1),
            'heat_intensity': round(heat_intensity, 1),
            'position_count': data['count'],
            'total_value': round(data['value'], 2),
            'positions': data['positions']
        })
    
    conn.close()
    return {
        'total_portfolio_value': round(total_value, 2),
        'sectors': heatmap,
        'timestamp': datetime.now().isoformat()
    }

def get_risk_metrics():
    """实时风险指数 - 包含回撤、集中度、波动率代理"""
    conn = get_db()
    c = conn.cursor()
    
    # 1. 获取最大回撤
    c.execute("""
        SELECT 
            COUNT(*) as high_drawdown_count,
            AVG(CASE WHEN peak_price > 0 THEN (current_price - peak_price) / peak_price * 100 ELSE 0 END) as avg_drawdown,
            MIN(CASE WHEN peak_price > 0 THEN (current_price - peak_price) / peak_price * 100 ELSE 0 END) as max_drawdown
        FROM positions WHERE shares > 0 AND peak_price > current_price
    """)
    dd_stats = c.fetchone()
    if not dd_stats or dd_stats['high_drawdown_count'] == 0:
        dd_stats = {'high_drawdown_count': 0, 'avg_drawdown': 0, 'max_drawdown': 0}
    
    # 2. 获取持仓集中度 (Herfindahl Index)
    c.execute("""
        SELECT 
            SUM(shares * current_price) as total_value,
            COUNT(*) as position_count,
            MAX(shares * current_price) as max_position_value
        FROM positions WHERE shares > 0 AND current_price > 0
    """)
    pos_stats = c.fetchone() or {}
    if not pos_stats:
        pos_stats = {'total_value': 0, 'position_count': 0, 'max_position_value': 0}
    
    total_val = pos_stats['total_value'] or 1
    position_count = pos_stats['position_count'] or 1
    max_pos_val = pos_stats['max_position_value'] or 0
    
    # 集中度 (0-100, 越低越分散)
    concentration = min(100, (max_pos_val / total_val * 100) * 1.5) if total_val > 0 else 0
    
    # 3. 风险评分 (0-100, 越低风险越低)
    avg_dd = dd_stats['avg_drawdown'] or 0
    drawdown_risk = min(100, max(0, 50 + abs(avg_dd) * 2))
    concentration_risk = concentration  # 集中度直接作为风险
    
    total_risk = (drawdown_risk * 0.4 + concentration_risk * 0.6)  # 加权
    
    risk_level = '低' if total_risk < 30 else '中' if total_risk < 60 else '高'
    
    conn.close()
    return {
        'total_risk_score': round(total_risk, 1),
        'risk_level': risk_level,
        'drawdown_risk': round(drawdown_risk, 1),
        'concentration_risk': round(concentration_risk, 1),
        'position_count': position_count,
        'max_drawdown': round(dd_stats['max_drawdown'] or 0, 2),
        'high_drawdown_positions': dd_stats['high_drawdown_count'] or 0,
        'timestamp': datetime.now().isoformat()
    }

def get_daily_performance_summary():
    """日统计 - 今日交易摘要"""
    conn = get_db()
    c = conn.cursor()
    
    # 今日交易统计
    c.execute("""
        SELECT 
            SUM(CASE WHEN direction='BUY' THEN shares ELSE 0 END) as buy_shares,
            SUM(CASE WHEN direction='SELL' THEN shares ELSE 0 END) as sell_shares,
            COUNT(*) as total_trades,
            COUNT(DISTINCT symbol) as unique_symbols
        FROM trades
        WHERE DATE(trade_date) = DATE('now', 'localtime')
    """)
    trade_stats = c.fetchone()
    
    # 今日P&L
    c.execute("""
        SELECT total_value FROM daily_snapshots
        WHERE DATE(date) = DATE('now', 'localtime')
        ORDER BY date DESC LIMIT 1
    """)
    today_snapshot = c.fetchone()
    
    c.execute("""
        SELECT total_value FROM daily_snapshots
        WHERE DATE(date) = DATE('now', 'localtime', '-1 day')
        ORDER BY date DESC LIMIT 1
    """)
    yesterday_snapshot = c.fetchone()
    
    today_pnl = 0
    if today_snapshot and yesterday_snapshot:
        today_pnl = today_snapshot['total_value'] - yesterday_snapshot['total_value']
    
    today_pnl_pct = (today_pnl / INITIAL_CAPITAL * 100) if INITIAL_CAPITAL else 0
    
    # 赢率（从持仓推导）
    c.execute("""
        SELECT 
            COUNT(*) as sell_count,
            SUM(CASE WHEN (current_price - avg_cost) > 0 THEN 1 ELSE 0 END) as win_count
        FROM positions
    """)
    win_stats = c.fetchone()
    
    win_rate = 0
    if win_stats and win_stats['sell_count'] > 0:
        win_rate = (win_stats['win_count'] / win_stats['sell_count'] * 100) if win_stats['win_count'] else 0
    
    conn.close()
    return {
        'date': datetime.now().date().isoformat(),
        'total_trades': trade_stats['total_trades'] or 0,
        'buy_trades': trade_stats['buy_shares'] or 0,
        'sell_trades': trade_stats['sell_shares'] or 0,
        'unique_symbols': trade_stats['unique_symbols'] or 0,
        'daily_pnl': round(today_pnl, 2),
        'daily_pnl_pct': round(today_pnl_pct, 2),
        'win_rate': round(win_rate, 1),
        'timestamp': datetime.now().isoformat()
    }

def main():
    """测试所有新增功能"""
    print("\n=== v5.141 盘中UI优化测试 ===\n")
    
    try:
        print("1. 增强版性能指标:")
        metrics = get_performance_metrics()
        print(f"   获取 {len(metrics)} 个持仓指标")
        if metrics:
            best = metrics[0]
            print(f"   TOP: {best['symbol']} - ROI {best['pnl_pct']}% | 效率评分 {best['efficiency_score']}")
        
        print("\n2. 资金分配热力图:")
        heatmap = get_capital_allocation_heatmap()
        print(f"   投资组合总值: ¥{heatmap['total_portfolio_value']}")
        print(f"   赛道数: {len(heatmap['sectors'])}")
        for sector in heatmap['sectors'][:3]:
            print(f"   - {sector['sector']}: {sector['allocation_pct']}% | 强度 {sector['heat_intensity']}")
        
        print("\n3. 实时风险指数:")
        risk = get_risk_metrics()
        print(f"   总体风险评分: {risk['total_risk_score']} ({risk['risk_level']})")
        print(f"   回撤风险: {risk['drawdown_risk']} | 集中度风险: {risk['concentration_risk']}")
        print(f"   持仓数: {risk['position_count']} | 最大回撤: {risk['max_drawdown']}%")
        
        print("\n4. 日统计摘要:")
        summary = get_daily_performance_summary()
        print(f"   交易数: {summary['total_trades']} | 独立标的: {summary['unique_symbols']}")
        print(f"   日P&L: ¥{summary['daily_pnl']} ({summary['daily_pnl_pct']}%)")
        print(f"   赢率: {summary['win_rate']}%")
        
        print("\n✅ v5.141 测试完成")
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
