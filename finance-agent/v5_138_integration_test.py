#!/usr/bin/env python3
"""v5.138 集成测试: 市值分层 + 多级止盈 + 资金面增强"""

import sys
sys.path.insert(0, '/home/nikefd/finance-agent')

from v5_138_phase2_market_cap_adaptive import *
from v5_138_phase3_scaled_exit import *
from v5_138_phase4_funding_enhance import *

def test_all():
    print("🧪 v5.138 集成测试")
    print("=" * 60)
    
    # Test Phase 2
    print("\n📊 Phase 2: 市值分层参数自适应")
    print("-" * 40)
    
    # 东方证券
    cap_east = 180_000_000_000
    print(f"东方证券(600958): {get_market_cap_tier(cap_east)}")
    print(f"  MACD: {get_adaptive_macd_params(cap_east)}")
    print(f"  RSI周期: {get_adaptive_rsi_period(cap_east)}")
    
    # 华映科技
    cap_huaying = 20_000_000_000
    print(f"\n华映科技(000536): {get_market_cap_tier(cap_huaying)}")
    print(f"  MACD: {get_adaptive_macd_params(cap_huaying)}")
    print(f"  RSI周期: {get_adaptive_rsi_period(cap_huaying)}")
    
    # Test Phase 3
    print("\n\n📈 Phase 3: 多级止盈策略")
    print("-" * 40)
    
    pos = Position('600958', 9.23, 600, '2026-05-28')
    prices = [9.50, 10.00, 10.50, 11.00]
    
    for price in prices:
        result = execute_scaled_exit(pos, price)
        if result['exit_signal']:
            print(f"✅ ¥{price:.2f}: {result['exit_phase']} | 卖{result['exit_qty']}股 | 已止盈¥{result['realized_profit']:.0f}")
        else:
            print(f"⏳ ¥{price:.2f}: 持有 | 收益{result['profit_pct']*100:.1f}%")
    
    # Test Phase 4
    print("\n\n💰 Phase 4: 资金面增强信号")
    print("-" * 40)
    
    vol_data = {'current': 5000000, 'ma5': 3000000}
    order_data = {'large_order_count': 15, 'avg_large_order_size': 10}
    margin_data = {'balance_change_pct': 0.05}
    
    score, breakdown = calculate_enhanced_funding_score(
        '000536', vol_data, order_data, margin_data
    )
    
    print(f"华映科技(000536) 资金面评分: {score:.0f}/100")
    print(f"  基础(无龙虎榜): {breakdown['base']}")
    print(f"  成交量突增: +{breakdown['volume']}")
    print(f"  机构参与: +{breakdown['institutional']}")
    print(f"  融资净买: +{breakdown['margin']}")
    
    print("\n✨ 集成测试完成！")

if __name__ == '__main__':
    test_all()
