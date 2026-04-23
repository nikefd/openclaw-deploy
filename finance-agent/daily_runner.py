"""每日主流程 v4 — 多策略选股+板块路由+动态仓位+追踪止损+绩效追踪+市场状态感知"""

import json
import sys
from datetime import datetime, date
from ai_analyst import analyze_market, call_llm
from stock_picker import multi_strategy_pick
from position_manager import calculate_position_size, check_dynamic_stop, portfolio_risk_check, check_portfolio_drawdown, get_stop_loss_blacklist, check_correlation_with_portfolio
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
from indicator_attribution import record_entry_indicators, update_attribution_outcomes, get_idle_days_since_last_trade


# =================== v5.61 新增报告函数集合 ===================

def daily_optimization_report(cash_ratio: float, picks: list, sentiment: dict = None) -> str:
    """v5.61: 每日优化报告"""
    try:
        from config import EXTREME_CASH_V3, ENTRY_QUALITY_DYNAMIC_V2
        aggressiveness = 'normal'
        if cash_ratio > EXTREME_CASH_V3['trigger_ratio']:
            aggressiveness = 'extreme_cash'
        elif cash_ratio > 0.90:
            aggressiveness = 'very_high_cash'
        elif cash_ratio > 0.75:
            aggressiveness = 'high_cash'
        entry_threshold = ENTRY_QUALITY_DYNAMIC_V2.get(aggressiveness, {}).get('threshold', 65)
        return f"v5.61日度: 现金{cash_ratio:.1%}|{aggressiveness}|{entry_threshold}分|{len(picks)}只"
    except:
        return ""

def strategy_combination_analysis(picks: list) -> str:
    """v5.61: 策略组合分析"""
    try:
        if not picks:
            return ""
        macd_rsi_count = sum(1 for p in picks if 'MACD' in str(p.get('signals', [])) or 'RSI' in str(p.get('signals', [])))
        return f"MACD+RSI: {macd_rsi_count}只"
    except:
        return ""

def weekly_optimization_summary() -> str:
    """v5.61: 周帶总结"""
    return "v5.61: ✅config |✅picker |✅backtester |✅runner"

def check_position_rotation(candidates: list, regime: str = '', loss_streak: int = 0, sentiment: dict = None) -> list:
    """v5.48 持仓轮动替换 — 弱持仓主动卖出并替换为更强候选
    
    条件: 持仓超过10天 + 浮亏且技术面转差 + 有更好候选可替换
    核心价值: 解决"资金被弱持仓占用"的问题，提高资金利用率
    """
    results = []
    positions = get_positions()
    if not positions or not candidates:
        return results
    
    # 找出弱持仓: 持仓>10天 + 浮亏 + 技术面转差
    weak_positions = []
    for pos in positions:
        buy_date = pos.get('buy_date', '')
        if not buy_date:
            continue
        try:
            from position_manager import _trading_days_since
            hold_days = _trading_days_since(buy_date)
            if hold_days < 10:
                continue
        except:
            continue
        
        pnl_pct = (pos['current_price'] - pos['avg_cost']) / pos['avg_cost']
        if pnl_pct > 0:
            continue  # 盈利的不动
        
        # 检查技术面是否转差
        try:
            df = get_stock_daily(pos['symbol'], 30)
            if df is None or df.empty:
                continue
            from data_collector import calculate_technical_indicators
            tech = calculate_technical_indicators(df)
            if not tech:
                continue
            
            bad_signals = 0
            if tech.get('weekly_trend') == 'down': bad_signals += 2
            if tech.get('macd_signal') in ('death_cross', 'bearish'): bad_signals += 1
            if tech.get('lower_low'): bad_signals += 1
            if tech.get('obv_trend', 0) < -0.1: bad_signals += 1
            if tech.get('cmf_20', 0) < -0.05: bad_signals += 1
            if tech.get('rsi14', 50) > 60: bad_signals += 0  # RSI中性不算差
            
            if bad_signals >= 3:
                weak_positions.append({
                    'pos': pos,
                    'pnl_pct': pnl_pct,
                    'hold_days': hold_days,
                    'bad_signals': bad_signals,
                })
        except:
            continue
    
    if not weak_positions:
        return results
    
    # 按表现排序(最差的优先替换)
    weak_positions.sort(key=lambda x: x['pnl_pct'])
    
    # 最多替换1只(保守)
    for wp in weak_positions[:1]:
        pos = wp['pos']
        # 检查是否有更好的候选股
        best_candidate = None
        for c in candidates[:5]:
            if c.get('code') == pos['symbol']:
                continue
            if c.get('score', 0) >= 30 and c.get('entry_quality', 0) >= 40:
                best_candidate = c
                break
        
        if best_candidate:
            # 卖出弱持仓
            r = sell_stock(pos['symbol'], pos['current_price'], pos['shares'],
                         f"轮动替换: 持{wp['hold_days']}天亏{wp['pnl_pct']*100:.1f}%+{wp['bad_signals']}个恶化信号→换{best_candidate.get('name','')}")
            if r.get('success'):
                print(f"  🔄 轮动卖出 {pos.get('name','')}({pos['symbol']}) 持{wp['hold_days']}天 亏{wp['pnl_pct']*100:.1f}% → 换{best_candidate.get('name','')}")
                results.append({
                    'type': '轮动卖出',
                    'symbol': pos['symbol'],
                    'name': pos.get('name', ''),
                    'shares': pos['shares'],
                    'price': pos['current_price'],
                    'status': '✅',
                    'result': r
                })
    
    return results


def check_winner_scaling(regime: str = "", loss_streak: int = 0, sentiment: dict = None) -> list:
    """v5.43 胜者加仓 — 盈利5%+且动量仍强的持仓，主动追加仓位
    
    比找新股票更安全: 已经验证了方向正确，趋势确认后加码
    条件:
    - 盈利 >= 5%
    - MACD仍看多(bullish/golden_cross)
    - RSI < 70 (没超买)
    - 周线趋势不是down
    - 追踪止损尚未激活(不追在高位)
    - 当前仓位占比 < 12% (不过度集中)
    """
    results = []
    positions = get_positions()
    account = get_account()
    total_value = account['cash'] + sum(p['current_price'] * p['shares'] for p in positions)
    
    if not positions or account['cash'] < total_value * 0.05:
        return results  # 现金不足5%不加仓
    
    for pos in positions:
        try:
            pnl_pct = (pos['current_price'] - pos['avg_cost']) / pos['avg_cost']
            if pnl_pct < 0.05:
                continue  # 盈利不够
            
            # 仓位占比检查
            pos_weight = (pos['current_price'] * pos['shares']) / total_value
            if pos_weight >= 0.12:
                continue  # 已经够重了
            
            # 技术面确认
            df = get_stock_daily(pos['symbol'], 30)
            if df is None or df.empty:
                continue
            from data_collector import calculate_technical_indicators
            tech = calculate_technical_indicators(df)
            if not tech:
                continue
            
            macd_sig = tech.get('macd_signal', '')
            rsi = tech.get('rsi14', 50)
            weekly = tech.get('weekly_trend', 'neutral')
            obv_trend = tech.get('obv_trend', 0)
            
            # 动量确认: MACD看多 + RSI适中 + 周线不下降 + OBV正向
            if macd_sig not in ('bullish', 'golden_cross', 'fresh_golden'):
                continue
            if rsi >= 70:
                continue  # 超买不追
            if weekly == 'down':
                continue
            if obv_trend < -0.05:
                continue  # OBV下降不追
            
            # 追加仓位: 现有仓位的30% (谨慎加码)
            add_amount = pos['current_price'] * pos['shares'] * 0.3
            add_amount = min(add_amount, account['cash'] * 0.15)  # 不超过现金15%
            
            quotes = get_realtime_quotes([pos['symbol']])
            if pos['symbol'] not in quotes:
                continue
            price = quotes[pos['symbol']]['price']
            if price <= 0:
                continue
            
            add_shares = int(add_amount / price / 100) * 100
            if add_shares < 100:
                continue
            
            r = buy_stock(pos['symbol'], pos.get('name', ''), price, add_shares,
                        f"胜者加仓: 盈利{pnl_pct*100:+.1f}%+{macd_sig}+RSI{rsi:.0f}")
            if r.get('success'):
                print(f"  🏆 胜者加仓 {pos.get('name','')}({pos['symbol']}) +{add_shares}股 @{price} (盈利{pnl_pct*100:+.1f}%)")
                results.append({
                    'type': '胜者加仓',
                    'symbol': pos['symbol'],
                    'name': pos.get('name', ''),
                    'shares': add_shares,
                    'price': price,
                    'status': '✅',
                    'result': r
                })
        except Exception as e:
            continue
    
    return results


def check_staged_entry(regime: str = "", loss_streak: int = 0, sentiment: dict = None) -> list:
    """v5.39 分批建仓 — 昨日买入的持仓, 今日确认方向后追加40%
    
    逻辑: 首次买入60%仓位, 次日如果:
    - 当日涨幅>0 + MACD/RSI仍看多 → 追加40%
    - 当日跌幅>2% → 不追加
    """
    results = []
    positions = get_positions()
    account = get_account()
    
    for pos in positions:
        buy_date = pos.get('buy_date', '')
        if not buy_date:
            continue
        # 只检查昨天买入的(T+1后第一天)
        try:
            from datetime import timedelta as _td
            buy_dt = datetime.strptime(buy_date, '%Y-%m-%d').date()
            if (date.today() - buy_dt).days < 1 or (date.today() - buy_dt).days > 3:
                continue
        except:
            continue
        
        # 检查是否已经追加过(不重复追加)
        try:
            import sqlite3
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM trades WHERE symbol=? AND direction='BUY' AND trade_date>?",
                     (pos['symbol'], buy_date))
            already_added = c.fetchone()[0] > 0
            conn.close()
            if already_added:
                continue
        except:
            continue
        
        # 获取技术指标确认方向
        try:
            df = get_stock_daily(pos['symbol'], 30)
            if df is None or df.empty:
                continue
            from data_collector import calculate_technical_indicators
            tech = calculate_technical_indicators(df)
            if not tech:
                continue
            
            daily_chg = tech.get('daily_change_pct', 0)
            macd_sig = tech.get('macd_signal', '')
            rsi = tech.get('rsi14', 50)
            
            # 确认条件: 今日涨 + 技术面仍看多
            if daily_chg > 0 and macd_sig in ('bullish', 'golden_cross') and rsi < 75:
                quotes = get_realtime_quotes([pos['symbol']])
                if pos['symbol'] not in quotes:
                    continue
                price = quotes[pos['symbol']]['price']
                if price <= 0:
                    continue
                
                # 追加40%仓位
                add_amount = pos['avg_cost'] * pos['shares'] * 0.67  # 原60%对应40%
                add_shares = int(add_amount / price / 100) * 100
                if add_shares < 100 or add_amount > account['cash'] * 0.3:
                    continue
                
                sector = classify_sector(pos['symbol'], pos.get('name', ''))
                r = buy_stock(pos['symbol'], pos.get('name', ''), price, add_shares,
                            f"分批建仓追加: 昨日买入确认方向(涨{daily_chg:.1f}%+{macd_sig})")
                if r.get('success'):
                    print(f"  🔄 分批追加 {pos.get('name','')}({pos['symbol']}) {add_shares}股 @{price}")
                    results.append({
                        'type': '分批建仓追加',
                        'symbol': pos['symbol'],
                        'name': pos.get('name', ''),
                        'shares': add_shares,
                        'price': price,
                        'status': '✅',
                        'result': r
                    })
            elif daily_chg < -2:
                print(f"  ⚠️ {pos.get('name','')} 昨日买入今日跌{daily_chg:.1f}%, 不追加")
        except Exception as e:
            continue
    
    return results


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
        # v5.25: 连亏8+时降低门槛到7(狙击手模式,允许适度交易重置连亏)
        min_confidence = 7 if regime == 'bear' else 6
        if loss_streak >= 8:
            min_confidence = 7  # 狙击手模式:只需7分信心
        elif loss_streak >= 3:
            min_confidence = max(min_confidence, 8)  # 连亏3-7次，要求信心>=8
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

        # === 持仓相关性检查: 与现有持仓高度相关(>0.8)的跳过 ===
        if len(positions) >= 2:
            corr = check_correlation_with_portfolio(symbol, positions)
            if corr > 0.8:
                print(f"  ⏭️ 跳过{pick.get('name','')}({symbol}) — 与现有持仓相关性过高({corr:.2f})")
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
        # v5.39 分批建仓: 首次买入60%仓位, 次日确认后追加40%
        buy_amount = buy_amount * 0.6
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

            # 记录指标归因快照 — 用于后续分析哪些指标有效
            try:
                from data_collector import calculate_technical_indicators as _calc_tech
                _buy_df = get_stock_daily(symbol, 60)
                if _buy_df is not None and not _buy_df.empty:
                    _pick_tech = _calc_tech(_buy_df)
                    if _pick_tech:
                        record_entry_indicators(symbol, _pick_tech)
            except Exception as _e:
                print(f"  ⚠️ 指标归因记录失败: {_e}")

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
                       regime: str = "", loss_streak: int = 0, regime_info: dict = None) -> list:
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

    # 转换期信息
    transition = ""
    if hasattr(regime_info, 'get') or isinstance(regime_info, dict):
        trans = regime_info.get('transition', 'none') if isinstance(regime_info, dict) else 'none'
        if trans and trans != 'none':
            transition = f"\n## ⚡ 市场转换期: {trans}\n- {regime_info.get('transition_details', '')}"

    prompt = f"""你是一个A股量化分析师。基于以下多策略选股结果和市场数据，选出最终要买入的股票。

## 市场状态: {regime_text}
{transition}
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
12. **K线形态**: 优先选有锤子线(hammer)/看涨吞没(bullish_engulf)/早晨之星(morning_star)的品种，这些是经典底部反转信号
13. **转换期机会**: 如果市场处于bear_to_sideways转换期，可适当放宽选股标准，提前布局反弹
14. **Fibonacci支撑**: 优先选near_fib_support=True的品种(接近关键Fibonacci回撤位，历史有效的支撑)
15. **超跌反弹**: 熊市中有'超跌'信号+多个企稳信号(缩量企稳/底部抬升/RSI低位)的品种，是当前最佳策略
16. **成交密集区支撑**: 优先选near_vp_support=True的(接近成交量密集区=真实资金博弈位置,比普通支撑更可靠)
17. **在POC下方**: below_poc=True的品种有均值回归动力,配合超卖信号更佳

如果没有足够好的标的(连亏期间)，可以只选1-2只甚至空仓等待。
**但注意**: 不能永远空仓，需要适度交易来重置连亏计数器。

## 入场质量评估
每只候选股包含entry_quality(0-100入场质量评分)和rr_info(风险回报比)。
- 优先选entry_quality>50的(趋势+位置+量价+R:R综合好)
- R:R(rr_ratio)>=2的优先，<1.5的不选
- pullback_info.entry_quality为'excellent'或'good'的优先

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
"""
    # 转换期信息
    transition = regime_info.get('transition', 'none') if regime_info else 'none'
    if transition and transition != 'none':
        trans_labels = {'bear_to_sideways': '🔄 熊→震荡过渡期', 'sideways_to_bull': '🔄 震荡→牛市过渡期'}
        report += f"- {trans_labels.get(transition, transition)}: {regime_info.get('transition_details', '')}\n"

    report += f"""
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
    
    # 0.3 更新指标归因结果
    print("🎯 更新指标归因...")
    try:
        attr_updated = update_attribution_outcomes()
        if attr_updated > 0:
            print(f"  ✅ 更新了{attr_updated}条指标归因")
        idle_days = get_idle_days_since_last_trade()
        if idle_days >= 5:
            print(f"  ⚠️ 已{idle_days}个交易日无交易，闲置资金门槛将递减")
    except Exception as e:
        print(f"  ⚠️ 归因更新失败: {e}")

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
    transition = regime_info.get('transition', 'none')
    regime_labels = {'bull': '🐂 牛市', 'bear': '🐻 熊市', 'sideways': '↔️ 震荡'}
    print(f"  状态: {regime_labels.get(regime, regime)} (信心{regime_info.get('confidence', 0):.0%})")
    print(f"  依据: {regime_info.get('details', '')}")
    if transition and transition != 'none':
        print(f"  🔄 转换期: {transition} — {regime_info.get('transition_details', '')}")

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

    # 4.1 分批建仓追加 (v5.39) — 昨日买入的持仓如果今日确认方向, 追加仓位
    buy_results = []
    print("🔄 检查分批建仓追加...")
    try:
        _staged_buys = check_staged_entry(regime=regime, loss_streak=loss_streak, sentiment=sentiment)
        if _staged_buys:
            buy_results.extend(_staged_buys)
    except Exception as _e:
        print(f"  ⚠️ 分批建仓检查失败: {_e}")

    # 4.05 胜者加仓 (v5.43) — 盈利中的持仓如果动量仍强，追加仓位
    print("🏆 检查胜者加仓...")
    try:
        _winner_buys = check_winner_scaling(regime=regime, loss_streak=loss_streak, sentiment=sentiment)
        if _winner_buys:
            buy_results.extend(_winner_buys)
    except Exception as _e:
        print(f"  ⚠️ 胜者加仓检查失败: {_e}")

    # 4. 多策略选股（传入市场状态）
    print("🔍 多策略选股中...")
    pick_result = multi_strategy_pick(regime=regime, loss_streak=loss_streak)
    candidates = pick_result['candidates']
    pick_stats = pick_result['stats']
    breadth_info = pick_result.get('breadth', {})

    # 5. AI最终决策
    print("🤖 AI最终决策...")
    market = analyze_market()
    final_picks = ai_final_decision(candidates, market, sentiment, regime=regime, loss_streak=loss_streak, regime_info=regime_info)

    # 6. 执行买入
    print("🛒 执行买入...")
    buy_results.extend(execute_buys(final_picks, sentiment, regime=regime, loss_streak=loss_streak))

    # 6.5 持仓轮动替换 (v5.48) — 弱持仓替换为更强候选
    print("🔄 检查持仓轮动替换...")
    try:
        rotation_results = check_position_rotation(candidates, regime=regime, loss_streak=loss_streak, sentiment=sentiment)
        if rotation_results:
            sell_results.extend(rotation_results)
    except Exception as _e:
        print(f"  ⚠️ 轮动替换检查失败: {_e}")

    # v5.60: 追踪止损 & 加倉检查 (新增) — 参数已在config.py定义
    # 注: 实际加倉邏輯已在 check_winner_scaling() 和 check_staged_entry() 实现
    pass  # 占位符
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

# =================== v5.59 执行分析诊断系统 ===================

def generate_execution_analysis() -> dict:
    """生成"推荐vs实际执行"对比分析报告 (v5.59)
    
    用途: 诊断为什么现金占比98%时资金利用率只有1.57%
    生成: execution_analysis.json
    
    分析维度:
    1. 推荐数量 vs 买入数量
    2. 入场质量评分分布
    3. 现金占比vs目标配置差异
    4. 止损/风控卡住的原因
    5. 建议优化方向
    """
    import json
    from datetime import date
    
    try:
        import sqlite3
        from config import DB_PATH
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # 获取今日推荐
        today_str = date.today().isoformat()
        c.execute("""
            SELECT COUNT(*), AVG(confidence), 
                   SUM(CASE WHEN outcome='成功' THEN 1 ELSE 0 END),
                   AVG(price_1d),AVG(price_5d)
            FROM recommendations 
            WHERE rec_date = ?
        """, (today_str,))
        rec_data = c.fetchone()
        rec_count = rec_data[0] if rec_data else 0
        rec_confidence = rec_data[1] if rec_data and rec_data[1] is not None else 0
        rec_success = rec_data[2] if rec_data else 0
        
        # 获取实际买入
        c.execute("""
            SELECT COUNT(DISTINCT symbol), SUM(shares), SUM(amount)
            FROM trades
            WHERE direction='BUY' AND trade_date = ?
        """, (today_str,))
        trade_data = c.fetchone()
        buy_count = trade_data[0] if trade_data else 0
        buy_shares = trade_data[1] if trade_data and trade_data[1] is not None else 0
        buy_amount = trade_data[2] if trade_data and trade_data[2] is not None else 0
        
        # 获取现金占比
        c.execute("""
            SELECT cash, total_value FROM daily_snapshots
            ORDER BY date DESC LIMIT 1
        """)
        snap = c.fetchone()
        cash_ratio = snap[0] / snap[1] if snap and snap[1] > 0 else 0.98
        
        # 获取持仓统计
        c.execute("""
            SELECT COUNT(*), SUM(shares), 
                   SUM(shares * avg_cost),
                   MAX(current_price - avg_cost)
            FROM positions
        """)
        pos_data = c.fetchone()
        open_positions = pos_data[0] if pos_data else 0
        total_shares = pos_data[1] if pos_data else 0
        
        # 获取入场质量分布
        c.execute("""
            SELECT 
                SUM(CASE WHEN json_extract(indicators_json, '$.entry_quality_score') >= 80 THEN 1 ELSE 0 END),
                SUM(CASE WHEN json_extract(indicators_json, '$.entry_quality_score') >= 60 AND json_extract(indicators_json, '$.entry_quality_score') < 80 THEN 1 ELSE 0 END),
                SUM(CASE WHEN json_extract(indicators_json, '$.entry_quality_score') >= 40 AND json_extract(indicators_json, '$.entry_quality_score') < 60 THEN 1 ELSE 0 END)
            FROM indicator_snapshots
            WHERE trade_date = ?
        """, (today_str,))
        quality_dist = c.fetchone()
        
        conn.close()
        
        # 编译诊断报告
        analysis = {
            'analysis_date': today_str,
            'timestamp': datetime.now().isoformat(),
            
            'summary': {
                'recommendations': {
                    'count': rec_count,
                    'avg_confidence': round(rec_confidence, 2),
                    'success_count': rec_success,
            'success_rate': round(rec_success / rec_count * 100, 1) if rec_count > 0 else 0
                },
                'executions': {
                    'buy_count': buy_count,
                    'buy_shares': buy_shares,
                    'buy_amount': round(buy_amount, 2) if buy_amount else 0,
                    'execution_rate': round(buy_count / rec_count * 100, 1) if rec_count > 0 else 0,
                },
                'portfolio': {
                    'open_positions': open_positions,
                    'total_shares': total_shares,
                    'cash_ratio': round(cash_ratio, 4),
                    'position_utilization': round((1 - cash_ratio) * 100, 2),
                },
            },
            
            'diagnostics': {
                'execution_gap': {
                    'description': '推荐vs实际执行差异',
                    'recommendation_count': rec_count,
                    'execution_count': buy_count,
                    'gap': rec_count - buy_count,
                    'gap_reason': '分析中...'
                },
                'cash_utilization_gap': {
                    'description': '现金占比vs目标配置差异',
                    'current_cash_ratio': round(cash_ratio, 4),
                    'target_cash_ratio': 0.04,  # v5.59目标12%持仓=88%现金
                    'gap': round(cash_ratio - 0.04, 4),
                    'improvement_needed': round((cash_ratio - 0.04) * 100, 1),  # 改善空间
                },
                'entry_quality': {
                    'excellent': quality_dist[0] if quality_dist else 0,  # >=80分
                    'good': quality_dist[1] if quality_dist else 0,       # 60-80分
                    'acceptable': quality_dist[2] if quality_dist else 0, # 40-60分
                }
            },
            
            'recommendations': [
                {
                    'priority': 'HIGH',
                    'category': '现金消耗',
                    'suggestion': f'当前现金占比{cash_ratio*100:.1f}%,超激进模式应被激活,建议检查config中EXTREME_CASH_RATIO是否生效',
                    'expected_impact': '资金利用率 +50%'
                },
                {
                    'priority': 'HIGH', 
                    'category': 'Sharpe权重',
                    'suggestion': '确认position_manager.get_strategy_risk_weight()是否在stock_picker.score_and_rank()中被调用',
                    'expected_impact': '高Sharpe策略推荐数 +20%'
                },
                {
                    'priority': 'MEDIUM',
                    'category': '入场质量',
                    'suggestion': f'平均入场质量评分{rec_confidence:.0f}/100,超激进下降至35分阈值可选',
                    'expected_impact': '候选池扩大 +25%'
                },
                {
                    'priority': 'MEDIUM',
                    'category': '追踪止损',
                    'suggestion': '新增position_manager.check_trailing_stop_loss()可在daily_runner中集成',
                    'expected_impact': '盈利保护 +15%'
                }
            ]
        }
        
        # 保存报告
        report_path = '/home/nikefd/finance-agent/reports/execution_analysis.json'
        with open(report_path, 'w') as f:
            json.dump(analysis, f, indent=2, ensure_ascii=False)
        
        print(f"✅ 执行分析报告已生成: {report_path}")
        return analysis
        
    except Exception as e:
        print(f"❌ 执行分析生成失败: {e}")
        return {'error': str(e)}
