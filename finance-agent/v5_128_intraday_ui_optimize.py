#!/usr/bin/env python3
"""
v5.128 盤中UI優化② (11:30)
核心：实时情感热力图 + 信号质量评分 + 入场质量看板
"""

import json
import sqlite3
from datetime import datetime, timedelta
from collections import defaultdict

DB_PATH = '/home/nikefd/finance-agent/data/trading.db'

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def _get_sentiment_label(score):
    """根据分数计算情绪标签"""
    if score >= 70:
        return '乐观'
    elif score >= 40:
        return '中性'
    else:
        return '悲观'

def _compute_adjustment_from_sentiment(score):
    """根据情绪评分计算参数调节"""
    if score >= 85:  # 极度贪婪
        return {
            'action': '🔴 减仓',
            'detail': '市场过热，风险提示',
            'kelly_adj': 0.6,  # 仓位调节至60%
            'stop_loss_tighten': 2,  # 止损收紧2%
        }
    elif score >= 70:  # 乐观
        return {
            'action': '⚡ 均衡',
            'detail': '市场向好，正常操作',
            'kelly_adj': 0.85,
            'stop_loss_tighten': 0,
        }
    elif score >= 40:  # 中性
        return {
            'action': '→ 中性',
            'detail': '市场震荡，谨慎操作',
            'kelly_adj': 1.0,
            'stop_loss_tighten': 1,
        }
    else:  # 悲观/恐慌
        return {
            'action': '🟢 逆向加仓',
            'detail': '恐慌情绪，逆向布局',
            'kelly_adj': 1.3,  # 加仓至130%
            'stop_loss_tighten': -1,  # 止损放宽
        }

def get_sentiment_heatmap_v128():
    """实时情绪热力图 - 近7日每日情绪 + 变化趋势"""
    conn = get_db()
    
    # 查询近7日情绪数据
    rows = conn.execute("""
        SELECT date, sentiment_score
        FROM daily_snapshots
        WHERE date >= date('now', '-7 days')
        ORDER BY date ASC
    """).fetchall()
    
    heatmap = []
    for i, row in enumerate(rows):
        curr_score = row['sentiment_score'] or 50
        curr_label = _get_sentiment_label(curr_score)
        
        # 与前一天比较
        prev_score = rows[i-1]['sentiment_score'] if i > 0 else curr_score
        change = curr_score - prev_score
        
        # 判断趋势
        if change > 10:
            trend = '↑ 升温'
            trend_icon = '🔥'
        elif change < -10:
            trend = '↓ 降温'
            trend_icon = '❄️'
        else:
            trend = '→ 平稳'
            trend_icon = '⚡'
        
        # 情绪颜色映射
        if curr_score >= 70:
            color = '#e63946'  # 红色-极度贪婪
        elif curr_score >= 60:
            color = '#f4a261'  # 橙色-乐观
        elif curr_score >= 40:
            color = '#ffd166'  # 黄色-中性
        else:
            color = '#2ec4b6'  # 青色-悲观
        
        heatmap.append({
            'date': row['date'],
            'score': curr_score,
            'label': curr_label,
            'change': change,
            'trend': trend,
            'trend_icon': trend_icon,
            'color': color,
            'adjustment': _compute_adjustment_from_sentiment(curr_score)
        })
    
    # 统计7日内各情绪等级出现次数
    distribution = defaultdict(int)
    for item in heatmap:
        distribution[item['label']] += 1
    
    conn.close()
    
    return {
        'heatmap': heatmap,
        'current_score': heatmap[-1]['score'] if heatmap else 50,
        'current_label': heatmap[-1]['label'] if heatmap else '中性',
        'distribution': dict(distribution),
        '7day_avg': round(sum(h['score'] for h in heatmap) / len(heatmap), 1) if heatmap else 50,
    }

def get_signal_quality_v128():
    """信号质量评分 - MACD/RSI指标有效性"""
    conn = get_db()
    
    # 获取最近30天的信号记录
    signals = conn.execute("""
        SELECT 
            symbol, direction, strength as signal_strength,
            created_at, reason
        FROM signals
        WHERE created_at >= date('now', '-30 days')
        ORDER BY created_at DESC
        LIMIT 100
    """).fetchall()
    
    if not signals:
        return {
            'macd': {'total': 0, 'avg_strength': 0, 'recent': []},
            'rsi': {'total': 0, 'avg_strength': 0, 'recent': []},
            'combined_quality': 0,
        }
    
    macd_signals = []
    rsi_signals = []
    
    for sig in signals:
        reason = sig['reason'] or ''
        strength = sig['signal_strength'] or 5
        
        if 'MACD' in reason or 'macd' in reason.lower():
            macd_signals.append({'date': sig['created_at'], 'strength': strength, 'reason': reason})
        if 'RSI' in reason or 'rsi' in reason.lower():
            rsi_signals.append({'date': sig['created_at'], 'strength': strength, 'reason': reason})
    
    # 计算MACD统计
    macd_stats = {
        'total': len(macd_signals),
        'avg_strength': round(sum(s['strength'] for s in macd_signals) / len(macd_signals), 1) if macd_signals else 0,
        'recent': [
            {
                'date': s['date'],
                'strength': s['strength'],
                'quality_score': min(100, s['strength'] * 15),  # 1-10分 -> 15-150分 (capped at 100)
            }
            for s in macd_signals[:5]
        ]
    }
    
    # 计算RSI统计
    rsi_stats = {
        'total': len(rsi_signals),
        'avg_strength': round(sum(s['strength'] for s in rsi_signals) / len(rsi_signals), 1) if rsi_signals else 0,
        'recent': [
            {
                'date': s['date'],
                'strength': s['strength'],
                'quality_score': min(100, s['strength'] * 15),
            }
            for s in rsi_signals[:5]
        ]
    }
    
    # 综合质量评分
    combined = (macd_stats['avg_strength'] + rsi_stats['avg_strength']) / 2 * 10 if (macd_stats['avg_strength'] or rsi_stats['avg_strength']) else 0
    combined_quality = min(100, combined)
    
    conn.close()
    
    return {
        'macd': macd_stats,
        'rsi': rsi_stats,
        'combined_quality': round(combined_quality, 1),
        'quality_level': '优秀' if combined_quality >= 70 else '良好' if combined_quality >= 50 else '一般',
    }

def get_entry_quality_distribution_v128():
    """入场质量评分分布 - 当日候选股的评分统计"""
    conn = get_db()
    
    # 获取今日候选股及评分
    candidates = conn.execute("""
        SELECT score
        FROM candidate_snapshots
        WHERE snapshot_date = date('now')
        ORDER BY score DESC
    """).fetchall()
    
    if not candidates:
        return {
            'total': 0,
            'distribution': {'excellent': 0, 'good': 0, 'fair': 0, 'poor': 0},
            'avg_score': 0,
            'score_ranges': {},
        }
    
    scores = [c['score'] for c in candidates]
    distribution = {
        'excellent': len([s for s in scores if s >= 80]),  # >=80分
        'good': len([s for s in scores if 70 <= s < 80]),  # 70-79分
        'fair': len([s for s in scores if 60 <= s < 70]),  # 60-69分
        'poor': len([s for s in scores if s < 60]),        # <60分
    }
    
    avg_score = round(sum(scores) / len(scores), 1)
    
    # 获取分数分布
    score_ranges = {
        '90+': len([s for s in scores if s >= 90]),
        '80-90': len([s for s in scores if 80 <= s < 90]),
        '70-80': len([s for s in scores if 70 <= s < 80]),
        '60-70': len([s for s in scores if 60 <= s < 70]),
        '<60': len([s for s in scores if s < 60]),
    }
    
    conn.close()
    
    return {
        'total': len(candidates),
        'distribution': distribution,
        'avg_score': avg_score,
        'score_ranges': score_ranges,
        'quality_rating': '优质' if avg_score >= 75 else '正常' if avg_score >= 65 else '偏弱',
    }

def get_intraday_quick_metrics_v128():
    """盤中快速指标 - 用于dashboard卡片快速展示"""
    conn = get_db()
    
    # 获取最新账户状态
    account = conn.execute("""
        SELECT cash, total_value
        FROM account
        ORDER BY id DESC
        LIMIT 1
    """).fetchone() or {'cash': 0, 'total_value': 1000000}
    
    # 获取今日市场快照
    today_snapshot = conn.execute("""
        SELECT total_value, sentiment_score
        FROM daily_snapshots
        WHERE date = date('now')
        LIMIT 1
    """).fetchone() or {'total_value': 1000000, 'sentiment_score': 50}
    
    # 获取昨日市场快照
    yesterday_snapshot = conn.execute("""
        SELECT total_value
        FROM daily_snapshots
        WHERE date = date('now', '-1 day')
        LIMIT 1
    """).fetchone() or {'total_value': 1000000}
    
    # 计算今日收益
    today_pnl = today_snapshot['total_value'] - yesterday_snapshot['total_value']
    today_pnl_pct = round(today_pnl / yesterday_snapshot['total_value'] * 100, 2) if yesterday_snapshot['total_value'] else 0
    
    # 获取持仓数量
    positions = conn.execute("""
        SELECT COUNT(*) as count FROM positions WHERE shares > 0
    """).fetchone()
    position_count = positions['count'] if positions else 0
    
    # 现金比率
    cash_ratio = round(account['cash'] / account['total_value'] * 100, 1) if account['total_value'] else 0
    
    conn.close()
    
    return {
        'today_pnl': round(today_pnl, 2),
        'today_pnl_pct': today_pnl_pct,
        'cash_ratio': cash_ratio,
        'position_count': position_count,
        'sentiment_score': today_snapshot['sentiment_score'] or 50,
        'total_value': round(account['total_value'], 2),
        'cash_amount': round(account['cash'], 2),
    }

def get_dashboard_aggregate_v128():
    """一次性获取所有盤中UI数据 (聚合API，减少请求数)"""
    return {
        'timestamp': datetime.now().isoformat(),
        'sentiment_heatmap': get_sentiment_heatmap_v128(),
        'signal_quality': get_signal_quality_v128(),
        'entry_quality': get_entry_quality_distribution_v128(),
        'quick_metrics': get_intraday_quick_metrics_v128(),
    }

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1:
        action = sys.argv[1]
        if action == 'sentiment':
            print(json.dumps(get_sentiment_heatmap_v128(), ensure_ascii=False, indent=2))
        elif action == 'signals':
            print(json.dumps(get_signal_quality_v128(), ensure_ascii=False, indent=2))
        elif action == 'entry':
            print(json.dumps(get_entry_quality_distribution_v128(), ensure_ascii=False, indent=2))
        elif action == 'aggregate':
            print(json.dumps(get_dashboard_aggregate_v128(), ensure_ascii=False, indent=2))
    else:
        # 默认输出聚合数据
        print(json.dumps(get_dashboard_aggregate_v128(), ensure_ascii=False, indent=2))
