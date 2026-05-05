"""
v5.84 backtester 集成模块

准确率分析集成到回测框架中
"""

import sys
sys.path.insert(0, '/home/nikefd/finance-agent')

from v5_84_DEEP_OPTIMIZE import analyze_backtest_accuracy, BACKTEST_ACCURACY_ANALYSIS_V84
from datetime import datetime, timedelta
from typing import Dict, List
import json

# =================== 准确率分析集成 ===================

def generate_accuracy_report_by_quality_grade(backtest_results: Dict) -> Dict:
    """按入场质量等级生成准确率报告
    
    分析每个质量等级的实际成功率
    """
    try:
        report = {
            'version': 'v5.84',
            'timestamp': datetime.now().isoformat(),
            'analysis_period': 'backtest',
            'grades': {}
        }
        
        # 如果有回测结果，从中提取数据
        if not backtest_results:
            print("【v5.84】准确率分析: 暂无回测数据 [SKIP]")
            return report
        
        # 按质量等级分组
        for grade_key, grade_info in BACKTEST_ACCURACY_ANALYSIS_V84['quality_grades'].items():
            quality_range = grade_info['range']
            
            # 从回测结果中提取该等级的推荐
            recommendations = [r for r in backtest_results.get('recommendations', [])
                             if quality_range[0] <= r.get('quality_score', 0) < quality_range[1]]
            
            # 计算该等级的成功率
            if recommendations:
                wins = sum(1 for r in recommendations if r.get('status') == 'win')
                draws = sum(1 for r in recommendations if r.get('status') == 'draw')
                losses = sum(1 for r in recommendations if r.get('status') == 'loss')
                
                win_rate = (wins + draws * 0.5) / len(recommendations) if recommendations else 0
                
                report['grades'][grade_key] = {
                    'range': quality_range,
                    'description': grade_info['description'],
                    'target_win_rate': grade_info['target_win_rate'],
                    'actual_win_rate': round(win_rate, 3),
                    'sample_count': len(recommendations),
                    'wins': wins,
                    'draws': draws,
                    'losses': losses,
                    'adjustment_needed': win_rate < BACKTEST_ACCURACY_ANALYSIS_V84['min_win_rate_threshold']
                }
            else:
                report['grades'][grade_key] = {
                    'range': quality_range,
                    'description': grade_info['description'],
                    'target_win_rate': grade_info['target_win_rate'],
                    'actual_win_rate': None,
                    'sample_count': 0,
                    'adjustment_needed': False
                }
        
        return report
    except Exception as e:
        print(f"【v5.84】准确率报告生成失败: {e}")
        return {'error': str(e)}


def check_and_auto_adjust_entry_threshold(accuracy_report: Dict) -> Dict:
    """检查各质量等级成功率，自动调整入场阈值
    
    如果某等级成功率<40%, 自动提升入场门槛
    """
    try:
        adjustments = {
            'needed': False,
            'changes': []
        }
        
        for grade_key, grade_data in accuracy_report.get('grades', {}).items():
            if grade_data.get('sample_count', 0) < 5:
                # 样本太少，不调整
                continue
            
            actual_rate = grade_data.get('actual_win_rate')
            if actual_rate is None:
                continue
            
            if actual_rate < BACKTEST_ACCURACY_ANALYSIS_V84['min_win_rate_threshold']:
                # 成功率过低，需要调整
                adjustments['needed'] = True
                adjustments['changes'].append({
                    'grade': grade_key,
                    'current_win_rate': round(actual_rate, 3),
                    'min_threshold': BACKTEST_ACCURACY_ANALYSIS_V84['min_win_rate_threshold'],
                    'adjustment': 'raise_entry_quality_threshold_by_5_points',
                    'reason': f"成功率{actual_rate:.1%} < 40%, 降低虚假信号"
                })
        
        return adjustments
    except Exception as e:
        print(f"【v5.84】自动调整失败: {e}")
        return {'error': str(e)}


# =================== 回测验证集成 ===================

def validate_v5_84_backtest_improvements():
    """验证v5.84优化的回测收益改进
    
    预期改进:
    - 混合池: 5.06% → 8-10%
    - 科技+新能源维持高收益
    - 整体Sharpe提升
    """
    print("\n" + "="*80)
    print("📊 v5.84 回测验证框架")
    print("="*80)
    
    benchmarks = {
        'v5.83_mixed_pool': {
            'return': 0.0506,
            'sharpe': 0.86,
            'win_rate': 0.50,
            'description': 'v5.83 混合池基准'
        },
        'v5.83_tech_growth': {
            'return': 0.171,
            'sharpe': 2.35,
            'win_rate': 0.60,
            'description': 'v5.83 科技成长TOP1'
        },
        'v5.83_new_energy': {
            'return': 0.1466,
            'sharpe': 1.78,
            'win_rate': 0.70,
            'description': 'v5.83 新能源TOP2'
        },
    }
    
    v5_84_targets = {
        'mixed_pool_target': {
            'return': 0.09,      # 目标8-10%, 取中值
            'sharpe': 1.2,
            'win_rate': 0.60,
            'improvement': '+78%',
            'description': 'v5.84 混合池目标'
        },
        'overall_target': {
            'return': 0.16,      # 目标12-20%, 取中值
            'sharpe': 1.5,
            'win_rate': 0.65,
            'improvement': '+100%',
            'description': 'v5.84 整体目标'
        }
    }
    
    print("\n【v5.83 基准性能】")
    print("-" * 80)
    for key, bench in benchmarks.items():
        print(f"  {bench['description']:20} | 收益{bench['return']:6.2%} | Sharpe{bench['sharpe']:4.2f} | 胜率{bench['win_rate']:5.0%}")
    
    print("\n【v5.84 优化目标】")
    print("-" * 80)
    for key, target in v5_84_targets.items():
        print(f"  {target['description']:20} | 收益{target['return']:6.2%} | Sharpe{target['sharpe']:4.2f} | 胜率{target['win_rate']:5.0%} ({target['improvement']})")
    
    print("\n【v5.84 优化策略影响分析】")
    print("-" * 80)
    strategies = [
        {
            'name': '【混合池权重调整】',
            'impact': '科技2.0x, 新能源1.8x, 消费0.3x',
            'expected': '混合池偏向高效赛道 → 5.06% → 8-10%',
            'confidence': '高 (基于回测数据权重)'
        },
        {
            'name': '【MACD参数优化】',
            'impact': '赛道级差异化参数 (科技标准, 新能源快速, 消费保守)',
            'expected': '指标反应灵敏度提升 → Sharpe +15-20%',
            'confidence': '中 (参数级优化)'
        },
        {
            'name': '【快速选股】',
            'impact': '现金>90%时<5秒完成 (降维评估)',
            'expected': '建仓响应快 → 抓住热点 → 成功率+5%',
            'confidence': '中 (需实盘验证)'
        },
        {
            'name': '【多样化防护】',
            'impact': '前5大不超70%, 赛道多样性≥3',
            'expected': '降低单一风险 → 回撤-10-20%, Sharpe +10%',
            'confidence': '高 (风险管理标准)'
        },
    ]
    
    for strategy in strategies:
        print(f"\n  {strategy['name']}")
        print(f"    影响: {strategy['impact']}")
        print(f"    预期: {strategy['expected']}")
        print(f"    置信度: {strategy['confidence']}")
    
    print("\n【v5.84 回测验证清单】")
    print("-" * 80)
    checklist = [
        ("混合池5.06% → 8-10%", "backtester.py --backtest-one MACD+RSI --sector 混合池"),
        ("科技17.1%维持", "backtester.py --backtest-one MACD+RSI --sector 科技成长"),
        ("新能源14.66%维持", "backtester.py --backtest-one MACD+RSI --sector 新能源"),
        ("整体Sharpe提升", "backtester.py --backtest-all"),
        ("准确率分析(30天)", "backtester.py --accuracy-report"),
    ]
    
    for i, (test, cmd) in enumerate(checklist, 1):
        print(f"  {i}. {test:20} → {cmd}")
    
    print("\n" + "="*80)
    print("✅ v5.84 回测验证框架已输出")
    print("="*80 + "\n")


if __name__ == '__main__':
    validate_v5_84_backtest_improvements()
