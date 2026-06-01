#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v5.141 配置集成方案
将3个新模块的配置集成到 config.py
"""

import json
from typing import Dict

# 新增配置字段
V5_141_CONFIG_ADDON = {
    # ==================== 信号融合引擎 v2.0 ====================
    'SIGNAL_FUSION_ENABLED': True,
    'DYNAMIC_WEIGHT_OPTIMIZATION': True,
    
    # 基础权重配置
    'BASE_SIGNAL_WEIGHTS': {
        'technical': 0.40,
        'funding': 0.30,
        'sentiment': 0.20,
        'fundamental': 0.10,
    },
    
    # 情绪状态权重矩阵 (核心)
    'EMOTION_WEIGHT_MATRIX': {
        'extreme_greed': {
            'technical': 0.30,
            'funding': 0.40,
            'sentiment': 0.20,
            'fundamental': 0.10,
        },
        'greed': {
            'technical': 0.35,
            'funding': 0.35,
            'sentiment': 0.20,
            'fundamental': 0.10,
        },
        'neutral': {
            'technical': 0.45,
            'funding': 0.25,
            'sentiment': 0.15,
            'fundamental': 0.15,
        },
        'fear': {
            'technical': 0.45,
            'funding': 0.25,
            'sentiment': 0.10,
            'fundamental': 0.20,
        },
        'extreme_fear': {
            'technical': 0.40,
            'funding': 0.25,
            'sentiment': 0.05,
            'fundamental': 0.30,
        },
    },
    
    # ==================== AI补偿评分系统 ====================
    'AI_COMPENSATION_ENABLED': True,
    'COMPENSATION_BASE_SCORE': 20,
    
    'COMPENSATION_WEIGHTS': {
        'volume_surge': 0.25,
        'institutional_activity': 0.20,
        'margin_buying': 0.10,
        'emotion_correlation': 0.15,
        'sector_momentum': 0.10,
    },
    
    'COMPENSATION_THRESHOLDS': {
        'volume_surge_multiplier': 1.5,
        'institutional_min_count': 3,
        'margin_increase_pct': 0.03,
        'correlation_threshold': 0.65,
        'sector_momentum_pct': 0.70,
    },
    
    # ==================== 市场状态机 ====================
    'STATE_MACHINE_ENABLED': True,
    
    'STATE_CONFIGS': {
        'extreme_greed': {
            'max_positions': 3,
            'position_size': 0.10,
            'add_position_enabled': False,
            'new_entry_enabled': False,
            'trailing_stop_pct': 0.025,
            'kelly_coefficient': 1.35,
            'min_cash_ratio': 0.15,
            'entry_quality_threshold': 25,
        },
        'greed': {
            'max_positions': 5,
            'position_size': 0.12,
            'add_position_enabled': True,
            'add_position_limit': 0.5,
            'new_entry_enabled': True,
            'trailing_stop_pct': 0.04,
            'kelly_coefficient': 1.60,
            'min_cash_ratio': 0.08,
            'entry_quality_threshold': 15,
        },
        'neutral': {
            'max_positions': 8,
            'position_size': 0.15,
            'add_position_enabled': True,
            'add_position_limit': 1.0,
            'new_entry_enabled': True,
            'trailing_stop_pct': 0.05,
            'kelly_coefficient': 1.75,
            'min_cash_ratio': 0.05,
            'entry_quality_threshold': 12,
        },
        'fear': {
            'max_positions': 10,
            'position_size': 0.08,
            'add_position_enabled': True,
            'add_position_limit': 2.0,
            'new_entry_enabled': True,
            'bottom_fish_enabled': True,
            'trailing_stop_pct': 0.06,
            'kelly_coefficient': 1.90,
            'min_cash_ratio': 0.02,
            'entry_quality_threshold': 8,
        },
        'extreme_fear': {
            'max_positions': 12,
            'position_size': 0.06,
            'add_position_enabled': True,
            'add_position_limit': 3.0,
            'new_entry_enabled': True,
            'bottom_fish_enabled': True,
            'all_in_enabled': True,
            'trailing_stop_pct': 0.08,
            'kelly_coefficient': 2.00,
            'min_cash_ratio': 0.00,
            'entry_quality_threshold': 5,
        },
    },
    
    # ==================== 融合参数 ====================
    'SIGNAL_FUSION_WEIGHTS_V141': {
        'technical': 0.40,
        'funding': 0.30,
        'sentiment': 0.20,
        'fundamental': 0.10,
    },
    
    'AI_COMPENSATION_FUSION_WEIGHT': 0.25,  # 信号75% + AI补偿25%
    'SIGNAL_FUSION_WEIGHT': 0.75,
}


def generate_config_integration_code() -> str:
    """
    生成配置集成代码 (供config.py集成)
    """
    code = '''
# ==================== v5.141 深度优化配置 ====================
# 生成时间: 2026-05-29 22:00
# 模块: 信号融合引擎 v2.0 + AI补偿 + 市场状态机

# 启用新优化功能
SIGNAL_FUSION_ENABLED = True
DYNAMIC_WEIGHT_OPTIMIZATION = True
AI_COMPENSATION_ENABLED = True
STATE_MACHINE_ENABLED = True

# -------- 信号融合引擎 --------
BASE_SIGNAL_WEIGHTS = {
    'technical': 0.40,
    'funding': 0.30,
    'sentiment': 0.20,
    'fundamental': 0.10,
}

# 情绪状态权重矩阵 (动态权重核心)
EMOTION_WEIGHT_MATRIX = {
    'extreme_greed': {
        'technical': 0.30,
        'funding': 0.40,
        'sentiment': 0.20,
        'fundamental': 0.10,
    },
    'greed': {
        'technical': 0.35,
        'funding': 0.35,
        'sentiment': 0.20,
        'fundamental': 0.10,
    },
    'neutral': {
        'technical': 0.45,
        'funding': 0.25,
        'sentiment': 0.15,
        'fundamental': 0.15,
    },
    'fear': {
        'technical': 0.45,
        'funding': 0.25,
        'sentiment': 0.10,
        'fundamental': 0.20,
    },
    'extreme_fear': {
        'technical': 0.40,
        'funding': 0.25,
        'sentiment': 0.05,
        'fundamental': 0.30,
    },
}

# -------- AI补偿评分系统 --------
COMPENSATION_BASE_SCORE = 20
COMPENSATION_WEIGHTS = {
    'volume_surge': 0.25,
    'institutional_activity': 0.20,
    'margin_buying': 0.10,
    'emotion_correlation': 0.15,
    'sector_momentum': 0.10,
}

COMPENSATION_THRESHOLDS = {
    'volume_surge_multiplier': 1.5,
    'institutional_min_count': 3,
    'margin_increase_pct': 0.03,
    'correlation_threshold': 0.65,
    'sector_momentum_pct': 0.70,
}

# -------- 市场状态机 --------
STATE_CONFIGS = {
    'extreme_greed': {
        'max_positions': 3,
        'position_size': 0.10,
        'add_position_enabled': False,
        'new_entry_enabled': False,
        'trailing_stop_pct': 0.025,
        'kelly_coefficient': 1.35,
        'min_cash_ratio': 0.15,
        'entry_quality_threshold': 25,
    },
    'greed': {
        'max_positions': 5,
        'position_size': 0.12,
        'add_position_enabled': True,
        'add_position_limit': 0.5,
        'new_entry_enabled': True,
        'trailing_stop_pct': 0.04,
        'kelly_coefficient': 1.60,
        'min_cash_ratio': 0.08,
        'entry_quality_threshold': 15,
    },
    'neutral': {
        'max_positions': 8,
        'position_size': 0.15,
        'add_position_enabled': True,
        'add_position_limit': 1.0,
        'new_entry_enabled': True,
        'trailing_stop_pct': 0.05,
        'kelly_coefficient': 1.75,
        'min_cash_ratio': 0.05,
        'entry_quality_threshold': 12,
    },
    'fear': {
        'max_positions': 10,
        'position_size': 0.08,
        'add_position_enabled': True,
        'add_position_limit': 2.0,
        'new_entry_enabled': True,
        'bottom_fish_enabled': True,
        'trailing_stop_pct': 0.06,
        'kelly_coefficient': 1.90,
        'min_cash_ratio': 0.02,
        'entry_quality_threshold': 8,
    },
    'extreme_fear': {
        'max_positions': 12,
        'position_size': 0.06,
        'add_position_enabled': True,
        'add_position_limit': 3.0,
        'new_entry_enabled': True,
        'bottom_fish_enabled': True,
        'all_in_enabled': True,
        'trailing_stop_pct': 0.08,
        'kelly_coefficient': 2.00,
        'min_cash_ratio': 0.00,
        'entry_quality_threshold': 5,
    },
}

# -------- 融合参数 --------
AI_COMPENSATION_FUSION_WEIGHT = 0.25  # 信号75% + AI补偿25%
SIGNAL_FUSION_WEIGHT = 0.75
    '''
    return code


if __name__ == '__main__':
    print("=" * 80)
    print("v5.141 配置集成方案")
    print("=" * 80)
    
    # 输出配置字典
    print("\n📋 新增配置字典:")
    print(json.dumps(V5_141_CONFIG_ADDON, indent=2))
    
    # 输出集成代码
    print("\n" + "=" * 80)
    print("📝 集成代码 (添加到config.py):")
    print("=" * 80)
    print(generate_config_integration_code())
    
    print("\n✅ 配置集成方案生成完成")
