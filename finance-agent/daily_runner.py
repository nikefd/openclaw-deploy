"""每日主流程 — 盘后复盘 + AI选股 + 模拟交易 + 生成报告"""

import json
import sys
from datetime import datetime, date
from ai_analyst import pick_stocks, analyze_market, analyze_stock, call_llm
from trading_engine import (
    get_account, get_positions, buy_stock, sell_stock,
    save_daily_snapshot, init_db
)
from data_collector import get_stock_daily
from config import *


def update_positions_price():
    """更新所有持仓的最新价格"""
    import sqlite3
    positions = get_positions()
    if not positions:
        return

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    for pos in positions:
        symbol = pos['symbol']
        df = get_stock_daily(symbol, days=5)
        if not df.empty:
            latest_price = float(df.iloc[-1]['收盘'])
            c.execute("UPDATE positions SET current_price=?, updated_at=? WHERE symbol=?",
                      (latest_price, datetime.now().isoformat(), symbol))
    conn.commit()
    conn.close()


def check_stop_loss_take_profit():
    """检查止损止盈"""
    positions = get_positions()
    actions = []
    for pos in positions:
        if pos['current_price'] and pos['avg_cost']:
            pnl_pct = (pos['current_price'] - pos['avg_cost']) / pos['avg_cost']
            if pnl_pct <= STOP_LOSS:
                actions.append({
                    "action": "SELL",
                    "symbol": pos['symbol'],
                    "name": pos['name'],
                    "reason": f"止损: 亏损{pnl_pct*100:.1f}%",
                    "shares": pos['shares'],
                    "price": pos['current_price']
                })
            elif pnl_pct >= TAKE_PROFIT:
                actions.append({
                    "action": "SELL",
                    "symbol": pos['symbol'],
                    "name": pos['name'],
                    "reason": f"止盈: 盈利{pnl_pct*100:.1f}%",
                    "shares": pos['shares'],
                    "price": pos['current_price']
                })
    return actions


def execute_trades(picks: dict):
    """根据AI选股结果执行模拟交易"""
    results = []

    # 先检查止损止盈
    sl_tp = check_stop_loss_take_profit()
    for action in sl_tp:
        r = sell_stock(action['symbol'], action['price'], action['shares'], action['reason'])
        results.append({"type": "止损止盈", **action, "result": r})

    # 执行买入
    picks_list = picks.get("picks", [])
    if not picks_list:
        return results

    account = get_account()
    available_cash = account['cash']

    for pick in picks_list:
        if pick.get('confidence', 0) < 6:
            continue  # 信心不足的跳过

        symbol = pick.get('symbol', '')
        if not symbol:
            continue

        price = pick.get('buy_price', 0)
        if not price:
            # 用最新价
            df = get_stock_daily(symbol, days=5)
            if df.empty:
                continue
            price = float(df.iloc[-1]['收盘'])

        position_pct = min(pick.get('position_pct', 0.1), MAX_SINGLE_POSITION)
        buy_amount = available_cash * position_pct
        shares = int(buy_amount / price / 100) * 100  # 取整到100股

        if shares < 100:
            continue

        r = buy_stock(symbol, pick.get('name', ''), price, shares, pick.get('reason', ''))
        results.append({"type": "AI选股买入", "symbol": symbol, "name": pick.get('name', ''),
                        "shares": shares, "price": price, "result": r})

        if r.get('success'):
            available_cash -= r.get('cost', 0)

    return results


def generate_daily_report(market_analysis: dict, trade_results: list, picks: dict) -> str:
    """生成每日报告"""
    account = get_account()
    positions = get_positions()

    # 计算持仓盈亏
    pos_details = []
    total_pos_value = 0
    for p in positions:
        pnl = (p['current_price'] - p['avg_cost']) * p['shares']
        pnl_pct = (p['current_price'] - p['avg_cost']) / p['avg_cost'] * 100
        value = p['current_price'] * p['shares']
        total_pos_value += value
        pos_details.append(f"  {p['name']}({p['symbol']}): {p['shares']}股 | "
                          f"成本{p['avg_cost']:.2f} 现价{p['current_price']:.2f} | "
                          f"盈亏{pnl:+,.2f}({pnl_pct:+.1f}%)")

    total_value = account['cash'] + total_pos_value
    total_return = (total_value - INITIAL_CAPITAL) / INITIAL_CAPITAL * 100

    report = f"""
📊 **金融Agent日报** — {datetime.now().strftime('%Y年%m月%d日')}
{'='*50}

💰 **账户概览**
- 总资产: ¥{total_value:,.2f}
- 可用现金: ¥{account['cash']:,.2f}
- 持仓市值: ¥{total_pos_value:,.2f}
- 总收益率: {total_return:+.2f}%

📈 **当前持仓** ({len(positions)}只)
{chr(10).join(pos_details) if pos_details else '  空仓'}

🤖 **今日AI研判**
{market_analysis.get('analysis', 'N/A')[:1000]}

🎯 **今日交易**
"""
    if trade_results:
        for t in trade_results:
            status = "✅" if t.get('result', {}).get('success') else "❌"
            report += f"  {status} {t['type']}: {t.get('name','')}({t.get('symbol','')}) {t.get('shares',0)}股 @ {t.get('price',0):.2f}\n"
    else:
        report += "  无交易\n"

    # AI推荐
    picks_list = picks.get("picks", [])
    if picks_list:
        report += "\n🔍 **AI推荐关注**\n"
        for p in picks_list:
            report += f"  ⭐ {p.get('name','')}({p.get('symbol','')}) 信心:{p.get('confidence','?')}/10 — {p.get('reason','')[:60]}\n"

    market_view = picks.get("market_view", "")
    if market_view:
        report += f"\n💡 **一句话观点**: {market_view}\n"

    report += f"\n⚠️ *以上为AI模拟盘分析，不构成投资建议*"
    return report


def run_daily():
    """每日主流程"""
    print(f"[{datetime.now()}] 🚀 开始每日分析...")

    # 1. 更新持仓价格
    print("📊 更新持仓价格...")
    update_positions_price()

    # 2. AI分析选股
    print("🧠 AI分析选股中...")
    result = pick_stocks()
    market = result.get("market", {})
    picks = result.get("picks", {})

    # 3. 执行交易
    print("💹 执行模拟交易...")
    trade_results = execute_trades(picks)

    # 4. 保存快照
    sentiment = market.get("sentiment", {})
    save_daily_snapshot(
        sentiment_score=sentiment.get("sentiment_score", 0),
        notes=json.dumps(picks, ensure_ascii=False)[:500]
    )

    # 5. 生成报告
    print("📝 生成日报...")
    report = generate_daily_report(market, trade_results, picks)

    # 保存报告
    report_file = f"{REPORT_DIR}/{date.today().isoformat()}.md"
    with open(report_file, 'w') as f:
        f.write(report)

    print(report)
    print(f"\n✅ 日报已保存到 {report_file}")
    return report


if __name__ == "__main__":
    init_db()
    run_daily()
