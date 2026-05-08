#!/usr/bin/env python3
"""信号有效性分析 — 供API调用"""
import sqlite3, json
DB = '/home/nikefd/finance-agent/data/trading.db'
c = sqlite3.connect(DB)
c.row_factory = sqlite3.Row
r = c.execute("""
  SELECT b.reason as buy_reason, b.price as buy_price,
         s.price as sell_price, s.reason as sell_reason
  FROM trades b
  JOIN trades s ON b.symbol = s.symbol AND s.direction = 'SELL'
    AND s.id = (SELECT MIN(s2.id) FROM trades s2 WHERE s2.symbol = b.symbol AND s2.direction = 'SELL' AND s2.id > b.id)
  WHERE b.direction = 'BUY' AND b.trade_date >= date('now', '-60 days')
""").fetchall()
print(json.dumps([dict(x) for x in r]))
