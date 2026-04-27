"""
【v5.64 position_manager.py 集成模块】
在position_manager.py中调用动态止损和风控函数
"""

import sys
sys.path.insert(0, '/home/nikefd/finance-agent')

try:
    from v5_64_deep_optimize_functions import (
        dynamic_stop_loss_by_sector,
        leverage_market_detection,
        position_size_limit_check,
        position_correlation_check
    )
except ImportError as e:
    print(f"⚠️ v5.64函数导入失败: {e}")


def apply_v5_64_dynamic_stop_loss(position: dict, current_price: float, sector: str = '', regime: str = '') -> dict:
    """v5.64: 应用动态止损到持仓
    
    用途: 在check_dynamic_stop中调用，替代固定的stop_loss参数
    
    示例:
        sl_result = apply_v5_64_dynamic_stop_loss(
            position={'code': '000001', 'entry_price': 10.0, ...},
            current_price=9.8,
            sector='科技成长',
            regime='normal'
        )
        stop_loss_pct = sl_result['stop_loss_pct']
    """
    try:
        from config import V5_64_OPTIMIZATIONS_ENABLED
        
        if not V5_64_OPTIMIZATIONS_ENABLED.get('dynamic_stop_loss', False):
            return None  # 未启用，返回None由调用方使用默认值
        
        result = dynamic_stop_loss_by_sector(
            position=position,
            current_price=current_price,
            sector=sector,
            regime=regime
        )
        
        return {
            'stop_loss_pct': result.get('stop_loss_pct'),
            'stop_loss_price': result.get('stop_loss_price'),
            'take_profit_pct': result.get('take_profit_pct'),
            'take_profit_price': result.get('take_profit_price'),
            'basis': result.get('basis', 'UNKNOWN'),
            '_v5_64_applied': True
        }
    except Exception as e:
        print(f"    ⚠️ v5.64动态止损应用异常: {e}")
        return None


def check_leverage_market_v5_64(positions: list) -> dict:
    """v5.64: 检测高杠杆市场，调整整体激进度
    
    用途: 在calculate_kelly_position_size前调用
    
    输出:
        {
            'leverage_level': 'HIGH',
            'aggressiveness_penalty': -0.10,  # 激进度-10%
            'stop_loss_penalty': -0.01,       # 止损-1%
            'recommendation': '市场高杠杆，降低激进度'
        }
    """
    try:
        from config import V5_64_OPTIMIZATIONS_ENABLED
        
        if not V5_64_OPTIMIZATIONS_ENABLED.get('leverage_detection', False):
            return {'leverage_level': 'NORMAL', 'aggressiveness_penalty': 0}
        
        result = leverage_market_detection()
        
        if result['leverage_level'] == 'HIGH':
            print(f"    ⚠️ v5.64: 检测到高杠杆市场 (融资余额>5000亿), 激进度-10%")
        
        return result
    except Exception as e:
        print(f"    ⚠️ v5.64杠杆检测异常: {e}")
        return {'leverage_level': 'UNKNOWN', 'aggressiveness_penalty': 0}


def check_position_size_limit_v5_64(
    total_capital: float,
    current_holdings: list,
    candidate: dict,
    position_size: float
) -> bool:
    """v5.64: 检查头寸限制 (持仓数 + 单只头寸)
    
    用途: 在allocate_positions中调用，判断是否可以加仓
    
    返回: True=可以加仓, False=禁止加仓
    """
    try:
        from config import V5_64_OPTIMIZATIONS_ENABLED
        
        if not V5_64_OPTIMIZATIONS_ENABLED.get('leverage_detection', False):
            return True  # 未启用，允许加仓
        
        result = position_size_limit_check(
            total_capital=total_capital,
            existing_positions=current_holdings,
            new_position_size=position_size,
            num_positions=len(current_holdings)
        )
        
        if not result['can_add']:
            for warning in result['warnings']:
                print(f"    ⚠️ v5.64: {warning}")
        
        return result['can_add']
    except Exception as e:
        print(f"    ⚠️ v5.64头寸检查异常: {e}")
        return True  # 异常时允许加仓


def check_correlation_v5_64(current_holdings: list, new_candidate: dict) -> bool:
    """v5.64: 检查头寸相关性 (防止科技赛道过度集中)
    
    用途: 在allocate_positions中调用，判断是否存在过高相关性风险
    
    返回: True=可以加仓, False=风险过高
    """
    try:
        from config import V5_64_OPTIMIZATIONS_ENABLED
        
        if not V5_64_OPTIMIZATIONS_ENABLED.get('position_correlation', False):
            return True  # 未启用，允许加仓
        
        result = position_correlation_check(
            holdings=current_holdings,
            new_candidate=new_candidate
        )
        
        if result['risk_level'] == 'HIGH':
            print(f"    ❌ v5.64: 相关性风险过高 - {result['recommendation']}")
            return False
        elif result['risk_level'] == 'MEDIUM':
            print(f"    ⚠️ v5.64: 相关性风险中等 - {result['recommendation']}")
            # 返回True但记录警告
            return True
        
        return result['can_add']
    except Exception as e:
        print(f"    ⚠️ v5.64相关性检查异常: {e}")
        return True  # 异常时允许加仓


# ============================================================================
# 【集成指南】在position_manager.py现有代码中的调用位置
# ============================================================================

"""

=== 集成点 1: check_dynamic_stop() 中应用动态止损 ===

在 position_manager.py 的 check_dynamic_stop() 函数中，替换旧的固定stop_loss:

    # OLD CODE:
    stop_loss = STOP_LOSS  # -0.08 固定值
    
    # NEW CODE (v5.64):
    sl_result = apply_v5_64_dynamic_stop_loss(
        position=pos,
        current_price=current_prices.get(pos['code'], pos['current_price']),
        sector=pos.get('sector', '科技成长'),
        regime=regime
    )
    stop_loss = sl_result['stop_loss_pct'] if sl_result else STOP_LOSS


=== 集成点 2: calculate_kelly_position_size() 前检查杠杆 ===

在 calculate_kelly_position_size() 前：

    # v5.64: 检查市场杠杆
    leverage = check_leverage_market_v5_64(positions)
    if leverage['aggressiveness_penalty'] != 0:
        # 应用激进度惩罚
        kelly_size *= (1 + leverage['aggressiveness_penalty'])


=== 集成点 3: allocate_positions() 中检查头寸限制 ===

在 allocate_positions() 中：

    for candidate in ranked:
        # v5.64: 检查头寸限制
        if not check_position_size_limit_v5_64(
            total_capital=total_capital,
            current_holdings=current_holdings,
            candidate=candidate,
            position_size=calculated_size
        ):
            continue  # 跳过此候选
        
        # v5.64: 检查相关性
        if not check_correlation_v5_64(current_holdings, candidate):
            continue  # 风险过高，跳过
        
        # 正常分配头寸


=== 集成点 4: 持仓记录中添加v5.64元数据 ===

在 add_position() 时记录：

    position = {
        'code': code,
        'entry_price': entry_price,
        ...
        '_v5_64_stop_loss': sl_result,           # 动态止损信息
        '_v5_64_sector': sector,                 # 赛道
        '_v5_64_entry_timing': entry_timing,    # 入场时机
    }

"""
