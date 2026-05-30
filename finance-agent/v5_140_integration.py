"""v5.140 集成入口 - stock_picker.py 中调用 v5.140_DEEP_EVENING_OPTIMIZE"""

# 在stock_picker.py顶部添加导入
import sys
try:
    from v5_140_DEEP_EVENING_OPTIMIZE import IntegratedOptimizer, V5_140_CONFIG
    V5_140_AVAILABLE = True
    print("✅ v5.140晚间深度优化已加载")
except ImportError as e:
    print(f"⚠️  v5.140优化模块未找到: {e}")
    V5_140_AVAILABLE = False

# 在multi_strategy_pick()函数中,处理完所有策略后,检查是否应用v5.140
def apply_v5_140_optimization_if_enabled(candidates: list, 
                                         account_state: dict = None,
                                         margin_data: dict = None) -> dict:
    """条件化应用v5.140优化
    
    触发条件:
    1. V5_140_AVAILABLE = True (模块可用)
    2. cash_ratio > 0.985 (现金>98.5%)
    3. candidates数量 > 50 (有足够候选)
    """
    
    if not V5_140_AVAILABLE:
        return None
    
    if not account_state:
        return None
    
    cash_ratio = account_state.get('cash_ratio', 0)
    
    # 仅在现金占比>98.5%时触发v5.140
    if cash_ratio <= 0.985:
        return None
    
    if len(candidates) < 50:
        return None
    
    print(f"✅ 触发v5.140晚间深度优化 (现金{cash_ratio*100:.1f}%, 候选{len(candidates)}只)")
    
    # 执行v5.140优化
    config = V5_140_CONFIG()
    optimizer = IntegratedOptimizer(config)
    
    result = optimizer.execute_deep_optimize(
        candidates,
        account_state,
        margin_data or {}
    )
    
    return result

# =================== 在daily_runner.py中集成 ===================
# 在daily_runner.py的multi_strategy_pick调用后添加:
#
#   picks = multi_strategy_pick(sentiment, account_state, ...)
#   
#   # v5.140: 条件化应用晚间深度优化
#   if config_module.V5_140_DEEP_OPTIMIZE_ACTIVE:
#       from v5_140_integration import apply_v5_140_optimization_if_enabled
#       v5_140_result = apply_v5_140_optimization_if_enabled(
#           picks,
#           account_state={'cash_ratio': cash/total_value, 'total_value': total_value, ...},
#           margin_data={}  # 需要从data_collector获取
#       )
#       
#       if v5_140_result:
#           picks = v5_140_result['picks']  # 更新picks
#           allocation_result = v5_140_result['allocation']  # 赛道分配
#           print(f"✅ v5.140优化应用完成: {len(picks)}只 | "
#                 f"配置: {v5_140_result['metadata']}")

print("✅ v5.140集成模块已加载")
