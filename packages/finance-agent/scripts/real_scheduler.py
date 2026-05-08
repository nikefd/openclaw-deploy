"""实盘调度器 — 盘前预案 + 盘中决策

8:30 盘前预案: 基于昨日数据，生成方向性建议
9:45 盘中决策: 基于开盘15分钟实时数据，生成最终操作指令
"""

import json
import sys
from datetime import datetime
from real_trader import (
    get_positions, get_account, get_today_actions,
    add_action, generate_daily_actions
)
from data_collector import (
    get_realtime_quotes, get_market_indices, get_market_sentiment,
    get_stock_daily, calculate_technical_indicators
)


def pre_market_analysis():
    """盘前预案 (8:30) — 基于昨日收盘数据
    
    输出: 方向性建议，让斌哥心里有数
    """
    today = datetime.now().strftime('%Y-%m-%d')
    print(f"☀️ 盘前预案 {today}")
    print("=" * 50)
    
    # 1. 大盘状态
    indices = get_market_indices()
    print("\n📊 大盘指数(昨收):")
    for name, data in indices.items():
        chg = data.get('change_pct', 0)
        icon = '🟢' if chg > 0 else '🔴' if chg < 0 else '⚪'
        print(f"  {icon} {name}: {data.get('price', 0)} ({chg:+.2f}%)")
    
    # 2. 市场情绪
    sentiment = get_market_sentiment()
    score = sentiment.get('sentiment_score', 50)
    label = sentiment.get('sentiment_label', '中性')
    print(f"\n🌡️ 市场情绪: {score}/100 ({label})")
    print(f"  涨停 {sentiment.get('limit_up_count', 0)} | "
          f"跌停 {sentiment.get('limit_down_count', 0)} | "
          f"炸板 {sentiment.get('bomb_count', 0)}")
    
    # 3. 持仓检查
    positions = get_positions()
    account = get_account()
    print(f"\n💼 持仓 {len(positions)} 只 | 资金 ¥{account.get('total_capital', 0):,.0f}")
    
    warnings = []
    for pos in positions:
        symbol = pos['symbol']
        name = pos['name']
        cost = pos['avg_cost']
        
        # 用昨日收盘价估算
        df = get_stock_daily(symbol, 5)
        if df is not None and not df.empty:
            last_close = float(df['收盘'].iloc[-1])
            pnl_pct = (last_close - cost) / cost * 100
            
            if pnl_pct <= -8:
                warnings.append(f"🚨 {name}({symbol}) 亏损{pnl_pct:.1f}% — 已破止损线，今天重点关注！")
            elif pnl_pct <= -5:
                warnings.append(f"⚠️ {name}({symbol}) 亏损{pnl_pct:.1f}% — 接近止损线")
            elif pnl_pct >= 20:
                warnings.append(f"🎯 {name}({symbol}) 盈利{pnl_pct:.1f}% — 考虑止盈")
    
    if warnings:
        print("\n⚡ 重点关注:")
        for w in warnings:
            print(f"  {w}")
    else:
        print("\n✅ 持仓暂无预警")
    
    # 4. 今日大方向
    print("\n📋 今日方向:")
    if score >= 65:
        print("  → 市场情绪偏乐观，可适度进攻")
    elif score >= 45:
        print("  → 市场中性，按计划操作即可")
    elif score >= 30:
        print("  → 市场偏谨慎，优先防守（止损>买入）")
    else:
        print("  → 市场恐慌，不宜新开仓，严守止损")
    
    print("\n⏰ 10:00后出盘中决策，届时再看最终操作指令")
    return {'type': 'pre_market', 'date': today, 'sentiment': score, 'warnings': warnings}


def market_open_decision():
    """盘中决策 (9:45-10:00) — 基于开盘实时数据
    
    输出: 具体操作指令（买/卖/持有），这是最终下单依据
    """
    today = datetime.now().strftime('%Y-%m-%d')
    print(f"🔔 盘中决策 {today}")
    print("=" * 50)
    
    # 1. 开盘实时数据
    indices = get_market_indices()
    print("\n📊 大盘实时:")
    market_direction = 'neutral'
    for name, data in indices.items():
        chg = data.get('change_pct', 0)
        icon = '🟢' if chg > 0 else '🔴' if chg < 0 else '⚪'
        print(f"  {icon} {name}: {data.get('price', 0)} ({chg:+.2f}%)")
        if '上证' in name:
            if chg > 0.5: market_direction = 'up'
            elif chg < -0.5: market_direction = 'down'
    
    # 2. 实时持仓盈亏
    positions = get_positions()
    if positions:
        codes = [p['symbol'] for p in positions]
        quotes = get_realtime_quotes(codes)
        
        print("\n💼 持仓实时盈亏:")
        for pos in positions:
            q = quotes.get(pos['symbol'], {})
            current = q.get('price', 0)
            if current <= 0:
                continue
            pnl_pct = (current - pos['avg_cost']) / pos['avg_cost'] * 100
            day_chg = q.get('change_pct', 0)
            icon = '🟢' if pnl_pct > 0 else '🔴'
            print(f"  {icon} {pos['name']} 成本{pos['avg_cost']:.2f} → 现价{current:.2f} "
                  f"盈亏{pnl_pct:+.1f}% 今日{day_chg:+.1f}%")
    
    # 3. 运行完整选股分析，生成操作建议
    print("\n🤖 运行完整分析...")
    result = generate_daily_actions()
    
    actions = result['actions']
    buys = [a for a in actions if a['action_type'] == 'buy']
    sells = [a for a in actions if a['action_type'] == 'sell']
    holds = [a for a in actions if a['action_type'] == 'hold']
    
    # 4. 输出最终指令
    print(f"\n{'='*50}")
    print(f"📋 最终操作指令 ({today})")
    print(f"{'='*50}")
    
    if sells:
        print(f"\n🔴 卖出 ({len(sells)}只):")
        for a in sells:
            print(f"  ▸ {a['name']}({a['symbol']}) @{a.get('price', '?')}")
            print(f"    原因: {a['reason']}")
            # 大盘低开时，止损更紧迫
            if market_direction == 'down' and '止损' in a.get('reason', ''):
                print(f"    ⚡ 大盘低开，建议尽快执行止损！")
    
    if buys:
        print(f"\n🟢 买入 ({len(buys)}只):")
        for a in buys:
            print(f"  ▸ {a['name']}({a['symbol']}) @{a.get('price', '?')}")
            print(f"    目标: {a.get('target_price', '?')} | 止损: {a.get('stop_loss', '?')} | 仓位: {a.get('position_pct', '?')}%")
            print(f"    原因: {a['reason']}")
            # 大盘大跌时，降低买入建议的紧迫性
            if market_direction == 'down':
                print(f"    ⚠️ 大盘走弱，建议等下午确认方向后再买")
    
    if holds:
        print(f"\n⚪ 持有 ({len(holds)}只):")
        for a in holds:
            print(f"  ▸ {a['name']}({a['symbol']}) — {a['reason']}")
    
    if not sells and not buys:
        print("\n✅ 今日无操作建议，继续持有观察")
    
    print(f"\n💡 提醒: 卖出上午做(10:00-10:30)，买入下午做(13:30-14:30)")
    
    return result


if __name__ == "__main__":
    import sys
    mode = sys.argv[1] if len(sys.argv) > 1 else 'decision'
    
    if mode == 'pre':
        pre_market_analysis()
    elif mode == 'decision':
        market_open_decision()
    else:
        print(f"用法: python3 real_scheduler.py [pre|decision]")
        print(f"  pre      — 盘前预案(8:30)")
        print(f"  decision — 盘中决策(9:45)")
