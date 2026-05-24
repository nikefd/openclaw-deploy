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


def backtest_ma_cross(symbols: list, start_date: str, end_date: str,
                      strategy_name: str = "MA_CROSS") -> dict:
    """策略2: 均线突破策略 — 金叉+站上60日线+放量"""
    engine = BacktestEngine()
    print(f"\n📊 回测 [{strategy_name}] | {start_date} ~ {end_date} | {len(symbols)}只股票池")

    all_data = {}
    for sym in symbols:
        df = get_stock_daily(sym, days=365)
        if df is not None and not df.empty:
            all_data[sym] = df
            time.sleep(0.3)
    print(f"  加载了{len(all_data)}只股票数据")
    if not all_data:
        return {"error": "无数据"}

    sample = list(all_data.values())[0]
    trade_dates = [d for d in sample['日期'].tolist() if start_date <= d <= end_date]
    print(f"  交易日: {len(trade_dates)}天")

    for i, date in enumerate(trade_dates):
        prices = {}
        for sym, df in all_data.items():
            row = df[df['日期'] == date]
            if not row.empty:
                prices[sym] = float(row.iloc[0]['收盘'])
        engine.update_prices(prices)

        if i % 5 == 0 and i >= 20:
            # 止损 + 死叉卖出
            for sym in list(engine.positions.keys()):
                pos = engine.positions[sym]
                pnl_pct = (pos['current_price'] - pos['cost']) / pos['cost']
                if pnl_pct <= -0.08:
                    engine.sell(sym, pos['current_price'], pos['shares'], date, f"止损{pnl_pct*100:.1f}%")
                    continue
                # 检查死叉
                if sym in all_data:
                    mask = all_data[sym]['日期'] <= date
                    hist = all_data[sym][mask].tail(60)
                    if len(hist) >= 20:
                        tech = calculate_technical_indicators(hist)
                        if tech and tech.get('ma5', 0) < tech.get('ma20', 0):
                            engine.sell(sym, pos['current_price'], pos['shares'], date, "MA5下穿MA20死叉")

            # 买入信号
            for sym, df in all_data.items():
                if sym in engine.positions or len(engine.positions) >= MAX_POSITIONS:
                    break
                mask = df['日期'] <= date
                hist = df[mask].tail(60)
                if len(hist) < 25:
                    continue
                tech = calculate_technical_indicators(hist)
                if not tech:
                    continue
                ma5 = tech.get('ma5', 0)
                ma20 = tech.get('ma20', 0)
                ma60 = tech.get('ma60', 0)
                vol_ratio = tech.get('volume_ratio', 1)
                price = tech.get('current_price', 0)
                # 需要前一天ma5<=ma20 今天ma5>ma20 (金叉近似)
                # 用macd_signal作为辅助判断金叉趋势
                if ma5 > ma20 and price > ma60 > 0 and vol_ratio > 1.3:
                    # 进一步确认: ma5刚刚上穿(差距小)
                    if 0 < (ma5 - ma20) / ma20 < 0.03:
                        buy_price = prices.get(sym, 0)
                        if buy_price > 0:
                            buy_amount = engine.cash * 0.10
                            shares = int(buy_amount / buy_price / 100) * 100
                            if shares >= 100:
                                engine.buy(sym, sym, buy_price, shares, date, "MA金叉+站上60日线+放量")

        engine.record_daily(date)

    for sym in list(engine.positions.keys()):
        pos = engine.positions[sym]
        engine.sell(sym, pos['current_price'], pos['shares'], trade_dates[-1], "回测结束清仓")

    stats = engine.get_stats()
    stats['strategy'] = strategy_name
    stats['start_date'] = start_date
    stats['end_date'] = end_date
    stats['stock_pool'] = len(symbols)
    save_backtest_result(stats, engine.trades)
    return stats


def backtest_boll_revert(symbols: list, start_date: str, end_date: str,
                         strategy_name: str = "BOLL_REVERT") -> dict:
    """策略3: 布林带回归策略 — 触下轨+RSI<30+MACD走平"""
    engine = BacktestEngine()
    print(f"\n📊 回测 [{strategy_name}] | {start_date} ~ {end_date} | {len(symbols)}只股票池")

    all_data = {}
    for sym in symbols:
        df = get_stock_daily(sym, days=365)
        if df is not None and not df.empty:
            all_data[sym] = df
            time.sleep(0.3)
    print(f"  加载了{len(all_data)}只股票数据")
    if not all_data:
        return {"error": "无数据"}

    sample = list(all_data.values())[0]
    trade_dates = [d for d in sample['日期'].tolist() if start_date <= d <= end_date]
    print(f"  交易日: {len(trade_dates)}天")

    for i, date in enumerate(trade_dates):
        prices = {}
        for sym, df in all_data.items():
            row = df[df['日期'] == date]
            if not row.empty:
                prices[sym] = float(row.iloc[0]['收盘'])
        engine.update_prices(prices)

        if i % 3 == 0 and i >= 20:
            # 卖出: 触上轨 或 止损-6%
            for sym in list(engine.positions.keys()):
                pos = engine.positions[sym]
                pnl_pct = (pos['current_price'] - pos['cost']) / pos['cost']
                if pnl_pct <= -0.06:
                    engine.sell(sym, pos['current_price'], pos['shares'], date, f"止损{pnl_pct*100:.1f}%")
                    continue
                if sym in all_data:
                    mask = all_data[sym]['日期'] <= date
                    hist = all_data[sym][mask].tail(60)
                    if len(hist) >= 20:
                        tech = calculate_technical_indicators(hist)
                        if tech and tech.get('current_price', 0) >= tech.get('boll_upper', float('inf')):
                            engine.sell(sym, pos['current_price'], pos['shares'], date, "触及布林上轨止盈")

            # 买入
            for sym, df in all_data.items():
                if sym in engine.positions or len(engine.positions) >= MAX_POSITIONS:
                    break
                mask = df['日期'] <= date
                hist = df[mask].tail(60)
                if len(hist) < 20:
                    continue
                tech = calculate_technical_indicators(hist)
                if not tech:
                    continue
                price = tech.get('current_price', 0)
                boll_lower = tech.get('boll_lower', 0)
                rsi = tech.get('rsi14', 50)
                macd_val = tech.get('macd', 0)
                # 价格触及下轨 + RSI<30 + MACD走平或底背离(简化为macd绝对值小)
                if price > 0 and boll_lower > 0 and price <= boll_lower * 1.01 and rsi < 30 and abs(macd_val) < 0.5:
                    buy_price = prices.get(sym, 0)
                    if buy_price > 0:
                        buy_amount = engine.cash * 0.10
                        shares = int(buy_amount / buy_price / 100) * 100
                        if shares >= 100:
                            engine.buy(sym, sym, buy_price, shares, date, f"布林下轨+RSI{rsi:.0f}")

        engine.record_daily(date)

    for sym in list(engine.positions.keys()):
        pos = engine.positions[sym]
        engine.sell(sym, pos['current_price'], pos['shares'], trade_dates[-1], "回测结束清仓")

    stats = engine.get_stats()
    stats['strategy'] = strategy_name
    stats['start_date'] = start_date
    stats['end_date'] = end_date
    stats['stock_pool'] = len(symbols)
    save_backtest_result(stats, engine.trades)
    return stats


def backtest_trend_follow(symbols: list, start_date: str, end_date: str,
                          strategy_name: str = "TREND_FOLLOW") -> dict:
    """策略4: 趋势跟踪策略 — 多头排列+MACD>0+量比>1.2"""
    engine = BacktestEngine()
    print(f"\n📊 回测 [{strategy_name}] | {start_date} ~ {end_date} | {len(symbols)}只股票池")

    all_data = {}
    for sym in symbols:
        df = get_stock_daily(sym, days=365)
        if df is not None and not df.empty:
            all_data[sym] = df
            time.sleep(0.3)
    print(f"  加载了{len(all_data)}只股票数据")
    if not all_data:
        return {"error": "无数据"}

    sample = list(all_data.values())[0]
    trade_dates = [d for d in sample['日期'].tolist() if start_date <= d <= end_date]
    print(f"  交易日: {len(trade_dates)}天")

    for i, date in enumerate(trade_dates):
        prices = {}
        for sym, df in all_data.items():
            row = df[df['日期'] == date]
            if not row.empty:
                prices[sym] = float(row.iloc[0]['收盘'])
        engine.update_prices(prices)

        if i % 5 == 0 and i >= 20:
            # 卖出
            for sym in list(engine.positions.keys()):
                pos = engine.positions[sym]
                pnl_pct = (pos['current_price'] - pos['cost']) / pos['cost']
                if pnl_pct <= -0.10:
                    engine.sell(sym, pos['current_price'], pos['shares'], date, f"止损{pnl_pct*100:.1f}%")
                    continue
                if pnl_pct >= 0.25:
                    engine.sell(sym, pos['current_price'], pos['shares'], date, f"止盈{pnl_pct*100:.1f}%")
                    continue
                if sym in all_data:
                    mask = all_data[sym]['日期'] <= date
                    hist = all_data[sym][mask].tail(60)
                    if len(hist) >= 20:
                        tech = calculate_technical_indicators(hist)
                        if tech:
                            trend = tech.get('trend', '')
                            if '多头' not in trend:
                                engine.sell(sym, pos['current_price'], pos['shares'], date, "趋势破坏卖出")

            # 买入
            for sym, df in all_data.items():
                if sym in engine.positions or len(engine.positions) >= MAX_POSITIONS:
                    break
                mask = df['日期'] <= date
                hist = df[mask].tail(60)
                if len(hist) < 60:
                    continue
                tech = calculate_technical_indicators(hist)
                if not tech:
                    continue
                ma5 = tech.get('ma5', 0)
                ma10 = tech.get('ma10', 0)
                ma20 = tech.get('ma20', 0)
                ma60 = tech.get('ma60', 0)
                macd_val = tech.get('macd', 0)
                vol_ratio = tech.get('volume_ratio', 1)
                if ma5 > ma10 > ma20 > ma60 > 0 and macd_val > 0 and vol_ratio > 1.2:
                    buy_price = prices.get(sym, 0)
                    if buy_price > 0:
                        buy_amount = engine.cash * 0.10
                        shares = int(buy_amount / buy_price / 100) * 100
                        if shares >= 100:
                            engine.buy(sym, sym, buy_price, shares, date, "多头排列+MACD正+放量")

        engine.record_daily(date)

    for sym in list(engine.positions.keys()):
        pos = engine.positions[sym]
        engine.sell(sym, pos['current_price'], pos['shares'], trade_dates[-1], "回测结束清仓")

    stats = engine.get_stats()
    stats['strategy'] = strategy_name
    stats['start_date'] = start_date
    stats['end_date'] = end_date
    stats['stock_pool'] = len(symbols)
    save_backtest_result(stats, engine.trades)
    return stats


def backtest_volume_breakout(symbols: list, start_date: str, end_date: str,
                             strategy_name: str = "VOLUME_BREAKOUT") -> dict:
    """策略5: 缩量突破策略 — 缩量整理后放量突破"""
    engine = BacktestEngine()
    print(f"\n📊 回测 [{strategy_name}] | {start_date} ~ {end_date} | {len(symbols)}只股票池")

    all_data = {}
    for sym in symbols:
        df = get_stock_daily(sym, days=365)
        if df is not None and not df.empty:
            all_data[sym] = df
            time.sleep(0.3)
    print(f"  加载了{len(all_data)}只股票数据")
    if not all_data:
        return {"error": "无数据"}

    sample = list(all_data.values())[0]
    trade_dates = [d for d in sample['日期'].tolist() if start_date <= d <= end_date]
    print(f"  交易日: {len(trade_dates)}天")

    for i, date in enumerate(trade_dates):
        prices = {}
        for sym, df in all_data.items():
            row = df[df['日期'] == date]
            if not row.empty:
                prices[sym] = float(row.iloc[0]['收盘'])
        engine.update_prices(prices)

        if i % 3 == 0 and i >= 20:
            # 卖出: 量价背离或止损
            for sym in list(engine.positions.keys()):
                pos = engine.positions[sym]
                pnl_pct = (pos['current_price'] - pos['cost']) / pos['cost']
                if pnl_pct <= -0.07:
                    engine.sell(sym, pos['current_price'], pos['shares'], date, f"止损{pnl_pct*100:.1f}%")
                    continue
                if sym in all_data:
                    mask = all_data[sym]['日期'] <= date
                    hist = all_data[sym][mask].tail(10)
                    if len(hist) >= 5:
                        close = hist['收盘'].astype(float)
                        vol = hist['成交量'].astype(float)
                        # 量价背离: 价格涨但量缩
                        if close.iloc[-1] > close.iloc[-3] and vol.iloc[-1] < vol.iloc[-3] * 0.7:
                            engine.sell(sym, pos['current_price'], pos['shares'], date, "量价背离卖出")

            # 买入
            for sym, df in all_data.items():
                if sym in engine.positions or len(engine.positions) >= MAX_POSITIONS:
                    break
                mask = df['日期'] <= date
                hist = df[mask].tail(20)
                if len(hist) < 10:
                    continue
                close = hist['收盘'].astype(float)
                vol = hist['成交量'].astype(float)
                vol_ma5 = vol.rolling(5).mean()
                if vol_ma5.iloc[-1] is None or vol_ma5.iloc[-1] == 0:
                    continue
                # 计算近几天的量比
                recent_ratios = []
                for j in range(-4, -1):
                    if len(vol) >= abs(j) and vol_ma5.iloc[j] > 0:
                        recent_ratios.append(vol.iloc[j] / vol_ma5.iloc[j])
                today_ratio = vol.iloc[-1] / vol_ma5.iloc[-1] if vol_ma5.iloc[-1] > 0 else 1
                # 缩量3天 + 今天放量 + 创5日新高
                if len(recent_ratios) >= 3 and all(r < 0.7 for r in recent_ratios) and today_ratio > 2:
                    high_5d = close.tail(5).max()
                    if close.iloc[-1] >= high_5d:
                        buy_price = prices.get(sym, 0)
                        if buy_price > 0:
                            buy_amount = engine.cash * 0.10
                            shares = int(buy_amount / buy_price / 100) * 100
                            if shares >= 100:
                                engine.buy(sym, sym, buy_price, shares, date, "缩量后放量突破")

        engine.record_daily(date)

    for sym in list(engine.positions.keys()):
        pos = engine.positions[sym]
        engine.sell(sym, pos['current_price'], pos['shares'], trade_dates[-1], "回测结束清仓")

    stats = engine.get_stats()
    stats['strategy'] = strategy_name
    stats['start_date'] = start_date
    stats['end_date'] = end_date
    stats['stock_pool'] = len(symbols)
    save_backtest_result(stats, engine.trades)
    return stats


def backtest_multi_factor(symbols: list, start_date: str, end_date: str,
                          strategy_name: str = "MULTI_FACTOR") -> dict:
    """策略6: 综合多因子策略 — 融合所有信号打分"""
    engine = BacktestEngine()
    print(f"\n📊 回测 [{strategy_name}] | {start_date} ~ {end_date} | {len(symbols)}只股票池")

    all_data = {}
    for sym in symbols:
        df = get_stock_daily(sym, days=365)
        if df is not None and not df.empty:
            all_data[sym] = df
            time.sleep(0.3)
    print(f"  加载了{len(all_data)}只股票数据")
    if not all_data:
        return {"error": "无数据"}

    sample = list(all_data.values())[0]
    trade_dates = [d for d in sample['日期'].tolist() if start_date <= d <= end_date]
    print(f"  交易日: {len(trade_dates)}天")

    for i, date in enumerate(trade_dates):
        prices = {}
        for sym, df in all_data.items():
            row = df[df['日期'] == date]
            if not row.empty:
                prices[sym] = float(row.iloc[0]['收盘'])
        engine.update_prices(prices)

        if i % 5 == 0 and i >= 20:
            # 卖出
            for sym in list(engine.positions.keys()):
                pos = engine.positions[sym]
                pnl_pct = (pos['current_price'] - pos['cost']) / pos['cost']
                if pnl_pct <= -0.08:
                    engine.sell(sym, pos['current_price'], pos['shares'], date, f"止损{pnl_pct*100:.1f}%")
                    continue
                if pnl_pct >= 0.25:
                    engine.sell(sym, pos['current_price'], pos['shares'], date, f"止盈{pnl_pct*100:.1f}%")
                    continue
                # 多因子卖出: 得分过低
                if sym in all_data:
                    mask = all_data[sym]['日期'] <= date
                    hist = all_data[sym][mask].tail(60)
                    if len(hist) >= 20:
                        tech = calculate_technical_indicators(hist)
                        if tech:
                            sell_score = 0
                            if tech.get('ma5', 0) < tech.get('ma20', 0):
                                sell_score += 2
                            if tech.get('macd', 0) < 0:
                                sell_score += 1
                            if tech.get('rsi14', 50) > 75:
                                sell_score += 1
                            if '空头' in tech.get('trend', ''):
                                sell_score += 2
                            if sell_score >= 4:
                                engine.sell(sym, pos['current_price'], pos['shares'], date, f"多因子卖出得分{sell_score}")

            # 买入: 综合打分
            scored_stocks = []
            for sym, df in all_data.items():
                if sym in engine.positions:
                    continue
                mask = df['日期'] <= date
                hist = df[mask].tail(60)
                if len(hist) < 20:
                    continue
                tech = calculate_technical_indicators(hist)
                if not tech:
                    continue

                score = 0
                # F1: MACD金叉 (+3) / bullish (+1)
                sig = tech.get('macd_signal', '')
                if sig == 'golden_cross':
                    score += 3
                elif sig == 'bullish':
                    score += 1
                # F2: RSI健康 (+2)
                rsi = tech.get('rsi14', 50)
                if 30 < rsi < 60:
                    score += 2
                elif rsi < 30:
                    score += 1  # 超卖也有机会
                # F3: 趋势 (+2)
                if '多头' in tech.get('trend', ''):
                    score += 2
                # F4: 放量 (+1)
                if tech.get('volume_ratio', 1) > 1.3:
                    score += 1
                # F5: 布林位置 (+1)
                price = tech.get('current_price', 0)
                boll_mid = tech.get('boll_middle', 0)
                boll_lower = tech.get('boll_lower', 0)
                if price > boll_mid > 0:
                    score += 1
                elif 0 < price <= boll_lower * 1.02:
                    score += 1  # 超跌
                # F6: MA金叉近似 (+1)
                ma5 = tech.get('ma5', 0)
                ma20 = tech.get('ma20', 0)
                if ma5 > ma20 > 0 and (ma5 - ma20) / ma20 < 0.02:
                    score += 1
                # F7: KDJ金叉 (+1)
                if tech.get('kdj_signal', '') == 'golden_cross':
                    score += 1

                if score >= 7:
                    scored_stocks.append((sym, score))

            # 按得分排序买入
            scored_stocks.sort(key=lambda x: -x[1])
            for sym, score in scored_stocks:
                if len(engine.positions) >= MAX_POSITIONS:
                    break
                buy_price = prices.get(sym, 0)
                if buy_price > 0:
                    buy_amount = engine.cash * 0.10
                    shares = int(buy_amount / buy_price / 100) * 100
                    if shares >= 100:
                        engine.buy(sym, sym, buy_price, shares, date, f"多因子得分{score}")

        engine.record_daily(date)

    for sym in list(engine.positions.keys()):
        pos = engine.positions[sym]
        engine.sell(sym, pos['current_price'], pos['shares'], trade_dates[-1], "回测结束清仓")

    stats = engine.get_stats()
    stats['strategy'] = strategy_name
    stats['start_date'] = start_date
    stats['end_date'] = end_date
    stats['stock_pool'] = len(symbols)
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


# =================== v5.61 新增回测函数集合 ===================

def run_sector_backtest(sector: str, strategy: str, params: dict) -> dict:
    """v5.61: 赛道参数化回测
    
    Args:
        sector: 赛道名称 ('科技成长', '新能源', '白马消费')
        strategy: 策略名 ('下MACD_RSI')
        params: 参数字典 {'macd_weight': 2.5, 'rsi_weight': 2.0}
    
    Returns: 回测结果 dict
    """
    sector_pools = {
        '科技成长': ['603601', '002371', '300750', '688012', '002415', '300124', '688008', '300033'],
        '新能源': ['601016', '600438', '002594', '300274', '601012', '600089', '002129', '300014'],
        '白马消费': ['600519', '000858', '600887', '603288', '000596', '605499', '600809', '000568'],
    }
    
    if sector not in sector_pools:
        return {'error': f'未正确的赛道: {sector}'}
    
    symbols = sector_pools[sector]
    print(f"\n  🏭 v5.61赛道回测: {sector} | {strategy} | 参数2: {params}")
    
    # 根据策略选择回测函数
    strategy_funcs = {
        'MACD_RSI': backtest_technical_strategy,
        'MA_CROSS': backtest_ma_cross,
        'TREND_FOLLOW': backtest_trend_follow,
        'MULTI_FACTOR': backtest_multi_factor,
    }
    
    if strategy not in strategy_funcs:
        return {'error': f'未正确的策略: {strategy}'}
    
    try:
        stats, trades = strategy_funcs[strategy](symbols, '2024-01-01', '2025-04-23')
        stats['sector'] = sector
        stats['strategy'] = strategy
        stats['params'] = params
        print(f"  ✅ {sector} {strategy} 回测完成: 收益{stats.get('total_return', 0):.2%}")
        return stats
    except Exception as e:
        print(f"  ⚠️ 回测失败: {e}")
        return {'error': str(e)}


def run_combined_strategy_backtest() -> dict:
    """v5.61: 组合回测 - 测MACD权重2.5x的效果
    
    在超激进模式下，将MACD权重从2.2x提升到2.5x
    Returns: 权重对比表
    """
    print(f"\n  💡 v5.61组合回测: MACD权重 2.2x vs 2.5x")
    
    # 不同权重下的回测参数
    backtest_configs = [
        {'name': 'MACD 2.2x (现有)', 'macd_weight': 2.2, 'sharpe_multiplier': 2.0},
        {'name': 'MACD 2.5x (v5.61优化)', 'macd_weight': 2.5, 'sharpe_multiplier': 2.5},
    ]
    
    test_pool = ['600519', '300750', '603601', '601016', '000858', '002371', '300124', '002415']
    
    results = []
    for config in backtest_configs:
        try:
            stats, trades = backtest_technical_strategy(test_pool, '2024-01-01', '2025-04-23')
            stats['config'] = config['name']
            stats['macd_weight'] = config['macd_weight']
            stats['sharpe_multiplier'] = config['sharpe_multiplier']
            results.append(stats)
            print(f"    ✅ {config['name']}: 收益 {stats.get('total_return', 0):.2%} | Sharpe {stats.get('sharpe_ratio', 0):.2f}")
        except Exception as e:
            print(f"    ⚠️ {config['name']} 失败: {e}")
    
    return {
        'comparison': results,
        'recommendation': '建议采用2.5x权重以获得更好的策略旍性' if len(results) >= 2 else ''
    }


def generate_backtest_comparison() -> str:
    """v5.61: 生成回测对比报告
    
    输出权重2.2x vs 2.5x vs 原基准的对比表
    """
    print(f"\n  📉 v5.61回测对比报告")
    
    # 执行组合回测
    comparison = run_combined_strategy_backtest()
    
    # 执行赛道子回测
    sector_results = []
    for sector in ['科技成长', '新能源', '白马消费']:
        result = run_sector_backtest(sector, 'MACD_RSI', {'macd_weight': 2.5})
        sector_results.append(result)
    
    # 整理成报告
    report = f"""
# v5.61 回测对比报告

## 权重对比 (MACD权重调整)
"""
    for result in comparison.get('comparison', []):
        report += f"""
### {result.get('config', '')}
- 收益: {result.get('total_return', 0):.2%}
- Sharpe: {result.get('sharpe_ratio', 0):.2f}
- 胜率: {result.get('win_rate', 0):.2%}
- 最大回撤: {result.get('max_drawdown', 0):.2%}
"""
    
    report += f"""

## 赛道效果 (MACD 2.5x)
"""
    for result in sector_results:
        if 'error' not in result:
            report += f"""
### {result.get('sector', '')}
- 收益: {result.get('total_return', 0):.2%}
- Sharpe: {result.get('sharpe_ratio', 0):.2f}
- 交易数: {result.get('total_trades', 0)}
"""
    
    report += f"""

## 优化建议
{comparison.get('recommendation', '')}
"""
    
    return report


# =================== 原有函数继续 ===================

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

    strategies = {
        "MACD+RSI": backtest_technical_strategy,
        "MA_CROSS": backtest_ma_cross,
        "BOLL_REVERT": backtest_boll_revert,
        "TREND_FOLLOW": backtest_trend_follow,
        "VOLUME_BREAKOUT": backtest_volume_breakout,
        "MULTI_FACTOR": backtest_multi_factor,
    }

    all_results = {}
    for strat_name, strat_func in strategies.items():
        for pool_name, symbols in stock_pools.items():
            key = f"{strat_name} ({pool_name})"
            print(f"\n{'='*60}")
            print(f"🏊 策略: {strat_name} | 股票池: {pool_name} ({len(symbols)}只)")
            print(f"{'='*60}")

            stats = strat_func(
                symbols=symbols,
                start_date="2025-06-01",
                end_date="2026-03-25",
                strategy_name=key
            )

            if 'error' not in stats:
                all_results[key] = stats
                print(f"\n  📈 总收益: {stats['total_return']:+.2f}%")
                print(f"  📉 最大回撤: {stats['max_drawdown']:.2f}%")
                print(f"  🎯 胜率: {stats['win_rate']:.1f}%")
                print(f"  📊 盈亏比: {stats['profit_factor']:.2f}")
                print(f"  ⚡ 夏普比率: {stats['sharpe_ratio']:.2f}")
                print(f"  🔄 总交易: {stats['total_trades']}笔 (赢{stats['win_trades']} 亏{stats['loss_trades']})")

    # 总结
    print(f"\n\n{'='*70}")
    print("📊 全部策略回测总结")
    print(f"{'='*70}")
    print(f"{'策略':<35} {'收益':>8} {'回撤':>8} {'胜率':>8} {'夏普':>8} {'盈亏比':>8}")
    print("-" * 70)
    for name, s in all_results.items():
        print(f"{name:<35} {s['total_return']:>+7.2f}% {s['max_drawdown']:>7.2f}% {s['win_rate']:>7.1f}% {s['sharpe_ratio']:>7.2f} {s['profit_factor']:>7.2f}")

    return all_results


if __name__ == "__main__":
    results = run_full_backtest()
