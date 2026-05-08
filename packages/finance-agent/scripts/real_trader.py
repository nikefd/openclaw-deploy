"""实盘操作模块 — 管理真实持仓 + 生成每日操作建议

流程: 
  1. 斌哥录入/更新真实持仓
  2. 每天早盘前生成操作建议（买/卖/持有）
  3. 推送到 /finance 页面
  4. 斌哥手动执行后确认
  5. 收盘后自动跟踪结果
"""

import sqlite3
import json
from datetime import datetime, timedelta

DB_PATH = "/home/nikefd/finance-agent/data/trading.db"


def _init_tables():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 实盘持仓
    c.execute('''CREATE TABLE IF NOT EXISTS real_positions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT NOT NULL,
        name TEXT,
        shares INTEGER NOT NULL,
        avg_cost REAL NOT NULL,
        buy_date TEXT,
        notes TEXT,
        status TEXT DEFAULT 'holding',   -- holding / sold
        updated_at TEXT
    )''')
    
    # 每日操作建议
    c.execute('''CREATE TABLE IF NOT EXISTS daily_actions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        action_type TEXT NOT NULL,        -- buy / sell / hold
        symbol TEXT NOT NULL,
        name TEXT,
        price REAL,                       -- 建议价格
        target_price REAL,                -- 目标价
        stop_loss REAL,                   -- 止损价
        position_pct REAL,               -- 建议仓位%
        reason TEXT,
        signals TEXT,                     -- JSON: 触发信号
        confidence INTEGER,              -- 1-10
        status TEXT DEFAULT 'pending',    -- pending / executed / skipped / partial
        executed_price REAL,              -- 实际执行价格
        executed_at TEXT,
        notes TEXT,
        created_at TEXT
    )''')
    
    # 实盘账户概览
    c.execute('''CREATE TABLE IF NOT EXISTS real_account (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        total_capital REAL,              -- 总资金
        available_cash REAL,             -- 可用现金
        updated_at TEXT
    )''')
    
    conn.commit()
    conn.close()

_init_tables()


# ============================================================
# 持仓管理
# ============================================================
def get_positions() -> list:
    """获取当前持仓"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM real_positions WHERE status='holding' ORDER BY buy_date DESC")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def add_position(symbol: str, name: str, shares: int, avg_cost: float,
                 buy_date: str = None, notes: str = "") -> dict:
    """添加持仓"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 检查是否已有该股持仓
    c.execute("SELECT id, shares, avg_cost FROM real_positions WHERE symbol=? AND status='holding'", (symbol,))
    existing = c.fetchone()
    
    if existing:
        # 合并持仓（加权平均成本）
        old_shares, old_cost = existing[1], existing[2]
        new_shares = old_shares + shares
        new_cost = (old_shares * old_cost + shares * avg_cost) / new_shares
        c.execute("UPDATE real_positions SET shares=?, avg_cost=?, updated_at=?, notes=? WHERE id=?",
                  (new_shares, round(new_cost, 3), datetime.now().isoformat(), notes, existing[0]))
        result = {'action': 'merged', 'symbol': symbol, 'shares': new_shares, 'avg_cost': round(new_cost, 3)}
    else:
        c.execute('''INSERT INTO real_positions (symbol, name, shares, avg_cost, buy_date, notes, status, updated_at)
                     VALUES (?, ?, ?, ?, ?, ?, 'holding', ?)''',
                  (symbol, name, shares, avg_cost, buy_date or datetime.now().strftime('%Y-%m-%d'),
                   notes, datetime.now().isoformat()))
        result = {'action': 'added', 'symbol': symbol, 'shares': shares, 'avg_cost': avg_cost}
    
    conn.commit()
    conn.close()
    return result


def sell_position(symbol: str, shares: int = None, price: float = None, notes: str = "") -> dict:
    """卖出持仓（部分或全部）"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, shares, avg_cost, name FROM real_positions WHERE symbol=? AND status='holding'", (symbol,))
    pos = c.fetchone()
    if not pos:
        conn.close()
        return {'error': f'{symbol}无持仓'}
    
    pos_id, cur_shares, avg_cost, name = pos
    sell_shares = shares or cur_shares
    
    if sell_shares >= cur_shares:
        # 全部卖出
        c.execute("UPDATE real_positions SET status='sold', updated_at=?, notes=? WHERE id=?",
                  (datetime.now().isoformat(), f"卖出@{price or '?'} {notes}", pos_id))
        result = {'action': 'sold_all', 'symbol': symbol, 'shares': cur_shares}
    else:
        # 部分卖出
        c.execute("UPDATE real_positions SET shares=?, updated_at=?, notes=? WHERE id=?",
                  (cur_shares - sell_shares, datetime.now().isoformat(), f"部分卖出{sell_shares}@{price or '?'} {notes}", pos_id))
        result = {'action': 'sold_partial', 'symbol': symbol, 'sold': sell_shares, 'remaining': cur_shares - sell_shares}
    
    conn.commit()
    conn.close()
    return result


def update_account(total_capital: float, available_cash: float):
    """更新账户资金"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM real_account")
    c.execute("INSERT INTO real_account (total_capital, available_cash, updated_at) VALUES (?, ?, ?)",
              (total_capital, available_cash, datetime.now().isoformat()))
    conn.commit()
    conn.close()


def get_account() -> dict:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM real_account ORDER BY id DESC LIMIT 1")
    row = c.fetchone()
    conn.close()
    return dict(row) if row else {'total_capital': 0, 'available_cash': 0}


# ============================================================
# 操作建议管理
# ============================================================
def get_today_actions(date: str = None) -> list:
    """获取今日操作建议"""
    date = date or datetime.now().strftime('%Y-%m-%d')
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM daily_actions WHERE date=? ORDER BY action_type, confidence DESC", (date,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def add_action(date: str, action_type: str, symbol: str, name: str,
               price: float = None, target_price: float = None, stop_loss: float = None,
               position_pct: float = None, reason: str = "", signals: list = None,
               confidence: int = 7) -> dict:
    """添加操作建议"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT INTO daily_actions 
                 (date, action_type, symbol, name, price, target_price, stop_loss,
                  position_pct, reason, signals, confidence, status, created_at)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)''',
              (date, action_type, symbol, name, price, target_price, stop_loss,
               position_pct, reason, json.dumps(signals or [], ensure_ascii=False),
               confidence, datetime.now().isoformat()))
    action_id = c.lastrowid
    conn.commit()
    conn.close()
    return {'id': action_id, 'action_type': action_type, 'symbol': symbol}


def update_action_status(action_id: int, status: str, executed_price: float = None, notes: str = ""):
    """更新操作状态"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''UPDATE daily_actions SET status=?, executed_price=?, executed_at=?, notes=? WHERE id=?''',
              (status, executed_price, datetime.now().isoformat() if status == 'executed' else None,
               notes, action_id))
    conn.commit()
    conn.close()


def get_actions_history(days: int = 7) -> list:
    """获取近N天操作历史"""
    since = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM daily_actions WHERE date>=? ORDER BY date DESC, action_type, confidence DESC", (since,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


# ============================================================
# 生成每日操作建议（核心逻辑）
# ============================================================
def generate_daily_actions() -> dict:
    """基于持仓 + 市场分析 + 选股结果，生成今日操作建议
    
    逻辑:
    1. 检查现有持仓 → 是否需要止损/止盈/减仓
    2. 检查选股推荐 → 是否有值得买入的
    3. 结合资金面/新闻面 → 调整仓位建议
    """
    from data_collector import get_realtime_quotes, get_stock_daily, calculate_technical_indicators, get_market_sentiment
    
    today = datetime.now().strftime('%Y-%m-%d')
    positions = get_positions()
    account = get_account()
    actions = []
    
    print(f"📋 生成{today}操作建议...")
    print(f"  持仓: {len(positions)}只, 资金: {account.get('total_capital', 0):.0f}")
    
    # --- 1. 检查现有持仓(多维度综合评估) ---
    if positions:
        codes = [p['symbol'] for p in positions]
        quotes = get_realtime_quotes(codes)
        
        # 获取新闻信号和资金面(复用，避免重复调用)
        news_signals = None
        money_overview = None
        try:
            from news_collector import collect_and_analyze, get_news_score_for_stock
            print("  📰 采集新闻信号(用于持仓评估)...")
            news_result = collect_and_analyze()
            news_signals = news_result.get('signals', {})
        except Exception as e:
            print(f"  ⚠️ 新闻采集跳过: {e}")
        
        try:
            from market_data_ext import get_money_flow_overview, get_stock_money_signals
            print("  💰 采集资金面(用于持仓评估)...")
            money_overview = get_money_flow_overview()
        except Exception as e:
            print(f"  ⚠️ 资金面采集跳过: {e}")
        
        sentiment = get_market_sentiment()
        sentiment_score = sentiment.get('sentiment_score', 50)
        
        for pos in positions:
            symbol = pos['symbol']
            name = pos['name']
            avg_cost = pos['avg_cost']
            shares = pos['shares']
            
            current_price = quotes.get(symbol, {}).get('price', 0)
            if current_price <= 0:
                continue
            
            pnl_pct = (current_price - avg_cost) / avg_cost * 100
            
            # === 收集多维度信号 ===
            sell_score = 0   # 正数=越该卖
            hold_score = 0   # 正数=越该拿
            signals_list = []
            reasons = []
            
            # --- A. 盈亏维度 ---
            if pnl_pct <= -12:
                sell_score += 40
                signals_list.append('深度亏损')
                reasons.append(f'⚠️ 亏损{pnl_pct:.1f}%，深度套牢')
            elif pnl_pct <= -8:
                sell_score += 25
                signals_list.append('破止损线')
                reasons.append(f'⚠️ 亏损{pnl_pct:.1f}%，已破-8%止损线')
            elif pnl_pct <= -5:
                sell_score += 10
                signals_list.append('接近止损')
            elif pnl_pct >= 30:
                sell_score += 30
                signals_list.append('大幅盈利')
                reasons.append(f'🎯 盈利{pnl_pct:.1f}%，建议止盈全部')
            elif pnl_pct >= 20:
                sell_score += 15
                signals_list.append('止盈区间')
                reasons.append(f'🎯 盈利{pnl_pct:.1f}%，建议卖出一半锁利')
            elif pnl_pct > 5:
                hold_score += 10  # 小幅盈利，没必要卖
            
            # --- B. 技术面维度 ---
            df = get_stock_daily(symbol, 60)
            tech = calculate_technical_indicators(df) if df is not None and not df.empty else {}
            
            # MACD
            macd_sig = tech.get('macd_signal', '')
            if macd_sig == 'death_cross':
                sell_score += 20
                signals_list.append('MACD死叉')
            elif macd_sig == 'golden_cross':
                hold_score += 20
                signals_list.append('MACD金叉')
            elif macd_sig == 'bearish':
                sell_score += 5
            elif macd_sig == 'bullish':
                hold_score += 10
            
            # 趋势
            trend = tech.get('trend', '')
            if '空头' in trend or '弱势' in trend:
                sell_score += 15
                signals_list.append('空头排列')
            elif '多头' in trend or '强势' in trend:
                hold_score += 15
                signals_list.append('多头排列')
            
            # RSI
            rsi = tech.get('rsi14', 50)
            if rsi > 80:
                sell_score += 10
                signals_list.append(f'RSI超买({rsi:.0f})')
            elif rsi < 30:
                hold_score += 10  # 超卖反而不该卖
                signals_list.append(f'RSI超卖({rsi:.0f})')
            
            # RSI背离
            if tech.get('rsi_divergence') == 'bearish':
                sell_score += 15
                signals_list.append('RSI顶背离')
            elif tech.get('rsi_divergence') == 'bullish':
                hold_score += 15
                signals_list.append('RSI底背离')
            
            # KDJ
            kdj_sig = tech.get('kdj_signal', '')
            if kdj_sig == 'death_cross':
                sell_score += 8
                signals_list.append('KDJ死叉')
            elif kdj_sig == 'golden_cross':
                hold_score += 8
            elif kdj_sig == 'overbought':
                sell_score += 5
            
            # 动量衰减
            if tech.get('momentum_decay'):
                sell_score += 10
                signals_list.append('动量衰减')
            if tech.get('volume_price_diverge'):
                sell_score += 8
                signals_list.append('量价背离')
            if tech.get('obv_price_diverge'):
                sell_score += 8
                signals_list.append('OBV背离')
            
            # 跳空缺口
            if tech.get('gap_down'):
                sell_score += 12
                signals_list.append('向下跳空')
            if tech.get('gap_up'):
                hold_score += 8
            
            # 均线支撑/破位
            price = current_price
            ma20 = tech.get('ma20', 0)
            ma60 = tech.get('ma60', 0)
            if ma60 and price < ma60 * 0.97:  # 跌破60日均线3%
                sell_score += 12
                signals_list.append('破MA60')
            elif ma20 and price < ma20 * 0.97:
                sell_score += 6
                signals_list.append('破MA20')
            
            # 布林带
            boll_lower = tech.get('boll_lower', 0)
            boll_upper = tech.get('boll_upper', 0)
            if boll_lower and price < boll_lower:
                sell_score += 10
                signals_list.append('破布林下轨')
            elif boll_upper and price > boll_upper:
                sell_score += 5  # 超买区间
            
            # ATR波动
            atr_pct = tech.get('atr_pct', 0)
            if atr_pct > 5:
                sell_score += 5  # 高波动风险加大
            
            # --- C. 新闻/消息面 ---
            if news_signals:
                try:
                    news_score = get_news_score_for_stock(symbol, name, news_signals)
                    if news_score['score_delta'] < -10:
                        sell_score += 15
                        signals_list.append('新闻利空')
                        if news_score['reasons']:
                            reasons.append(news_score['reasons'][0])
                    elif news_score['score_delta'] > 10:
                        hold_score += 10
                        signals_list.append('新闻利好')
                    elif news_score['score_delta'] < 0:
                        sell_score += 5
                    elif news_score['score_delta'] > 0:
                        hold_score += 5
                except:
                    pass
            
            # --- D. 资金面 ---
            if money_overview:
                try:
                    money_sig = get_stock_money_signals(symbol, name, money_overview)
                    if money_sig['score_delta'] < -10:
                        sell_score += 15
                        signals_list.append('资金撤退')
                        if money_sig['reasons']:
                            reasons.append(money_sig['reasons'][0])
                    elif money_sig['score_delta'] > 10:
                        hold_score += 12
                        signals_list.append('资金支撑')
                        if money_sig['reasons']:
                            reasons.append(money_sig['reasons'][0])
                    # 北向减持是强信号
                    if money_sig.get('northbound_hold') == False:
                        for r in money_sig.get('reasons', []):
                            if '减持' in r:
                                sell_score += 10
                                signals_list.append('北向减持')
                                break
                except:
                    pass
            
            # --- E. 市场情绪调节 ---
            if sentiment_score < 30:  # 恐慌市场
                sell_score += 8  # 恐慌时更倾向防守
            elif sentiment_score > 75:
                hold_score += 5  # 乐观时可以多拿
            
            # === 综合判断 ===
            net_score = sell_score - hold_score  # 正数=该卖，负数=该拿
            
            print(f"  📊 {name}({symbol}): 盈亏{pnl_pct:+.1f}% | "
                  f"卖出分{sell_score} vs 持有分{hold_score} | "
                  f"净分{net_score} | 信号:{','.join(signals_list[:5])}")
            
            if net_score >= 35:
                # 强烈建议卖出
                action_type = 'sell'
                confidence = min(9, 6 + net_score // 15)
                if not reasons:
                    reasons.append(f'综合评估: 卖出信号({sell_score}分) >> 持有信号({hold_score}分)')
                reasons.append(f'触发: {", ".join(signals_list[:4])}')
            elif net_score >= 20:
                # 建议减仓
                action_type = 'sell'
                confidence = 6
                if not reasons:
                    reasons.append(f'多项指标转弱，建议减仓一半')
                reasons.append(f'触发: {", ".join(signals_list[:4])}')
            elif net_score <= -15:
                # 明确持有
                action_type = 'hold'
                confidence = 7
                hold_reason = f"盈亏{pnl_pct:+.1f}% | {trend} | RSI:{rsi:.0f}"
                if signals_list:
                    hold_reason += f" | 利好: {', '.join([s for s in signals_list if '金叉' in s or '多头' in s or '利好' in s or '支撑' in s or '底背离' in s][:2]) or '基本面稳定'}"
                reasons = [hold_reason]
            else:
                # 中性持有，密切观察
                action_type = 'hold'
                confidence = 5
                hold_reason = f"盈亏{pnl_pct:+.1f}% | {trend} | RSI:{rsi:.0f} | ⚠️密切观察"
                reasons = [hold_reason]
            
            actions.append({
                'action_type': action_type,
                'symbol': symbol,
                'name': name,
                'price': current_price,
                'reason': ' | '.join(reasons[:3]),
                'signals': signals_list[:6],
                'confidence': confidence,
            })
    
    # --- 2. 检查是否有买入机会 ---
    try:
        from stock_picker import multi_strategy_pick
        from market_regime import detect_market_regime
        
        regime_data = detect_market_regime()
        regime = regime_data.get('regime', '')
        
        result = multi_strategy_pick(regime=regime, use_news=True)
        candidates = result.get('candidates', [])
        
        # 当前持仓代码
        holding_symbols = {p['symbol'] for p in positions}
        
        # 筛选买入候选（排除已持有的）
        for c in candidates[:5]:
            if c['code'] in holding_symbols:
                continue
            if c.get('at_limit'):
                continue
            if c['score'] < 20:  # 分数太低不推
                continue
            
            price = c.get('realtime_price', 0)
            tech = c.get('technical', {})
            
            # 止损价 = 买入价 * (1 - 8%)
            stop_loss = round(price * 0.92, 2) if price else None
            # 目标价 = 买入价 * (1 + 15%)
            target = round(price * 1.15, 2) if price else None
            
            signals = c.get('signals', [])
            news_reasons = c.get('news_reasons', [])
            money_reasons = c.get('money_reasons', [])
            
            all_reasons = signals.copy()
            if news_reasons:
                all_reasons.extend([r.split(':')[-1].strip() for r in news_reasons[:2]])
            if money_reasons:
                all_reasons.extend([r.split(':')[-1].strip() for r in money_reasons[:2]])
            
            reason_parts = [f"综合评分{c['score']}分"]
            if c.get('news_reasons'):
                reason_parts.append(c['news_reasons'][0])
            if c.get('money_reasons'):
                reason_parts.append(c['money_reasons'][0])
            
            actions.append({
                'action_type': 'buy', 'symbol': c['code'], 'name': c.get('name', ''),
                'price': price,
                'target_price': target,
                'stop_loss': stop_loss,
                'position_pct': 10,  # 默认10%仓位
                'reason': ' | '.join(reason_parts),
                'signals': all_reasons[:6],
                'confidence': min(c['score'] // 5, 10),
            })
        
    except Exception as e:
        print(f"  ⚠️ 选股分析失败: {e}")
    
    # --- 3. 保存到数据库 ---
    for a in actions:
        add_action(
            date=today,
            action_type=a['action_type'],
            symbol=a['symbol'],
            name=a.get('name', ''),
            price=a.get('price'),
            target_price=a.get('target_price'),
            stop_loss=a.get('stop_loss'),
            position_pct=a.get('position_pct'),
            reason=a.get('reason', ''),
            signals=a.get('signals', []),
            confidence=a.get('confidence', 5),
        )
    
    # 统计
    buys = [a for a in actions if a['action_type'] == 'buy']
    sells = [a for a in actions if a['action_type'] == 'sell']
    holds = [a for a in actions if a['action_type'] == 'hold']
    
    print(f"  📋 生成完毕: 买入{len(buys)} | 卖出{len(sells)} | 持有{len(holds)}")
    
    return {
        'date': today,
        'actions': actions,
        'summary': {
            'buy_count': len(buys),
            'sell_count': len(sells),
            'hold_count': len(holds),
        }
    }


if __name__ == "__main__":
    print("=== 实盘操作模块测试 ===")
    positions = get_positions()
    print(f"当前持仓: {len(positions)}只")
    for p in positions:
        print(f"  {p['name']}({p['symbol']}) {p['shares']}股 成本{p['avg_cost']}")
    
    actions = get_today_actions()
    print(f"\n今日操作建议: {len(actions)}条")
    for a in actions:
        icon = {'buy': '🟢', 'sell': '🔴', 'hold': '⚪'}.get(a['action_type'], '?')
        print(f"  {icon} {a['action_type'].upper()} {a['name']}({a['symbol']}) @{a['price']} - {a['reason']}")
