"""
v5.75 集成模块 - 与stock_picker.py的接口适配

职责:
1. 在stock_picker.py的score_and_rank()中应用混合池权重
2. 在stock_picker.py的score_and_rank()中应用赛道差异化MACD参数
3. 激活FastPickCache并在高现金时使用快速选股
4. 与BacktestAccuracyAnalyzer集成
"""

import sys
import time
from typing import List, Dict, Optional

# 导入v5.75优化模块
try:
    from v5_75_MIXED_POOL_OPTIMIZATION import (
        MIXED_POOL_SECTOR_WEIGHTS_V75,
        MACD_PARAMS_SECTOR_OPTIMIZED_V75,
        RSI_PARAMS_SECTOR_OPTIMIZED_V75,
        FastPickCache,
        FAST_PICK_TRIGGER_CONFIG,
        apply_mixed_pool_sector_weights_v75,
        apply_sector_macd_params,
        enable_fast_pick_if_needed,
        validate_mixed_pool_config
    )
    V5_75_MIXED_POOL_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  v5.75混合池模块导入失败: {e}")
    V5_75_MIXED_POOL_AVAILABLE = False

try:
    from backtest_analyzer_v75 import (
        BacktestAccuracyAnalyzer,
        ATRDrawdownControl
    )
    V5_75_BACKTEST_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  v5.75回测分析模块导入失败: {e}")
    V5_75_BACKTEST_AVAILABLE = False

try:
    from config import (
        APPLY_MIXED_POOL_SECTOR_WEIGHTS_V75,
        APPLY_SECTOR_MACD_PARAMS_V75,
        APPLY_FAST_PICK_V75,
        APPLY_ATR_DRAWDOWN_CONTROL_V75,
        BACKTEST_ACCURACY_ANALYSIS_V75,
        ATR_DRAWDOWN_CONTROL_V75,
        FAST_PICK_MODE_V75,
        V5_75_OPTIMIZATION_ACTIVE
    )
    V5_75_CONFIG_AVAILABLE = True
except ImportError:
    print("⚠️  v5.75配置导入失败,使用默认参数")
    V5_75_CONFIG_AVAILABLE = False
    # 默认参数
    APPLY_MIXED_POOL_SECTOR_WEIGHTS_V75 = True
    APPLY_SECTOR_MACD_PARAMS_V75 = True
    APPLY_FAST_PICK_V75 = True
    APPLY_ATR_DRAWDOWN_CONTROL_V75 = True
    V5_75_OPTIMIZATION_ACTIVE = True


# 全局快速选股缓存实例
_fast_pick_cache = None


def get_fast_pick_cache():
    """获取或初始化快速选股缓存"""
    global _fast_pick_cache
    if _fast_pick_cache is None:
        _fast_pick_cache = FastPickCache(max_size=50)
    return _fast_pick_cache


def integrate_mixed_pool_weights(candidates: List) -> List:
    """【集成函数】在score_and_rank中应用混合池权重
    
    在stock_picker.py的score_and_rank()中调用:
    
    ```python
    # 在score_and_rank函数末尾,返回ranked之前
    if V5_75_OPTIMIZATION_ACTIVE:
        ranked = integrate_mixed_pool_weights(ranked)
    return ranked
    ```
    
    Args:
        candidates: score_and_rank输出的排序候选列表
    
    Returns: 应用了混合池权重的候选列表
    """
    
    if not V5_75_OPTIMIZATION_ACTIVE or not APPLY_MIXED_POOL_SECTOR_WEIGHTS_V75:
        return candidates
    
    if not V5_75_MIXED_POOL_AVAILABLE:
        return candidates
    
    try:
        # 应用混合池权重优化
        candidates = apply_mixed_pool_sector_weights_v75(candidates)
        print(f"  ✅ v5.75混合池权重应用完成: {len(candidates)}只候选")
        return candidates
    except Exception as e:
        print(f"  ⚠️  v5.75混合池权重应用失败: {e}")
        return candidates


def integrate_sector_macd_params(code: str, name: str) -> Dict:
    """【集成函数】获取赛道差异化MACD参数
    
    在stock_picker.py的calculate_technical_indicators()中调用:
    
    ```python
    # 获取赛道特定MACD参数
    macd_config = integrate_sector_macd_params(code, name)
    macd_params = macd_config['macd']
    rsi_params = macd_config['rsi']
    # 使用macd_params/rsi_params计算指标
    ```
    
    Args:
        code: 股票代码
        name: 股票名称
    
    Returns: {'macd': {...}, 'rsi': {...}, 'sector': str, 'description': str}
    """
    
    if not V5_75_OPTIMIZATION_ACTIVE or not APPLY_SECTOR_MACD_PARAMS_V75:
        # 降级到默认配置
        from config import MACD_PARAMS, RSI_PARAMS
        return {
            'macd': MACD_PARAMS,
            'rsi': RSI_PARAMS,
            'sector': '默认',
            'description': '使用全局MACD参数'
        }
    
    if not V5_75_MIXED_POOL_AVAILABLE:
        return {'macd': {}, 'rsi': {}}
    
    try:
        config = apply_sector_macd_params(code, name)
        return config
    except Exception as e:
        print(f"  ⚠️  赛道MACD参数获取失败({code}): {e}")
        from config import MACD_PARAMS, RSI_PARAMS
        return {
            'macd': MACD_PARAMS,
            'rsi': RSI_PARAMS,
            'sector': '错误恢复',
            'description': f'错误: {e}'
        }


def integrate_fast_pick_suggestion(candidates: List, cash_ratio: float, 
                                   picker_elapsed_time: float) -> Dict:
    """【集成函数】快速选股建议
    
    在stock_picker.py的multi_strategy_pick()末尾调用:
    
    ```python
    # 检查是否应用快速选股
    fast_pick_result = integrate_fast_pick_suggestion(
        ranked_candidates, current_cash_ratio, elapsed_time
    )
    if fast_pick_result['use_fast_pick']:
        ranked_candidates = fast_pick_result['fast_pick_result']
        print(f"  ⚡ FastPick已应用: {len(ranked_candidates)}只候选")
    ```
    
    Args:
        candidates: 全量排序后的候选列表
        cash_ratio: 当前现金占比
        picker_elapsed_time: 本次选股耗时(秒)
    
    Returns: {
        'use_fast_pick': bool,
        'fast_pick_result': list,
        'cache_hit': bool,
        'reason': str
    }
    """
    
    if not V5_75_OPTIMIZATION_ACTIVE or not APPLY_FAST_PICK_V75:
        return {
            'use_fast_pick': False,
            'reason': 'FastPick未启用'
        }
    
    if not V5_75_MIXED_POOL_AVAILABLE:
        return {
            'use_fast_pick': False,
            'reason': 'v5.75模块不可用'
        }
    
    try:
        # 检查是否激活快速选股
        should_activate = enable_fast_pick_if_needed(cash_ratio, picker_elapsed_time)
        
        if not should_activate:
            return {
                'use_fast_pick': False,
                'reason': f'条件未满足 (现金{cash_ratio:.1%}, 耗时{picker_elapsed_time:.1f}s)'
            }
        
        # 更新缓存
        cache = get_fast_pick_cache()
        cache.update_cache(candidates, MIXED_POOL_SECTOR_WEIGHTS_V75)
        
        # 快速选股
        target_count = FAST_PICK_MODE_V75.get('fast_pick_target', 10)
        sector_weights = {k: {'normalized_weight': v['weight']} for k, v in MIXED_POOL_SECTOR_WEIGHTS_V75.items()}
        
        fast_pick_result = cache.fast_pick(
            target_count=target_count,
            cash_ratio=cash_ratio,
            sector_weights=sector_weights
        )
        
        return {
            'use_fast_pick': True,
            'fast_pick_result': fast_pick_result,
            'cache_hit': True,
            'cache_stats': cache.get_stats(),
            'reason': f'FastPick激活成功: {len(fast_pick_result)}只候选'
        }
    
    except Exception as e:
        print(f"  ⚠️  快速选股失败: {e}")
        return {
            'use_fast_pick': False,
            'reason': f'错误: {e}'
        }


def integrate_backtest_accuracy_report(report_dir: str = None) -> Optional[str]:
    """【集成函数】生成实盘准确率分析报告
    
    在daily_runner.py的main()中定期调用(每周1次):
    
    ```python
    # 每周生成实盘准确率分析报告
    if weekday == 4:  # 周五
        report = integrate_backtest_accuracy_report()
        if report:
            print(report)
            # 保存报告
            with open(f'{REPORT_DIR}/accuracy_report_{date.today()}.txt', 'w') as f:
                f.write(report)
    ```
    
    Args:
        report_dir: 报告目录 (可选)
    
    Returns: 报告文本
    """
    
    if not V5_75_OPTIMIZATION_ACTIVE or not BACKTEST_ACCURACY_ANALYSIS_V75['enabled']:
        return None
    
    if not V5_75_BACKTEST_AVAILABLE:
        return None
    
    try:
        analyzer = BacktestAccuracyAnalyzer(
            backtest_log_path=BACKTEST_ACCURACY_ANALYSIS_V75.get('backtest_log_path'),
            trade_log_path=BACKTEST_ACCURACY_ANALYSIS_V75.get('trade_log_path')
        )
        
        analyzer.load_backtest_records()
        analyzer.load_trade_records()
        
        report = analyzer.generate_report()
        return report
    
    except Exception as e:
        print(f"  ⚠️  准确率分析报告生成失败: {e}")
        return None


def integrate_atr_drawdown_control(positions: Dict, current_prices: Dict) -> Dict:
    """【集成函数】ATR动态止损评估
    
    在position_manager.py的check_stop_loss()中调用:
    
    ```python
    # 对所有持仓进行ATR动态止损评估
    for code in positions:
        atr_assessment = integrate_atr_drawdown_control({code: positions[code]}, {code: current_prices[code]})
        if atr_assessment['recommendation'] == 'STOP_LOSS':
            trigger_stop_loss(code)
    ```
    
    Args:
        positions: 持仓字典 {code: {entry_price, shares, ...}}
        current_prices: 当前价格字典 {code: price}
    
    Returns: {
        'code': str,
        'current_price': float,
        'current_stop_loss': float,
        'trigger_stop_loss': bool,
        'recommendation': str
    }
    """
    
    if not V5_75_OPTIMIZATION_ACTIVE or not APPLY_ATR_DRAWDOWN_CONTROL_V75:
        return {'recommendation': 'HOLD', 'reason': 'ATR控制未启用'}
    
    if not V5_75_BACKTEST_AVAILABLE:
        return {'recommendation': 'HOLD', 'reason': 'v5.75模块不可用'}
    
    try:
        atr_control = ATRDrawdownControl(target_max_dd=ATR_DRAWDOWN_CONTROL_V75['target_max_dd'])
        
        # 简化处理: 如果传入单个持仓,直接评估
        assessment = atr_control.get_portfolio_max_dd_estimate(positions, current_prices)
        
        return {
            'portfolio_assessment': assessment,
            'status': assessment['status'],
            'recommendation': 'REDUCE_POSITION' if assessment['status'] == 'EXCEED' else 'HOLD'
        }
    
    except Exception as e:
        print(f"  ⚠️  ATR止损评估失败: {e}")
        return {'recommendation': 'HOLD', 'reason': f'错误: {e}'}


def print_v5_75_status():
    """打印v5.75优化模块状态"""
    
    print("\n" + "="*70)
    print("【v5.75优化模块状态】")
    print("="*70)
    
    print(f"\n模块可用性:")
    print(f"  混合池优化模块: {'✅' if V5_75_MIXED_POOL_AVAILABLE else '❌'}")
    print(f"  回测分析模块: {'✅' if V5_75_BACKTEST_AVAILABLE else '❌'}")
    print(f"  配置模块: {'✅' if V5_75_CONFIG_AVAILABLE else '❌'}")
    print(f"  整体激活状态: {'✅ 激活' if V5_75_OPTIMIZATION_ACTIVE else '❌ 关闭'}")
    
    print(f"\n功能启用状态:")
    print(f"  混合池权重: {'✅' if APPLY_MIXED_POOL_SECTOR_WEIGHTS_V75 else '❌'}")
    print(f"  赛道MACD参数: {'✅' if APPLY_SECTOR_MACD_PARAMS_V75 else '❌'}")
    print(f"  快速选股模式: {'✅' if APPLY_FAST_PICK_V75 else '❌'}")
    print(f"  ATR回撤控制: {'✅' if APPLY_ATR_DRAWDOWN_CONTROL_V75 else '❌'}")
    
    if V5_75_MIXED_POOL_AVAILABLE:
        print(f"\n混合池配置:")
        config = validate_mixed_pool_config()
        print(f"  预期加权收益: {config['expected_weighted_return']:.2%}")
        print(f"  预期加权Sharpe: {config['expected_weighted_sharpe']:.2f}")
    
    print("\n" + "="*70 + "\n")


if __name__ == '__main__':
    print_v5_75_status()
    
    # 测试集成函数
    print("【测试集成函数】\n")
    
    # 测试混合池权重集成
    test_candidates = [
        {'code': '000001', 'name': '平安银行', 'score': 50},
        {'code': '300750', 'name': '宁德时代', 'score': 60},
    ]
    result = integrate_mixed_pool_weights(test_candidates)
    print(f"混合池权重集成: {len(result)}只候选已处理\n")
    
    # 测试赛道MACD参数集成
    macd_config = integrate_sector_macd_params('603601', '华硕软件')
    print(f"赛道MACD参数: {macd_config['sector']} - {macd_config['description']}\n")
    
    # 测试快速选股建议
    fast_pick_result = integrate_fast_pick_suggestion(test_candidates, 0.95, 6.0)
    print(f"快速选股建议: {'✅ 激活' if fast_pick_result['use_fast_pick'] else '❌ 不激活'} ({fast_pick_result['reason']})\n")
    
    # 测试准确率报告
    report = integrate_backtest_accuracy_report()
    if report:
        print(f"准确率报告生成成功:\n{report[:500]}...\n")
    
    print("✅ 所有集成函数测试完成")
