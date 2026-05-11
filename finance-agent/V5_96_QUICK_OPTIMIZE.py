"""
v5.96 快速优化 - 现金激进部署 + 防超时
修复: 
1. 超激进模式下仅评估TOP45候选 (防超时)
2. 激活快速建仓: 现金>96% 时自动触发 5-8只 微仓建仓
3. 添加选股超时保护 (180秒)
"""

def apply_fast_aggressive_deployment_v96(ranked_candidates, cash_ratio):
    """快速激进部署: 现金>96% 自动微仓建仓"""
    if cash_ratio > 0.96 and ranked_candidates:
        # 取TOP 5-8只高质量候选
        target_count = min(8, len(ranked_candidates) // 2)
        return ranked_candidates[:target_count]
    return ranked_candidates[:3]  # 保守: TOP3

def apply_position_size_extreme_v96(position_size, cash_ratio, target_count=8):
    """极端现金激进下的仓位计算"""
    if cash_ratio > 0.98:
        # 96.6% 现金 -> 部署80% (¥800k) 分配给8只
        return max(0.08, min(0.15, position_size * 1.5))
    elif cash_ratio > 0.90:
        return max(0.06, min(0.12, position_size * 1.2))
    return position_size

def apply_timeout_protection_v96(stock_picker_func, timeout_seconds=180):
    """为选股函数添加超时保护"""
    import signal
    import threading
    
    result = [None]
    exception = [None]
    
    def wrapped():
        try:
            result[0] = stock_picker_func()
        except Exception as e:
            exception[0] = e
    
    thread = threading.Thread(target=wrapped, daemon=True)
    thread.start()
    thread.join(timeout=timeout_seconds)
    
    if thread.is_alive():
        # 超时 - 返回快速备选方案
        return {
            'status': 'timeout',
            'candidates': [],
            'fallback_available': True,
            'message': f'选股超时 >{timeout_seconds}s, 使用快速降级方案'
        }
    
    if exception[0]:
        raise exception[0]
    
    return result[0]

# 配置检查
CONFIG_OPTIMIZATIONS = {
    'v5.96': {
        'CANDIDATE_POOL_EXPANDED': {
            'momentum_target': 45,      # 防超时
            'volume_target': 25,        # 防超时
        },
        'EXTREME_CASH_V3_MODE': {
            'candidate_pool_target': 45,  # 防超时
        },
        'POSITION_SIZE_EXTREME_V96': True,  # 激活极端仓位计算
    }
}

print("✅ v5.96 快速优化已加载")
print("  - 候选池限制: 75 → 45 只")
print("  - 快速建仓: 现金>96% 自动微仓")
print("  - 选股超时保护: 180秒")
