"""
v5.84 stock_picker 集成模块

核心函数集成到 score_and_rank() 中
"""

import sys
sys.path.insert(0, '/home/nikefd/finance-agent')

from v5_84_DEEP_OPTIMIZE import (
    apply_sector_macd_params,
    apply_mixed_pool_sector_weights,
    fast_pick_engine,
    check_portfolio_concentration,
    MIXED_POOL_SECTOR_WEIGHTS_V84,
    MACD_PARAMS_SECTOR_V84,
    FAST_PICK_CONFIG_V84
)
from performance_tracker import classify_sector

# =================== 集成点1: MACD赛道差异化 ===================
def integrate_sector_macd_params_into_scoring(candidates: list) -> list:
    """在score_and_rank中集成MACD赛道差异化
    
    为每个候选应用其赛道的最优MACD参数
    """
    try:
        enhanced = []
        for stock in candidates:
            sector = stock.get('sector', '默认')
            if not sector or sector == '':
                sector = classify_sector(stock.get('code', ''))
            
            # 应用赛道MACD参数
            stock_with_macd = apply_sector_macd_params(stock, sector)
            enhanced.append(stock_with_macd)
        
        print(f"【v5.84】MACD赛道差异化已应用 {len(enhanced)}只候选 [DONE]")
        return enhanced
    except Exception as e:
        print(f"【v5.84】MACD赛道差异化集成失败: {e} [ERROR]")
        return candidates


# =================== 集成点2: 混合池赛道权重 ===================
def integrate_mixed_pool_weights_into_ranking(ranked: list) -> list:
    """在score_and_rank中集成混合池权重调整
    
    优先选择高效赛道(科技成长、新能源)，压制低效赛道(消费)
    """
    try:
        weighted = apply_mixed_pool_sector_weights(ranked)
        
        # 统计权重应用情况
        tech_boost = sum(1 for s in weighted if s.get('sector_weight', 1.0) >= 1.5)
        consume_down = sum(1 for s in weighted if s.get('sector_weight', 1.0) <= 0.5)
        
        print(f"【v5.84】混合池权重调整 [DONE]")
        print(f"        • 科技成长/新能源提升: {tech_boost}只")
        print(f"        • 消费/低效压制: {consume_down}只")
        print(f"        • 目标: 混合池收益 5.06% → 8-10%, Sharpe 0.86 → 1.2+")
        
        return weighted
    except Exception as e:
        print(f"【v5.84】混合池权重集成失败: {e} [ERROR]")
        return ranked


# =================== 集成点3: 快速选股引擎 ===================
def integrate_fast_pick_engine(candidates: list, cash_ratio: float) -> tuple:
    """在score_and_rank中集成快速选股
    
    现金>90%时快速完成评估不超5秒
    """
    try:
        picked, stats = fast_pick_engine(candidates, cash_ratio, timeout_seconds=5.0)
        
        if stats['mode'] == 'fast':
            print(f"【v5.84】快速选股引擎激活 [DONE]")
            print(f"        • 现金占比: {cash_ratio:.1%} (触发值>90%)")
            print(f"        • 评估维度: {stats['dimensions_used']}个 (降维优化)")
            print(f"        • 响应时间: {stats['elapsed_ms']}ms < 5000ms")
            if stats.get('timeout'):
                print(f"        ⚠️  超时警告!")
        
        return picked, stats
    except Exception as e:
        print(f"【v5.84】快速选股引擎失败: {e} [ERROR]")
        return candidates, {'error': str(e)}


# =================== 集成点4: 多样化防护 ===================
def integrate_portfolio_concentration_check(positions: list) -> dict:
    """在建仓前检查多样化防护
    
    前5大持仓不超70%, 避免单一集中
    """
    try:
        report = check_portfolio_concentration(positions)
        
        print(f"【v5.84】多样化防护检查 [DONE]")
        if report['valid']:
            print(f"        ✓ 投资组合集中度正常")
            print(f"        • 赛道分布: {len(report['sector_distribution'])}个赛道")
        else:
            print(f"        ⚠️  集中度过高")
            for violation in report['violations']:
                print(f"        • {violation}")
            if report.get('rebalance_action'):
                print(f"        → 自动调整: {report['rebalance_action']}")
        
        return report
    except Exception as e:
        print(f"【v5.84】多样化防护检查失败: {e} [ERROR]")
        return {'error': str(e)}


# =================== 集成测试 ===================
def test_v5_84_integration():
    """测试v5.84各集成点"""
    
    print("\n" + "="*80)
    print("🧪 v5.84 stock_picker 集成测试")
    print("="*80)
    
    # 测试数据
    test_candidates = [
        {
            'code': '000001',
            'name': '平安银行',
            'sector': '金融',
            'score': 65,
            'signal': 'MACD+RSI',
            'macd_signal': 'golden',
            'rsi': 45,
            'volume_spike': 1.3,
            'sector_inflow_pct': 0.02,
            'price_momentum': 0.05,
        },
        {
            'code': '300070',
            'name': '碧水源',
            'sector': '科技成长',
            'score': 72,
            'signal': 'MACD+RSI',
            'macd_signal': 'golden',
            'rsi': 35,
            'volume_spike': 1.5,
            'sector_inflow_pct': 0.05,
            'price_momentum': 0.08,
        },
        {
            'code': '600519',
            'name': '贵州茅台',
            'sector': '消费白马',
            'score': 58,
            'signal': 'MULTI_FACTOR',
            'macd_signal': 'neutral',
            'rsi': 55,
            'volume_spike': 1.1,
            'sector_inflow_pct': 0.01,
            'price_momentum': 0.02,
        },
    ]
    
    print("\n【1】测试MACD赛道差异化")
    print("-" * 80)
    enhanced = integrate_sector_macd_params_into_scoring(test_candidates)
    for stock in enhanced[:2]:
        if 'macd_params' in stock:
            print(f"  {stock['code']} ({stock.get('sector')}): "
                  f"MACD({stock['macd_params']['fast']},{stock['macd_params']['slow']},{stock['macd_params']['signal']})")
    
    print("\n【2】测试混合池权重")
    print("-" * 80)
    weighted = integrate_mixed_pool_weights_into_ranking(enhanced)
    for stock in weighted[:3]:
        print(f"  {stock['code']}: 原分{stock.get('original_score', 0)}"
              f" × {stock.get('sector_weight', 1.0):.1f}x "
              f"= {stock.get('weighted_score', 0)}")
    
    print("\n【3】测试快速选股引擎")
    print("-" * 80)
    picked_high, stats_high = integrate_fast_pick_engine(weighted, cash_ratio=0.95)
    print(f"  高现金模式(95%): 模式={stats_high.get('mode')}, "
          f"维度={stats_high.get('dimensions_used')}, "
          f"耗时={stats_high.get('elapsed_ms')}ms")
    
    picked_normal, stats_normal = integrate_fast_pick_engine(weighted, cash_ratio=0.50)
    print(f"  正常模式(50%):  模式={stats_normal.get('mode')}, "
          f"维度={stats_normal.get('dimensions_used')}, "
          f"耗时={stats_normal.get('elapsed_ms')}ms")
    
    print("\n【4】测试多样化防护")
    print("-" * 80)
    test_positions = [
        {'code': '000001', 'weight': 0.15, 'sector': '金融'},
        {'code': '300070', 'weight': 0.12, 'sector': '科技成长'},
        {'code': '600519', 'weight': 0.08, 'sector': '消费白马'},
        {'code': '000858', 'weight': 0.06, 'sector': '新能源'},
        {'code': '600036', 'weight': 0.05, 'sector': '金融'},
    ]
    report = integrate_portfolio_concentration_check(test_positions)
    
    print("\n" + "="*80)
    print("✅ v5.84 集成测试完成")
    print("="*80 + "\n")


if __name__ == '__main__':
    test_v5_84_integration()
