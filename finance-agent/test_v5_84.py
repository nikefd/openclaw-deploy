"""
v5.84 单元测试框架

验证所有v5.84优化函数的正确性
"""

import sys
sys.path.insert(0, '/home/nikefd/finance-agent')

from v5_84_DEEP_OPTIMIZE import (
    apply_sector_macd_params,
    apply_mixed_pool_sector_weights,
    fast_pick_engine,
    check_portfolio_concentration,
    calculate_fast_score,
    MIXED_POOL_SECTOR_WEIGHTS_V84,
    MACD_PARAMS_SECTOR_V84,
    FAST_PICK_CONFIG_V84,
    PORTFOLIO_CONCENTRATION_CHECK_V84
)
from datetime import datetime

# =================== 单元测试 ===================

class TestV5_84:
    """v5.84优化函数单元测试"""
    
    passed = 0
    failed = 0
    
    @staticmethod
    def assert_equal(actual, expected, test_name):
        """断言相等"""
        if actual == expected:
            print(f"  ✅ {test_name}")
            TestV5_84.passed += 1
            return True
        else:
            print(f"  ❌ {test_name}: 期望{expected}, 实际{actual}")
            TestV5_84.failed += 1
            return False
    
    @staticmethod
    def assert_true(condition, test_name):
        """断言真"""
        if condition:
            print(f"  ✅ {test_name}")
            TestV5_84.passed += 1
            return True
        else:
            print(f"  ❌ {test_name}: 条件不满足")
            TestV5_84.failed += 1
            return False
    
    @staticmethod
    def test_sector_macd_params():
        """测试MACD赛道差异化"""
        print("\n【单元测试】MACD赛道差异化")
        print("-" * 60)
        
        # 测试科技成长
        stock_tech = {'code': '300001', 'sector': '科技成长'}
        result = apply_sector_macd_params(stock_tech, '科技成长')
        TestV5_84.assert_equal(result['macd_params']['fast'], 12, "科技成长 fast=12")
        TestV5_84.assert_equal(result['macd_params']['slow'], 26, "科技成长 slow=26")
        
        # 测试新能源
        stock_ne = {'code': '300002', 'sector': '新能源'}
        result = apply_sector_macd_params(stock_ne, '新能源')
        TestV5_84.assert_equal(result['macd_params']['fast'], 10, "新能源 fast=10")
        TestV5_84.assert_equal(result['macd_params']['slow'], 24, "新能源 slow=24")
        
        # 测试消费白马
        stock_consume = {'code': '600000', 'sector': '消费白马'}
        result = apply_sector_macd_params(stock_consume, '消费白马')
        TestV5_84.assert_equal(result['macd_params']['fast'], 14, "消费白马 fast=14")
        TestV5_84.assert_equal(result['macd_params']['slow'], 28, "消费白马 slow=28")
    
    @staticmethod
    def test_mixed_pool_weights():
        """测试混合池权重调整"""
        print("\n【单元测试】混合池权重调整")
        print("-" * 60)
        
        candidates = [
            {'code': '300001', 'sector': '科技成长', 'score': 60},
            {'code': '300002', 'sector': '新能源', 'score': 50},
            {'code': '600000', 'sector': '消费白马', 'score': 70},
        ]
        
        result = apply_mixed_pool_sector_weights(candidates)
        
        # 验证科技成长权重提升
        tech_stock = [r for r in result if r['code'] == '300001'][0]
        TestV5_84.assert_equal(tech_stock['sector_weight'], 2.0, "科技成长权重2.0x")
        TestV5_84.assert_equal(tech_stock['weighted_score'], 120, "科技成长加权分数120")
        
        # 验证消费权重压制
        consume_stock = [r for r in result if r['code'] == '600000'][0]
        TestV5_84.assert_equal(consume_stock['sector_weight'], 0.3, "消费权重0.3x")
        TestV5_84.assert_equal(consume_stock['weighted_score'], 21, "消费加权分数21")
        
        # 验证排序 (权重后应该是 科技→新能源→消费)
        TestV5_84.assert_equal(result[0]['code'], '300001', "排序第一: 科技成长")
        TestV5_84.assert_equal(result[2]['code'], '600000', "排序最后: 消费白马")
    
    @staticmethod
    def test_fast_score():
        """测试快速评分"""
        print("\n【单元测试】快速评分")
        print("-" * 60)
        
        stock_good = {
            'code': '300001',
            'macd_signal': 'golden',
            'rsi': 35,
            'volume_spike': 1.3,
            'sector_inflow_pct': 0.04,
            'price_momentum': 0.05,
        }
        
        score = calculate_fast_score(stock_good)
        TestV5_84.assert_true(score > 80, f"优质股快速分数>80 (实际{score})")
        
        stock_bad = {
            'code': '600000',
            'macd_signal': 'dead',
            'rsi': 80,
            'volume_spike': 0.9,
            'sector_inflow_pct': -0.02,
            'price_momentum': -0.01,
        }
        
        score = calculate_fast_score(stock_bad)
        TestV5_84.assert_true(score < 30, f"低质股快速分数<30 (实际{score})")
    
    @staticmethod
    def test_fast_pick_engine():
        """测试快速选股引擎"""
        print("\n【单元测试】快速选股引擎")
        print("-" * 60)
        
        candidates = [
            {'code': f'00000{i}', 'sector': '科技成长', 'score': 50+i} 
            for i in range(1, 11)
        ]
        
        # 高现金模式 (快速)
        picked_fast, stats_fast = fast_pick_engine(candidates, cash_ratio=0.95, timeout_seconds=5.0)
        TestV5_84.assert_equal(stats_fast['mode'], 'fast', "高现金触发快速模式")
        TestV5_84.assert_equal(stats_fast['dimensions_used'], 5, "快速模式5维度")
        TestV5_84.assert_true(stats_fast['elapsed_ms'] < 100, f"响应<100ms (实际{stats_fast['elapsed_ms']}ms)")
        
        # 正常模式
        picked_normal, stats_normal = fast_pick_engine(candidates, cash_ratio=0.50, timeout_seconds=5.0)
        TestV5_84.assert_equal(stats_normal['mode'], 'normal', "正常现金使用正常模式")
        TestV5_84.assert_equal(stats_normal['dimensions_used'], 10, "正常模式10维度")
    
    @staticmethod
    def test_portfolio_concentration():
        """测试多样化防护"""
        print("\n【单元测试】多样化防护")
        print("-" * 60)
        
        # 正常多样化持仓
        positions_good = [
            {'code': '000001', 'weight': 0.12, 'sector': '金融'},
            {'code': '300001', 'weight': 0.10, 'sector': '科技成长'},
            {'code': '000858', 'weight': 0.08, 'sector': '新能源'},
            {'code': '600000', 'weight': 0.07, 'sector': '消费白马'},
            {'code': '600001', 'weight': 0.06, 'sector': '医药'},
        ]
        
        report = check_portfolio_concentration(positions_good)
        TestV5_84.assert_true(report['valid'], "正常多样化通过检查")
        TestV5_84.assert_true(len(report['sector_distribution']) >= 3, "赛道分布≥3")
        
        # 集中度过高持仓
        positions_bad = [
            {'code': '000001', 'weight': 0.30, 'sector': '金融'},
            {'code': '000002', 'weight': 0.28, 'sector': '金融'},
            {'code': '000003', 'weight': 0.25, 'sector': '金融'},
            {'code': '300001', 'weight': 0.10, 'sector': '科技成长'},
            {'code': '300002', 'weight': 0.07, 'sector': '科技成长'},
        ]
        
        report = check_portfolio_concentration(positions_bad)
        TestV5_84.assert_true(not report['valid'], "过高集中度检查失败")
        TestV5_84.assert_true(len(report['violations']) > 0, "有违规提示")
    
    @staticmethod
    def run_all():
        """运行所有测试"""
        print("\n" + "="*70)
        print("🧪 v5.84 单元测试框架")
        print("="*70)
        
        TestV5_84.test_sector_macd_params()
        TestV5_84.test_mixed_pool_weights()
        TestV5_84.test_fast_score()
        TestV5_84.test_fast_pick_engine()
        TestV5_84.test_portfolio_concentration()
        
        print("\n" + "="*70)
        print(f"✅ 测试完成: 通过 {TestV5_84.passed}, 失败 {TestV5_84.failed}")
        print("="*70 + "\n")
        
        return TestV5_84.failed == 0


if __name__ == '__main__':
    success = TestV5_84.run_all()
    exit(0 if success else 1)
