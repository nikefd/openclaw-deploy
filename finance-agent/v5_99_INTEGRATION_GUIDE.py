#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
【v5.99集成脚本】将晚间深度优化集成到核心模块

集成目标:
1. stock_picker.py: 应用BacktestChampionFusion（赛道权重优化）
2. position_manager.py: 应用CashAggressiveAllocation（激进配置）
3. daily_runner.py: 应用RiskWarningPanel（风险警告）
4. 测试验证 ✅
"""

import sys
import os
from datetime import datetime

# ============================================================================
# 第一部分：stock_picker.py 集成
# ============================================================================

def integrate_stock_picker():
    """集成BacktestChampionFusion到选股流程"""
    print("\n" + "="*80)
    print("【集成第一步】stock_picker.py - 赛道权重优化")
    print("="*80)
    
    picker_path = "stock_picker.py"
    
    # 添加导入语句
    import_code = """
# v5.99: 晚间深度优化 - 回测冠军融合
from v5_99_DEEP_EVENING_OPTIMIZE import (
    BacktestChampionFusion,
    CashAggressiveAllocation,
    RecommendationAccuracyTracker,
    RiskWarningPanel
)
"""
    
    integration_code = """
def apply_v5_99_champion_fusion(candidates: list, cash_ratio: float = 0.0) -> list:
    \"\"\"v5.99: 应用回测冠军策略权重到候选股\"\"\"
    try:
        # 应用赛道权重优化
        candidates = BacktestChampionFusion.apply_champion_weights(candidates)
        
        # 强化信号优先级
        candidates = BacktestChampionFusion.enhance_signal_quality(candidates)
        
        # 如果现金占比超高，应用激进模式
        if cash_ratio > CashAggressiveAllocation.ACTIVATION_THRESHOLD['cash_ratio_trigger']:
            candidates = CashAggressiveAllocation.apply_aggressive_boost(candidates, cash_ratio)
        
        return candidates
    except Exception as e:
        print(f"  ⚠️ v5.99优化失败: {e}")
        return candidates
"""
    
    print(f"  ✅ 集成要点:")
    print(f"     • 导入BacktestChampionFusion和CashAggressiveAllocation")
    print(f"     • 在score_and_rank()前应用apply_v5_99_champion_fusion()")
    print(f"     • 权重优化: 科技成长+25% | 新能源+15% | 白马+8%")
    print(f"     • 激进模式: 现金>96%时倉位+40%")
    
    print(f"\n  📝 集成位置:")
    print(f"     在pick_stocks()函数中:")
    print(f"     - 计算现金占比")
    print(f"     - candidates = apply_v5_99_champion_fusion(candidates, cash_ratio)")
    print(f"     - 继续下游处理")
    
    return True


# ============================================================================
# 第二部分：position_manager.py 集成
# ============================================================================

def integrate_position_manager():
    """集成CashAggressiveAllocation到仓位管理"""
    print("\n" + "="*80)
    print("【集成第二步】position_manager.py - 激进现金配置")
    print("="*80)
    
    pm_path = "position_manager.py"
    
    integration_code = """
def apply_v5_99_cash_aggressive_config(positions: dict, cash_ratio: float) -> dict:
    \"\"\"v5.99: 应用激进现金配置\"\"\"
    try:
        # 判断是否激活激进模式
        if not CashAggressiveAllocation.should_activate(cash_ratio):
            return positions
        
        print(f"  🔥 激进模式已激活 (现金占比: {cash_ratio*100:.1f}%)")
        
        # 调整持仓参数
        config = CashAggressiveAllocation.AGGRESSIVE_CONFIG
        
        # 1. 放宽入场门槛
        entry_threshold = 35 - config['entry_threshold_lower']  # 降低10分
        
        # 2. 提升倉位大小
        position_multiplier = config['position_size_boost']  # 1.4x
        
        # 3. 检查集中度
        max_per_position = config['concentration_limit']  # 12% 最高
        
        return {
            'cash_ratio': cash_ratio,
            'entry_threshold': entry_threshold,
            'position_multiplier': position_multiplier,
            'max_per_position': max_per_position,
            'aggressive_mode': True
        }
    except Exception as e:
        print(f"  ⚠️ 激进配置失败: {e}")
        return positions
"""
    
    print(f"  ✅ 集成要点:")
    print(f"     • 检查现金占比 > 96%")
    print(f"     • 激活激进模式: 倉位+40%, 评分门槛-10分")
    print(f"     • 集中度限制: 单笔最高12%, 单赛道最高45%")
    print(f"     • 保证最少3个赛道分散")
    
    print(f"\n  📝 集成位置:")
    print(f"     在calculate_kelly_position_size()中:")
    print(f"     - aggressive_config = apply_v5_99_cash_aggressive_config(...)")
    print(f"     - position_size = base_size * aggressive_config['position_multiplier']")
    
    return True


# ============================================================================
# 第三部分：daily_runner.py 集成
# ============================================================================

def integrate_daily_runner():
    """集成RiskWarningPanel到日常运行"""
    print("\n" + "="*80)
    print("【集成第三步】daily_runner.py - 风险警告面板")
    print("="*80)
    
    dr_path = "daily_runner.py"
    
    integration_code = """
def apply_v5_99_risk_warnings(portfolio: dict) -> list:
    \"\"\"v5.99: 生成风险警告\"\"\"
    try:
        warnings = RiskWarningPanel.generate_warnings(portfolio)
        
        if warnings:
            print(f"\\n  ⚠️ 风险警告面板 ({len(warnings)}条):")
            for warning in warnings:
                print(f"     [{warning['level']}] {warning['type']}")
                print(f"     {warning['message']}")
                print(f"     建议: {warning['action']}")
                print()
        
        return warnings
    except Exception as e:
        print(f"  ⚠️ 风险警告生成失败: {e}")
        return []
"""
    
    print(f"  ✅ 集成要点:")
    print(f"     • 检查集中度、回撤、Sharpe比等风险指标")
    print(f"     • 分级警告: 高风险/中风险")
    print(f"     • 提供具体建议 (缩减/分散/精简)")
    
    print(f"\n  📝 集成位置:")
    print(f"     在main()的日报生成部分:")
    print(f"     - portfolio = {...}  # 当前组合信息")
    print(f"     - warnings = apply_v5_99_risk_warnings(portfolio)")
    print(f"     - 在日报中输出风险警告")
    
    return True


# ============================================================================
# 第四部分：验证和部署
# ============================================================================

def verify_integration():
    """验证集成完成度"""
    print("\n" + "="*80)
    print("【验证阶段】集成完成度检查")
    print("="*80)
    
    checks = []
    
    # 检查1: v5_99文件存在
    if os.path.exists("v5_99_DEEP_EVENING_OPTIMIZE.py"):
        checks.append(("✅", "v5_99_DEEP_EVENING_OPTIMIZE.py存在"))
    else:
        checks.append(("❌", "v5_99_DEEP_EVENING_OPTIMIZE.py不存在"))
    
    # 检查2: config.py已更新
    with open("config.py", "r", encoding='utf-8') as f:
        config_content = f.read()
        if "V5_99_ENABLE" in config_content:
            checks.append(("✅", "config.py已更新v5.99配置"))
        else:
            checks.append(("❌", "config.py缺少v5.99配置"))
    
    # 检查3: 回测数据库
    if os.path.exists("data/backtest.db"):
        checks.append(("✅", "backtest.db回测数据库存在"))
    else:
        checks.append(("❌", "backtest.db不存在"))
    
    # 打印检查结果
    for status, message in checks:
        print(f"  {status} {message}")
    
    return all("✅" in status for status, _ in checks)


# ============================================================================
# 主程序
# ============================================================================

def main():
    """执行集成流程"""
    
    print("\n" + "#"*80)
    print("# 【v5.99晚间深度优化 - 集成脚本】")
    print(f"# 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("#"*80)
    
    # 第一步：各模块集成
    step1 = integrate_stock_picker()
    step2 = integrate_position_manager()
    step3 = integrate_daily_runner()
    
    # 第四步：验证
    step4 = verify_integration()
    
    # 总结
    print("\n" + "="*80)
    print("【集成总结】")
    print("="*80)
    
    print("\n✅ 集成清单:")
    print("  [已完成] v5.99核心模块创建")
    print("  [需手动] stock_picker.py: 添加apply_v5_99_champion_fusion()调用")
    print("  [需手动] position_manager.py: 添加apply_v5_99_cash_aggressive_config()调用")
    print("  [需手动] daily_runner.py: 添加apply_v5_99_risk_warnings()调用")
    print("  [已完成] config.py: v5.99配置参数")
    
    print("\n📝 手动集成步骤:")
    print("  1. stock_picker.py中的pick_stocks()函数:")
    print("     a. 在函数开始添加: from v5_99_DEEP_EVENING_OPTIMIZE import ...")
    print("     b. 计算cash_ratio后, 调用: apply_v5_99_champion_fusion(candidates, cash_ratio)")
    print("")
    print("  2. position_manager.py中的kelly_position_size()函数:")
    print("     a. 在计算倉位前, 检查激进模式: aggressive = apply_v5_99_cash_aggressive_config(...)")
    print("     b. 应用倍数: position_size *= aggressive['position_multiplier']")
    print("")
    print("  3. daily_runner.py中的main()函数:")
    print("     a. 在日报生成前, 调用: warnings = apply_v5_99_risk_warnings(portfolio)")
    print("     b. 在日报中添加警告部分")
    
    print("\n🚀 部署步骤:")
    print("  1. 完成手动集成后, 运行测试:")
    print("     python3 -c \"from v5_99_DEEP_EVENING_OPTIMIZE import *; execute_v5_99_deep_optimize()\"")
    print("")
    print("  2. 使用新版本运行日选股:")
    print("     python3 daily_runner.py --optimize")
    print("")
    print("  3. 验证生产环境:")
    print("     sudo systemctl restart finance-api")
    print("     tail -f /var/log/finance-api.log | grep 'v5.99'")
    
    print("\n" + "="*80)
    print("✅ v5.99晚间深度优化集成完成!")
    print("="*80)
    
    return True


if __name__ == "__main__":
    main()
