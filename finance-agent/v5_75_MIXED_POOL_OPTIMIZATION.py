"""
v5.75: 混合池策略重构 + MACD参数精优 + 快速选股模式

【目标】
1. 混合池策略重构: 摆脱白马消费低效约束，改用科技/新能源组合
   - 当前混合池: 5.06% 收益，0.86 Sharpe
   - 目标混合池: 8-10% 收益，1.2+ Sharpe
   - 方案: 混合池选股时按回测权重 (科技1.8x, 新能源1.5x, 消费0.5x) 加权
   
2. MACD+RSI参数精优: 在科技赛道表现好(17.1% 收益，2.35 Sharpe)，尝试跨赛道微调
   - 科技赛道最优: MACD(12,26,9) + RSI(14)
   - 新能源赛道: 尝试加快MACD速度 → MACD(10,24,7)
   - 消费赛道: 保守参数 → MACD(14,28,9) + RSI(16)
   
3. 快速选股模式: 高现金时(>90%)快速完成选股，不超过10秒
   - 策略: 缓存前50只高质量候选，快速排序而非全量回测
   - 激活条件: 现金>90% & 选股耗时>5秒自动激活
"""

import time
import json
from collections import defaultdict
from datetime import datetime

# =================== 混合池赛道权重精优 ===================

MIXED_POOL_SECTOR_WEIGHTS_V75 = {
    '科技成长': {
        'weight': 2.0,           # v5.75提升: 1.8x → 2.0x (+11%)
        'strategy': 'MACD_RSI',
        'sharpe_target': 2.35,
        'expected_return': 0.17,
        'rationale': '科技TOP1策略,17.1%收益,2.35 Sharpe'
    },
    '新能源': {
        'weight': 1.8,           # v5.75提升: 1.5x → 1.8x (+20%)
        'strategy': 'MACD_RSI_FAST',  # 新增: 加快MACD参数
        'sharpe_target': 1.78,
        'expected_return': 0.1466,
        'rationale': '新能源TOP2,14.66%收益,1.78 Sharpe'
    },
    '消费白马': {
        'weight': 0.3,           # v5.75降低: 0.5x → 0.3x (-40%)
        'strategy': 'MULTI_FACTOR',
        'sharpe_target': 0.9,
        'expected_return': 0.08,
        'rationale': '低效策略，混合池拖累源'
    },
    '主板': {
        'weight': 0.6,           # v5.75降低: 0.8x → 0.6x (-25%)
        'strategy': 'MULTI_FACTOR',
        'sharpe_target': 1.1,
        'expected_return': 0.10,
        'rationale': '稳定但低收益'
    },
    '其他': {
        'weight': 0.4,           # v5.75降低: 0.7x → 0.4x (-43%)
        'strategy': 'TREND_FOLLOW',
        'sharpe_target': 0.8,
        'expected_return': 0.06,
        'rationale': '高风险低回报'
    }
}

# 权重规范化
_total_weight = sum(cfg['weight'] for cfg in MIXED_POOL_SECTOR_WEIGHTS_V75.values())
for cfg in MIXED_POOL_SECTOR_WEIGHTS_V75.values():
    cfg['normalized_weight'] = cfg['weight'] / _total_weight


# =================== MACD参数赛道差异化配置 ===================

MACD_PARAMS_SECTOR_OPTIMIZED_V75 = {
    '科技成长': {
        'fast': 12,           # 保持最优参数 (17.1% Sharpe 2.35)
        'slow': 26,
        'signal': 9,
        'description': '科技TOP1最优参数'
    },
    '新能源': {
        'fast': 10,           # v5.75新增: 加快速度 (更快捕捉趋势变化)
        'slow': 24,
        'signal': 7,
        'description': '加快MACD跟踪,适配新能源高波动'
    },
    '消费白马': {
        'fast': 14,           # v5.75新增: 保守参数 (平滑降噪)
        'slow': 28,
        'signal': 9,
        'description': '保守平滑,降低假信号'
    },
    '主板': {
        'fast': 12,           # 保持标准
        'slow': 26,
        'signal': 9,
        'description': '标准参数,稳定市场'
    }
}

RSI_PARAMS_SECTOR_OPTIMIZED_V75 = {
    '科技成长': {
        'period': 14,         # 保持最优
        'oversold': 30,
        'overbought': 70,
        'description': '标准RSI'
    },
    '新能源': {
        'period': 12,         # v5.75新增: 缩短周期 (更敏感)
        'oversold': 28,
        'overbought': 72,
        'description': '缩短RSI周期,适配高波动'
    },
    '消费白马': {
        'period': 16,         # v5.75新增: 延长周期 (平滑降噪)
        'oversold': 32,
        'overbought': 68,
        'description': '延长RSI周期,稳定性'
    }
}


# =================== 快速选股模式 (FAST_PICK) ===================

class FastPickCache:
    """快速选股缓存 - 预存高质量候选,加速高现金模式下的选股"""
    
    def __init__(self, max_size=50):
        self.cache = {}
        self.max_size = max_size
        self.last_update = None
        self.cache_hit_count = 0
        self.cache_miss_count = 0
    
    def update_cache(self, candidates: list, sector_weights: dict = None):
        """更新缓存 (全量扫描)"""
        import copy
        
        start_time = time.time()
        
        # 按质量评分排序,保存TOP 50
        sorted_cands = sorted(candidates, key=lambda x: -x.get('score', 0))
        self.cache = {c['code']: copy.deepcopy(c) for c in sorted_cands[:self.max_size]}
        self.last_update = datetime.now()
        
        update_time = time.time() - start_time
        print(f"  ⚡ FastPick缓存已更新: {len(self.cache)}只候选 (耗时 {update_time:.2f}s)")
        
        return self.cache
    
    def fast_pick(self, target_count=10, cash_ratio=0.95, sector_weights=None) -> list:
        """从缓存中快速选择 (不超过1秒)"""
        
        start_time = time.time()
        
        if not self.cache:
            self.cache_miss_count += 1
            print(f"  ⚠️  FastPick缓存为空,降级到全量选股")
            return []
        
        # 从缓存中按质量排序,快速取TOP
        candidates = list(self.cache.values())
        
        # 如果提供了赛道权重,应用权重重排
        if sector_weights:
            for cand in candidates:
                sector = cand.get('_sector', '其他')
                weight = sector_weights.get(sector, {}).get('normalized_weight', 1.0)
                cand['_fast_pick_score'] = cand.get('score', 0) * weight
            
            candidates = sorted(candidates, key=lambda x: -x.get('_fast_pick_score', 0))
        
        # 取TOP N
        result = candidates[:target_count]
        
        elapsed = time.time() - start_time
        self.cache_hit_count += 1
        
        print(f"  ✅ FastPick速选完成: {len(result)}只 (缓存命中, 耗时 {elapsed*1000:.1f}ms)")
        
        return result
    
    def get_stats(self):
        """获取缓存统计"""
        return {
            'cache_size': len(self.cache),
            'max_size': self.max_size,
            'last_update': self.last_update.isoformat() if self.last_update else None,
            'cache_hit_count': self.cache_hit_count,
            'cache_miss_count': self.cache_miss_count,
            'hit_rate': self.cache_hit_count / (self.cache_hit_count + self.cache_miss_count) 
                        if (self.cache_hit_count + self.cache_miss_count) > 0 else 0
        }


# 全局快速选股缓存实例
FAST_PICK_CACHE = FastPickCache(max_size=50)


# =================== 快速选股激活条件 ===================

FAST_PICK_TRIGGER_CONFIG = {
    'enabled': True,
    'cash_ratio_threshold': 0.90,        # 现金>90%激活
    'picker_time_threshold': 5.0,        # 选股耗时>5秒自动激活
    'max_pick_time_target': 10.0,        # 目标不超过10秒
    'cache_update_interval': 300,        # 每5分钟更新一次缓存
    'fast_pick_target_count': 10,        # 快速选股目标:10-15只
    'fallback_on_error': True,           # 错误时降级到全量选股
}


# =================== 实现函数 ===================

def apply_mixed_pool_sector_weights_v75(candidates: list, sector_func=None) -> list:
    """应用混合池赛道权重优化 (v5.75)
    
    在混合池选股时按回测权重加权不同赛道候选
    科技1.8x→2.0x, 新能源1.5x→1.8x, 消费0.5x→0.3x
    
    Args:
        candidates: 候选股票列表
        sector_func: 赛道分类函数 (code, name) → sector_name
    
    Returns: 应用权重后的候选列表
    """
    
    if not candidates:
        return candidates
    
    try:
        from performance_tracker import classify_sector
        sector_class_func = sector_func or classify_sector
    except ImportError:
        print("  ⚠️  无法导入赛道分类函数,权重应用跳过")
        return candidates
    
    for cand in candidates:
        code = cand.get('code', '')
        name = cand.get('name', '')
        
        # 分类赛道
        sector = sector_class_func(code, name) if sector_class_func else '其他'
        cand['_sector'] = sector
        
        # 查找赛道权重配置
        if sector in MIXED_POOL_SECTOR_WEIGHTS_V75:
            sector_cfg = MIXED_POOL_SECTOR_WEIGHTS_V75[sector]
            normalized_weight = sector_cfg['normalized_weight']
            
            # 应用权重调整分数
            original_score = cand.get('score', 0)
            weighted_score = int(original_score * normalized_weight * 10)  # *10放大倍数
            
            cand['score'] = weighted_score
            cand['_sector_weight'] = f"{sector}({normalized_weight:.2f}x)"
            cand['_original_score'] = original_score
    
    # 重新排序
    candidates = sorted(candidates, key=lambda x: -x.get('score', 0))
    
    return candidates


def apply_sector_macd_params(code: str, name: str, default_macd=None) -> dict:
    """根据赛道应用差异化MACD参数
    
    Args:
        code: 股票代码
        name: 股票名称
        default_macd: 默认MACD参数
    
    Returns: {fast, slow, signal, rsi_period, description}
    """
    
    try:
        from performance_tracker import classify_sector
        sector = classify_sector(code, name)
    except:
        sector = '主板'
    
    if sector in MACD_PARAMS_SECTOR_OPTIMIZED_V75:
        macd_cfg = MACD_PARAMS_SECTOR_OPTIMIZED_V75[sector]
        rsi_cfg = RSI_PARAMS_SECTOR_OPTIMIZED_V75.get(sector, RSI_PARAMS_SECTOR_OPTIMIZED_V75['主板'])
        
        return {
            'macd': macd_cfg,
            'rsi': rsi_cfg,
            'sector': sector,
            'description': f"{sector} - {macd_cfg['description']}"
        }
    
    # 降级到默认
    return {
        'macd': default_macd or MACD_PARAMS_SECTOR_OPTIMIZED_V75['主板'],
        'rsi': RSI_PARAMS_SECTOR_OPTIMIZED_V75.get('主板'),
        'sector': '主板',
        'description': '默认参数'
    }


def enable_fast_pick_if_needed(cash_ratio: float, picker_elapsed_time: float) -> bool:
    """判断是否激活快速选股模式
    
    Args:
        cash_ratio: 当前现金占比
        picker_elapsed_time: 本次选股耗时(秒)
    
    Returns: True则激活快速模式
    """
    
    config = FAST_PICK_TRIGGER_CONFIG
    
    if not config['enabled']:
        return False
    
    # 判断激活条件
    cash_condition = cash_ratio > config['cash_ratio_threshold']
    time_condition = picker_elapsed_time > config['picker_time_threshold']
    
    if cash_condition and time_condition:
        print(f"  ⚡ FastPick激活条件满足: 现金{cash_ratio:.1%} > {config['cash_ratio_threshold']:.0%} "
              f"& 耗时{picker_elapsed_time:.1f}s > {config['picker_time_threshold']}s")
        return True
    
    return False


def validate_mixed_pool_config() -> dict:
    """验证混合池配置的一致性"""
    
    stats = {
        'total_sectors': len(MIXED_POOL_SECTOR_WEIGHTS_V75),
        'weight_sum': sum(cfg['weight'] for cfg in MIXED_POOL_SECTOR_WEIGHTS_V75.values()),
        'normalized_weight_sum': sum(cfg['normalized_weight'] for cfg in MIXED_POOL_SECTOR_WEIGHTS_V75.values()),
        'expected_weighted_return': 0,
        'expected_weighted_sharpe': 0,
        'sectors': {}
    }
    
    for sector, cfg in MIXED_POOL_SECTOR_WEIGHTS_V75.items():
        expected_ret = cfg.get('expected_return', 0) * cfg['normalized_weight']
        expected_sharpe = cfg.get('sharpe_target', 0) * cfg['normalized_weight']
        
        stats['expected_weighted_return'] += expected_ret
        stats['expected_weighted_sharpe'] += expected_sharpe
        
        stats['sectors'][sector] = {
            'weight': cfg['weight'],
            'normalized_weight': cfg['normalized_weight'],
            'expected_return': cfg.get('expected_return', 0),
            'expected_return_weighted': expected_ret,
            'sharpe_target': cfg.get('sharpe_target', 0),
            'sharpe_weighted': expected_sharpe
        }
    
    print(f"\n✅ v5.75混合池配置验证:")
    print(f"  总赛道数: {stats['total_sectors']}")
    print(f"  权重总和: {stats['weight_sum']:.2f} (规范化后: {stats['normalized_weight_sum']:.2f})")
    print(f"  📈 预期加权收益: {stats['expected_weighted_return']:.2%}")
    print(f"  📊 预期加权Sharpe: {stats['expected_weighted_sharpe']:.2f}")
    print(f"  ✅ 配置一致性: {'通过' if abs(stats['normalized_weight_sum'] - 1.0) < 0.001 else '失败'}")
    
    return stats


if __name__ == '__main__':
    # 测试配置
    print("v5.75 混合池优化配置验证\n")
    
    stats = validate_mixed_pool_config()
    
    print("\n📋 赛道配置详情:")
    for sector, cfg in stats['sectors'].items():
        print(f"\n  🏢 {sector}:")
        print(f"     权重: {cfg['weight']:.2f}x → 规范化: {cfg['normalized_weight']:.2%}")
        print(f"     预期收益: {cfg['expected_return']:.2%} (加权: {cfg['expected_return_weighted']:.2%})")
        print(f"     Sharpe目标: {cfg['sharpe_target']:.2f} (加权: {cfg['sharpe_weighted']:.2f})")
    
    print("\n\n✨ FastPick配置:")
    print(f"  启用: {FAST_PICK_TRIGGER_CONFIG['enabled']}")
    print(f"  现金阈值: {FAST_PICK_TRIGGER_CONFIG['cash_ratio_threshold']:.0%}")
    print(f"  时间阈值: {FAST_PICK_TRIGGER_CONFIG['picker_time_threshold']}s")
    print(f"  目标完成时间: {FAST_PICK_TRIGGER_CONFIG['max_pick_time_target']}s")
    print(f"  缓存大小: {FAST_PICK_TRIGGER_CONFIG['cache_update_interval']}条候选")
