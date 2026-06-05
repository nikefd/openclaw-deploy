#!/usr/bin/env python3
"""
v5.154 配置集成 - 將三個改進融入系統
"""

import sys
sys.path.insert(0, '/home/nikefd/finance-agent')

from v5_154_premarket_optimize import (
    ExtremeGreedDefenseSystem,
    SharpeAdaptiveKelly,
    LayeredCacheSystem,
)

def integrate_v5_154_to_config():
    """
    將v5.154的改進集成到config.py
    """
    
    # 第1步: 讀取現有config
    with open('/home/nikefd/finance-agent/config.py', 'r', encoding='utf-8') as f:
        config_content = f.read()
    
    # 第2步: 檢查是否已經有v5.154標記
    if 'v5_154_INTEGRATED' in config_content:
        print("⚠️  v5.154已集成，跳過")
        return
    
    # 第3步: 準備新增的配置段
    new_config_segment = '''

# =============================================================================
# v5.154 盤前優化① - 極度貪婪防御 + Sharpe動態Kelly + 分層緩存
# =============================================================================
# v5_154_INTEGRATED: True
# 改進: 
#   ① 極度貪婪(>92分)時自動啟動防御機制
#   ② Sharpe動態調整Kelly倍數
#   ③ 分層緩存 (熱選股2min, 冷備選8min, 指標10min)

# 極度貪婪防御等級配置
# 當市場情緒指數達到某個閾值時自動調整參數
EXTREME_GREED_DEFENSE_LEVELS = {
    'level_1': {  # 中等貪婪 (85-92)
        'sentiment_threshold': (85, 92),
        'entry_quality_threshold': 18,     # +20%
        'max_positions': 12,               # -20%
        'max_single_position': 0.035,      # -12.5%
        'kelly_multiplier': 0.85,          # -15%
        'aggressive_ratio': 0.45,          # -10%
        'cash_reserve': 0.15,              # +50%
    },
    'level_2': {  # 強貪婪 (92-94)
        'sentiment_threshold': (92, 94),
        'entry_quality_threshold': 22,     # +47%
        'max_positions': 10,               # -33%
        'max_single_position': 0.03,       # -25%
        'kelly_multiplier': 0.70,          # -30%
        'aggressive_ratio': 0.40,          # -20%
        'cash_reserve': 0.20,              # +100%
    },
    'level_3': {  # 超強貪婪 (94-96)
        'sentiment_threshold': (94, 96),
        'entry_quality_threshold': 28,     # +87%
        'max_positions': 8,                # -47%
        'max_single_position': 0.025,      # -37.5%
        'kelly_multiplier': 0.55,          # -45%
        'aggressive_ratio': 0.35,          # -30%
        'cash_reserve': 0.25,              # +150%
    },
    'level_4': {  # 極限貪婪 (96+)
        'sentiment_threshold': (96, 100),
        'entry_quality_threshold': 35,     # +133%
        'max_positions': 5,                # -67%
        'max_single_position': 0.02,       # -50%
        'kelly_multiplier': 0.40,          # -60%
        'aggressive_ratio': 0.25,          # -50%
        'cash_reserve': 0.30,              # +200%
    },
}

# Sharpe動態Kelly系數
# 當市場Sharpe比率變化時自動調整Kelly倍數
# 公式: dynamic_kelly = base_kelly × (current_sharpe / base_sharpe)
SHARPE_ADAPTIVE_KELLY = {
    'enabled': True,
    'base_sharpe': 2.35,  # v5.153的基準Sharpe
    'sector_base_kelly': {
        'tech': 1.8,
        'energy': 1.6,
        'white_horse': 1.2,
        'default': 1.5,
    },
    'kelly_bounds': {
        'min': 0.3,  # 下限保護 (極端市場)
        'max': 2.0,  # 上限保護 (過度激進)
    },
}

# 分層緩存配置 (v5.154)
LAYERED_CACHE_CONFIG = {
    'enabled': True,
    'ttl_seconds': {
        'hot_picks': 120,       # 熱選股: 2分鐘
        'cold_candidates': 480, # 冷備選: 8分鐘
        'indicators': 600,      # 技術指標: 10分鐘
        'market_data': 60,      # 市場數據: 1分鐘
    },
    'premarket_warmup': {
        'enabled': True,
        'start_hour': 7,         # UTC 7:00 (北京時間15:00)
        'end_hour': 8,           # UTC 8:00 (北京時間16:00)
        'warmup_items': ['hot_picks', 'indicators'],  # 預熱項目
    },
}
'''
    
    # 第4步: 在config最後加入新段
    config_content += new_config_segment
    
    # 第5步: 寫回配置檔
    with open('/home/nikefd/finance-agent/config.py', 'a', encoding='utf-8') as f:
        f.write(new_config_segment)
    
    print("✅ v5.154配置集成成功")
    print("   - 極度貪婪防御等級: 4個")
    print("   - Sharpe動態Kelly: 已啟用")
    print("   - 分層緩存: 已啟用(盤前預熱)")
    
    return True


if __name__ == '__main__':
    integrate_v5_154_to_config()
    print("\n✅ 配置集成完成，v5.154已整合至系統")
