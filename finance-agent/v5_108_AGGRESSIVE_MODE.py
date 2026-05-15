#!/usr/bin/env python3
"""
v5.108 - 激进建仓模式优化脚本
目标: 加快资金利用率，激活积压现金

执行:
  python3 v5_108_AGGRESSIVE_MODE.py
"""

import json
import sys
from datetime import datetime

# ============================================
# 优化①: 动态持仓规划
# ============================================

def aggressive_position_sizing():
    """
    基于当前现金，计算激进建仓规模
    
    逻辑:
    - 现金 ¥967,700
    - 保留比例 75% (而非95%)
    - 可用建仓金额: ¥241,925
    - 目标持仓数: 8只
    - 每只初始金额: ¥30,240
    """
    
    total_cash = 967700.17
    reserve_ratio = 0.75  # 保留75% (原95%)
    reserved_cash = total_cash * reserve_ratio
    available_cash = total_cash - reserved_cash
    
    target_positions = 8
    per_position_budget = available_cash / target_positions
    
    report = {
        "timestamp": datetime.now().isoformat(),
        "optimization": "v5.108 - Aggressive Mode",
        "current_cash": total_cash,
        "reserve_ratio": f"{reserve_ratio:.1%}",
        "reserved_cash": reserved_cash,
        "available_for_buying": available_cash,
        "target_positions": target_positions,
        "per_position_budget": per_position_budget,
        "recommendation": f"立即建仓 {target_positions} 只，每只约 ¥{per_position_budget:,.0f}"
    }
    
    return report


# ============================================
# 优化②: 入选阈值调整
# ============================================

def aggressive_threshold_config():
    """
    调整stock_picker中的confidence阈值
    
    改变:
    - ai_final_decision() 中的激进阈值: 45分 → 35分
    - multi_strategy_pick() 中的最低质量评分: 50分 → 30分
    """
    
    config_changes = {
        "ai_final_decision_threshold": {
            "old": 45,
            "new": 35,
            "reason": "降低入选标准，激活更多候选股"
        },
        "quality_score_minimum": {
            "old": 50,
            "new": 30,
            "reason": "扩大选股池，从45只 → 65-75只"
        },
        "max_per_trade": {
            "old": 3,
            "new": 5,
            "reason": "单次建仓数 3→5，加快持仓积累"
        }
    }
    
    return config_changes


# ============================================
# 优化③: 快速选股池优化
# ============================================

def fast_stock_selection():
    """
    基于v5.107热力图数据快速挑选股票
    
    优先级:
    1. 高情感评分期间的涨停板股 (>75分情感)
    2. 近5周胜率>60%的策略持仓
    3. 集中度<50%的多元化补充
    """
    
    priority = [
        {
            "rank": 1,
            "name": "涨停池高情感股",
            "condition": "情感评分 > 75",
            "expected_count": 5,
            "allocation_ratio": "40%"
        },
        {
            "rank": 2,
            "name": "高胜率策略股",
            "condition": "近5周胜率 > 60%",
            "expected_count": 8,
            "allocation_ratio": "35%"
        },
        {
            "rank": 3,
            "name": "多元化补充",
            "condition": "集中度补充 <50%",
            "expected_count": 10,
            "allocation_ratio": "25%"
        }
    ]
    
    return priority


# ============================================
# 优化④: 执行计划
# ============================================

def execution_plan():
    """生成具体执行步骤"""
    
    steps = [
        {
            "step": 1,
            "action": "修改ai_analyst.py",
            "change": "ai_final_decision() 阈值 45 → 35",
            "file": "ai_analyst.py",
            "line": "L150-160"
        },
        {
            "step": 2,
            "action": "修改stock_picker.py",
            "change": "quality_min_threshold 50 → 30",
            "file": "stock_picker.py",
            "line": "L2800-2850"
        },
        {
            "step": 3,
            "action": "修改position_manager.py",
            "change": "max_concurrent_buys 3 → 5",
            "file": "position_manager.py",
            "line": "L500-520"
        },
        {
            "step": 4,
            "action": "执行新建仓",
            "change": "运行 python3 daily_runner.py",
            "expected_result": "新增 5 只持仓"
        }
    ]
    
    return steps


# ============================================
# 主函数
# ============================================

def main():
    print("\n" + "="*60)
    print("🚀 v5.108 激进建仓模式优化")
    print("="*60 + "\n")
    
    # 优化①
    print("\n【优化①】持仓规划:")
    sizing = aggressive_position_sizing()
    for key, value in sizing.items():
        if key != 'timestamp':
            print(f"  {key}: {value}")
    
    # 优化②
    print("\n【优化②】阈值调整:")
    thresholds = aggressive_threshold_config()
    for param, change in thresholds.items():
        print(f"  {param}:")
        print(f"    旧值: {change['old']} → 新值: {change['new']}")
        print(f"    原因: {change['reason']}")
    
    # 优化③
    print("\n【优化③】快速选股优先级:")
    pools = fast_stock_selection()
    for pool in pools:
        print(f"  等级{pool['rank']}: {pool['name']}")
        print(f"    条件: {pool['condition']}")
        print(f"    预期数量: {pool['expected_count']}")
        print(f"    配置比例: {pool['allocation_ratio']}")
    
    # 优化④
    print("\n【优化④】执行步骤:")
    steps = execution_plan()
    for step in steps:
        print(f"  步骤{step['step']}: {step['action']}")
        print(f"    修改: {step['change']}")
        if 'expected_result' in step:
            print(f"    预期: {step['expected_result']}")
    
    print("\n" + "="*60)
    print("⚠️  注意: 此脚本仅输出优化建议")
    print("    需手动修改config.py/相关模块才能生效")
    print("="*60 + "\n")
    
    # 保存报告
    report = {
        "version": "v5.108",
        "timestamp": datetime.now().isoformat(),
        "sizing": sizing,
        "thresholds": thresholds,
        "priority": pools,
        "steps": steps
    }
    
    with open("v5_108_AGGRESSIVE_REPORT.json", "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"✅ 报告已保存: v5_108_AGGRESSIVE_REPORT.json\n")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
