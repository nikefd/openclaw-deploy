#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v5.141 部署前最终验证脚本
- 语法检查
- 导入验证
- 功能测试
- 报告生成
"""

import sys
import json
import subprocess
from datetime import datetime

def run_command(cmd):
    """运行命令并返回结果"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "命令超时"
    except Exception as e:
        return False, "", str(e)

def test_import():
    """测试所有模块导入"""
    print("\n✓ 测试模块导入...")
    tests = [
        ("v5_141_signal_fusion_engine", "SignalWeightOptimizer"),
        ("v5_141_ai_compensation", "AICompensationScorer"),
        ("v5_141_market_state_machine", "MarketStateMachine"),
    ]
    
    for module, cls in tests:
        try:
            exec(f"from {module} import {cls}")
            print(f"  ✓ {module}.{cls}")
        except Exception as e:
            print(f"  ✗ {module}.{cls}: {e}")
            return False
    
    return True

def test_signal_fusion():
    """测试信号融合引擎"""
    print("\n✓ 测试信号融合引擎...")
    try:
        from v5_141_signal_fusion_engine import SignalWeightOptimizer
        
        opt = SignalWeightOptimizer()
        
        # 测试3个情绪状态
        test_cases = [
            (95, "extreme_greed"),
            (60, "neutral"),
            (25, "fear"),
        ]
        
        for sentiment, expected_state in test_cases:
            state = opt.get_emotion_state(sentiment)
            if state == expected_state:
                print(f"  ✓ 情绪{sentiment} → {state}")
            else:
                print(f"  ✗ 情绪{sentiment} 失败")
                return False
        
        # 测试动态权重 (情绪92, 低波动15%)
        weights = opt.get_dynamic_weights(96, volatility=15)
        if abs(weights['funding'] - 0.4) < 0.01:
            print(f"  ✓ 极度贪婪权重正确 (资金40%)")
        else:
            print(f"  ✗ 极度贪婪权重错误 (资金{weights['funding']:.2f})")
            return False
        
        return True
    except Exception as e:
        print(f"  ✗ 错误: {e}")
        return False

def test_ai_compensation():
    """测试AI补偿模块"""
    print("\n✓ 测试AI补偿模块...")
    try:
        from v5_141_ai_compensation import AICompensationScorer
        
        scorer = AICompensationScorer()
        
        # 测试成交量信号
        vol_score = scorer.calculate_volume_signal(1500000, 900000)
        if 10 <= vol_score <= 25:
            print(f"  ✓ 成交量信号: {vol_score:.0f}")
        else:
            print(f"  ✗ 成交量信号异常: {vol_score}")
            return False
        
        # 测试机构信号
        inst_score = scorer.calculate_institutional_signal(5, 0.40, 0.60)
        if 15 <= inst_score <= 20:
            print(f"  ✓ 机构信号: {inst_score:.0f}")
        else:
            print(f"  ✗ 机构信号异常: {inst_score}")
            return False
        
        return True
    except Exception as e:
        print(f"  ✗ 错误: {e}")
        return False

def test_state_machine():
    """测试市场状态机"""
    print("\n✓ 测试市场状态机...")
    try:
        from v5_141_market_state_machine import MarketStateMachine, MarketState
        
        fsm = MarketStateMachine()
        
        # 测试状态获取
        test_cases = [
            (95, MarketState.EXTREME_GREED),
            (85, MarketState.GREED),
            (60, MarketState.NEUTRAL),
            (30, MarketState.FEAR),
            (15, MarketState.EXTREME_FEAR),
        ]
        
        for sentiment, expected_state in test_cases:
            state = fsm.get_state(sentiment)
            if state == expected_state:
                print(f"  ✓ 情绪{sentiment} → {state.value}")
            else:
                print(f"  ✗ 情绪{sentiment} 失败 (期望{expected_state.value}, 实际{state.value})")
                return False
        
        # 测试状态转移
        fsm.transition(92)
        if fsm.current_state == MarketState.EXTREME_GREED:
            print(f"  ✓ 状态转移: NEUTRAL → EXTREME_GREED")
        else:
            print(f"  ✗ 状态转移失败")
            return False
        
        # 测试配置获取
        config = fsm.get_current_config()
        if config['kelly_coefficient'] == 1.35:
            print(f"  ✓ Kelly系数: {config['kelly_coefficient']}")
        else:
            print(f"  ✗ Kelly系数错误")
            return False
        
        return True
    except Exception as e:
        print(f"  ✗ 错误: {e}")
        return False

def generate_final_report():
    """生成最终验证报告"""
    print("\n" + "="*80)
    print("v5.141 部署前最终验证")
    print("="*80)
    
    report = {
        'timestamp': datetime.now().isoformat(),
        'version': 'v5.141',
        'status': 'PRE_DEPLOYMENT',
        'checks': {},
    }
    
    # 1. 模块导入检查
    print("\n[1/4] 模块导入检查...")
    report['checks']['import'] = test_import()
    print(f"  结果: {'✓ 通过' if report['checks']['import'] else '✗ 失败'}")
    
    # 2. 信号融合引擎检查
    print("\n[2/4] 信号融合引擎检查...")
    report['checks']['signal_fusion'] = test_signal_fusion()
    print(f"  结果: {'✓ 通过' if report['checks']['signal_fusion'] else '✗ 失败'}")
    
    # 3. AI补偿模块检查
    print("\n[3/4] AI补偿模块检查...")
    report['checks']['ai_compensation'] = test_ai_compensation()
    print(f"  结果: {'✓ 通过' if report['checks']['ai_compensation'] else '✗ 失败'}")
    
    # 4. 市场状态机检查
    print("\n[4/4] 市场状态机检查...")
    report['checks']['state_machine'] = test_state_machine()
    print(f"  结果: {'✓ 通过' if report['checks']['state_machine'] else '✗ 失败'}")
    
    # 总体结果
    all_passed = all(report['checks'].values())
    report['overall_status'] = 'READY_FOR_DEPLOYMENT' if all_passed else 'VERIFICATION_FAILED'
    
    print("\n" + "="*80)
    print("验证结果汇总")
    print("="*80)
    
    for check, result in report['checks'].items():
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{check:20s} {status}")
    
    print("\n总体状态:", report['overall_status'])
    
    if all_passed:
        print("\n✨ 所有检查通过,可以部署!")
        print("\n部署步骤:")
        print("1. chmod +x v5_141_deploy.sh")
        print("2. ./v5_141_deploy.sh")
        print("3. 监控: tail -f /var/log/finance-api.log")
    else:
        print("\n⚠️  部分检查失败,请修复后重新部署")
        sys.exit(1)
    
    return report

if __name__ == '__main__':
    report = generate_final_report()
    
    # 保存报告
    with open('v5_141_predeployment_check.json', 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"\n报告已保存: v5_141_predeployment_check.json")
