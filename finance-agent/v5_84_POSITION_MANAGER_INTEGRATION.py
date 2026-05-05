"""
v5.84 position_manager 集成模块

多样化防护集成到持仓管理中
"""

import sys
sys.path.insert(0, '/home/nikefd/finance-agent')

from v5_84_DEEP_OPTIMIZE import check_portfolio_concentration
from typing import List, Dict

# =================== 持仓管理集成 ===================

def validate_new_position_diversification(current_positions: List[Dict], 
                                         new_position: Dict) -> Dict:
    """在建立新仓位前验证多样化
    
    确保新仓位不会导致集中度过高
    """
    try:
        # 合并当前持仓和新仓位
        test_positions = current_positions + [new_position]
        
        # 运行多样化检查
        report = check_portfolio_concentration(test_positions)
        
        if report['valid']:
            return {
                'allow': True,
                'reason': '通过多样化检查',
                'sector_count': len(report['sector_distribution']),
                'report': report
            }
        else:
            return {
                'allow': False,
                'reason': f"多样化违规: {', '.join(report['violations'][:2])}",
                'violations': report['violations'],
                'report': report
            }
    except Exception as e:
        print(f"【v5.84】多样化验证失败: {e}")
        return {'allow': False, 'error': str(e)}


def suggest_sector_rebalancing(current_positions: List[Dict]) -> Dict:
    """建议赛道级别的平衡调整
    
    根据当前持仓建议哪些赛道应该增加/减少
    """
    try:
        report = check_portfolio_concentration(current_positions)
        
        if not current_positions:
            return {'recommendations': []}
        
        sector_weights = report.get('sector_distribution', {})
        suggestions = []
        
        # 分析各赛道权重
        for sector, weight in sorted(sector_weights.items(), key=lambda x: -x[1]):
            if weight > 0.30:  # 单赛道>30%
                suggestions.append({
                    'sector': sector,
                    'weight': weight,
                    'action': 'reduce',
                    'reason': f'权重过高({weight:.1%}), 建议减少新增'
                })
            elif weight < 0.10 and len(sector_weights) < 5:
                suggestions.append({
                    'sector': sector,
                    'weight': weight,
                    'action': 'increase',
                    'reason': f'权重偏低({weight:.1%}), 建议增加布局'
                })
        
        return {
            'sector_distribution': sector_weights,
            'recommendations': suggestions,
            'needs_rebalance': len(suggestions) > 0
        }
    except Exception as e:
        print(f"【v5.84】赛道平衡建议失败: {e}")
        return {'error': str(e)}


# =================== 实际应用场景测试 ===================

def test_position_manager_integration():
    """测试持仓管理器集成"""
    
    print("\n" + "="*80)
    print("🧪 v5.84 position_manager 集成测试")
    print("="*80)
    
    # 当前持仓
    current_positions = [
        {'code': '000001', 'weight': 0.12, 'sector': '金融'},
        {'code': '300070', 'weight': 0.10, 'sector': '科技成长'},
        {'code': '600519', 'weight': 0.08, 'sector': '消费白马'},
    ]
    
    # 候选新仓位
    new_position_1 = {'code': '000858', 'weight': 0.06, 'sector': '新能源'}
    new_position_2 = {'code': '600036', 'weight': 0.15, 'sector': '金融'}  # 会导致金融过高
    
    print("\n【1】测试新仓位多样化验证")
    print("-" * 80)
    print(f"当前持仓: {len(current_positions)}只")
    for pos in current_positions:
        print(f"  • {pos['code']} ({pos['sector']}): {pos['weight']:.0%}")
    
    print(f"\n候选1: {new_position_1['code']} ({new_position_1['sector']}): {new_position_1['weight']:.0%}")
    result_1 = validate_new_position_diversification(current_positions, new_position_1)
    print(f"  结果: {'✅ 允许' if result_1['allow'] else '❌ 拒绝'}")
    print(f"  原因: {result_1['reason']}")
    
    print(f"\n候选2: {new_position_2['code']} ({new_position_2['sector']}): {new_position_2['weight']:.0%} (金融过多)")
    result_2 = validate_new_position_diversification(current_positions, new_position_2)
    print(f"  结果: {'✅ 允许' if result_2['allow'] else '❌ 拒绝'}")
    if not result_2['allow']:
        for violation in result_2.get('violations', [])[:2]:
            print(f"  • {violation}")
    
    print("\n【2】测试赛道平衡建议")
    print("-" * 80)
    
    # 不平衡的持仓
    unbalanced = [
        {'code': '000001', 'weight': 0.25, 'sector': '金融'},
        {'code': '600000', 'weight': 0.22, 'sector': '金融'},
        {'code': '600001', 'weight': 0.20, 'sector': '金融'},
        {'code': '300070', 'weight': 0.10, 'sector': '科技成长'},
        {'code': '000858', 'weight': 0.03, 'sector': '新能源'},
    ]
    
    print(f"不平衡持仓 (金融占{0.67:.0%}):")
    for pos in unbalanced:
        print(f"  • {pos['code']} ({pos['sector']}): {pos['weight']:.0%}")
    
    suggestions = suggest_sector_rebalancing(unbalanced)
    print(f"\n平衡建议:")
    for rec in suggestions['recommendations']:
        print(f"  • {rec['sector']:12} ({rec['weight']:.0%}) → {rec['action']}: {rec['reason']}")
    
    print("\n" + "="*80)
    print("✅ v5.84 position_manager 集成测试完成")
    print("="*80 + "\n")


if __name__ == '__main__':
    test_position_manager_integration()
