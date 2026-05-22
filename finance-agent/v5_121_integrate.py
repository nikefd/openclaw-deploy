#!/usr/bin/env python3
"""
v5.121 集成脚本 - 将优化应用到config.py, stock_picker.py, position_manager.py
"""

import re
import shutil
from datetime import datetime

def backup_file(filepath):
    """备份文件"""
    backup_path = f"{filepath}.backup_v5.121_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy(filepath, backup_path)
    return backup_path

def integrate_config_changes():
    """集成config.py配置变更"""
    print("\n【1】修改config.py...")
    
    config_path = 'config.py'
    backup = backup_file(config_path)
    print(f"  ✓ 备份到: {backup}")
    
    with open(config_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    changes = [
        # 改动1: ENTRY_QUALITY_THRESHOLD 20→18
        (
            r'ENTRY_QUALITY_THRESHOLD = 20\s+# v5\.120:',
            'ENTRY_QUALITY_THRESHOLD = 18  # v5.121: 20→18 (-10%, 激进建仓)',
            'ENTRY_QUALITY_THRESHOLD: 20→18'
        ),
        # 改动2: KELLY_COEFFICIENT 1.45→1.52
        (
            r'KELLY_COEFFICIENT = 1\.45\s+# Kelly系数',
            'KELLY_COEFFICIENT = 1.52  # Kelly系数 (v5.121: 1.45→1.52, +4.8%激进)',
            'KELLY_COEFFICIENT: 1.45→1.52'
        ),
        # 改动3: MAX_POSITIONS 12→15
        (
            r'MAX_POSITIONS = 12\s+# v5\.109:',
            'MAX_POSITIONS = 15  # v5.121: 12→15 (资金利用75-85%)',
            'MAX_POSITIONS: 12→15'
        ),
        # 改动4: MIN_CASH_RATIO 0.05→0.03
        (
            r'MIN_CASH_RATIO = 0\.05\s+# v5\.115:',
            'MIN_CASH_RATIO = 0.03  # v5.121: 5%→3% (激进建仓)',
            'MIN_CASH_RATIO: 0.05→0.03'
        ),
        # 改动5: KELLY_MAX_POSITION 0.038→0.042
        (
            r'KELLY_MAX_POSITION = 0\.038\s+# Kelly最大仓位',
            'KELLY_MAX_POSITION = 0.042  # Kelly最大仓位 (v5.121: +10.5%)',
            'KELLY_MAX_POSITION: 0.038→0.042'
        ),
    ]
    
    for pattern, replacement, desc in changes:
        new_content = re.sub(pattern, replacement, content)
        if new_content != content:
            content = new_content
            print(f"  ✓ {desc}")
        else:
            print(f"  ⚠ {desc} (未找到匹配, 可能已修改)")
    
    with open(config_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"  ✅ config.py修改完成")


def add_sector_routing_to_config():
    """添加赛道路由到config.py"""
    print("\n【2】添加赛道路由到config.py...")
    
    config_path = 'config.py'
    
    with open(config_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # 查找合适的位置插入 (在SECTOR_STRATEGY_ROUTING之后)
    insert_idx = None
    for i, line in enumerate(lines):
        if 'SECTOR_STRATEGY_ROUTING = {' in line:
            # 找到section末尾
            brace_count = 0
            for j in range(i, len(lines)):
                brace_count += lines[j].count('{') - lines[j].count('}')
                if brace_count == 0 and j > i:
                    insert_idx = j + 1
                    break
    
    if insert_idx:
        new_section = """
# =================== v5.121: 赛道入场质量阈值 + Kelly倍数 ===================
# 基于回测数据的赛道差异化配置
SECTOR_QUALITY_THRESHOLDS = {
    '科技成长': 22,      # MACD+RSI最优(17.1%) - 要求高
    '新能源': 18,        # MACD+RSI次优(14.66%) - 趋势强
    '消费白马': 20,      # MULTI_FACTOR防御(6.61%) - 稳定性
    '金融周期': 19,      # 中等要求
    '其他': 20           # 默认
}

SECTOR_KELLY_MULTIPLIERS = {
    '科技成长': 1.0,     # 基础Kelly系数
    '新能源': 0.95,      # 略保守
    '消费白马': 0.85,    # 防御型保守
    '金融周期': 0.90,    # 中等保守
    '其他': 0.80         # 默认保守
}

# =================== v5.121: Sharpe分级风险管理 ===================
SHARPE_GRADED_RISK = {
    'high': {
        'threshold': 2.0,
        'position_multiplier': 1.3,
        'stop_loss': -0.10
    },
    'medium': {
        'threshold': 1.5,
        'position_multiplier': 1.15,
        'stop_loss': -0.09
    },
    'normal': {
        'threshold': 1.0,
        'position_multiplier': 1.0,
        'stop_loss': -0.08
    },
    'low': {
        'threshold': 0.5,
        'position_multiplier': 0.75,
        'stop_loss': -0.07
    }
}

"""
        lines.insert(insert_idx, new_section)
        
        with open(config_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        
        print(f"  ✅ 赛道路由配置已添加到config.py")
    else:
        print(f"  ⚠ 未找到合适的插入位置")


def create_v5_121_integration_module():
    """创建v5.121集成模块"""
    print("\n【3】创建v5.121集成模块...")
    
    content = '''"""
v5.121 集成模块 - Sharpe分级管理 + 赛道智能路由 + 动态入场
"""

import config

class V5_121_SectorRouter:
    """赛道智能路由"""
    
    @staticmethod
    def get_quality_threshold(sector):
        """获取赛道入场质量阈值"""
        return config.SECTOR_QUALITY_THRESHOLDS.get(sector, 20)
    
    @staticmethod
    def get_kelly_multiplier(sector):
        """获取赛道Kelly倍数"""
        return config.SECTOR_KELLY_MULTIPLIERS.get(sector, 0.80)


class V5_121_SharpeGradedRisk:
    """Sharpe分级风险管理"""
    
    @staticmethod
    def get_risk_config(sharpe_ratio):
        """根据Sharpe值获取风险配置"""
        if sharpe_ratio >= 2.0:
            return config.SHARPE_GRADED_RISK['high']
        elif sharpe_ratio >= 1.5:
            return config.SHARPE_GRADED_RISK['medium']
        elif sharpe_ratio >= 1.0:
            return config.SHARPE_GRADED_RISK['normal']
        else:
            return config.SHARPE_GRADED_RISK['low']
    
    @staticmethod
    def adjust_stop_loss(base_stop_loss, sharpe_ratio):
        """根据Sharpe调整止损"""
        config = V5_121_SharpeGradedRisk.get_risk_config(sharpe_ratio)
        return config['stop_loss']
    
    @staticmethod
    def adjust_position_size(base_size, sharpe_ratio):
        """根据Sharpe调整仓位"""
        config = V5_121_SharpeGradedRisk.get_risk_config(sharpe_ratio)
        return base_size * config['position_multiplier']


class V5_121_DynamicEntryQuality:
    """动态入场质量系统"""
    
    @staticmethod
    def get_threshold(market_emotion, cash_ratio, sector='其他'):
        """获取动态入场质量阈值"""
        # 基础阈值 (赛道特定)
        base = V5_121_SectorRouter.get_quality_threshold(sector)
        
        # 情绪调整
        if market_emotion > 90:
            emotion_adj = +8
        elif market_emotion > 85:
            emotion_adj = +5
        elif market_emotion > 70:
            emotion_adj = +2
        elif market_emotion < 30:
            emotion_adj = -3
        else:
            emotion_adj = 0
        
        # 现金调整
        if cash_ratio > 0.95:
            cash_adj = -5
        elif cash_ratio > 0.85:
            cash_adj = -3
        elif cash_ratio > 0.70:
            cash_adj = -1
        else:
            cash_adj = 0
        
        threshold = max(12, base + emotion_adj + cash_adj)
        return threshold


class V5_121_KellyOptimizer:
    """Kelly系数优化器"""
    
    @staticmethod
    def get_optimized_kelly(sector='其他'):
        """获取赛道优化的Kelly系数"""
        base_kelly = config.KELLY_COEFFICIENT  # 1.52
        sector_multiplier = V5_121_SectorRouter.get_kelly_multiplier(sector)
        return base_kelly * sector_multiplier
'''
    
    with open('v5_121_integration.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"  ✅ v5_121_integration.py创建完成")


def main():
    """主函数"""
    print("\n" + "=" * 80)
    print("v5.121 配置集成脚本")
    print("=" * 80)
    
    try:
        integrate_config_changes()
        add_sector_routing_to_config()
        create_v5_121_integration_module()
        
        print("\n" + "=" * 80)
        print("✅ v5.121集成完成!")
        print("=" * 80)
        print("\n下一步:")
        print("  1. 在stock_picker.py中导入v5_121_integration")
        print("  2. 在position_manager.py中使用Sharpe分级管理")
        print("  3. 测试确保无破坏")
        print("  4. 部署到openclaw-deploy")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
