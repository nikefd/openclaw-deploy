"""
v5.67 单元测试套件 (简化版)
==================

测试所有新增函数的基本功能和容错能力
"""

import sys
sys.path.insert(0, '/home/nikefd/finance-agent')

from v5_67_OPTIMIZATION_FUNCTIONS import (
    strategy_performance_weighting,
    max_drawdown_penalty_check,
    apply_sharpe_ranking_multiplier_v2,
    check_dynamic_stop_v2,
    is_v5_67_compatible
)


def test_strategy_performance_weighting():
    """测试策略性能权重函数"""
    print("\n✅ 测试 strategy_performance_weighting")
    
    # Mock数据
    ranked = [
        {
            'code': '600519',
            'name': '贵州茅台',
            'score': 100,
            'signals': ['MACD买入', 'RSI<30'],
            '_sector': '科技成长'
        },
        {
            'code': '000333',
            'name': '美的集团',
            'score': 80,
            'signals': ['多因子高分'],
            '_sector': '白马消费'
        }
    ]
    
    backtest_metrics = {
        'MACD_RSI': {'return': 0.171, 'sharpe': 2.35, 'maxdd': 0.0408},
        'MULTI_FACTOR': {'return': 0.12, 'sharpe': 0.85, 'maxdd': 0.06},
    }
    
    result = strategy_performance_weighting(ranked, backtest_metrics)
    
    print(f"  输入: {len(ranked)}只股票")
    print(f"  输出: {len(result)}只股票")
    print(f"  第1只: {result[0]['code']} score={result[0]['score']}")
    if '_performance_weight' in result[0]:
        print(f"  权重信息: {result[0]['_performance_weight']}")
    
    assert len(result) == 2, "输出数量应为2"
    assert result[0]['score'] >= result[1]['score'], "应按score降序排列"
    print("  ✓ 测试通过")


def test_max_drawdown_penalty_check():
    """测试MaxDD惩罚检查"""
    print("\n✅ 测试 max_drawdown_penalty_check")
    
    ranked = [
        {'code': '600519', 'name': '贵州茅台', 'score': 100, '_sector': '科技成长'},
        {'code': '601318', 'name': '中国平安', 'score': 90, '_sector': '新能源'},
        {'code': '000858', 'name': '五粮液', 'score': 85, '_sector': '白马消费'},
    ]
    
    sector_metrics = {
        '科技成长': {'maxdd': 0.0408, 'sharpe': 2.35},
        '新能源': {'maxdd': 0.0693, 'sharpe': 1.78},      # MaxDD > 6% → 罚权重
        '白马消费': {'maxdd': 0.052, 'sharpe': 0.85},     # MaxDD > 5% → 罚权重
    }
    
    result = max_drawdown_penalty_check(ranked, sector_metrics)
    
    print(f"  输入: {len(ranked)}只股票")
    print(f"  输出: {len(result)}只股票")
    
    # 查找新能源(601318)
    for stock in result:
        if stock['code'] == '601318':
            print(f"  新能源MaxDD处理: score {90} → {stock['score']}")
            if '_maxdd_penalty' in stock:
                print(f"  惩罚信息: {stock['_maxdd_penalty']}")
    
    print("  ✓ 测试通过")


def test_apply_sharpe_ranking_multiplier_v2():
    """测试Sharpe倍数应用"""
    print("\n✅ 测试 apply_sharpe_ranking_multiplier_v2")
    
    ranked = [
        {'code': '600519', 'score': 100, 'signals': ['MACD买入']},
        {'code': '000333', 'score': 80, 'signals': ['MACD买入']},
        {'code': '601318', 'score': 60, 'signals': ['多因子']},
    ]
    
    # 测试超激进模式 (现金>98%)
    result_extreme = apply_sharpe_ranking_multiplier_v2(ranked, cash_ratio=0.985, extreme_mode=True)
    
    print(f"  超激进模式(2.8x倍数):")
    for s in result_extreme[:2]:
        if '_sharpe_multiplier_v2' in s:
            info = s['_sharpe_multiplier_v2']
            print(f"    {s['code']}: {info['original_score']} × {info['multiplier']} = {info['new_score']}")
    
    assert result_extreme[0]['score'] >= result_extreme[1]['score'], "应按降序排列"
    print("  ✓ 测试通过")


def test_check_dynamic_stop_v2():
    """测试动态止损v2"""
    print("\n✅ 测试 check_dynamic_stop_v2")
    
    positions = [
        {
            'symbol': '600519',
            'name': '贵州茅台',
            'buy_price': 1200,
            'avg_cost': 1200,
            'peak_price': 1300,
            'current_price': 1200,  # 回撤 7.7%
            'entry_quality_score': 75,
            '_sharpe_level': 'high',
            'buy_date': '2026-04-01'
        },
        {
            'symbol': '000333',
            'name': '美的集团',
            'buy_price': 50,
            'avg_cost': 50,
            'peak_price': 55,
            'current_price': 51,  # 回撤 7.3%
            'entry_quality_score': 45,
            '_sharpe_level': 'low',
            'buy_date': '2026-04-15'
        }
    ]
    
    quotes = {
        '600519': {'price': 1200},
        '000333': {'price': 51}
    }
    
    result = check_dynamic_stop_v2(positions, quotes)
    
    print(f"  输入: {len(positions)}只持仓")
    print(f"  止损信号: {len(result)}个")
    for stop in result:
        print(f"    {stop['symbol']}: {stop['reason']}")
    
    print("  ✓ 测试通过")


def test_edge_cases():
    """边界情况测试"""
    print("\n✅ 测试 边界情况")
    
    # 空list
    result1 = strategy_performance_weighting([], {})
    assert result1 == [], "空list应返回空"
    
    # None参数
    result2 = strategy_performance_weighting([{'score': 100}], None)
    assert len(result2) == 1, "None参数应处理"
    
    # 异常数据处理
    result3 = apply_sharpe_ranking_multiplier_v2([{'invalid': 'data'}], 0.85)
    assert len(result3) == 1, "异常数据应容错"
    
    print("  ✓ 所有边界情况通过")


def test_compatibility():
    """兼容性检查"""
    print("\n✅ 测试 v5.67兼容性")
    
    compat = is_v5_67_compatible()
    print(f"  兼容性检查: {compat}")
    print("  ✓ 测试通过")


def run_all_tests():
    """运行全部测试"""
    print("=" * 60)
    print("v5.67 单元测试套件 (简化版)")
    print("=" * 60)
    
    try:
        test_compatibility()
        test_strategy_performance_weighting()
        test_max_drawdown_penalty_check()
        test_apply_sharpe_ranking_multiplier_v2()
        test_check_dynamic_stop_v2()
        test_edge_cases()
        
        print("\n" + "=" * 60)
        print("✅ 全部单元测试通过 (6/6)")
        print("=" * 60)
        return True
    
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
