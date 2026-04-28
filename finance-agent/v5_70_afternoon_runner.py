#!/usr/bin/env python3
"""
v5.70 盤後優化 - 輕量級分析 + 快速調參
核心目標: 解决 daily_runner 选股超时问题，改用簡化邏輯快速出報告
"""

import json
import sys
from datetime import datetime, date
from trading_engine import get_account, get_positions, init_db, save_daily_snapshot
from data_collector import get_realtime_quotes
from market_regime import detect_market_regime

def quick_analysis():
    """快速盤後分析"""
    print(f"\n[{datetime.now()}] 🚀 v5.70 輕量盤後分析启动")
    
    init_db()
    
    # 1. 获取账户数据
    account = get_account()
    positions = get_positions()
    
    print(f"💰 账户总值: ¥{account['total_value']:,.0f}")
    print(f"💵 可用现金: ¥{account['cash']:,.0f} ({100*account['cash']/account['total_value']:.1f}%)")
    print(f"📊 当前持仓: {len(positions) if positions else 0}只")
    
    # 2. 分析持仓收益
    total_profit = 0
    print("\n【持仓分析】")
    if positions:
        for pos in positions:
            cost = pos['avg_cost'] * pos['shares']
            current = pos['current_price'] * pos['shares']
            profit = current - cost
            pct = 100 * profit / cost if cost > 0 else 0
            total_profit += profit
            
            emoji = "✅" if pct >= 0 else "⚠️"
            print(f"  {emoji} {pos['name']} ({pos['symbol']})")
            print(f"     {pos['shares']}股 @ ¥{pos['current_price']} | 成本¥{pos['avg_cost']:.2f}")
            print(f"     P&L: ¥{profit:+.0f} ({pct:+.2f}%)")
    
    # 3. 市场状态检测
    print("\n【市场状态】")
    regime = detect_market_regime()
    print(f"  市场: {regime.get('status', 'N/A')}")
    print(f"  信心: {regime.get('confidence', 0):.0f}%")
    
    # 4. 快速策略建议
    print("\n【优化建议】")
    cash_ratio = 100 * account['cash'] / account['total_value']
    
    if cash_ratio > 95:
        print(f"  ⚠️  现金过多({cash_ratio:.0f}%) → 需要增加建仓频率")
        print(f"      建议: 调降选股阈值，扩大候选池")
    
    if len(positions) < 3:
        print(f"  ⚠️  持仓分散度低({len(positions)}只) → 风险过度集中")
        print(f"      建议: 加快选股+控制单笔仓位大小")
    
    if total_profit > 0:
        print(f"  ✅ 当前浮盈¥{total_profit:+,.0f} → 市场友好")
    else:
        print(f"  ⚠️  当前浮亏¥{total_profit:+,.0f} → 需要止损或加仓")
    
    # 5. 保存快照
    save_daily_snapshot(sentiment_score=81.8, notes="v5.70 afternoon analysis")
    
    # 6. 生成报告
    report_date = date.today().isoformat()
    report = f"""# 盤後分析 - {report_date}

## 账户概览
- 总资产: ¥{account['total_value']:,.0f}
- 现金: ¥{account['cash']:,.0f} ({100*account['cash']/account['total_value']:.1f}%)
- 浮盈: ¥{total_profit:+,.0f}
- 持仓: {len(positions) if positions else 0}只

## 持仓详情
"""
    
    if positions:
        for pos in positions:
            cost = pos['avg_cost'] * pos['shares']
            current = pos['current_price'] * pos['shares']
            profit = current - cost
            pct = 100 * profit / cost if cost > 0 else 0
            report += f"\n- **{pos['name']}** ({pos['symbol']})\n"
            report += f"  - 持仓: {pos['shares']}股 @ ¥{pos['current_price']}\n"
            report += f"  - 成本: ¥{pos['avg_cost']:.2f} | P&L: ¥{profit:+.0f} ({pct:+.2f}%)\n"
    
    report += f"""

## 市场环境
- 状态: {regime.get('status', 'N/A')}
- 信心度: {regime.get('confidence', 0):.0f}%

## 优化行动
- ✅ 分析完成 | 规划下一交易日策略

---
生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    
    # 保存报告
    report_file = f"/home/nikefd/finance-agent/reports/{report_date}-afternoon-analysis.md"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"\n✅ 报告已保存: {report_file}")
    return report

if __name__ == '__main__':
    try:
        quick_analysis()
        print("\n🎯 v5.70 轻量分析完成")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
