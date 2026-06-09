#!/usr/bin/env python3
"""
v5.160 回测系统增强 + 信号质量追踪
===================================
目標: 
  ① 优化回测结果展示 (新增Sortino/Calmar比率)
  ② 信号质量追踪 (每日记录推荐→成交→平仓全流程)
  ③ 策略指标归因分析 (各指标单独贡献度)

作者: 金融Agent自动优化工程师
时间: 2026-06-09 03:30 UTC
"""

import sqlite3
import json
from typing import Dict, List, Any, Tuple
from datetime import datetime, timedelta

DB_PATH = '/home/nikefd/finance-agent/data/trading.db'
INITIAL_CAPITAL = 1000000

class BacktestEnhancer:
    """回测结果增强 - 新增风险调整指标"""
    
    @staticmethod
    def calculate_advanced_metrics(snapshots_data: List[Dict]) -> Dict[str, float]:
        """计算高级风险指标"""
        
        if len(snapshots_data) < 2:
            return {}
        
        values = [s['total_value'] for s in snapshots_data]
        
        # ① 最大回撤 (Maximum Drawdown)
        max_dd = 0
        peak = values[0]
        for v in values:
            if v > peak:
                peak = v
            dd = (peak - v) / peak * 100 if peak > 0 else 0
            max_dd = max(max_dd, dd)
        
        # ② 日收益率
        daily_returns = []
        for i in range(1, len(values)):
            ret = (values[i] - values[i-1]) / values[i-1] if values[i-1] > 0 else 0
            daily_returns.append(ret)
        
        avg_daily_ret = sum(daily_returns) / len(daily_returns) if daily_returns else 0
        
        # ③ 标准差
        variance = sum((r - avg_daily_ret) ** 2 for r in daily_returns) / len(daily_returns) if daily_returns else 0
        std_daily_ret = variance ** 0.5
        
        # ④ Sharpe比率 = (年化收益 - 无风险利率) / 年化波动率
        # 无风险利率设为2% (年)
        annual_return = avg_daily_ret * 252
        annual_std = std_daily_ret * (252 ** 0.5)
        sharpe = (annual_return - 0.02) / annual_std if annual_std > 0 else 0
        
        # ⑤ Sortino比率 = (年化收益 - 无风险利率) / 下行波动率
        downside_returns = [r for r in daily_returns if r < 0]
        downside_var = sum(r ** 2 for r in downside_returns) / len(downside_returns) if downside_returns else 0
        downside_std = downside_var ** 0.5
        downside_annual_std = downside_std * (252 ** 0.5)
        sortino = (annual_return - 0.02) / downside_annual_std if downside_annual_std > 0 else 0
        
        # ⑥ Calmar比率 = 年化收益 / 最大回撤
        calmar = annual_return / (max_dd / 100) if max_dd > 0 else 0
        
        # ⑦ 恢复时间 (Recovery Factor) = 总收益 / 最大回撤
        total_return = (values[-1] - values[0]) / values[0] * 100 if values[0] > 0 else 0
        recovery_factor = total_return / (max_dd if max_dd > 0 else 1)
        
        # ⑧ K比率 (Kappa) - 偏度调整
        # 简化版: 只计算三阶矩
        skewness = sum((r - avg_daily_ret) ** 3 for r in daily_returns) / len(daily_returns) if daily_returns else 0
        
        return {
            'max_drawdown': round(max_dd, 2),
            'sharpe_ratio': round(sharpe, 2),
            'sortino_ratio': round(sortino, 2),
            'calmar_ratio': round(calmar, 2),
            'recovery_factor': round(recovery_factor, 2),
            'annual_return': round(annual_return * 100, 2),
            'annual_volatility': round(annual_std * 100, 2),
            'skewness': round(skewness, 4),
        }

class SignalQualityTracker:
    """信号质量追踪 - 推荐→成交→平仓全流程"""
    
    @staticmethod
    def track_signal_lifecycle(signal_date: str, symbol: str, score: float) -> Dict[str, Any]:
        """追踪单个信号的完整生命周期"""
        
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        
        # ① 推荐时的信息
        signal_info = {
            'date': signal_date,
            'symbol': symbol,
            'recommendation_score': score,
        }
        
        # ② 查找该信号后续的交易
        trades = conn.execute("""
            SELECT * FROM trades 
            WHERE symbol = ? AND trade_date >= ?
            ORDER BY trade_date ASC
        """, [symbol, signal_date]).fetchall()
        
        buy_trade = None
        sell_trade = None
        
        for t in trades:
            if t['direction'] == 'BUY' and not buy_trade:
                buy_trade = t
            elif t['direction'] == 'SELL' and buy_trade:
                sell_trade = t
                break
        
        # ③ 计算信号效果
        if buy_trade:
            signal_info['buy_date'] = buy_trade['trade_date']
            signal_info['buy_price'] = buy_trade['price']
            signal_info['entry_delay_days'] = (
                (datetime.fromisoformat(buy_trade['trade_date']).date() - 
                 datetime.fromisoformat(signal_date).date()).days
            )
        
        if buy_trade and sell_trade:
            hold_days = (
                datetime.fromisoformat(sell_trade['trade_date']).date() - 
                datetime.fromisoformat(buy_trade['trade_date']).date()
            ).days
            
            pnl = (sell_trade['price'] - buy_trade['price']) * buy_trade['shares']
            pnl_pct = ((sell_trade['price'] - buy_trade['price']) / buy_trade['price'] * 100)
            
            signal_info.update({
                'sell_date': sell_trade['trade_date'],
                'sell_price': sell_trade['price'],
                'hold_days': hold_days,
                'pnl': round(pnl, 2),
                'pnl_pct': round(pnl_pct, 2),
                'result': 'win' if pnl > 0 else 'loss',
            })
        elif buy_trade:
            # 还未平仓
            signal_info['result'] = 'open'
        else:
            # 未成交
            signal_info['result'] = 'no_trade'
        
        conn.close()
        
        return signal_info

class IndicatorAttribution:
    """指标归因分析 - 各指标单独贡献度"""
    
    @staticmethod
    def analyze_indicator_effectiveness() -> Dict[str, Any]:
        """分析各技术指标的单独贡献度"""
        
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        
        # 获取所有已平仓交易的指标快照
        snapshots = conn.execute("""
            SELECT 
                trade_id, 
                indicators_json, 
                outcome,
                outcome_pnl_pct,
                trade_date
            FROM indicator_snapshots
            WHERE outcome IN ('win', 'loss')
            ORDER BY trade_date DESC
            LIMIT 200
        """).fetchall()
        
        conn.close()
        
        if not snapshots:
            return {'error': 'Not enough data'}
        
        # 解析指标数据
        indicator_stats = {}
        
        for snap in snapshots:
            try:
                indicators = json.loads(snap['indicators_json'])
            except:
                continue
            
            outcome = snap['outcome']
            pnl_pct = snap['outcome_pnl_pct'] or 0
            
            for indicator_name, indicator_value in indicators.items():
                if indicator_name not in indicator_stats:
                    indicator_stats[indicator_name] = {
                        'win_count': 0,
                        'loss_count': 0,
                        'win_pnl_sum': 0,
                        'loss_pnl_sum': 0,
                        'appearances': 0
                    }
                
                stats = indicator_stats[indicator_name]
                
                # 只统计指标存在(非null/非0/非false)的情况
                if indicator_value and indicator_value != 0 and indicator_value != 'none' and indicator_value != 'neutral':
                    stats['appearances'] += 1
                    
                    if outcome == 'win':
                        stats['win_count'] += 1
                        stats['win_pnl_sum'] += pnl_pct
                    elif outcome == 'loss':
                        stats['loss_count'] += 1
                        stats['loss_pnl_sum'] += pnl_pct
        
        # 计算每个指标的有效性指标
        result = []
        for indicator_name, stats in indicator_stats.items():
            total = stats['win_count'] + stats['loss_count']
            if total < 2:
                continue
            
            win_rate = (stats['win_count'] / total * 100) if total > 0 else 0
            avg_pnl_when_present = (stats['win_pnl_sum'] + stats['loss_pnl_sum']) / total if total > 0 else 0
            expectation = (stats['win_count'] * (stats['win_pnl_sum'] / stats['win_count'] if stats['win_count'] > 0 else 0) - 
                          stats['loss_count'] * abs(stats['loss_pnl_sum'] / stats['loss_count'] if stats['loss_count'] > 0 else 0)) / total if total > 0 else 0
            
            result.append({
                'indicator': indicator_name,
                'appearances': stats['appearances'],
                'win_count': stats['win_count'],
                'loss_count': stats['loss_count'],
                'win_rate': round(win_rate, 2),
                'avg_pnl': round(avg_pnl_when_present, 2),
                'expectation': round(expectation, 2),  # 期望收益
                'effectiveness_score': round(
                    (win_rate / 100 * stats['appearances']) +  # 胜率权重
                    (max(0, avg_pnl_when_present) / 10),  # P&L权重
                    2
                )
            })
        
        # 按有效性得分排序
        result.sort(key=lambda x: x['effectiveness_score'], reverse=True)
        
        return {
            'indicators': result,
            'total_signals': len(snapshots),
            'analysis_date': datetime.now().isoformat()
        }

def get_backtest_enhanced_report() -> Dict[str, Any]:
    """获取增强版回测报告"""
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    snapshots = conn.execute(
        'SELECT * FROM daily_snapshots ORDER BY date ASC'
    ).fetchall()
    
    conn.close()
    
    if not snapshots:
        return {'error': 'No data'}
    
    # 计算高级指标
    metrics = BacktestEnhancer.calculate_advanced_metrics([dict(s) for s in snapshots])
    
    return {
        'advanced_metrics': metrics,
        'indicator_analysis': IndicatorAttribution.analyze_indicator_effectiveness(),
        'report_date': datetime.now().isoformat()
    }

if __name__ == '__main__':
    report = get_backtest_enhanced_report()
    print(json.dumps(report, ensure_ascii=False, indent=2))
