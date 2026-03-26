"""模拟交易引擎 — A股规则(T+1, 涨跌停, 佣金印花税)"""

import sqlite3
import json
from datetime import datetime, date
from config import *


def init_db():
    """初始化数据库"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS account (
        id INTEGER PRIMARY KEY,
        cash REAL,
        total_value REAL,
        created_at TEXT,
        updated_at TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS positions (
        symbol TEXT PRIMARY KEY,
        name TEXT,
        shares INTEGER,
        avg_cost REAL,
        buy_date TEXT,
        current_price REAL,
        updated_at TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT,
        name TEXT,
        direction TEXT,
        price REAL,
        shares INTEGER,
        amount REAL,
        commission REAL,
        tax REAL,
        reason TEXT,
        trade_date TEXT,
        created_at TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS daily_snapshots (
        date TEXT PRIMARY KEY,
        cash REAL,
        positions_value REAL,
        total_value REAL,
        positions_json TEXT,
        sentiment_score REAL,
        notes TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS signals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT,
        name TEXT,
        direction TEXT,
        strength REAL,
        reason TEXT,
        source TEXT,
        created_at TEXT
    )''')

    # 初始化账户
    c.execute("SELECT COUNT(*) FROM account")
    if c.fetchone()[0] == 0:
        now = datetime.now().isoformat()
        c.execute("INSERT INTO account VALUES (1, ?, ?, ?, ?)",
                  (INITIAL_CAPITAL, INITIAL_CAPITAL, now, now))

    conn.commit()
    conn.close()


def get_account():
    """获取账户信息"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT cash, total_value FROM account WHERE id=1")
    row = c.fetchone()
    conn.close()
    return {"cash": row[0], "total_value": row[1]} if row else None


def get_positions():
    """获取所有持仓"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM positions")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def buy_stock(symbol: str, name: str, price: float, shares: int, reason: str = ""):
    """买入股票"""
    if shares <= 0 or shares % 100 != 0:
        return {"error": "买入数量必须是100的整数倍"}

    amount = price * shares
    commission = max(amount * COMMISSION_RATE, MIN_COMMISSION)
    total_cost = amount + commission

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # 检查资金
    c.execute("SELECT cash FROM account WHERE id=1")
    cash = c.fetchone()[0]
    if total_cost > cash:
        conn.close()
        return {"error": f"资金不足: 需要{total_cost:.2f}, 可用{cash:.2f}"}

    # 检查持仓数量限制
    c.execute("SELECT COUNT(*) FROM positions")
    pos_count = c.fetchone()[0]
    c.execute("SELECT symbol FROM positions WHERE symbol=?", (symbol,))
    existing = c.fetchone()
    if not existing and pos_count >= MAX_POSITIONS:
        conn.close()
        return {"error": f"持仓已达上限{MAX_POSITIONS}只"}

    now = datetime.now().isoformat()
    today = date.today().isoformat()

    # 更新/新建持仓
    if existing:
        c.execute("SELECT shares, avg_cost FROM positions WHERE symbol=?", (symbol,))
        old = c.fetchone()
        new_shares = old[0] + shares
        new_cost = (old[0] * old[1] + amount) / new_shares
        c.execute("UPDATE positions SET shares=?, avg_cost=?, current_price=?, updated_at=? WHERE symbol=?",
                  (new_shares, new_cost, price, now, symbol))
    else:
        c.execute("INSERT INTO positions VALUES (?,?,?,?,?,?,?)",
                  (symbol, name, shares, price, today, price, now))

    # 扣款
    c.execute("UPDATE account SET cash=cash-?, updated_at=? WHERE id=1", (total_cost, now))

    # 记录交易
    c.execute("INSERT INTO trades (symbol,name,direction,price,shares,amount,commission,tax,reason,trade_date,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
              (symbol, name, "BUY", price, shares, amount, commission, 0, reason, today, now))

    conn.commit()
    conn.close()
    return {"success": True, "symbol": symbol, "shares": shares, "cost": total_cost}


def sell_stock(symbol: str, price: float, shares: int, reason: str = ""):
    """卖出股票"""
    if shares <= 0 or shares % 100 != 0:
        return {"error": "卖出数量必须是100的整数倍"}

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("SELECT name, shares, avg_cost, buy_date FROM positions WHERE symbol=?", (symbol,))
    pos = c.fetchone()
    if not pos:
        conn.close()
        return {"error": f"未持有{symbol}"}
    name, held, avg_cost, buy_date = pos

    # T+1检查
    if buy_date == date.today().isoformat():
        conn.close()
        return {"error": f"{symbol}今日买入，T+1不可卖出"}

    if shares > held:
        conn.close()
        return {"error": f"持有{held}股，不足卖出{shares}股"}

    amount = price * shares
    commission = max(amount * COMMISSION_RATE, MIN_COMMISSION)
    tax = amount * STAMP_TAX_RATE
    net = amount - commission - tax

    now = datetime.now().isoformat()
    today = date.today().isoformat()

    if shares == held:
        c.execute("DELETE FROM positions WHERE symbol=?", (symbol,))
    else:
        c.execute("UPDATE positions SET shares=shares-?, current_price=?, updated_at=? WHERE symbol=?",
                  (shares, price, now, symbol))

    c.execute("UPDATE account SET cash=cash+?, updated_at=? WHERE id=1", (net, now))

    c.execute("INSERT INTO trades (symbol,name,direction,price,shares,amount,commission,tax,reason,trade_date,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
              (symbol, name, "SELL", price, shares, amount, commission, tax, reason, today, now))

    profit = (price - avg_cost) * shares - commission - tax
    conn.commit()
    conn.close()
    return {"success": True, "symbol": symbol, "shares": shares, "net": net, "profit": profit}


def save_daily_snapshot(sentiment_score: float = 0, notes: str = ""):
    """保存每日快照"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("SELECT cash FROM account WHERE id=1")
    cash = c.fetchone()[0]

    c.execute("SELECT symbol, name, shares, current_price FROM positions")
    positions = c.fetchall()
    pos_value = sum(s[2] * s[3] for s in positions)
    total = cash + pos_value

    c.execute("UPDATE account SET total_value=?, updated_at=? WHERE id=1",
              (total, datetime.now().isoformat()))

    today = date.today().isoformat()
    pos_json = json.dumps([{"symbol": p[0], "name": p[1], "shares": p[2], "price": p[3]} for p in positions])

    c.execute("INSERT OR REPLACE INTO daily_snapshots VALUES (?,?,?,?,?,?,?)",
              (today, cash, pos_value, total, pos_json, sentiment_score, notes))

    conn.commit()
    conn.close()
    return {"date": today, "cash": cash, "positions_value": pos_value, "total": total}


# 初始化
init_db()

if __name__ == "__main__":
    print("=== 模拟交易引擎测试 ===")
    acc = get_account()
    print(f"账户: 现金={acc['cash']:,.2f}, 总值={acc['total_value']:,.2f}")
    print(f"持仓: {get_positions()}")
