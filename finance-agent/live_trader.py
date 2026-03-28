"""实盘交易接口 — 华泰证券 (通过 easytrader + miniQMT)

实盘交易有两种方案:
1. easytrader + 同花顺客户端 (模拟操作，需要Windows)
2. easytrader + miniQMT (券商官方API，推荐)

当前状态: 模拟盘阶段，此模块为实盘预留接口
"""

import json
from datetime import datetime
from config import *

# 实盘开关 — 默认关闭！！
LIVE_TRADING_ENABLED = False
LIVE_TRADING_CONFIRM = False  # 双重确认


class LiveTrader:
    """实盘交易接口 (预留)"""

    def __init__(self):
        self.connected = False
        self.trader = None

    def connect(self, broker='miniqmt'):
        """连接券商"""
        if not LIVE_TRADING_ENABLED:
            print("⛔ 实盘交易未开启，当前为模拟盘模式")
            return False

        if not LIVE_TRADING_CONFIRM:
            print("⛔ 实盘交易需要双重确认")
            return False

        try:
            import easytrader
            if broker == 'miniqmt':
                self.trader = easytrader.use('miniqmt')
                # self.trader.connect(r'C:\国金QMT交易端路径')  # 需要配置
            elif broker == 'ths':
                self.trader = easytrader.use('ths')
                # self.trader.connect(r'C:\同花顺路径')
            self.connected = True
            print(f"✅ 已连接 {broker}")
            return True
        except Exception as e:
            print(f"❌ 连接失败: {e}")
            return False

    def get_balance(self):
        """查询账户余额"""
        if not self.connected:
            return None
        try:
            return self.trader.balance
        except Exception as e:
            print(f"查询余额失败: {e}")
            return None

    def get_positions(self):
        """查询持仓"""
        if not self.connected:
            return []
        try:
            return self.trader.position
        except Exception as e:
            print(f"查询持仓失败: {e}")
            return []

    def buy(self, symbol: str, price: float, shares: int, reason: str = ""):
        """买入"""
        if not self.connected:
            return {"error": "未连接券商"}

        # 安全检查
        if shares < 100:
            return {"error": "买入数量不足100股"}
        if shares > 10000:
            return {"error": "单笔买入超过10000股，需要手动确认"}
        if price * shares > 200000:
            return {"error": f"单笔金额{price*shares:.0f}元超过20万，需要手动确认"}

        try:
            result = self.trader.buy(symbol, price=price, amount=shares)
            log_trade("BUY", symbol, price, shares, reason, result)
            return {"success": True, "result": result}
        except Exception as e:
            return {"error": str(e)}

    def sell(self, symbol: str, price: float, shares: int, reason: str = ""):
        """卖出"""
        if not self.connected:
            return {"error": "未连接券商"}

        try:
            result = self.trader.sell(symbol, price=price, amount=shares)
            log_trade("SELL", symbol, price, shares, reason, result)
            return {"success": True, "result": result}
        except Exception as e:
            return {"error": str(e)}


def log_trade(direction, symbol, price, shares, reason, result):
    """记录实盘交易日志"""
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS live_trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        direction TEXT, symbol TEXT, price REAL, shares INTEGER,
        amount REAL, reason TEXT, result TEXT, created_at TEXT
    )""")
    c.execute("INSERT INTO live_trades VALUES (NULL,?,?,?,?,?,?,?,?)",
              (direction, symbol, price, shares, price * shares, reason,
               json.dumps(result, default=str), datetime.now().isoformat()))
    conn.commit()
    conn.close()


# ============================================================
# 实盘准入条件 — 必须全部满足才能开启实盘！
# ============================================================
LIVE_TRADING_REQUIREMENTS = {
    "模拟盘运行天数": {"required": 30, "current": 1, "met": False},
    "模拟盘总收益率": {"required": ">5%", "current": "0%", "met": False},
    "模拟盘最大回撤": {"required": "<10%", "current": "0%", "met": False},
    "模拟盘胜率": {"required": ">50%", "current": "0%", "met": False},
    "回测夏普比率": {"required": ">1.5", "current": "2.35", "met": True},
    "券商API连接": {"required": "已连接", "current": "未配置", "met": False},
    "风控规则完善": {"required": "已完善", "current": "已有", "met": True},
    "人工审核确认": {"required": "斌哥确认", "current": "未确认", "met": False},
}


def check_live_readiness():
    """检查是否满足实盘条件"""
    all_met = all(v["met"] for v in LIVE_TRADING_REQUIREMENTS.values())
    return {
        "ready": all_met,
        "requirements": LIVE_TRADING_REQUIREMENTS,
        "unmet": [k for k, v in LIVE_TRADING_REQUIREMENTS.items() if not v["met"]]
    }
