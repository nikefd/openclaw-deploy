"""每日主流程 v4 — 多策略选股+板块路由+动态仓位+追踪止损+绩效追踪+市场状态感知"""

import json
import sys
from datetime import datetime, date
from ai_analyst import analyze_market, call_llm
from stock_picker import multi_strategy_pick
from position_manager import calculate_position_size, check_dynamic_stop, portfolio_risk_check, check_portfolio_drawdown, get_stop_loss_blacklist
from trading_engine import (
    get_account, get_positions, buy_stock, sell_stock,
    save_daily_snapshot, init_db
)
from data_collector import get_stock_daily, get_realtime_quotes, get_market_sentiment
from performance_tracker import (
    record_recommendation, update_recommendation_outcomes,
    get_performance_summary, classify_sector, init_tracker_tables
)
from market_regime import detect_market_regime
from config import *


def is_trading_day() -> bool:
    """判断今天是否为交易日（排除周末，节假日暂不处理）"""
    today = datetime.now()
    # 周六=5, 周日=6
    if today.weekday() >= 5:
        return False
    return True


def update_positions_price():
    """更新所有持仓的最新价格 + 追踪最高价(用于追踪止损)"""
    import sqlite3
    positions = get_positions()
    if not positions:
        return

    symbols = [p['symbol'] for p in positions]
    quotes = get_realtime_quotes(symbols)

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # 确保peak_price列存在
    try:
        c.execute("ALTER TABLE positions ADD COLUMN peak_price REAL DEFAULT 0")
    except:
        pass  # 列已存在

    for pos in positions:
        symbol = pos['symbol']
        if symbol in quotes and quotes[symbol]['price'] > 0:
            price = quotes[symbol]['price']
            # 更新peak_price — 取当前价和历史最高中的较大值
            old_peak = pos.get('peak_price', 0) or pos.get('avg_cost', 0)
            new_peak = max(old_peak, price)
            c.execute("UPDATE positions SET current_price=?, peak_price=?, updated_at=? WHERE symbol=?",
                      (price, new_peak, datetime.now().isoformat(), symbol))
    conn.commit()
    conn.close()


def execute_sells(sentiment_score: float, regime: str = "", loss_streak: int = 0) -> list:
    """执行卖出（止损止盈）"""
    results = []
    positions = get_positions()
    actions = check_dynamic_stop(positions, sentiment_score, regime=regime, loss_streak=loss_streak)

    for action in actions:
        r = sell_stock(action['symbol'], action['price'], action['shares'], action['reason'])
        status = "✅" if r.get('success') else f"❌ {r.get('error', '')}"
        results.append({
            "type": action['reason'],
            "symbol": action['symbol'],
            "name": action['name'],
            "shares": action['shares'],
            "price": action['price'],
            "status": status,
            "result": r
        })
        if r.get('success'):
            print(f"  💸 卖出 {action['name']}({action['symbol']}) {action['shares']}股 @{action['price']} — {action['reason']}")

    return results


def execute_buys(picks: list, sentiment: dict, regime: str = "", loss_streak: int = 0) -> list:
    """执行买入（含板块路由+绩效记录+连亏保护+回撤熔断）"""
    results = []
    
    # 回撤熔断检查
    dd_info = check_portfolio_drawdown()
    if dd_info.get('is_circuit_break'):
        print(f"  🚨 回撤熔断! 组合回撤{dd_info['drawdown_pct']:.1f}%超过阈值，暂停所有买入")
        return results
    if dd_info.get('reduce_position'):
        print(f"  ⚠️ 组合回撤{dd_info['drawdown_pct']:.1f}%，仓位自动减半")
    
    account = get_account()
    positions = get_positions()
    available_cash = account['cash']
    current_count = len(positions)
    held_symbols = {p['symbol'] for p in positions}
    
    # 止损黑名单
    blacklist = get_stop_loss_blacklist()
    if blacklist:
        print(f"  🚫 止损黑名单: {len(blacklist)}只股票近期止损，不买回")

    for pick in picks:
        if current_count >= MAX_POSITIONS:
            break

        symbol = pick.get('symbol', '')
        if not symbol or symbol in held_symbols:
            continue
        if symbol in blacklist:
            print(f"  ⏭️ 跳过{pick.get('name','')}({symbol}) — 近期止损过，黑名单期内")
            continue

        confidence = pick.get('confidence', 5)
        # 熊市/连亏时提高信心门槛，减少低质量开仓
        min_confidence = 7 if regime == 'bear' else 6
        if loss_streak >= 3:
            min_confidence = max(min_confidence, 8)  # 连亏3+次，要求信心>=8
        if confidence < min_confidence:
            continue

        # 获取实时价格
        quotes = get_realtime_quotes([symbol])
        if symbol not in quotes or quotes[symbol]['price'] <= 0:
            continue
        price = quotes[symbol]['price']

        # 跳过涨停股（买不进）
        if abs(quotes[symbol].get('change_pct', 0)) >= 9.8:
            print(f"  ⏭️ 跳过{pick.get('name','')}({symbol}) — 涨跌停无法交易")
            continue

        # 板块分类
        sector = classify_sector(symbol, pick.get('name', ''))

        # === 板块相关性检查: 同板块已有3只+，跳过 ===
        same_sector_count = sum(1 for p in positions if classify_sector(p['symbol'], p.get('name', '')) == sector)
        if same_sector_count >= 3:
            print(f"  ⏭️ 跳过{pick.get('name','')}({symbol}) — {sector}已有{same_sector_count}只持仓")
            continue

        # 动态仓位（含板块+市场状态+连亏保护+风险平价）
        # 获取ATR用于风险平价
        stock_atr = 0
        try:
            _df = get_stock_daily(symbol, 30)
            if _df is not None and not _df.empty:
                from data_collector import calculate_technical_indicators as _cti
                _t = _cti(_df)
                stock_atr = _t.get('atr_pct', 0)
        except:
            pass
        
        position_pct = calculate_position_size(
            confidence, 
            sentiment.get('sentiment_score', 50),
            current_count, 
            available_cash,
            sector=sector,
            regime=regime,
            loss_streak=loss_streak,
            atr_pct=stock_atr
        )
        buy_amount = available_cash * position_pct
        shares = int(buy_amount / price / 100) * 100

        if shares < 100:
            continue

        reason = pick.get('reason', '') or '+'.join(pick.get('signals', []))
        r = buy_stock(symbol, pick.get('name', ''), price, shares, reason[:200])

        status = "✅" if r.get('success') else f"❌ {r.get('error', '')}"
        results.append({
            "type": "AI选股买入",
            "symbol": symbol,
            "name": pick.get('name', ''),
            "shares": shares,
            "price": price,
            "confidence": confidence,
            "sector": sector,
            "status": status,
            "result": r
        })

        if r.get('success'):
            available_cash -= r.get('cost', 0)
            current_count += 1
            held_symbols.add(symbol)
            print(f"  🛒 买入 {pick.get('name','')}({symbol}) {shares}股 @{price} 信心:{confidence} 板块:{sector}")

            # 记录推荐 — 用于后续绩效追踪
            record_recommendation(
                symbol=symbol,
                name=pick.get('name', ''),
                price=price,
                confidence=confidence,
                signals=pick.get('signals', [pick.get('reason', '')]),
                strategy='multi_strategy',
                sector=sector
            )

    return results


def ai_final_decision(candidates: list, market_analysis: dict, sentiment: dict,
                       regime: str = "", loss_streak: int = 0) -> list:
    """AI最终决策 — 综合多策略结果让LLM做最后判断（含市场状态+连亏+绩效上下文）"""
    candidates_text = json.dumps(candidates[:10], ensure_ascii=False, default=str)[:3000]

    positions = get_positions()
    positions_text = ""
    if positions:
        positions_text = "\n".join([
            f"  {p['name']}({p['symbol']}): {p['shares']}股 成本{p['avg_cost']:.2f} 现价{p['current_price']:.2f} "
            f"盈亏{(p['current_price']-p['avg_cost'])/p['avg_cost']*100:+.1f}%"
            for p in positions
        ])

    # 获取近期绩效给AI参考
    perf_text = ""
    try:
        perf = get_performance_summary()
        if perf['total_recommendations'] > 0:
            perf_text = f"- 历史推荐{perf['total_recommendations']}次, 命中率{perf['hit_rate']}%, 平均最大收益{perf['avg_max_gain']:+.1f}%, 平均最大亏损{perf['avg_max_loss']:.1f}%"
            if perf.get('by_sector'):
                sector_parts = [f"{s['sector']}命中{s['hit_rate']}%" for s in perf['by_sector']]
                perf_text += f"\n- 板块: {' | '.join(sector_parts)}"
    except:
        pass

    regime_labels = {'bull': '牛市', 'bear': '熊市', 'sideways': '震荡'}
    regime_text = regime_labels.get(regime, '未知')

    prompt = f"""你是一个A股量化分析师。基于以下多策略选股结果和市场数据，选出最终要买入的股票。

## 市场状态: {regime_text}
## 市场情绪: {sentiment.get('sentiment_score', 50)}/100 ({sentiment.get('sentiment_label', '?')})
- 涨停: {sentiment.get('limit_up_count', 0)} 跌停: {sentiment.get('limit_down_count', 0)} 炸板: {sentiment.get('bomb_count', 0)}

## ⚠️ 近期战绩
- 连续止损次数: {loss_streak}次
{perf_text if perf_text else '- 无历史绩效数据'}

## 当前持仓
{positions_text or '空仓'}

## 多策略候选池（已按综合评分排序）
每只股票包含：代码、名称、信号来源、综合评分、技术指标（含周线趋势、Williams%R）
{candidates_text}

## 选股要求
1. **优先选**: 多信号叠加(量价齐升+大笔买入+MACD金叉)的品种
2. **避开**: RSI>80严重超买的、已涨停的、与现有持仓重复的、**周线下降趋势的**
3. **注意**: 不要追已经连续涨停3天以上的（回调风险大）
4. **分散**: 不要全选同一板块
5. **熊市策略**: 如果市场是熊市，优先选超跌反弹(RSI<30, Williams%R从超卖回升)而非趋势追涨
6. **连亏保护**: 连续止损{loss_streak}次，请提高选股标准——只选信心≥8的高确定性机会，宁可不买也不追高
7. **周线确认**: 优先选周线趋势为up或neutral的，避开weekly_downtrend=True的

7. **底部信号**: 优先选有缩量企稳(volume_dryup)+均线收敛突破(ma_converge_breakout)的品种
8. **相对强度**: 避开近10日大幅跑输大盘(rs_10d<-5%)的弱势股
9. **支撑位买入**: 优先选near_support=True且strong_support=True的品种（接近关键支撑位买入风险更低）
10. **避开阻力位**: near_resistance=True的品种上涨空间受限，谨慎选择
11. **Z-Score**: price_z_score < -1.5 的品种统计意义上超卖，适合均值回归策略

如果没有足够好的标的(连亏期间)，可以只选1-2只甚至空仓等待。

## 输出JSON格式
```json
{{
  "picks": [
    {{
      "symbol": "代码",
      "name": "名称",
      "confidence": 8,
      "reason": "选择理由(结合信号和技术面)",
      "signals": ["信号列表"]
    }}
  ],
  "market_view": "一句话总结"
}}
```
只输出JSON。"""

    result = call_llm(prompt, "你是顶级A股量化分析师。严格按JSON格式输出。")
    try:
        if "```json" in result:
            result = result.split("```json")[1].split("```")[0]
        elif "```" in result:
            result = result.split("```")[1].split("```")[0]
        data = json.loads(result.strip())
        return data.get('picks', [])
    except:
        print(f"  ⚠️ AI决策JSON解析失败，使用评分排序前5")
        return [{'symbol': c['code'], 'name': c['name'], 'confidence': min(c['score'] // 5, 10),
                 'reason': '+'.join(c['signals']), 'signals': c['signals']}
                for c in candidates[:5] if not c.get('at_limit')]


def generate_daily_report(market_analysis: dict, sell_results: list, buy_results: list, 
                          picks: list, sentiment: dict, pick_stats: dict,
                          regime_info: dict = None, loss_streak: int = 0,
                          dd_info: dict = None) -> str:
    """生成每日报告"""
    account = get_account()
    positions = get_positions()

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

    regime_info = regime_info or {}
    regime = regime_info.get('regime', 'sideways')
    regime_labels = {'bull': '🐂 牛市', 'bear': '🐻 熊市', 'sideways': '↔️ 震荡'}
    regime_label = regime_labels.get(regime, '未知')
    regime_conf = regime_info.get('confidence', 0)
    regime_details = regime_info.get('details', 'N/A')

    report = f"""
📊 **金融Agent日报** — {datetime.now().strftime('%Y年%m月%d日')}
{'='*50}

💰 **账户概览**
- 总资产: ¥{total_value:,.2f}
- 可用现金: ¥{account['cash']:,.2f}
- 持仓市值: ¥{total_pos_value:,.2f}
- 总收益率: {total_return:+.2f}%

🧠 **市场情绪**: {sentiment.get('sentiment_score', 0)}/100 ({sentiment.get('sentiment_label', '?')})
- 涨停{sentiment.get('limit_up_count', 0)}家 | 跌停{sentiment.get('limit_down_count', 0)}家 | 炸板{sentiment.get('bomb_count', 0)}家

📡 **市场状态**: {regime_label} (信心{regime_conf:.0%})
- {regime_details}

📈 **当前持仓** ({len(positions)}只)
{chr(10).join(pos_details) if pos_details else '  空仓'}

🤖 **今日AI研判**
{market_analysis.get('analysis', 'N/A')[:2000]}

🎯 **今日交易**
"""
    all_trades = sell_results + buy_results
    if all_trades:
        for t in all_trades:
            report += f"  {t['status']} {t['type']}: {t.get('name','')}({t.get('symbol','')}) {t.get('shares',0)}股 @ {t.get('price',0):.2f}\n"
    else:
        report += "  无交易\n"

    if picks:
        report += "\n🔍 **AI推荐关注**\n"
        for p in picks[:5]:
            report += f"  ⭐ {p.get('name','')}({p.get('symbol','')}) 信心:{p.get('confidence','?')}/10 — {p.get('reason','')[:80]}\n"

    report += f"""
📊 **选股统计**
- 动量信号: {pick_stats.get('momentum_count', 0)}只 | 资金信号: {pick_stats.get('money_flow_count', 0)}只
- 强势股: {pick_stats.get('strong_count', 0)}只 | 机构推荐: {pick_stats.get('institution_count', 0)}只
- 最终候选: {pick_stats.get('final_count', 0)}只
"""
    if loss_streak >= 2:
        report += f"⚠️ **连亏保护**: 连续{loss_streak}次止损，仓位已自动收缩\n"

    dd_info = dd_info or {}
    if dd_info.get('drawdown_pct', 0) < -3:
        report += f"📉 **组合回撤**: {dd_info['drawdown_pct']:.1f}% (峰值¥{dd_info.get('peak_value',0):,.0f})"
        if dd_info.get('is_circuit_break'):
            report += " 🚨**熔断中，暂停买入**"
        elif dd_info.get('reduce_position'):
            report += " ⚠️仓位已减半"
        report += "\n"

    # 绩效追踪摘要
    try:
        perf = get_performance_summary()
        if perf['total_recommendations'] > 0:
            report += f"""
📊 **历史推荐绩效** (共{perf['total_recommendations']}次推荐)
- 命中率: {perf['hit_rate']}% (赢{perf['wins']}次 / 亏{perf['losses']}次 / 平{perf['neutrals']}次)
- 平均最大收益: {perf['avg_max_gain']:+.1f}% | 平均最大亏损: {perf['avg_max_loss']:.1f}%
"""
            if perf['by_sector']:
                report += "- 板块: "
                report += " | ".join([f"{s['sector']}命中{s['hit_rate']}%" for s in perf['by_sector']])
                report += "\n"
    except:
        pass

    report += """
⚠️ *以上为AI模拟盘分析，不构成投资建议*"""
    return report


def run_daily():
    """每日主流程"""
    print(f"[{datetime.now()}] 🚀 开始每日分析...")

    # 0. 初始化
    init_tracker_tables()

    # 0.1 交易日检查
    if not is_trading_day():
        msg = f"[{datetime.now()}] 📅 今天不是交易日(周末)，跳过分析。"
        print(msg)
        return msg

    # 0.2 更新历史推荐表现（绩效追踪）
    print("📈 更新历史推荐绩效...")
    try:
        updated = update_recommendation_outcomes()
        if updated > 0:
            print(f"  ✅ 更新了{updated}条历史推荐表现")
    except Exception as e:
        print(f"  ⚠️ 绩效更新失败: {e}")

    # 1. 更新持仓价格（含追踪最高价）
    print("📊 更新持仓价格...")
    update_positions_price()

    # 2. 获取市场情绪
    print("🧠 获取市场情绪...")
    sentiment = get_market_sentiment()
    if sentiment is None:
        sentiment = {'sentiment_score': 50, 'sentiment_label': '中性'}
    print(f"  情绪: {sentiment.get('sentiment_score', 0)}/100 ({sentiment.get('sentiment_label', '?')})")

    # 2.5 检测市场状态
    print("📡 检测市场状态...")
    regime_info = detect_market_regime()
    regime = regime_info.get('regime', 'sideways')
    regime_labels = {'bull': '🐂 牛市', 'bear': '🐻 熊市', 'sideways': '↔️ 震荡'}
    print(f"  状态: {regime_labels.get(regime, regime)} (信心{regime_info.get('confidence', 0):.0%})")
    print(f"  依据: {regime_info.get('details', '')}")

    # 3. 风控检查 & 执行卖出
    print("🛡️ 风控检查...")
    positions = get_positions()
    account = get_account()
    risk = portfolio_risk_check(positions, account['total_value'])
    loss_streak = risk.get('loss_streak', 0)
    if risk['warnings']:
        for w in risk['warnings']:
            print(f"  ⚠️ {w}")

    print("💸 执行止损止盈...")
    sell_results = execute_sells(sentiment.get('sentiment_score', 50), regime=regime, loss_streak=loss_streak)

    # 4. 多策略选股（传入市场状态）
    print("🔍 多策略选股中...")
    pick_result = multi_strategy_pick(regime=regime, loss_streak=loss_streak)
    candidates = pick_result['candidates']
    pick_stats = pick_result['stats']
    breadth_info = pick_result.get('breadth', {})

    # 5. AI最终决策
    print("🤖 AI最终决策...")
    market = analyze_market()
    final_picks = ai_final_decision(candidates, market, sentiment, regime=regime, loss_streak=loss_streak)

    # 6. 执行买入
    print("🛒 执行买入...")
    buy_results = execute_buys(final_picks, sentiment, regime=regime, loss_streak=loss_streak)

    # 7. 保存快照
    save_daily_snapshot(
        sentiment_score=sentiment.get('sentiment_score', 0),
        notes=json.dumps({'picks': [p.get('symbol','') for p in final_picks], 'stats': pick_stats, 'regime': regime}, ensure_ascii=False)[:500]
    )

    # 8. 生成报告
    print("📝 生成日报...")
    dd_info = check_portfolio_drawdown()
    report = generate_daily_report(market, sell_results, buy_results, final_picks, sentiment, pick_stats, regime_info=regime_info, loss_streak=loss_streak, dd_info=dd_info)

    report_file = f"{REPORT_DIR}/{date.today().isoformat()}.md"
    with open(report_file, 'w') as f:
        f.write(report)

    print(report)
    print(f"\n✅ 日报已保存到 {report_file}")
    return report


if __name__ == "__main__":
    init_db()
    run_daily()
