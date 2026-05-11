"""
【v5.94 盘前优化 — Sharpe置信度自适应系统】

问题: v5.93中Sharpe倍数3.5x无条件应用，导致小样本策略权重过高
方案: 根据样本量对Sharpe权重进行置信度调整

核心逻辑:
  confidence_coeff = min(sample_size / 120, 1.0)  # 样本120为满置信
  adjusted_sharpe_multiplier = SHARPE_WEIGHT_MULTIPLIER_V3 * confidence_coeff
  
  样本量区间 | 置信系数 | Sharpe倍数 | 质量评级
  ---------|---------|----------|--------
  <30      | 0.25    | 0.875x   | 试验级 ⚠️
  30-60    | 0.50    | 1.75x    | 初步级 ⚡
  60-120   | 0.75    | 2.625x   | 稳定级 ✅
  >120     | 1.0     | 3.5x     | 成熟级 🔥
"""

import math
from typing import Dict, Tuple

# =================== v5.94 配置 ===================
V5_94_SHARPE_CONFIG = {
    'version': 'v5.94',
    'enabled': True,
    
    # Sharpe置信度参数
    'confidence_baseline': 120,  # 样本120为100%置信
    'base_sharpe_multiplier': 3.5,  # v5.93基础倍数
    'min_sample_size': 10,  # 最小样本(低于此忽略Sharpe)
    
    # 分级阈值
    'sample_thresholds': {
        'experimental': 30,   # <30: 试验级(系数0.25)
        'initial': 60,        # 30-60: 初步级(系数0.50)
        'stable': 120,        # 60-120: 稳定级(系数0.75)
        'mature': float('inf') # >120: 成熟级(系数1.0)
    },
    
    # 各级系数
    'confidence_coefficients': {
        'experimental': 0.25,
        'initial': 0.50,
        'stable': 0.75,
        'mature': 1.0
    }
}

def get_confidence_coefficient(sample_size: int) -> float:
    """根据样本量计算置信度系数"""
    cfg = V5_94_SHARPE_CONFIG
    
    # 样本过少，直接返回0(忽略Sharpe)
    if sample_size < cfg['min_sample_size']:
        return 0.0
    
    # 公式: min(样本/基线, 1.0)
    coeff = min(sample_size / cfg['confidence_baseline'], 1.0)
    return coeff

def get_confidence_level(sample_size: int) -> str:
    """获取置信度级别(用于日志)"""
    cfg = V5_94_SHARPE_CONFIG
    
    if sample_size < cfg['sample_thresholds']['experimental']:
        return 'experimental'
    elif sample_size < cfg['sample_thresholds']['initial']:
        return 'initial'
    elif sample_size < cfg['sample_thresholds']['stable']:
        return 'stable'
    else:
        return 'mature'

def adjust_sharpe_multiplier(
    base_multiplier: float,
    sample_size: int,
    strategy_name: str = ""
) -> Tuple[float, Dict[str, any]]:
    """
    调整Sharpe倍数 (根据样本量置信度)
    
    Args:
        base_multiplier: 基础倍数 (通常3.5x)
        sample_size: 策略样本数
        strategy_name: 策略名称(用于日志)
    
    Returns:
        (调整后倍数, 诊断信息dict)
    """
    cfg = V5_94_SHARPE_CONFIG
    coeff = get_confidence_coefficient(sample_size)
    level = get_confidence_level(sample_size)
    
    adjusted = base_multiplier * coeff
    
    diagnostic = {
        'strategy': strategy_name,
        'sample_size': sample_size,
        'confidence_level': level,
        'confidence_coeff': coeff,
        'base_multiplier': base_multiplier,
        'adjusted_multiplier': adjusted,
        'change_pct': (adjusted - base_multiplier) / base_multiplier * 100 if base_multiplier else 0
    }
    
    return adjusted, diagnostic

def apply_sharpe_adjustment_to_score(
    candidate_score: float,
    sharpe_ratio: float,
    sample_size: int,
    base_sharpe_multiplier: float = 3.5
) -> Tuple[float, Dict]:
    """
    在score_and_rank中应用Sharpe调整
    
    应用流程:
    1. 计算Sharpe置信系数
    2. 调整Sharpe倍数
    3. 重新计算Sharpe贡献分
    4. 更新候选总分
    
    Args:
        candidate_score: 原始候选分
        sharpe_ratio: Sharpe比率
        sample_size: 样本数
        base_sharpe_multiplier: 基础倍数
    
    Returns:
        (调整后分数, 调整信息)
    """
    adjusted_multiplier, diagnostic = adjust_sharpe_multiplier(
        base_sharpe_multiplier, sample_size
    )
    
    # 原始Sharpe贡献 vs 调整后贡献
    original_sharpe_contribution = sharpe_ratio * base_sharpe_multiplier
    adjusted_sharpe_contribution = sharpe_ratio * adjusted_multiplier
    sharpe_adjustment = adjusted_sharpe_contribution - original_sharpe_contribution
    
    # 总分调整
    adjusted_total_score = candidate_score + sharpe_adjustment
    
    adjustment_info = {
        **diagnostic,
        'original_sharpe_contribution': original_sharpe_contribution,
        'adjusted_sharpe_contribution': adjusted_sharpe_contribution,
        'sharpe_adjustment': sharpe_adjustment,
        'original_score': candidate_score,
        'adjusted_score': adjusted_total_score,
        'score_change': sharpe_adjustment
    }
    
    return adjusted_total_score, adjustment_info

# =================== 集成检查清单 ===================
def validate_sharpe_adjustment():
    """验证Sharpe调整系统完整性"""
    print("【v5.94 Sharpe置信度调整 — 验证】")
    print("-" * 50)
    
    # 测试样本
    test_samples = [10, 30, 60, 120, 200]
    print("\n样本量 | 置信系数 | Sharpe倍数 | 级别")
    print("------|---------|----------|--------")
    
    for sample in test_samples:
        coeff = get_confidence_coefficient(sample)
        multiplier = 3.5 * coeff
        level = get_confidence_level(sample)
        print(f"{sample:5} | {coeff:7.2%} | {multiplier:8.2f}x | {level:6s}")
    
    print("\n✅ v5.94 Sharpe置信度系统已就绪")

if __name__ == '__main__':
    validate_sharpe_adjustment()
