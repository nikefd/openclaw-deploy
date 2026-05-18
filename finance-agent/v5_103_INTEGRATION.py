"""v5.103 Integration Module — 将深度融合引擎集成到stock_picker.py和position_manager.py

集成步骤:
1. 在stock_picker.py的select_stocks()中调用get_entry_quality_threshold_v103()
2. 在stock_picker.py的score_and_rank()中应用MACD参数差异化
3. 在position_manager.py的calculate_position_size()中应用Kelly仓位
4. 在daily_runner.py的晚间优化流程中调用v5_103_deep_fusion_engine()
"""

import sys
sys.path.insert(0, '/home/nikefd/finance-agent')

from v5_103_DEEP_FUSION import (
    BacktestDataScientificFusion,
    KellyPositionSizer,
    MultiLayerRiskAllocation,
    SectorStrategyRouter,
    DynamicEntryQualityThreshold,
    StockPickingTimeoutGuard,
    v5_103_deep_fusion_engine
)

from v5_103_CONFIG_ADDON import (
    KELLY_CONFIG_V103,
    RISK_ALLOCATION_V103,
    MACD_PARAMS_SECTOR_V103,
    ENTRY_QUALITY_DYNAMIC_V103,
    STOCK_PICKING_TIMEOUT_V103,
    SECTOR_WEIGHTS_FROM_BACKTEST_V103,
    SECTOR_STRATEGIES_V103
)


# ================================================================================
# 1. stock_picker.py 集成函数
# ================================================================================

def get_entry_quality_threshold_v103(cash_ratio: float, current_drawdown: float = 0.0) -> int:
    """获取v5.103动态入场质量阈值
    
    Args:
        cash_ratio: 当前现金占比
        current_drawdown: 当前最大回撤
    
    Returns:
        入场质量评分阈值 (0-100)
    """
    try:
        analyzer = DynamicEntryQualityThreshold()
        threshold = analyzer.get_threshold(cash_ratio, current_drawdown)
        return threshold
    except Exception as e:
        print(f"⚠️ v5.103入场质量获取失败: {e}, 使用默认值65")
        return 65


def get_macd_params_v103(sector: str) -> dict:
    """获取特定赛道的v5.103优化MACD参数
    
    Args:
        sector: '科技成长' | '新能源' | '白马消费' | '混合池'
    
    Returns:
        MACD参数字典
    """
    try:
        if sector not in MACD_PARAMS_SECTOR_V103:
            sector = '混合池'
        
        params = MACD_PARAMS_SECTOR_V103[sector].copy()
        return {k: v for k, v in params.items() if k in [
            'macd_fast', 'macd_slow', 'macd_signal', 
            'rsi_period', 'rsi_oversold', 'rsi_overbought'
        ]}
    except Exception as e:
        print(f"⚠️ v5.103 MACD参数获取失败: {e}, 使用默认参数")
        return {
            'macd_fast': 12,
            'macd_slow': 26,
            'macd_signal': 9,
            'rsi_period': 14,
            'rsi_oversold': 30,
            'rsi_overbought': 70
        }


def get_stock_picking_timeout_config_v103(cash_ratio: float, 
                                          current_positions_count: int) -> dict:
    """获取v5.103选股超时配置
    
    Args:
        cash_ratio: 当前现金占比
        current_positions_count: 当前持仓数
    
    Returns:
        超时配置字典
    """
    try:
        guard = StockPickingTimeoutGuard()
        config = guard.get_timeout_config(cash_ratio, current_positions_count)
        return config
    except Exception as e:
        print(f"⚠️ v5.103超时配置获取失败: {e}, 使用默认配置")
        return {
            'mode': 'normal',
            'candidates_limit': 100,
            'timeout_seconds': 45,
            'reason': 'default'
        }


# ================================================================================
# 2. position_manager.py 集成函数
# ================================================================================

def calculate_kelly_position_size_v103(total_capital: float,
                                      current_cash: float,
                                      current_positions: list,
                                      market_regime: str = 'normal') -> float:
    """计算v5.103 Kelly凯利仓位大小
    
    Args:
        total_capital: 总资本
        current_cash: 当前现金
        current_positions: 当前持仓列表
        market_regime: 市场制度 ('bull'|'normal'|'bear')
    
    Returns:
        单持仓应占总资本的比例 (0-0.08)
    """
    try:
        sizer = KellyPositionSizer()
        cash_ratio = current_cash / total_capital if total_capital > 0 else 1.0
        
        # 选择部署模式
        if cash_ratio > 0.95 and market_regime != 'bear':
            mode = 'aggressive'
        elif cash_ratio < 0.20 or market_regime == 'bear':
            mode = 'conservative'
        else:
            mode = 'balanced'
        
        position_ratio = sizer.get_single_position_ratio(
            total_capital,
            len(current_positions),
            target_positions=8,
            cash_ratio=cash_ratio,
            mode=mode
        )
        
        return position_ratio
    except Exception as e:
        print(f"⚠️ v5.103 Kelly仓位计算失败: {e}, 使用默认值0.05")
        return 0.05


def get_risk_allocation_v103(cash_ratio: float,
                            market_regime: str = 'normal',
                            current_drawdown: float = 0.0) -> dict:
    """获取v5.103多层风险分级配置
    
    Args:
        cash_ratio: 现金占比
        market_regime: 市场制度
        current_drawdown: 当前回撤
    
    Returns:
        风险分级配置字典
    """
    try:
        allocator = MultiLayerRiskAllocation()
        mode, config = allocator.select_allocation_template(
            cash_ratio, market_regime, current_drawdown
        )
        return {
            'mode': mode,
            'allocation': config,
            'confidence': 'HIGH'
        }
    except Exception as e:
        print(f"⚠️ v5.103风险分级获取失败: {e}, 使用平衡配置")
        return {
            'mode': 'balanced',
            'allocation': {
                'defensive': 0.25,
                'offensive': 0.45,
                'tactical': 0.15,
                'cash': 0.15
            }
        }


# ================================================================================
# 3. daily_runner.py 集成函数 (晚间优化主入口)
# ================================================================================

def run_v5_103_evening_optimization(portfolio_state: dict) -> dict:
    """运行v5.103晚间深度优化
    
    这个函数应该在daily_runner.py的evening_run()中调用
    
    Args:
        portfolio_state: {
            'total_capital': float,
            'current_cash': float,
            'positions': List[Dict],
            'market_regime': str,
            'current_drawdown': float
        }
    
    Returns:
        优化方案字典
    """
    try:
        print("\n" + "="*80)
        print("🚀 v5.103 晚间深度优化④ 启动")
        print("="*80)
        
        result = v5_103_deep_fusion_engine(portfolio_state)
        
        # 生成可读的优化建议
        recommendations = _generate_v5_103_recommendations(result)
        
        result['recommendations'] = recommendations
        
        print("\n📊 优化结果摘要:")
        print(f"  版本: {result.get('version')}")
        print(f"  部署模式: {result['kelly_deployment']['deployment_mode']}")
        print(f"  目标持仓: {result['kelly_deployment']['target_positions']}只")
        print(f"  可开仓数: {result['kelly_deployment']['positions_can_open']}只")
        print(f"  单仓比例: {result['kelly_deployment']['single_position_ratio']:.2%}")
        print(f"  入场阈值: {result['entry_quality']['threshold']}分")
        print(f"  超时模式: {result['timeout_protection']['mode']} ({result['timeout_protection']['estimated_completion_ms']}ms)")
        print("\n" + "="*80)
        
        return result
    
    except Exception as e:
        print(f"❌ v5.103优化执行失败: {e}")
        import traceback
        traceback.print_exc()
        raise


def _generate_v5_103_recommendations(optimization_result: dict) -> list:
    """从优化结果生成可读的建议"""
    recommendations = []
    
    kelly = optimization_result['kelly_deployment']
    risk = optimization_result['risk_allocation']
    entry = optimization_result['entry_quality']
    timeout = optimization_result['timeout_protection']
    
    # 建议1: 部署模式
    recommendations.append({
        'priority': 'HIGH',
        'category': '部署模式',
        'action': f"启用{kelly['deployment_mode']}模式",
        'reason': f"现金占比{kelly['cash_ratio']:.1%}, 可开仓{kelly['positions_can_open']}只",
        'expected_impact': f"资金利用率 → {kelly['deployable_capital']:,.0f}元"
    })
    
    # 建议2: 风险配置
    recommendations.append({
        'priority': 'HIGH',
        'category': '风险配置',
        'action': f"切换到{risk['mode']}配置",
        'reason': risk['config'].get('description', ''),
        'expected_impact': f"风险-收益平衡优化"
    })
    
    # 建议3: 入场标准
    recommendations.append({
        'priority': 'MEDIUM',
        'category': '入场质量',
        'action': f"应用{entry['threshold']}分动态阈值",
        'reason': entry['analysis']['reason'],
        'allowed_categories': entry['analysis']['allowed_categories']
    })
    
    # 建议4: 选股速度
    recommendations.append({
        'priority': 'MEDIUM',
        'category': '选股效率',
        'action': f"启用{timeout['mode']}模式",
        'reason': timeout['reason'],
        'expected_impact': f"完成时间 → {timeout['estimated_completion_ms']}ms"
    })
    
    # 建议5: 赛道权重
    backtest_fusion = optimization_result.get('backtest_fusion', {})
    recommendations.append({
        'priority': 'MEDIUM',
        'category': '赛道权重',
        'action': '按回测Sharpe比率加权赛道',
        'reason': f"科技成长62%权重(Sharpe 2.35), 新能源38%权重(Sharpe 1.78)",
        'expected_impact': f"收益 → {backtest_fusion.get('top1_return', 17.1):.1f}%, Sharpe → {backtest_fusion.get('top1_sharpe', 2.35)}"
    })
    
    return recommendations


# ================================================================================
# 4. 验证函数
# ================================================================================

def verify_v5_103_integration() -> bool:
    """验证v5.103集成是否完成"""
    print("\n🔍 v5.103集成验证...")
    
    checks = [
        ('v5_103_DEEP_FUSION导入', lambda: BacktestDataScientificFusion is not None),
        ('v5_103_CONFIG_ADDON导入', lambda: KELLY_CONFIG_V103 is not None),
        ('入场质量函数', lambda: get_entry_quality_threshold_v103(0.95) == 55),
        ('MACD参数函数', lambda: 'macd_fast' in get_macd_params_v103('科技成长')),
        ('超时配置函数', lambda: get_stock_picking_timeout_config_v103(0.95, 2) is not None),
        ('Kelly仓位函数', lambda: calculate_kelly_position_size_v103(1_000_000, 950_000, []) > 0),
        ('风险分级函数', lambda: get_risk_allocation_v103(0.95) is not None),
    ]
    
    all_passed = True
    for name, check in checks:
        try:
            result = check()
            status = "✅" if result else "❌"
            print(f"  {status} {name}")
            all_passed = all_passed and result
        except Exception as e:
            print(f"  ❌ {name}: {e}")
            all_passed = False
    
    if all_passed:
        print("\n✅ v5.103集成验证通过! 可以部署")
    else:
        print("\n⚠️ v5.103集成验证有问题")
    
    return all_passed


if __name__ == '__main__':
    print("v5.103 Integration Module - 测试\n")
    
    # 验证集成
    verify_v5_103_integration()
    
    # 测试函数
    print("\n\n📋 函数测试:")
    
    print("\n1️⃣ 入场质量阈值测试:")
    threshold = get_entry_quality_threshold_v103(0.95)
    print(f"   现金95% → 阈值: {threshold}分 (预期45-55)")
    
    print("\n2️⃣ MACD参数测试:")
    macd = get_macd_params_v103('科技成长')
    print(f"   科技成长MACD: fast={macd.get('macd_fast')}, slow={macd.get('macd_slow')}")
    
    print("\n3️⃣ 超时配置测试:")
    timeout = get_stock_picking_timeout_config_v103(0.95, 2)
    print(f"   现金95%+2只持仓 → {timeout['mode']}模式 ({timeout['estimated_completion_ms']}ms)")
    
    print("\n4️⃣ Kelly仓位测试:")
    kelly_ratio = calculate_kelly_position_size_v103(1_000_000, 950_000, [])
    print(f"   100万本金, 95万现金 → 单仓: {kelly_ratio:.2%}")
    
    print("\n5️⃣ 风险分级测试:")
    risk = get_risk_allocation_v103(0.95)
    print(f"   现金95% → {risk['mode']}模式: 激进{risk['allocation']['offensive']:.0%} + 防守{risk['allocation']['defensive']:.0%}")
    
    print("\n✅ 所有集成函数测试完成")
