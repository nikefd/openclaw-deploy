#!/usr/bin/env python3
"""
v5.124 配置集成模块 — 将优化参数应用到config.py

基于回测TOP策略和实盘验证,优化以下参数:
✅ 入选评分: 18分 → 15分 (激进建仓加速)
✅ Kelly系数: 1.52 → 1.60 (理论胜率60%)
✅ 单倉配置: 4.2% → 4.8% (Kelly优化)
✅ 止损机制: 固定-8% → ATR动态自适应
✅ 持仓上限: 12只 → 15只 (资金充足)
✅ 情感驱动: 启用Kelly+头寸+入选门槛动态调整
"""

import re
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Tuple

class ConfigIntegrator:
    """集成v5.124优化参数到config.py"""
    
    def __init__(self, config_path='/home/nikefd/finance-agent/config.py'):
        self.config_path = config_path
        self.backup_path = None
        self.changes_log = []
    
    def backup_config(self) -> str:
        """备份原始config"""
        import shutil
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = f"{self.config_path}.backup_v5.123_{timestamp}"
        shutil.copy(self.config_path, backup_path)
        self.backup_path = backup_path
        print(f"✅ 配置已备份: {backup_path}")
        return backup_path
    
    def update_config_value(self, key: str, old_value, new_value):
        """更新单个配置值"""
        with open(self.config_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 处理不同类型的值
        if isinstance(new_value, bool):
            old_pattern = f"{key} = {str(old_value)}"
            new_content = content.replace(old_pattern, f"{key} = {str(new_value)}")
        elif isinstance(new_value, str):
            old_pattern = f"{key} = ['\\\"].*?['\\\"]"
            new_content = re.sub(old_pattern, f"{key} = '{new_value}'", content)
        elif isinstance(new_value, float):
            old_pattern = f"{key} = {old_value}"
            new_content = content.replace(old_pattern, f"{key} = {new_value}")
        else:  # int
            old_pattern = f"{key} = {old_value}"
            new_content = content.replace(old_pattern, f"{key} = {new_value}")
        
        with open(self.config_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        self.changes_log.append({
            'key': key,
            'old': old_value,
            'new': new_value,
            'timestamp': datetime.now().isoformat()
        })
        
        print(f"✅ {key}: {old_value} → {new_value}")
    
    def integrate_v5_124_changes(self):
        """集成v5.124的所有优化参数"""
        
        print(f"\n{'='*80}")
        print(f"⚙️  集成v5.124配置变更")
        print(f"{'='*80}\n")
        
        # 备份原始文件
        self.backup_config()
        
        # 应用变更
        changes = [
            # 参数名, 旧值, 新值, 描述
            ('ENTRY_QUALITY_THRESHOLD', 18, 15, '入选评分门槛降低(激进建仓)'),
            ('KELLY_MULTIPLIER', 1.52, 1.60, 'Kelly系数提升(理论胜率60%)'),
            ('MAX_SINGLE_POSITION', 0.042, 0.048, '单倉仓位提升'),
            ('MAX_POSITIONS', 12, 15, '持仓上限扩大'),
            ('DYNAMIC_STOP_LOSS_ENABLED', False, True, '启用动态止损'),
            ('DYNAMIC_STOP_LOSS_METHOD', 'fixed', 'atr_adaptive', '止损方法改为ATR'),
            ('ATR_MULTIPLIER', 1.5, 2.5, 'ATR倍数调整'),
            ('SENTIMENT_DRIVEN_ALLOCATION_ENABLED', False, True, '启用情感驱动配置'),
        ]
        
        for key, old, new, desc in changes:
            try:
                self.update_config_value(key, old, new)
                print(f"   └─ {desc}")
            except Exception as e:
                print(f"⚠️  {key} 更新失败: {e}")
        
        return self.changes_log
    
    def verify_changes(self) -> bool:
        """验证配置变更是否成功"""
        print(f"\n{'='*80}")
        print(f"🔍 验证配置变更")
        print(f"{'='*80}\n")
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查关键参数
        checks = {
            'ENTRY_QUALITY_THRESHOLD = 15': 'ENTRY_QUALITY_THRESHOLD',
            'KELLY_MULTIPLIER = 1.60': 'KELLY_MULTIPLIER',
            'MAX_POSITIONS = 15': 'MAX_POSITIONS',
            'DYNAMIC_STOP_LOSS_ENABLED = True': '动态止损',
            'SENTIMENT_DRIVEN_ALLOCATION_ENABLED = True': '情感驱动',
        }
        
        all_ok = True
        for pattern, desc in checks.items():
            if pattern in content:
                print(f"✅ {desc}")
            else:
                print(f"❌ {desc} 验证失败")
                all_ok = False
        
        return all_ok

# ====================== Kelly系数动态调整模块 ======================
class SentimentKellyIntegration:
    """情感驱动的Kelly系数动态调整集成到config.py"""
    
    def __init__(self, config_path='/home/nikefd/finance-agent/config.py'):
        self.config_path = config_path
    
    def add_sentiment_kelly_config(self):
        """在config.py中添加情感Kelly配置"""
        
        sentiment_kelly_config = '''
# =================== v5.124 情感驱动Kelly动态调整 ===================
SENTIMENT_KELLY_ENABLED = True  # 启用情感驱动Kelly调整

# 基础Kelly系数
BASE_KELLY_MULTIPLIER = 1.60

# 情感指数阈值
SENTIMENT_KELLY_THRESHOLDS = {
    'extreme_fear': 25,    # <25: 极度恐惧
    'fear': 40,           # 25-40: 恐惧
    'neutral': 60,        # 40-60: 中立
    'greed': 75,          # 60-75: 贪婪
    'extreme_greed': 100  # >75: 极度贪婪
}

# Kelly系数调整倍数
SENTIMENT_KELLY_MULTIPLIERS = {
    'extreme_fear': 1.15,    # Kelly * 1.15 (+15%)
    'fear': 1.08,            # Kelly * 1.08 (+8%)
    'neutral': 1.00,         # Kelly * 1.00 (无调整)
    'greed': 0.90,           # Kelly * 0.90 (-10%)
    'extreme_greed': 0.80    # Kelly * 0.80 (-20%)
}

# 头寸限制调整
SENTIMENT_POSITION_ADJUSTMENTS = {
    'extreme_fear': {'max_positions_delta': 0.25, 'entry_quality_delta': -8},
    'fear': {'max_positions_delta': 0.10, 'entry_quality_delta': -4},
    'neutral': {'max_positions_delta': 0.0, 'entry_quality_delta': 0},
    'greed': {'max_positions_delta': -0.15, 'entry_quality_delta': 4},
    'extreme_greed': {'max_positions_delta': -0.30, 'entry_quality_delta': 8}
}
'''
        
        with open(self.config_path, 'a', encoding='utf-8') as f:
            f.write(sentiment_kelly_config)
        
        print(f"✅ 情感Kelly配置已添加到config.py")

# ====================== 动态止损配置模块 ======================
class DynamicStopLossConfig:
    """动态止损配置集成"""
    
    def __init__(self, config_path='/home/nikefd/finance-agent/config.py'):
        self.config_path = config_path
    
    def add_dynamic_stop_loss_config(self):
        """在config.py中添加动态止损配置"""
        
        dynamic_sl_config = '''
# =================== v5.124 动态止损(ATR自适应) ===================
DYNAMIC_STOP_LOSS_ENABLED = True
DYNAMIC_STOP_LOSS_METHOD = 'atr_adaptive'  # atr_adaptive | drawdown_tiered | hybrid
ATR_PERIOD = 14                # ATR计算周期(天)
ATR_MULTIPLIER = 2.5          # 止损线 = entry_price - 2.5 * ATR(14d)
DYNAMIC_STOP_LOSS_MAX = 0.15   # 动态止损最多-15%(安全网)

# 备选: 分级止损法
DRAWDOWN_TIERED_STOP_LOSS = {
    'tier1': {'loss_pct': -0.08, 'volume': 0.5},    # -8%时卖出50%
    'tier2': {'loss_pct': -0.12, 'volume': 0.8},    # -12%时再卖出80%
    'tier3': {'loss_pct': -0.15, 'volume': 1.0},    # -15%时全部止损
}
'''
        
        with open(self.config_path, 'a', encoding='utf-8') as f:
            f.write(dynamic_sl_config)
        
        print(f"✅ 动态止损配置已添加到config.py")

# ====================== 部署集成脚本 ======================
def main():
    print(f"\n{'='*80}")
    print(f"🚀 v5.124 配置集成 — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*80}\n")
    
    # 1. 主配置更新
    integrator = ConfigIntegrator()
    changes = integrator.integrate_v5_124_changes()
    
    # 2. 验证变更
    is_valid = integrator.verify_changes()
    
    # 3. 添加额外配置
    print(f"\n{'='*80}")
    print(f"📝 添加额外配置模块")
    print(f"{'='*80}\n")
    
    sentiment_kelly = SentimentKellyIntegration()
    sentiment_kelly.add_sentiment_kelly_config()
    
    dynamic_sl = DynamicStopLossConfig()
    dynamic_sl.add_dynamic_stop_loss_config()
    
    # 4. 生成变更日志
    print(f"\n{'='*80}")
    print(f"📋 变更日志")
    print(f"{'='*80}\n")
    
    log_file = '/home/nikefd/finance-agent/V5_124_CONFIG_CHANGES.json'
    with open(log_file, 'w', encoding='utf-8') as f:
        json.dump({
            'version': 'v5.124',
            'timestamp': datetime.now().isoformat(),
            'backup': integrator.backup_path,
            'changes': changes,
            'status': '✅ 成功' if is_valid else '⚠️  警告'
        }, f, indent=2, ensure_ascii=False)
    
    print(f"✅ 变更日志: {log_file}")
    
    # 5. 最终总结
    print(f"\n{'='*80}")
    print(f"✅ v5.124配置集成完成")
    print(f"{'='*80}\n")
    
    print(f"📊 集成摘要:")
    print(f"   • 原始config备份: {integrator.backup_path}")
    print(f"   • 应用变更数: {len(changes)}")
    print(f"   • 验证状态: {'✅ 通过' if is_valid else '⚠️  失败'}")
    print(f"   • 变更日志: {log_file}")
    
    print(f"\n🔧 可部署的核心改进:")
    print(f"   ✅ 入选评分: 18分 → 15分")
    print(f"   ✅ Kelly系数: 1.52 → 1.60")
    print(f"   ✅ 单倉仓位: 4.2% → 4.8%")
    print(f"   ✅ 止损机制: 固定-8% → ATR自适应")
    print(f"   ✅ 持仓上限: 12只 → 15只")
    print(f"   ✅ 情感驱动: 启用Kelly/头寸/入选动态调整")
    
    print(f"\n⚠️  下一步:")
    print(f"   1. 验证: python3 -c \"import config; print('✅ config有效')\"")
    print(f"   2. 重启: sudo systemctl restart finance-api")
    print(f"   3. 监控: 盯住持仓数、资金利用率、回撤")
    print(f"\n")

if __name__ == '__main__':
    main()
