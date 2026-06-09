"""
v5.160 选股流程集成 - 在stock_picker.py中应用优化权重

关键集成点:
1. score_and_rank() 中应用策略权重
2. 候选过滤中应用赛道权重
3. 情绪驱动信号融合
4. 持仓优化
"""

import sys
import json
from datetime import datetime
from typing import Dict, List, Tuple, Optional

# 导入v5.160优化模块
try:
    from v5_160_strategy_optimization import (
        strategy_optimizer,
        get_v160_strategy_weight,
        apply_v160_optimization,
        get_v160_report
    )
    V5_160_AVAILABLE = True
except ImportError:
    print("⚠️  v5.160策略优化模块未找到")
    V5_160_AVAILABLE = False

try:
    from v5_160_config_addon import (
        ENABLE_V5_160_STRATEGY_FOCUS,
        V160_SECTOR_WEIGHTS_OPTIMIZED,
        V160_ENTRY_QUALITY_BY_STRATEGY,
        V160_KELLY_SHARPE_MULTIPLIER,
        V160_SENTIMENT_STRATEGY_OVERRIDE,
        V160_REMOVED_STRATEGIES
    )
    V5_160_CONFIG_AVAILABLE = True
except ImportError:
    print("⚠️  v5.160配置模块未找到")
    V5_160_CONFIG_AVAILABLE = False


# =================== 集成函数1: 策略权重应用 ===================

def apply_v160_strategy_weights_to_candidates(
    candidates: List[Dict],
    market_sentiment: float = 50,
    debug: bool = False
) -> List[Dict]:
    """
    在score_and_rank()中应用v5.160策略权重
    
    Usage:
        candidates = score_and_rank(...)
        candidates = apply_v160_strategy_weights_to_candidates(candidates, market_sentiment)
    
    Args:
        candidates: score_and_rank()输出的候选列表
        market_sentiment: 市场情绪分数(0-100)
        debug: 调试模式
    
    Returns: 应用权重后的候选列表
    """
    if not V5_160_AVAILABLE:
        return candidates
    
    if not ENABLE_V5_160_STRATEGY_FOCUS:
        return candidates
    
    optimization_stats = {
        'total': len(candidates),
        'boosted': 0,
        'removed': 0,
        'avg_score_change': 0.0,
        'sentiment': market_sentiment
    }
    
    score_changes = []
    
    for i, candidate in enumerate(candidates):
        original_score = candidate.get('score', 0)
        strategy_name = candidate.get('strategy_name', 'UNKNOWN')
        sector = candidate.get('sector', 'OTHER')
        
        # 检查是否是被移除的策略
        if strategy_name in V160_REMOVED_STRATEGIES:
            candidate['v160_status'] = 'REMOVED'
            candidate['optimized_score'] = 0
            optimization_stats['removed'] += 1
            if debug:
                print(f"  ❌ [{i}] {candidate.get('code')} ({strategy_name}): 移除失效策略")
            continue
        
        # 获取策略评分
        strategy_score = strategy_optimizer.get_strategy_score(strategy_name, market_sentiment)
        
        # 应用权重
        if strategy_score['recommended']:
            # 激进策略权重应用
            weight_multiplier = 1.0 + strategy_score['final_weight'] * 0.8
            optimized_score = original_score * weight_multiplier
            candidate['v160_status'] = 'BOOSTED'
            optimization_stats['boosted'] += 1
            
            if debug and weight_multiplier > 1.1:
                print(f"  ⬆️  [{i}] {candidate.get('code')} ({strategy_name}): {original_score:.2f} → {optimized_score:.2f}")
        else:
            # 弱势策略权重衰减
            optimized_score = original_score * 0.3
            candidate['v160_status'] = 'DECAYED'
            
            if debug:
                print(f"  ⬇️  [{i}] {candidate.get('code')} ({strategy_name}): {original_score:.2f} → {optimized_score:.2f}")
        
        # 应用赛道权重
        sector_weight = V160_SECTOR_WEIGHTS_OPTIMIZED.get(sector, 0.02)
        sector_multiplier = 1.0 + sector_weight * 0.5
        optimized_score *= sector_multiplier
        
        # 更新候选
        candidate['optimized_score'] = round(optimized_score, 2)
        candidate['strategy_weight'] = strategy_score['final_weight']
        candidate['sector_weight'] = sector_weight
        candidate['v160_optimization'] = {
            'strategy': strategy_name,
            'strategy_boost': round(strategy_score['final_weight'], 3),
            'sector_boost': round(sector_weight, 3),
            'reason': strategy_score['reason']
        }
        
        score_changes.append(optimized_score - original_score)
    
    # 重新排序 (基于optimized_score)
    candidates = sorted(
        candidates,
        key=lambda x: x.get('optimized_score', x.get('score', 0)),
        reverse=True
    )
    
    # 统计
    optimization_stats['avg_score_change'] = sum(score_changes) / len(score_changes) if score_changes else 0
    
    # 添加元数据
    for candidate in candidates:
        candidate['v160_optimization_stats'] = optimization_stats
    
    return candidates


# =================== 集成函数2: 情绪驱动信号融合 ===================

def apply_v160_sentiment_signal_fusion(
    candidates: List[Dict],
    market_sentiment: float = 50,
    debug: bool = False
) -> List[Dict]:
    """
    基于情绪的策略信号融合
    
    Args:
        candidates: 候选股票列表
        market_sentiment: 市场情绪(0-100)
        debug: 调试模式
    
    Returns: 融合后的候选列表
    """
    if not ENABLE_V5_160_STRATEGY_FOCUS:
        return candidates
    
    # 判断情绪等级
    if market_sentiment > 92:
        emotion = 'extreme_greed'
    elif market_sentiment > 85:
        emotion = 'greed'
    elif market_sentiment < 25:
        emotion = 'extreme_fear'
    elif market_sentiment < 40:
        emotion = 'fear'
    else:
        emotion = 'normal'
    
    if emotion == 'normal':
        return candidates
    
    # 获取情绪对应的策略调整
    override_config = V160_SENTIMENT_STRATEGY_OVERRIDE.get(emotion, {})
    
    if not override_config:
        return candidates
    
    preferred_strategy = override_config.get('preferred_strategy')
    sector_override = override_config.get('sector_override')
    entry_quality_delta = override_config.get('entry_quality_delta', 0)
    kelly_multiplier = override_config.get('kelly_multiplier', 1.0)
    
    if debug:
        print(f"\n💧 应用{emotion}情绪调整 (情绪={market_sentiment}):")
        print(f"  优先策略: {preferred_strategy}")
        print(f"  赛道偏好: {sector_override}")
        print(f"  入场质量调整: {entry_quality_delta:+d}")
    
    # 应用调整
    for candidate in candidates:
        strategy = candidate.get('strategy_name', '')
        sector = candidate.get('sector', '')
        
        # 优先策略加权
        if preferred_strategy and preferred_strategy in strategy:
            candidate['sentiment_boost'] = 1.25
            candidate['optimized_score'] *= 1.25
        else:
            candidate['sentiment_boost'] = 0.85
            candidate['optimized_score'] *= 0.85
        
        # 赛道偏好加权
        if sector_override and sector == sector_override:
            candidate['sector_sentiment_boost'] = 1.15
            candidate['optimized_score'] *= 1.15
        
        # 入场质量调整
        candidate['entry_quality_delta'] = entry_quality_delta
        candidate['kelly_multiplier'] = kelly_multiplier
    
    # 重新排序
    candidates = sorted(
        candidates,
        key=lambda x: x.get('optimized_score', 0),
        reverse=True
    )
    
    return candidates


# =================== 集成函数3: 入场质量调整 ===================

def get_v160_entry_quality_threshold(
    strategy_name: str,
    market_sentiment: float = 50
) -> int:
    """
    获取基于策略的入场质量门槛
    
    Args:
        strategy_name: 策略名称
        market_sentiment: 市场情绪
    
    Returns: 入场质量分数 (0-100)
    """
    if not V5_160_CONFIG_AVAILABLE:
        return 15  # 默认值
    
    # 基础门槛
    base_threshold = V160_ENTRY_QUALITY_BY_STRATEGY.get(strategy_name, 15)
    
    # 情绪调整
    override = V160_SENTIMENT_STRATEGY_OVERRIDE.get(
        'extreme_fear' if market_sentiment < 25 else
        'extreme_greed' if market_sentiment > 92 else
        'normal'
    )
    
    if override:
        entry_quality_delta = override.get('entry_quality_delta', 0)
        base_threshold += entry_quality_delta
    
    return max(5, min(100, base_threshold))  # 限制在5-100


# =================== 集成函数4: Kelly系数调整 ===================

def get_v160_kelly_multiplier(
    strategy_name: str,
    market_sentiment: float = 50,
    base_kelly: float = 1.75
) -> float:
    """
    获取基于策略和情绪的Kelly系数调整
    
    Args:
        strategy_name: 策略名称
        market_sentiment: 市场情绪
        base_kelly: 基础Kelly系数
    
    Returns: 调整后的Kelly系数
    """
    if not V5_160_CONFIG_AVAILABLE:
        return base_kelly
    
    # 基于策略的Kelly调整
    strategy_multiplier = V160_KELLY_SHARPE_MULTIPLIER.get(strategy_name, 1.0)
    kelly = base_kelly * strategy_multiplier
    
    # 基于情绪的Kelly调整
    override = V160_SENTIMENT_STRATEGY_OVERRIDE.get(
        'extreme_fear' if market_sentiment < 25 else
        'extreme_greed' if market_sentiment > 92 else
        'normal'
    )
    
    if override:
        kelly *= override.get('kelly_multiplier', 1.0)
    
    return kelly


# =================== 集成函数5: 持仓优化 ===================

def optimize_v160_holdings(
    current_holdings: List[Dict],
    portfolio_value: float = 100.0,
    market_sentiment: float = 50
) -> Dict:
    """
    基于v5.160优化的持仓管理
    
    Args:
        current_holdings: 当前持仓列表 [{code, shares, entry_price, current_price, strategy, ...}]
        portfolio_value: 组合总价值
        market_sentiment: 市场情绪
    
    Returns: 优化建议 {hold: [], sell: [], adjust: []}
    """
    if not V5_160_CONFIG_AVAILABLE:
        return {'hold': [], 'sell': [], 'adjust': []}
    
    recommendations = {
        'hold': [],
        'sell': [],
        'adjust': [],
        'sentiment': market_sentiment
    }
    
    for holding in current_holdings:
        strategy = holding.get('strategy_name', '')
        pnl_pct = holding.get('pnl_pct', 0)
        
        # 移除失效策略的持仓
        if strategy in V160_REMOVED_STRATEGIES:
            recommendations['sell'].append({
                'code': holding.get('code'),
                'reason': f'策略{strategy}已移除',
                'urgency': 'high'
            })
            continue
        
        # 高Sharpe策略的持仓保留
        strategy_score = strategy_optimizer.get_strategy_score(strategy, market_sentiment)
        if strategy_score['backtest_metrics']['sharpe'] > 1.5:
            recommendations['hold'].append({
                'code': holding.get('code'),
                'reason': f'TOP策略 (Sharpe {strategy_score["backtest_metrics"]["sharpe"]})',
                'boost_weight': 1.15
            })
        
        # 止损调整
        if pnl_pct < -0.08 and strategy not in ['MULTI_FACTOR_TECH', 'MA_CROSS']:
            recommendations['sell'].append({
                'code': holding.get('code'),
                'reason': f'触发止损 ({pnl_pct:.2%})',
                'urgency': 'high'
            })
    
    return recommendations


# =================== 集成函数6: 生成优化报告 ===================

def generate_v160_optimization_report(candidates: List[Dict]) -> Dict:
    """
    生成v5.160优化报告
    
    Args:
        candidates: 优化后的候选列表
    
    Returns: 优化报告
    """
    if not candidates:
        return {}
    
    strategies_used = {}
    sectors_used = {}
    
    for candidate in candidates[:20]:  # 取TOP20
        strategy = candidate.get('strategy_name', 'UNKNOWN')
        sector = candidate.get('sector', 'UNKNOWN')
        
        strategies_used[strategy] = strategies_used.get(strategy, 0) + 1
        sectors_used[sector] = sectors_used.get(sector, 0) + 1
    
    report = {
        'timestamp': datetime.now().isoformat(),
        'total_candidates': len(candidates),
        'top_20_strategies': strategies_used,
        'top_20_sectors': sectors_used,
        'avg_optimized_score': round(sum(c.get('optimized_score', 0) for c in candidates[:20]) / 20, 2),
        'v5_160_version': get_v160_report()['version']
    }
    
    return report


# =================== 测试/演示 ===================

def test_v160_integration():
    """测试v5.160集成"""
    print("=" * 80)
    print("v5.160 选股流程集成测试")
    print("=" * 80)
    
    # 模拟候选列表
    test_candidates = [
        {
            'code': '000001.SZ',
            'score': 75,
            'strategy_name': 'MACD_RSI_TECH_GROWTH',
            'sector': 'TECH_GROWTH'
        },
        {
            'code': '600000.SH',
            'score': 60,
            'strategy_name': 'VOLUME_BREAKOUT',
            'sector': 'FINANCE'
        },
        {
            'code': '300001.SZ',
            'score': 70,
            'strategy_name': 'MULTI_FACTOR_TECH',
            'sector': 'TECH_GROWTH'
        }
    ]
    
    print("\n📊 原始候选:")
    for c in test_candidates:
        print(f"  {c['code']}: {c['score']} ({c['strategy_name']})")
    
    # 应用优化
    optimized = apply_v160_strategy_weights_to_candidates(test_candidates, 50, debug=True)
    
    print("\n✅ 优化后候选:")
    for c in optimized:
        print(f"  {c['code']}: {c.get('optimized_score', c['score'])} ({c.get('v160_status', 'N/A')})")


if __name__ == '__main__':
    test_v160_integration()
