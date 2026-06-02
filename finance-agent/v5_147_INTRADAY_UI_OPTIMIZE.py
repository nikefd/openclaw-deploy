#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v5.147 盤中UI優化②性能指標聚合 + 情感觸發決策實時監控

任務: 优化盘中(11:30-14:30)的数据展示，提升交易执行效率
核心改进:
  ① 性能指标面板 (实时胜率/最大盈利/平均持仓日)
  ② MACD/RSI信号质量评分 (从0-100量化信号有效性)
  ③ 情感触发决策快照 (市场情绪→自适应参数→执行信号)
  ④ 止损黑名单实时监控 (近7日止损股票动态追踪)
  ⑤ 绩效卡片 (v5.82 vs v5.81对标)

输出: JSON数据供前端展示
作者: finance-agent-optimizer
日期: 2026-06-02 03:30 UTC
"""

import os
import sys
import json
import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

# ==================== 配置 ====================
DB_PATH = '/home/nikefd/finance-agent/data/trading.db'
LOG_LEVEL = logging.INFO
INITIAL_CAPITAL = 1000000

# 初始化日志
logging.basicConfig(
    level=LOG_LEVEL,
    format='[%(asctime)s][%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# ==================== 数据库访问 ====================

def get_db():
    """获取数据库连接"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def query_trades(days: int = 30) -> List[Dict]:
    """查询N天内的交易记录"""
    conn = get_db()
    sql = """
    SELECT * FROM trades 
    WHERE trade_date >= date('now', '-{} days')
    ORDER BY trade_date DESC, id DESC
    """.format(days)
    rows = conn.execute(sql).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def query_positions() -> List[Dict]:
    """查询当前持仓"""
    conn = get_db()
    rows = conn.execute('SELECT * FROM positions WHERE shares > 0').fetchall()
    conn.close()
    return [dict(r) for r in rows]

def query_account() -> Dict:
    """查询账户信息"""
    conn = get_db()
    row = conn.execute('SELECT * FROM account ORDER BY id DESC LIMIT 1').fetchone()
    conn.close()
    return dict(row) if row else {'cash': 0, 'total_value': INITIAL_CAPITAL}

def query_snapshots(days: int = 30) -> List[Dict]:
    """查询N天内的每日快照"""
    conn = get_db()
    sql = """
    SELECT * FROM daily_snapshots
    WHERE date >= date('now', '-{} days')
    ORDER BY date ASC
    """.format(days)
    rows = conn.execute(sql).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ==================== ① 性能指标面板 ====================

def get_performance_indicators() -> Dict[str, Any]:
    """
    获取实时性能指标
    
    返回:
    {
        'win_rate': 65.5,           # 胜率%
        'avg_holding_days': 4.2,    # 平均持仓天数
        'max_gain': 2500,           # 最大单笔盈利
        'max_loss': -1200,          # 最大单笔亏损
        'total_trades': 20,         # 总交易数
        'win_trades': 13,           # 赢利交易数
        'loss_trades': 7            # 亏损交易数
    }
    """
    try:
        trades = query_trades(days=30)
        sells = [t for t in trades if t['direction'] == 'SELL']
        
        if not sells:
            return {
                'win_rate': 0,
                'avg_holding_days': 0,
                'max_gain': 0,
                'max_loss': 0,
                'total_trades': 0,
                'win_trades': 0,
                'loss_trades': 0
            }
        
        # 计算胜率
        buys = [t for t in trades if t['direction'] == 'BUY']
        buy_map = {}
        for b in buys:
            if b['symbol'] not in buy_map:
                buy_map[b['symbol']] = []
            buy_map[b['symbol']].append(b)
        
        avg_costs = {}
        for sym, buy_list in buy_map.items():
            total_shares = sum(b['shares'] for b in buy_list)
            total_cost = sum(b['price'] * b['shares'] for b in buy_list)
            avg_costs[sym] = total_cost / total_shares if total_shares > 0 else 0
        
        wins = 0
        pnls = []
        holding_days_list = []
        
        for sell in sells:
            cost = avg_costs.get(sell['symbol'], 0)
            if cost > 0:
                pnl = (sell['price'] - cost) * sell['shares']
                pnls.append(pnl)
                
                if pnl > 0:
                    wins += 1
                
                # 计算持仓天数
                if buy_map.get(sell['symbol']):
                    buy_date = buy_map[sell['symbol']][0]['trade_date']
                    sell_date = sell['trade_date']
                    try:
                        days_held = (datetime.fromisoformat(sell_date) - 
                                   datetime.fromisoformat(buy_date)).days
                        holding_days_list.append(days_held)
                    except:
                        pass
        
        win_rate = (wins / len(sells) * 100) if sells else 0
        avg_holding_days = sum(holding_days_list) / len(holding_days_list) if holding_days_list else 0
        max_gain = max(pnls) if pnls else 0
        max_loss = min(pnls) if pnls else 0
        
        return {
            'win_rate': round(win_rate, 2),
            'avg_holding_days': round(avg_holding_days, 1),
            'max_gain': round(max_gain),
            'max_loss': round(max_loss),
            'total_trades': len(sells),
            'win_trades': wins,
            'loss_trades': len(sells) - wins
        }
    except Exception as e:
        logger.error(f'get_performance_indicators error: {e}')
        return {
            'win_rate': 0,
            'avg_holding_days': 0,
            'max_gain': 0,
            'max_loss': 0,
            'total_trades': 0,
            'win_trades': 0,
            'loss_trades': 0
        }

# ==================== ② MACD/RSI信号质量评分 ====================

def get_signal_quality_score() -> Dict[str, Any]:
    """
    计算MACD/RSI信号质量评分 (0-100)
    
    逻辑:
      - 遍历最近30个卖出信号
      - 对每个信号提取MACD/RSI指标
      - 计算指标有效性 (即 触发卖出时的精准度)
      - 最终得到质量分
    
    返回:
    {
        'macd': {
            'total': 12,              # MACD信号数
            'quality_avg': 78.5,      # 平均质量分 (0-100)
            'latest': 82              # 最近一个信号的质量分
        },
        'rsi': {
            'total': 15,
            'quality_avg': 65.3,
            'latest': 68
        },
        'combined_quality': 71.9      # 综合质量分
    }
    """
    try:
        trades = query_trades(days=60)
        sells = [t for t in trades if t['direction'] == 'SELL']
        
        if not sells:
            return {
                'macd': {'total': 0, 'quality_avg': 0, 'latest': 0},
                'rsi': {'total': 0, 'quality_avg': 0, 'latest': 0},
                'combined_quality': 0
            }
        
        # 统计信号触发频率
        macd_signals = [s for s in sells if s.get('reason', '').find('MACD') >= 0]
        rsi_signals = [s for s in sells if s.get('reason', '').find('RSI') >= 0]
        
        # 评估MACD信号质量
        # 假设: MACD金叉→卖出且盈利 = 高质量
        macd_qualities = []
        for sig in macd_signals[:10]:  # 最近10个
            # 简单评分: 如果盈利则加分
            pnl_pct = sig.get('pnl_pct', 0) or 0
            quality = min(100, max(0, 50 + pnl_pct * 10))
            macd_qualities.append(quality)
        
        macd_avg = sum(macd_qualities) / len(macd_qualities) if macd_qualities else 0
        macd_latest = macd_qualities[0] if macd_qualities else 0
        
        # 评估RSI信号质量
        rsi_qualities = []
        for sig in rsi_signals[:10]:
            pnl_pct = sig.get('pnl_pct', 0) or 0
            quality = min(100, max(0, 50 + pnl_pct * 8))
            rsi_qualities.append(quality)
        
        rsi_avg = sum(rsi_qualities) / len(rsi_qualities) if rsi_qualities else 0
        rsi_latest = rsi_qualities[0] if rsi_qualities else 0
        
        combined = (macd_avg + rsi_avg) / 2 if (macd_avg > 0 or rsi_avg > 0) else 0
        
        return {
            'macd': {
                'total': len(macd_signals),
                'quality_avg': round(macd_avg, 1),
                'latest': round(macd_latest, 1)
            },
            'rsi': {
                'total': len(rsi_signals),
                'quality_avg': round(rsi_avg, 1),
                'latest': round(rsi_latest, 1)
            },
            'combined_quality': round(combined, 1)
        }
    except Exception as e:
        logger.error(f'get_signal_quality_score error: {e}')
        return {
            'macd': {'total': 0, 'quality_avg': 0, 'latest': 0},
            'rsi': {'total': 0, 'quality_avg': 0, 'latest': 0},
            'combined_quality': 0
        }

# ==================== ③ 情感触发决策快照 ====================

def get_emotion_trigger_decision() -> Dict[str, Any]:
    """
    获取市场情绪→参数调整→执行信号的完整快照
    
    返回:
    {
        'sentiment_score': 78.5,      # 当前情绪评分
        'sentiment_label': '乐观',     # 情绪标签
        'adaptive_params': {
            'macd_fast': 12,          # MACD动态快线参数
            'macd_slow': 26,
            'rsi_period': 14,
            'kelly_multiplier': 1.0   # Kelly系数 (恐惧时↑, 贪婪时↓)
        },
        'triggered_signals': [        # 当前市场触发的所有信号
            {'type': 'MACD金叉', 'stocks': ['000001', '000002'], 'confidence': 0.85},
            {'type': 'RSI超卖', 'stocks': ['000003'], 'confidence': 0.72}
        ],
        'execution_status': '准备就绪',   # 执行状态
        'risk_level': 'moderate'      # 风险等级
    }
    """
    try:
        snapshots = query_snapshots(days=1)
        if not snapshots:
            sentiment_score = 50
            sentiment_label = '中性'
        else:
            sentiment_score = snapshots[-1].get('sentiment_score', 50)
            sentiment_label = snapshots[-1].get('sentiment_label', '中性')
        
        # 根据情绪生成自适应参数
        if sentiment_score >= 85:
            # 极度贪婪
            adaptive_params = {
                'macd_fast': 14, 'macd_slow': 24, 'signal': 11,
                'rsi_period': 14,
                'rsi_overbought': 80,
                'kelly_multiplier': 0.6,
                'mode': '高度谨慎'
            }
            risk_level = 'high'
        elif sentiment_score >= 70:
            # 乐观
            adaptive_params = {
                'macd_fast': 12, 'macd_slow': 26, 'signal': 9,
                'rsi_period': 14,
                'rsi_overbought': 70,
                'kelly_multiplier': 0.85,
                'mode': '适度保守'
            }
            risk_level = 'moderate'
        elif sentiment_score >= 40:
            # 中性
            adaptive_params = {
                'macd_fast': 12, 'macd_slow': 26, 'signal': 9,
                'rsi_period': 14,
                'rsi_overbought': 70,
                'kelly_multiplier': 1.0,
                'mode': '基准'
            }
            risk_level = 'moderate'
        else:
            # 恐慌
            adaptive_params = {
                'macd_fast': 10, 'macd_slow': 30, 'signal': 7,
                'rsi_period': 12,
                'rsi_overbought': 60,
                'kelly_multiplier': 1.3,
                'mode': '逆向加仓'
            }
            risk_level = 'low'
        
        # 获取最近的入场信号
        trades = query_trades(days=1)
        buys = [t for t in trades if t['direction'] == 'BUY']
        
        triggered_signals = []
        if buys:
            # 统计信号类型
            signal_types = {}
            for buy in buys:
                reason = buy.get('reason', '')
                if 'MACD' in reason:
                    signal_types.setdefault('MACD金叉', []).append(buy['symbol'])
                if 'RSI' in reason:
                    signal_types.setdefault('RSI超卖', []).append(buy['symbol'])
            
            for sig_type, stocks in signal_types.items():
                triggered_signals.append({
                    'type': sig_type,
                    'stocks': stocks,
                    'confidence': min(0.95, 0.5 + len(stocks) * 0.1)
                })
        
        return {
            'sentiment_score': round(sentiment_score, 1),
            'sentiment_label': sentiment_label,
            'adaptive_params': adaptive_params,
            'triggered_signals': triggered_signals,
            'execution_status': '准备就绪' if buys else '待信号',
            'risk_level': risk_level,
            'timestamp': datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f'get_emotion_trigger_decision error: {e}')
        return {
            'sentiment_score': 50,
            'sentiment_label': '中性',
            'adaptive_params': {},
            'triggered_signals': [],
            'execution_status': '错误',
            'risk_level': 'unknown',
            'error': str(e)
        }

# ==================== ④ 止损黑名单实时监控 ====================

def get_stoploss_blacklist_7d() -> Dict[str, Any]:
    """
    获取近7天内止损的股票黑名单
    
    返回:
    {
        'blacklist': [
            {
                'symbol': '000001',
                'name': '平安银行',
                'stop_loss_date': '2026-06-01',
                'pnl_pct': -8.2,
                'reason': '超跌风险'
            }
        ],
        'total_count': 5,
        'win_after_sl_pct': 20    # 止损后7天内再次进场的成功率
    }
    """
    try:
        trades = query_trades(days=7)
        sells = [t for t in trades if t['direction'] == 'SELL']
        
        # 筛选止损卖出
        blacklist = []
        for sell in sells:
            reason = sell.get('reason', '')
            if '止损' in reason or 'stop' in reason.lower():
                blacklist.append({
                    'symbol': sell.get('symbol', ''),
                    'name': sell.get('name', ''),
                    'stop_loss_date': sell.get('trade_date', ''),
                    'pnl_pct': sell.get('pnl_pct', 0),
                    'reason': reason
                })
        
        # 计算止损后重新进场的成功率
        blacklist_symbols = set(b['symbol'] for b in blacklist)
        rebuy_wins = 0
        rebuy_total = 0
        
        for sym in blacklist_symbols:
            recent_buys = [t for t in trades if t['direction'] == 'BUY' and t['symbol'] == sym]
            if recent_buys:
                recent_sells = [t for t in trades if t['direction'] == 'SELL' and t['symbol'] == sym]
                if recent_sells:
                    for sell in recent_sells:
                        if sell.get('pnl_pct', 0) > 0:
                            rebuy_wins += 1
                        rebuy_total += 1
        
        rebuy_success_rate = (rebuy_wins / rebuy_total * 100) if rebuy_total > 0 else 0
        
        return {
            'blacklist': blacklist,
            'total_count': len(blacklist),
            'win_after_sl_pct': round(rebuy_success_rate, 1),
            'recommendation': '黑名单中的股票需要冷静，建议观察3-5个交易日后再考虑重新进场'
        }
    except Exception as e:
        logger.error(f'get_stoploss_blacklist_7d error: {e}')
        return {
            'blacklist': [],
            'total_count': 0,
            'win_after_sl_pct': 0,
            'error': str(e)
        }

# ==================== ⑤ 绩效卡片 (v5.82 vs v5.81) ====================

def get_performance_cards() -> Dict[str, Any]:
    """
    获取绩效卡片数据，用于对标v5.81版本
    
    v5.81目标:
      - 总收益: 17.1%
      - 最大回撤: 4.08%
      - 勝率: 60.0%
      - Sharpe: 2.35
    
    返回:
    {
        'cards': [
            {
                'label': '总收益',
                'current': 19.66,
                'target': 17.1,
                'unit': '%',
                'achievement': 115.0,
                'status': 'excellent'
            }
        ]
    }
    """
    try:
        snapshots = query_snapshots(days=30)
        trades = query_trades(days=30)
        account = query_account()
        
        if not snapshots or not account:
            return {'cards': [], 'message': '数据不足'}
        
        # 计算总收益
        latest_val = snapshots[-1]['total_value']
        current_return = ((latest_val - INITIAL_CAPITAL) / INITIAL_CAPITAL * 100) if latest_val else 0
        
        # 计算最大回撤
        vals = [s['total_value'] for s in snapshots]
        peak = 0
        max_dd = 0
        for v in vals:
            if v > peak:
                peak = v
            dd = (peak - v) / peak * 100 if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd
        
        # 计算胜率
        buys = [t for t in trades if t['direction'] == 'BUY']
        sells = [t for t in trades if t['direction'] == 'SELL']
        buy_map = {}
        for b in buys:
            if b['symbol'] not in buy_map:
                buy_map[b['symbol']] = []
            buy_map[b['symbol']].append(b)
        
        avg_costs = {}
        for sym, buy_list in buy_map.items():
            total_shares = sum(b['shares'] for b in buy_list)
            total_cost = sum(b['price'] * b['shares'] for b in buy_list)
            avg_costs[sym] = total_cost / total_shares if total_shares > 0 else 0
        
        wins = 0
        for sell in sells:
            cost = avg_costs.get(sell['symbol'], 0)
            if cost > 0 and sell.get('price', 0) > cost:
                wins += 1
        
        win_rate = (wins / len(sells) * 100) if sells else 0
        
        # 计算Sharpe (简化版)
        daily_returns = []
        for i in range(1, len(vals)):
            ret = (vals[i] - vals[i-1]) / vals[i-1]
            daily_returns.append(ret)
        
        if daily_returns:
            mean_ret = sum(daily_returns) / len(daily_returns)
            variance = sum((r - mean_ret) ** 2 for r in daily_returns) / len(daily_returns)
            std_dev = variance ** 0.5
            sharpe = (mean_ret / std_dev * (252 ** 0.5)) if std_dev > 0 else 0
        else:
            sharpe = 0
        
        # 构建卡片
        cards = [
            {
                'label': '总收益',
                'current': round(current_return, 2),
                'target': 17.1,
                'unit': '%',
                'achievement': round(current_return / 17.1 * 100, 1),
                'status': 'excellent' if current_return >= 17.1 else 'good' if current_return >= 15 else 'normal'
            },
            {
                'label': '最大回撤',
                'current': round(max_dd, 2),
                'target': 4.08,
                'unit': '%',
                'achievement': round(max(0, (4.08 / max_dd * 100)) if max_dd > 0 else 0, 1),
                'status': 'excellent' if max_dd <= 4.08 else 'good' if max_dd <= 5 else 'warning'
            },
            {
                'label': '胜率',
                'current': round(win_rate, 1),
                'target': 60.0,
                'unit': '%',
                'achievement': round(win_rate / 60 * 100, 1),
                'status': 'excellent' if win_rate >= 60 else 'good' if win_rate >= 50 else 'normal'
            },
            {
                'label': 'Sharpe比率',
                'current': round(sharpe, 2),
                'target': 2.35,
                'unit': '',
                'achievement': round(sharpe / 2.35 * 100, 1),
                'status': 'excellent' if sharpe >= 2.35 else 'good' if sharpe >= 2.0 else 'normal'
            }
        ]
        
        return {
            'cards': cards,
            'v581_targets': {
                'total_return': 17.1,
                'max_drawdown': 4.08,
                'win_rate': 60.0,
                'sharpe_ratio': 2.35
            },
            'updated_at': datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f'get_performance_cards error: {e}')
        return {'cards': [], 'error': str(e)}

# ==================== 聚合API ====================

def get_intraday_ui_v147() -> Dict[str, Any]:
    """
    聚合所有盤中UI数据 (v5.147) - 单次API调用获取全部信息
    
    返回:
    {
        'performance_indicators': {...},
        'signal_quality': {...},
        'emotion_triggers': {...},
        'stoploss_blacklist': {...},
        'performance_cards': {...},
        'timestamp': '2026-06-02T03:30:00'
    }
    """
    return {
        'performance_indicators': get_performance_indicators(),
        'signal_quality': get_signal_quality_score(),
        'emotion_triggers': get_emotion_trigger_decision(),
        'stoploss_blacklist': get_stoploss_blacklist_7d(),
        'performance_cards': get_performance_cards(),
        'timestamp': datetime.now().isoformat(),
        'version': 'v5.147'
    }

# ==================== 主函数 ====================

if __name__ == '__main__':
    import json
    
    # 聚合数据
    data = get_intraday_ui_v147()
    print(json.dumps(data, ensure_ascii=False, indent=2))
