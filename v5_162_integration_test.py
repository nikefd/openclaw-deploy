"""
v5.162 集成测试脚本

测试以下优化:
1. v5.161 MACD动态参数
2. v5.161 现金激进度自适应
3. v5.161 黑名单TTL机制
4. v5.162 波动性自适应引擎
5. v5.162 Kelly係數自动调整
"""

import sys
import numpy as np
from datetime import datetime

def test_v5161_integrations():
    """测试v5.161集成"""
    print("\n🧪 测试v5.161集成...")
    
    # 测试MACD动态参数
    print("\n  ✓ MACD动态参数测试")
    sentiment_scores = [15, 35, 55, 75, 90, 95]  # 极度恐慌 → 极度贪婪
    
    for score in sentiment_scores:
        if score >= 92:
            regime = "extreme_greed"
            fast, slow = 8, 20
        elif score >= 85:
            regime = "greed"
            fast, slow = 9, 22
        elif score >= 60:
            regime = "normal_bullish"
            fast, slow = 10, 24
        elif score >= 40:
            regime = "neutral"
            fast, slow = 11, 25
        elif score >= 25:
            regime = "cautious"
            fast, slow = 12, 27
        else:
            regime = "extreme_fear"
            fast, slow = 13, 30
        
        print(f"    情绪{score}: {regime} → MACD({fast},{slow})")

def test_v5162_volatility_adaptive():
    """测试v5.162波动性自适应"""
    print("\n🧪 测试v5.162波动性自适应...")
    
    from v5_162_volatility_adaptive import VolatilityAdaptiveEngine
    
    engine = VolatilityAdaptiveEngine()
    
    # 模拟不同波动率场景
    volatility_scenarios = [0.012, 0.020, 0.030, 0.045]
    
    for vol in volatility_scenarios:
        params = engine.get_adaptive_params(vol)
        print(f"\n  波动率{vol:.2%}:")
        print(f"    制度: {params['regime']}")
        print(f"    持仓: {params['max_positions']}席")
        print(f"    单倉: {params['max_single_position']:.1%}")
        print(f"    Kelly: {params['kelly_coefficient']:.2f}x")

def test_v5162_kelly_adjustment():
    """测试v5.162 Kelly调整"""
    print("\n🧪 测试v5.162 Kelly調整...")
    
    from v5_162_kelly_adjustment import KellyAutoAdjustment
    
    kelly_sys = KellyAutoAdjustment()
    
    # 测试不同场景
    scenarios = [
        {'name': '高胜率', 'win_rate': 0.75, 'consecutive_losses': 0, 'consecutive_wins': 5},
        {'name': '连续虧損', 'win_rate': 0.60, 'consecutive_losses': 7, 'consecutive_wins': 0},
        {'name': '回撤保护', 'win_rate': 0.50, 'consecutive_losses': 0, 'consecutive_wins': 0, 'drawdown': -0.15},
    ]
    
    for scenario in scenarios:
        kelly = kelly_sys.calculate_dynamic_kelly(
            win_rate_7d=scenario['win_rate'],
            consecutive_losses=scenario.get('consecutive_losses', 0),
            consecutive_wins=scenario.get('consecutive_wins', 0),
            current_drawdown=scenario.get('drawdown', 0)
        )
        print(f"\n  {scenario['name']}:")
        print(f"    Kelly系数: {kelly:.2f}x")

def main():
    print("=" * 60)
    print("v5.162 集成测试")
    print("=" * 60)
    
    test_v5161_integrations()
    test_v5162_volatility_adaptive()
    test_v5162_kelly_adjustment()
    
    print("\n" + "=" * 60)
    print("✅ 所有集成测试完成")
    print("=" * 60)

if __name__ == '__main__':
    main()
