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
    
    # --- 1. 检查现有持仓 ---
    if positions:
        codes = [p['symbol'] for p in positions]
        quotes = get_realtime_quotes(codes)
        
        for pos in positions:
            symbol = pos['symbol']
            name = pos['name']
            avg_cost = pos['avg_cost']
            shares = pos['shares']
            
            current_price = quotes.get(symbol, {}).get('price', 0)
            if current_price <= 0:
                continue
            
            pnl_pct = (current_price - avg_cost) / avg_cost * 100
            
            # 技术面
            df = get_stock_daily(symbol, 30)
            tech = calculate_technical_indicators(df) if df is not None and not df.empty else {}
            
            # 止损判断
            if pnl_pct <= -8:
                actions.append({
                    'action_type': 'sell', 'symbol': symbol, 'name': name,
                    'price': current_price,
                    'reason': f'⚠️ 止损! 亏损{pnl_pct:.1f}%，超过-8%止损线',
                    'signals': ['止损触发'],
                    'confidence': 9,
                })
            # 止盈判断
            elif pnl_pct >= 20:
                actions.append({
                    'action_type': 'sell', 'symbol': symbol, 'name': name,
                    'price': current_price,
                    'reason': f'🎯 止盈! 盈利{pnl_pct:.1f}%，建议至少卖出一半锁定利润',
                    'signals': ['止盈触发'],
                    'confidence': 8,
                })
            # 技术面恶化
            elif tech.get('macd_signal') == 'death_cross' and pnl_pct < 0:
                actions.append({
                    'action_type': 'sell', 'symbol': symbol, 'name': name,
                    'price': current_price,
                    'reason': f'📉 MACD死叉+亏损{pnl_pct:.1f}%，趋势转弱建议减仓',
                    'signals': ['MACD死叉', f'亏损{pnl_pct:.1f}%'],
                    'confidence': 7,
                })
            else:
                # 持有
                trend = tech.get('trend', '')
                rsi = tech.get('rsi14', 50)
                hold_reason = f"盈亏{pnl_pct:+.1f}% | {trend} | RSI:{rsi:.0f}"
                actions.append({
                    'action_type': 'hold', 'symbol': symbol, 'name': name,
                    'price': current_price,
                    'reason': hold_reason,
                    'signals': [trend, f'RSI:{rsi:.0f}'],
                    'confidence': 5,
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
