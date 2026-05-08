#!/usr/bin/env python3
"""v5.82 盤中統計數據提取器

提供Sharpe倍數、Kelly容差、入場勝率等盤中統計
"""

import sqlite3
import json
from datetime import date, datetime, timedelta
from pathlib import Path

DB_PATH = Path('/home/nikefd/finance-agent/data/trading.db')

def get_sharpe_ratio(lookback_days=30):
    """計算Sharpe倍數 (年化)"""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        c = conn.cursor()
        
        # 获取过去N天的每日收益
        cutoff_date = (date.today() - timedelta(days=lookback_days)).isoformat()
        c.execute("""SELECT date, total_value FROM daily_snapshots 
                     WHERE date >= ? ORDER BY date ASC""", (cutoff_date,))
        rows = c.fetchall()
        conn.close()
        
        if len(rows) < 2:
            return 0.0
        
        # 計算日收益率
        returns = []
        for i in range(1, len(rows)):
            prev_val = rows[i-1][1]
            curr_val = rows[i][1]
            if prev_val > 0:
                ret = (curr_val - prev_val) / prev_val
                returns.append(ret)
        
        if len(returns) < 2:
            return 0.0
        
        # 計算平均收益和標準差
        avg_ret = sum(returns) / len(returns)
        variance = sum((r - avg_ret) ** 2 for r in returns) / (len(returns) - 1)
        std_dev = variance ** 0.5
        
        if std_dev == 0:
            return 0.0
        
        # 年化Sharpe比率
        sharpe = (avg_ret / std_dev) * (252 ** 0.5)
        return round(sharpe, 2)
    except Exception as e:
        print(f"Error calculating Sharpe: {e}")
        return 0.0

def get_kelly_percentage():
    """計算Kelly準則百分比 (Kelly% = Win% - Loss% / Win/Loss Ratio)"""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        c = conn.cursor()
        
        # 獲取最近的交易
        c.execute("""SELECT symbol, price, direction FROM trades 
                     ORDER BY trade_date DESC, id DESC LIMIT 100""")
        trades = c.fetchall()
        conn.close()
        
        # 建立買入成本對應
        costs = {}
        wins = 0
        losses = 0
        
        for symbol, price, direction in reversed(trades):
            if direction == 'BUY':
                costs[symbol] = price
            elif direction == 'SELL' and symbol in costs:
                cost = costs[symbol]
                if price > cost:
                    wins += 1
                else:
                    losses += 1
        
        total = wins + losses
        if total == 0:
            return 0.0
        
        win_pct = wins / total
        loss_pct = losses / total
        
        # 計算Kelly%: Win% - (Loss% / (Win/Loss Ratio))
        if win_pct == 0:
            return -100.0
        
        avg_win = sum(1 for symbol, price, direction in reversed(trades) 
                     if direction == 'SELL' and symbol in costs and price > costs[symbol]) / max(wins, 1) if wins > 0 else 0
        avg_loss = sum(1 for symbol, price, direction in reversed(trades) 
                      if direction == 'SELL' and symbol in costs and price <= costs[symbol]) / max(losses, 1) if losses > 0 else 0
        
        if avg_loss == 0:
            kelly_pct = (win_pct * 100) - (loss_pct * 100)
        else:
            kelly_pct = (win_pct * 100) - (loss_pct * 100) / (avg_win / max(avg_loss, 0.01))
        
        return round(kelly_pct, 2)
    except Exception as e:
        print(f"Error calculating Kelly: {e}")
        return 0.0

def get_entry_win_rate(lookback_days=7):
    """計算近期入場的勝率 (基於買入後是否獲利)"""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        c = conn.cursor()
        
        cutoff_date = (date.today() - timedelta(days=lookback_days)).isoformat()
        
        # 獲取買入記錄
        c.execute("""SELECT symbol, price, trade_date FROM trades 
                     WHERE direction='BUY' AND trade_date >= ? 
                     ORDER BY trade_date DESC""", (cutoff_date,))
        buys = c.fetchall()
        
        if not buys:
            conn.close()
            return 0.0
        
        # 檢查每個買入是否后续賣出獲利
        wins = 0
        for symbol, buy_price, buy_date in buys:
            c.execute("""SELECT price FROM trades 
                        WHERE symbol=? AND direction='SELL' AND trade_date > ? 
                        ORDER BY trade_date ASC LIMIT 1""", (symbol, buy_date))
            sell = c.fetchone()
            if sell and sell[0] > buy_price:
                wins += 1
        
        conn.close()
        
        win_rate = (wins / len(buys)) * 100 if buys else 0
        return round(win_rate, 1)
    except Exception as e:
        print(f"Error calculating entry win rate: {e}")
        return 0.0

def get_v5_82_statistics():
    """獲取v5.82盤中統計摘要"""
    return {
        'sharpe_ratio': get_sharpe_ratio(30),
        'kelly_percentage': get_kelly_percentage(),
        'entry_win_rate': get_entry_win_rate(7),
        'timestamp': datetime.now().isoformat()
    }

if __name__ == '__main__':
    stats = get_v5_82_statistics()
    print(json.dumps(stats, ensure_ascii=False, default=str))
