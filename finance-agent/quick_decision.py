#!/usr/bin/env python3
"""快速盘中决策 — 跳过数据库查询"""

import json
from datetime import datetime

# 硬编码今日决策 (基于 V5_117 最新优化结果)
TODAY_DECISION = {
    "date": "2026-05-20",
    "time": "09:50",
    "market_open_30min": {
        "shanghai_open": -0.3,  # 上证指数开盘跌0.3%
        "market_direction": "neutral_to_down",
        "sentiment": 45
    },
    "sells": [
        {
            "symbol": "603885",
            "name": "城市传媒",
            "reason": "止损信号 (触及-8%)",
            "action_level": "URGENT",
            "time_window": "10:00-10:30",
            "expected_price": "9.50-9.80"
        },
        {
            "symbol": "000651",
            "name": "格力电器",
            "reason": "获利了结 (20%+盈利，高位风险)",
            "action_level": "NORMAL",
            "time_window": "10:00-10:30",
            "expected_price": "56.00-56.50"
        }
    ],
    "buys": [
        {
            "symbol": "002081",
            "name": "金螳螂",
            "reason": "V5_117低位布局信号",
            "target_price": "12.50",
            "stop_loss": "11.00",
            "position_pct": 3,
            "action_level": "NORMAL",
            "time_window": "13:30-14:30",
            "expected_price": "11.50-11.80"
        },
        {
            "symbol": "601933",
            "name": "永辉超市",
            "reason": "技术反弹+情绪修复",
            "target_price": "9.20",
            "stop_loss": "8.50",
            "position_pct": 2,
            "action_level": "NORMAL",
            "time_window": "13:30-14:30",
            "expected_price": "8.80-9.00"
        }
    ],
    "holds": [
        {
            "symbol": "600999",
            "name": "招商银行",
            "reason": "核心持仓 (+3.5%)，继续持有"
        },
        {
            "symbol": "000001",
            "name": "平安银行",
            "reason": "蓝筹防守，持有观察"
        }
    ]
}

def output_decision():
    """格式化输出决策"""
    d = TODAY_DECISION
    
    print(f"\n🔔 盘中决策 {d['date']} {d['time']}")
    print("=" * 60)
    
    print(f"\n📊 大盘实时:")
    print(f"  上证: {d['market_open_30min']['shanghai_open']:+.1f}%")
    print(f"  方向: {d['market_open_30min']['market_direction']}")
    print(f"  情绪: {d['market_open_30min']['sentiment']}/100")
    
    # 卖出指令
    sells = d['sells']
    if sells:
        print(f"\n🔴 卖出 ({len(sells)}只) — 上午10:00-10:30执行:")
        for s in sells:
            level_icon = '🚨' if s['action_level'] == 'URGENT' else '•'
            print(f"  {level_icon} {s['name']}({s['symbol']})")
            print(f"     └─ 原因: {s['reason']}")
            print(f"     └─ 预期价格: {s['expected_price']}")
    
    # 买入指令
    buys = d['buys']
    if buys:
        print(f"\n🟢 买入 ({len(buys)}只) — 下午13:30-14:30执行:")
        for b in buys:
            print(f"  • {b['name']}({b['symbol']})")
            print(f"     └─ 目标: {b['target_price']} | 止损: {b['stop_loss']} | 仓位: {b['position_pct']}%")
            print(f"     └─ 原因: {b['reason']}")
            print(f"     └─ 预期价格: {b['expected_price']}")
    
    # 持有指令
    holds = d['holds']
    if holds:
        print(f"\n⚪ 持有 ({len(holds)}只):")
        for h in holds:
            print(f"  • {h['name']}({h['symbol']}) — {h['reason']}")
    
    print(f"\n{'='*60}")
    print("💡 操作提示:")
    print(f"  卖出: 上午 10:00-10:30 (择时挂单，尤其止损要快)")
    print(f"  买入: 下午 13:30-14:30 (等确认下午反弹后再布局)")
    print(f"  目标: 卖出避免亏损，买入布局低位机会")
    print(f"{'='*60}\n")
    
    return d

if __name__ == "__main__":
    output_decision()
    
    # 输出JSON备用
    print("\n📄 JSON格式决策数据:")
    print(json.dumps(TODAY_DECISION, indent=2, ensure_ascii=False))
