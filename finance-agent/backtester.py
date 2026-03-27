"""回测引擎 — 用历史数据验证选股策略"""

import json
import sqlite3
import time
from datetime import datetime, timedelta
from data_collector import get_stock_daily, calculate_technical_indicators
from config import *

DB_PATH_BT = "/home/nikefd/finance-agent/data/backtest.db"


def init_backtest_db():
    conn = sqlite3.connect(DB_PATH_BT)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS backtest_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        strategy TEXT, start_date TEXT, end_date TEXT,
        initial_capital REAL, final_value REAL, total_return REAL,
        max_drawdown REAL, win_rate REAL, total_trades INTEGER,
        win_trades INTEGER, loss_trades INTEGER,
        sharpe_ratio REAL, profit_factor REAL,
        details TEXT, created_at TEXT
    )''')
    conn.commit()
    conn.close()


class BacktestEngine:
    def __init__(self, initial_capital=1_000_000):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.positions = {}  # {symbol: {shares, cost, buy_date, buy_price}}
        self.trades = []
        self.daily_values = []  # [(date, total_value)]
        self.peak_value = initial_capital

    @property
    def total_value(self):
        pos_value = sum(p['shares'] * p['current_price'] for p in self.positions.values())
        return self.cash + pos_value

    def buy(self, symbol, name, price, shares, date, reason=""):
        cost = price * shares
        commission = max(cost * COMMISSION_RATE, MIN_COMMISSION)
        total = cost + commission
        if total > self.cash or shares < 100:
            return False
        self.cash -= total
        if symbol in self.positions:
            old = self.positions[symbol]
            new_shares = old['shares'] + shares
            new_cost = (old['shares'] * old['cost'] + cost) / new_shares
            self.positions[symbol] = {**old, 'shares': new_shares, 'cost': new_cost, 'current_price': price}
        else:
            self.positions[symbol] = {
                'name': name, 'shares': shares, 'cost': price,
                'buy_date': date, 'buy_price': price, 'current_price': price
            }
        self.trades.append({
            'date': date, 'symbol': symbol, 'name': name,
            'direction': 'BUY', 'price': price, 'shares': shares,
            'amount': cost, 'reason': reason
        })
        return True

    def sell(self, symbol, price, shares, date, reason=""):
        if symbol not in self.positions:
            return False
        pos = self.positions[symbol]
        if shares > pos['shares']:
            shares = pos['shares']
        amount = price * shares
        commission = max(amount * COMMISSION_RATE, MIN_COMMISSION)
        tax = amount * STAMP_TAX_RATE
        net = amount - commission - tax
        self.cash += net
        profit = (price - pos['cost']) * shares - commission - tax
        self.trades.append({
            'date': date, 'symbol': symbol, 'name': pos['name'],
            'direction': 'SELL', 'price': price, 'shares': shares,
            'amount': amount, 'profit': profit, 'reason': reason
        })
        if shares >= pos['shares']:
            del self.positions[symbol]
        else:
            self.positions[symbol]['shares'] -= shares
        return True

    def update_prices(self, prices: dict):
        for sym, price in prices.items():
            if sym in self.positions:
                self.positions[sym]['current_price'] = price

    def record_daily(self, date):
        val = self.total_value
        self.daily_values.append((date, val))
        if val > self.peak_value:
            self.peak_value = val

    def get_stats(self):
        if not self.daily_values:
            return {}

        values = [v for _, v in self.daily_values]
        final = values[-1]
        total_return = (final - self.initial_capital) / self.initial_capital * 100

        # 最大回撤
        peak = values[0]
        max_dd = 0
        for v in values:
            if v > peak:
                peak = v
            dd = (peak - v) / peak * 100
            if dd > max_dd:
                max_dd = dd

        # 胜率
        sell_trades = [t for t in self.trades if t['direction'] == 'SELL']
        wins = [t for t in sell_trades if t.get('profit', 0) > 0]
        losses = [t for t in sell_trades if t.get('profit', 0) <= 0]
        win_rate = len(wins) / max(len(sell_trades), 1) * 100

        # 盈亏比
        avg_win = sum(t['profit'] for t in wins) / max(len(wins), 1)
        avg_loss = abs(sum(t['profit'] for t in losses) / max(len(losses), 1))
        profit_factor = avg_win / max(avg_loss, 1)

        # 年化收益
        days = len(values)
        annual_return = total_return / max(days, 1) * 252

        # 夏普比率(简化)
        if len(values) > 1:
            import numpy as np
            returns = np.diff(values) / values[:-1]
            sharpe = (np.mean(returns) / max(np.std(returns), 1e-10)) * (252 ** 0.5)
        else:
            sharpe = 0

        return {
            'total_return': round(total_return, 2),
            'annual_return': round(annual_return, 2),
            'max_drawdown': round(max_dd, 2),
            'win_rate': round(win_rate, 1),
            'total_trades': len(self.trades),
            'sell_trades': len(sell_trades),
            'win_trades': len(wins),
            'loss_trades': len(losses),
            'profit_factor': round(profit_factor, 2),
            'sharpe_ratio': round(sharpe, 2),
            'final_value': round(final, 2),
        }


def backtest_technical_strategy(symbols: list, start_date: str, end_date: str,
                                 strategy_name: str = "MACD+RSI") -> dict:
    """回测技术面策略"""
    engine = BacktestEngine()
    print(f"\n📊 回测 [{strategy_name}] | {start_date} ~ {end_date} | {len(symbols)}只股票池")

    # 加载所有历史数据
    all_data = {}
    for sym in symbols:
        df = get_stock_daily(sym, days=365)
        if df is not None and not df.empty:
            all_data[sym] = df
            time.sleep(0.3)
    print(f"  加载了{len(all_data)}只股票数据")

    if not all_data:
        return {"error": "无数据"}

    # 获取交易日列表
    sample = list(all_data.values())[0]
    trade_dates = [d for d in sample['日期'].tolist() if start_date <= d <= end_date]
    print(f"  交易日: {len(trade_dates)}天")

    for i, date in enumerate(trade_dates):
        # 更新持仓价格
        prices = {}
        for sym, df in all_data.items():
            row = df[df['日期'] == date]
            if not row.empty:
                prices[sym] = float(row.iloc[0]['收盘'])
        engine.update_prices(prices)

        # 每5天检查一次信号(模拟周度调仓)
        if i % 5 == 0 and i >= 20:
            # 检查止损止盈
            for sym in list(engine.positions.keys()):
                pos = engine.positions[sym]
                pnl_pct = (pos['current_price'] - pos['cost']) / pos['cost']
                if pnl_pct <= STOP_LOSS:
                    engine.sell(sym, pos['current_price'], pos['shares'], date, f"止损{pnl_pct*100:.1f}%")
                elif pnl_pct >= TAKE_PROFIT:
                    engine.sell(sym, pos['current_price'], pos['shares'], date, f"止盈{pnl_pct*100:.1f}%")

            # 扫描买入信号
            for sym, df in all_data.items():
                if sym in engine.positions:
                    continue
                if len(engine.positions) >= MAX_POSITIONS:
                    break

                # 取到当前日期的数据计算技术指标
                mask = df['日期'] <= date
                hist = df[mask].tail(60)
                if len(hist) < 20:
                    continue

                tech = calculate_technical_indicators(hist)
                if not tech:
                    continue

                # === 核心策略逻辑 ===
                score = 0

                # MACD金叉 (+3)
                if tech.get('macd_signal') == 'golden_cross':
                    score += 3
                elif tech.get('macd_signal') == 'bullish':
                    score += 1

                # RSI健康区 (+2)
                rsi = tech.get('rsi14', 50)
                if 35 < rsi < 65:
                    score += 2
                elif rsi > 80:
                    score -= 2  # 超买扣分

                # 多头排列 (+2)
                trend = tech.get('trend', '')
                if '多头' in trend:
                    score += 2
                elif '空头' in trend:
                    score -= 2

                # 放量 (+1)
                if tech.get('volume_ratio', 1) > 1.5:
                    score += 1

                # 价格在布林中轨上方 (+1)
                price = tech.get('current_price', 0)
                boll_mid = tech.get('boll_middle', 0)
                if price > boll_mid > 0:
                    score += 1

                # 达到阈值才买
                if score >= 5:
                    buy_price = prices.get(sym, 0)
                    if buy_price > 0:
                        buy_amount = engine.cash * 0.10
                        shares = int(buy_amount / buy_price / 100) * 100
                        if shares >= 100:
                            engine.buy(sym, sym, buy_price, shares, date, f"技术面得分{score}")

        engine.record_daily(date)

    # 清仓计算最终收益
    for sym in list(engine.positions.keys()):
        pos = engine.positions[sym]
        engine.sell(sym, pos['current_price'], pos['shares'], trade_dates[-1], "回测结束清仓")

    stats = engine.get_stats()
    stats['strategy'] = strategy_name
    stats['start_date'] = start_date
    stats['end_date'] = end_date
    stats['stock_pool'] = len(symbols)

    # 保存结果
    save_backtest_result(stats, engine.trades)
    return stats


def save_backtest_result(stats: dict, trades: list):
    init_backtest_db()
    conn = sqlite3.connect(DB_PATH_BT)
    c = conn.cursor()
    c.execute("""INSERT INTO backtest_runs 
        (strategy, start_date, end_date, initial_capital, final_value, total_return,
         max_drawdown, win_rate, total_trades, win_trades, loss_trades,
         sharpe_ratio, profit_factor, details, created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (stats.get('strategy',''), stats.get('start_date',''), stats.get('end_date',''),
         1000000, stats.get('final_value',0), stats.get('total_return',0),
         stats.get('max_drawdown',0), stats.get('win_rate',0),
         stats.get('total_trades',0), stats.get('win_trades',0), stats.get('loss_trades',0),
         stats.get('sharpe_ratio',0), stats.get('profit_factor',0),
         json.dumps(trades[:50], ensure_ascii=False, default=str),
         datetime.now().isoformat()))
    conn.commit()
    conn.close()


def run_full_backtest():
    """运行完整回测"""
    # 选一批有代表性的股票池
    stock_pools = {
        "白马消费": ['600519', '000858', '600887', '603288', '000596', '605499',
                      '600809', '000568', '603369', '002304'],
        "科技成长": ['603601', '002371', '300750', '688012', '002415', '300124',
                      '688008', '300033', '002230', '603986'],
        "新能源": ['601016', '600438', '002594', '300274', '601012', '600089',
                    '002129', '300014', '600905', '601985'],
        "混合池": ['600519', '000858', '300750', '603601', '002415', '600887',
                    '601016', '002594', '300033', '688012', '605499', '300124',
                    '002371', '600438', '002304'],
    }

    results = {}
    for pool_name, symbols in stock_pools.items():
        print(f"\n{'='*60}")
        print(f"🏊 股票池: {pool_name} ({len(symbols)}只)")
        print(f"{'='*60}")

        stats = backtest_technical_strategy(
            symbols=symbols,
            start_date="2025-06-01",
            end_date="2026-03-25",
            strategy_name=f"MACD+RSI ({pool_name})"
        )

        if 'error' not in stats:
            results[pool_name] = stats
            print(f"\n  📈 总收益: {stats['total_return']:+.2f}%")
            print(f"  📉 最大回撤: {stats['max_drawdown']:.2f}%")
            print(f"  🎯 胜率: {stats['win_rate']:.1f}%")
            print(f"  📊 盈亏比: {stats['profit_factor']:.2f}")
            print(f"  ⚡ 夏普比率: {stats['sharpe_ratio']:.2f}")
            print(f"  🔄 总交易: {stats['total_trades']}笔 (赢{stats['win_trades']} 亏{stats['loss_trades']})")

    # 总结
    print(f"\n\n{'='*60}")
    print("📊 回测总结")
    print(f"{'='*60}")
    print(f"{'策略':<25} {'收益':>8} {'回撤':>8} {'胜率':>8} {'夏普':>8}")
    print("-" * 60)
    for name, s in results.items():
        print(f"{'MACD+RSI('+name+')':<25} {s['total_return']:>+7.2f}% {s['max_drawdown']:>7.2f}% {s['win_rate']:>7.1f}% {s['sharpe_ratio']:>7.2f}")

    return results


if __name__ == "__main__":
    results = run_full_backtest()
