#!/usr/bin/env python3
"""
UI Intraday Stats API Enhancement (v5.88 → v5.89)
新增 /api/finance/intraday-stats 端点
显示: 日内交易指标、现金检测状态、MACD信号统计

Author: 狗蛋 Financial Agent
Date: 2026-05-06 盤中優化
"""

import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
import sys

# Setup paths
PROJECT_ROOT = Path('/home/nikefd/finance-agent')
sys.path.insert(0, str(PROJECT_ROOT))

from config import (
    CASH_AUTO_DETECTION_LEVELS, 
    EXTREME_CASH_V87,
    DB_PATH
)


class IntradayStatsCollector:
    """收集和计算日内交易统计指标"""
    
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.today = datetime.now().date()
    
    def get_cash_status(self):
        """检测当前现金状态和触发的激活模式"""
        try:
            account = self.conn.execute(
                'SELECT cash, total_value FROM account ORDER BY id DESC LIMIT 1'
            ).fetchone()
            
            if not account:
                return {'mode': 'unknown', 'cash_ratio': 0, 'activated': False}
            
            cash = account['cash']
            total_value = account['total_value']
            cash_ratio = cash / total_value if total_value > 0 else 0
            
            # Detect which level is active
            mode = 'normal'
            multiplier = 1.0
            threshold = 0.75
            
            if cash_ratio >= CASH_AUTO_DETECTION_LEVELS['extreme']['threshold']:
                mode = 'extreme'
                threshold = CASH_AUTO_DETECTION_LEVELS['extreme']['threshold']
                multiplier = CASH_AUTO_DETECTION_LEVELS['extreme']['multiplier']
            elif cash_ratio >= CASH_AUTO_DETECTION_LEVELS['aggressive']['threshold']:
                mode = 'aggressive'
                threshold = CASH_AUTO_DETECTION_LEVELS['aggressive']['threshold']
                multiplier = CASH_AUTO_DETECTION_LEVELS['aggressive']['multiplier']
            
            return {
                'mode': mode,
                'cash_ratio': round(cash_ratio * 100, 2),
                'cash_amount': round(cash, 2),
                'threshold': round(threshold * 100, 2),
                'multiplier': multiplier,
                'activated': mode != 'normal'
            }
        except Exception as e:
            print(f"[Error] get_cash_status: {e}")
            return {'mode': 'error', 'cash_ratio': 0, 'activated': False}
    
    def get_intraday_trades(self):
        """获取今日所有交易"""
        try:
            # Get today's trades (buy + sell)
            trades = self.conn.execute(f"""
                SELECT symbol, operation, price, shares, total_cost, timestamp
                FROM trades
                WHERE DATE(timestamp) = ?
                ORDER BY timestamp ASC
            """, (self.today,)).fetchall()
            
            return [dict(t) for t in trades]
        except Exception as e:
            print(f"[Error] get_intraday_trades: {e}")
            return []
    
    def calculate_trade_metrics(self):
        """计算日内交易指标"""
        try:
            trades = self.get_intraday_trades()
            
            if not trades:
                return {
                    'total_trades': 0,
                    'buy_orders': 0,
                    'sell_orders': 0,
                    'win_trades': 0,
                    'loss_trades': 0,
                    'win_rate': 0,
                    'avg_pnl_pct': 0,
                    'total_pnl': 0
                }
            
            # Group by symbol to pair buy/sell
            sells = [t for t in trades if t['operation'] == 'SELL']
            buys = [t for t in trades if t['operation'] == 'BUY']
            
            # Calculate realized P&L from sell trades
            win_count = 0
            loss_count = 0
            total_pnl = 0
            pnl_pcts = []
            
            # Get buy prices for matching
            buy_prices = {}
            for buy in buys:
                symbol = buy['symbol']
                if symbol not in buy_prices:
                    buy_prices[symbol] = []
                buy_prices[symbol].append(buy['price'])
            
            for sell in sells:
                symbol = sell['symbol']
                if symbol in buy_prices and buy_prices[symbol]:
                    # Match with oldest buy (FIFO)
                    buy_price = buy_prices[symbol].pop(0)
                    pnl = (sell['price'] - buy_price) * sell['shares']
                    pnl_pct = (sell['price'] - buy_price) / buy_price * 100
                    total_pnl += pnl
                    pnl_pcts.append(pnl_pct)
                    
                    if pnl > 0:
                        win_count += 1
                    else:
                        loss_count += 1
            
            win_rate = (win_count / len(sells) * 100) if sells else 0
            avg_pnl_pct = sum(pnl_pcts) / len(pnl_pcts) if pnl_pcts else 0
            
            return {
                'total_trades': len(trades),
                'buy_orders': len(buys),
                'sell_orders': len(sells),
                'win_trades': win_count,
                'loss_trades': loss_count,
                'win_rate': round(win_rate, 2),
                'avg_pnl_pct': round(avg_pnl_pct, 2),
                'total_pnl': round(total_pnl, 2)
            }
        except Exception as e:
            print(f"[Error] calculate_trade_metrics: {e}")
            return {}
    
    def get_macd_signal_stats(self):
        """统计MACD信号触发次数（v5.88新增：直方图翻正）"""
        try:
            # 从daily_snapshots获取MACD相关数据
            snapshots = self.conn.execute(f"""
                SELECT date, macd_signal_count, macd_histogram_crosses
                FROM daily_snapshots
                WHERE DATE(date) >= DATE('now', '-7 days')
                ORDER BY date DESC
                LIMIT 7
            """).fetchall()
            
            if not snapshots:
                return {
                    'macd_signals_today': 0,
                    'histogram_crosses_today': 0,
                    'weekly_avg_signals': 0
                }
            
            today_snap = snapshots[0] if snapshots else None
            weekly_signals = sum([s['macd_signal_count'] or 0 for s in snapshots])
            weekly_crosses = sum([s['macd_histogram_crosses'] or 0 for s in snapshots])
            
            return {
                'macd_signals_today': today_snap['macd_signal_count'] if today_snap else 0,
                'histogram_crosses_today': today_snap['macd_histogram_crosses'] if today_snap else 0,
                'weekly_avg_signals': round(weekly_signals / 7, 1),
                'weekly_histogram_crosses': round(weekly_crosses / 7, 1)
            }
        except Exception as e:
            print(f"[Error] get_macd_signal_stats: {e}")
            return {
                'macd_signals_today': 0,
                'histogram_crosses_today': 0,
                'weekly_avg_signals': 0
            }
    
    def get_portfolio_heat_map(self):
        """生成仓位热力图数据（按风险等级分类）"""
        try:
            positions = self.conn.execute("""
                SELECT symbol, name, shares, current_price, avg_cost, peak_price
                FROM positions
                WHERE shares > 0
                ORDER BY (current_price - avg_cost) / avg_cost DESC
            """).fetchall()
            
            heat_map = {
                'high_gain': [],      # 收益 > 10%
                'normal': [],         # -5% ≤ 收益 ≤ 10%
                'warning': [],        # -10% ≤ 收益 < -5%
                'danger': []          # 收益 < -10%
            }
            
            for pos in positions:
                pnl_pct = ((pos['current_price'] - pos['avg_cost']) / pos['avg_cost'] * 100) if pos['avg_cost'] > 0 else 0
                risk_level = 'danger' if pnl_pct < -10 else 'warning' if pnl_pct < -5 else 'normal' if pnl_pct <= 10 else 'high_gain'
                
                heat_map[risk_level].append({
                    'symbol': pos['symbol'],
                    'name': pos['name'],
                    'pnl_pct': round(pnl_pct, 2),
                    'ratio': round((pos['shares'] * pos['current_price']) / (pos['shares'] * pos['avg_cost'] + 1) * 100, 1) if pos['avg_cost'] > 0 else 0
                })
            
            return heat_map
        except Exception as e:
            print(f"[Error] get_portfolio_heat_map: {e}")
            return {'high_gain': [], 'normal': [], 'warning': [], 'danger': []}
    
    def collect_all_stats(self):
        """收集所有统计数据"""
        return {
            'timestamp': datetime.now().isoformat(),
            'cash_status': self.get_cash_status(),
            'trade_metrics': self.calculate_trade_metrics(),
            'macd_signals': self.get_macd_signal_stats(),
            'portfolio_heat_map': self.get_portfolio_heat_map()
        }
    
    def close(self):
        self.conn.close()


if __name__ == '__main__':
    # Test
    collector = IntradayStatsCollector()
    stats = collector.collect_all_stats()
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    collector.close()
