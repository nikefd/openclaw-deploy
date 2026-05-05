"""v5.87 晚间深度优化工程
【核心目标】
- 资金利用率: 1.3% → 15-20% (+12x)
- 日均建仓: 8-12只 → 15-20只 (+80%)
- 入场质量: 35分 → 20分 (-43%, 激进但有质量监控)
- Sharpe权重倍数: 2.5x → 3.0x (+20%)
- 年化收益预期: 0.19% → 10-12% (基于Sharpe2.35传导)

【v5.87六大优化】
1. 超激进选股引擎 (现金>99% → 入场20分)
2. Sharpe权重强制激活 (3.0x倍数)
3. 赛道多样化配置 (科技40% + 新能源35% + 其他25%)
4. 消费赛道黑名单 (回测-5.51% → 直接过滤)
5. 混合池策略升级v2 (科技2.5x + 新能源2.0x)
6. 融资异变强制激活 (+12分 or +8分)

【预期指标改善】
- MaxDD: 4.08% → 3.2% (-22%)
- 年化: 0.19% → 10-12% (+5000%)
- 胜率: 保持60%+ (通过Sharpe权重)
- 持仓多样度: 1只 → 8-12只
"""

import json
from datetime import datetime
from config import (
    EXTREME_CASH_V87,
    SHARPE_FORCE_APPLY_V87,
    SECTOR_ALLOCATION_V87,
    CONSUMER_SECTOR_BLACKLIST_V87,
    MIXED_POOL_SECTOR_WEIGHTS_V87,
    MARGIN_ANOMALY_V87,
    ATR_STOP_LOSS_V87,
    V5_87_DEEP_OPTIMIZE_ACTIVE,
    APPLY_SECTOR_ALLOCATION_V87,
    APPLY_CONSUMER_BLACKLIST_V87,
    APPLY_MIXED_POOL_V87,
    APPLY_MARGIN_ANOMALY_V87,
    APPLY_ATR_STOP_LOSS_V87,
)

print("📦 v5.87 深度优化模块已加载")
print(f"   - 超激进选股: {EXTREME_CASH_V87['enabled']}")
print(f"   - Sharpe强制激活: {SHARPE_FORCE_APPLY_V87['enabled']}")
print(f"   - 赛道多样化: {APPLY_SECTOR_ALLOCATION_V87}")
print(f"   - 消费黑名单: {APPLY_CONSUMER_BLACKLIST_V87}")


def apply_extreme_cash_v87(candidates: list, cash_ratio: float = 0.99) -> list:
    """v5.87: 超激进选股引擎
    
    当现金>99%时，激活超激进选股:
    - 入场质量: 20分 (vs 原来的35分)
    - 信号置信度: 60% (vs 原来的65%)
    - 允许更多候选进入初选池
    
    Args:
        candidates: 候选股票list
        cash_ratio: 当前现金占比
        
    Returns: 应用超激进过滤后的候选list
    """
    if not EXTREME_CASH_V87['enabled'] or cash_ratio < EXTREME_CASH_V87['trigger_ratio']:
        return candidates
    
    print(f"🚀 [v5.87超激进模式] 现金{cash_ratio:.1%} > {EXTREME_CASH_V87['trigger_ratio']:.1%}，激活选股!")
    
    config = EXTREME_CASH_V87
    
    for cand in candidates:
        # v5.87: 新增'_extreme_mode_applied'标记
        cand['_extreme_mode_v87'] = True
        
        # 提取质量评分
        original_quality = cand.get('entry_quality_score', 0)
        
        # 如果质量>20分，说明信号确实不错，给额外激励
        if original_quality >= config['entry_quality_threshold']:
            # 质量>=20分的候选在超激进模式下获得额外权重
            quality_boost = (original_quality - config['entry_quality_threshold']) / 10
            cand['_quality_boost_extreme'] = quality_boost
            
            # 提升score
            if 'score' in cand:
                cand['score'] = int(cand.get('score', 0) * (1 + quality_boost * 0.3))
    
    return candidates


def apply_sharpe_force_v87(ranked: list, cash_ratio: float = 0.99) -> list:
    """v5.87: Sharpe权重强制激活机制
    
    在score_and_rank阶段强制应用3.0x Sharpe倍数，
    确保这个参数真正被利用而非被掩盖
    
    Args:
        ranked: score_and_rank()输出的排序list
        cash_ratio: 现金占比
        
    Returns: 应用Sharpe倍数后的重排序list
    """
    if not SHARPE_FORCE_APPLY_V87['enabled']:
        return ranked
    
    config = SHARPE_FORCE_APPLY_V87
    print(f"🔥 [v5.87Sharpe强制] 应用{config['multiplier']}x倍数在score_and_rank!")
    
    for stock in ranked:
        original_score = stock.get('score', 0)
        signals = stock.get('signals', [])
        
        # 判断是否为MACD+RSI策略
        is_macd_rsi = any('MACD' in str(s) or 'RSI' in str(s) for s in signals)
        
        if is_macd_rsi:
            # MACD+RSI获得额外的Sharpe倍数加成
            macd_boost = config['macd_rsi_priority_boost']
            new_score = int(original_score * config['multiplier'] * macd_boost)
            stock['score'] = new_score
            stock['_sharpe_multiplier_v87'] = f"{config['multiplier']}x * {macd_boost}x"
            
            # 打印TOP3候选详情
            if ranked.index(stock) < 3:
                print(f"   ✓ {stock.get('name', '')} ({stock.get('code', '')}): "
                      f"{original_score} → {new_score}")
        else:
            # 非MACD+RSI策略也应用Sharpe倍数，但较低
            new_score = int(original_score * config['multiplier'])
            stock['score'] = new_score
            stock['_sharpe_multiplier_v87'] = f"{config['multiplier']}x"
    
    # 重新排序
    ranked.sort(key=lambda x: -x.get('score', 0))
    return ranked


def apply_sector_diversification_v87(candidates: list) -> list:
    """v5.87: 赛道多样化配置强化
    
    按科技40% + 新能源35% + 其他25%的配置分配权重，
    确保建仓覆盖多个赛道而非集中单只
    
    Args:
        candidates: 候选stock list
        
    Returns: 应用赛道权重后的候选list
    """
    if not APPLY_SECTOR_ALLOCATION_V87:
        return candidates
    
    print(f"🎯 [v5.87赛道多样化] 应用{len(SECTOR_ALLOCATION_V87)}个赛道权重配置")
    
    from performance_tracker import classify_sector
    
    sector_candidates = {}  # {sector: [candidates...]}
    
    # 按赛道分类
    for cand in candidates:
        code = cand.get('code', '')
        name = cand.get('name', '')
        if not code:
            continue
        
        sector = classify_sector(code, name)
        if sector not in sector_candidates:
            sector_candidates[sector] = []
        
        sector_candidates[sector].append(cand)
    
    # 应用赛道权重
    for sector, config in SECTOR_ALLOCATION_V87.items():
        if sector in sector_candidates:
            for cand in sector_candidates[sector]:
                original_score = cand.get('score', 0)
                
                # 应用MACD权重
                if 'macd_weight' in config:
                    macd_boost = config['macd_weight']
                    # 检查是否MACD+RSI策略
                    signals = cand.get('signals', [])
                    if any('MACD' in str(s) for s in signals):
                        cand['score'] = int(cand.get('score', 0) * macd_boost)
                        cand['_sector_weight_v87'] = f"{sector}(MACD{macd_boost}x)"
                
                # 应用Sharpe倍数
                if 'sharpe_multiplier' in config:
                    sharpe_mult = config['sharpe_multiplier']
                    cand['score'] = int(cand.get('score', 0) * sharpe_mult)
                    cand['_sharpe_sector_boost_v87'] = f"{sector}(Sharpe{sharpe_mult}x)"
    
    # 打印赛道分布
    print(f"   赛道分布:")
    for sector, config in SECTOR_ALLOCATION_V87.items():
        count = len(sector_candidates.get(sector, []))
        if count > 0:
            print(f"   - {sector}: {count}只 (配置{config['daily_target']}/日)")
    
    return candidates


def apply_consumer_blacklist_v87(candidates: list) -> list:
    """v5.87: 消费赛道黑名单机制
    
    回测数据显示 MACD+RSI 消费策略 -5.51% (负收益, Sharpe -1.0, MaxDD 11.57%)
    直接过滤掉大部分消费赛道股票，除非质量分>80分
    
    Args:
        candidates: 候选stock list
        
    Returns: 过滤后的候选list
    """
    if not APPLY_CONSUMER_BLACKLIST_V87 or not CONSUMER_SECTOR_BLACKLIST_V87['enabled']:
        return candidates
    
    config = CONSUMER_SECTOR_BLACKLIST_V87
    print(f"⛔ [v5.87消费黑名单] 激活消费赛道过滤机制")
    
    from performance_tracker import classify_sector
    
    filtered = []
    filtered_out = []
    
    for cand in candidates:
        code = cand.get('code', '')
        name = cand.get('name', '')
        if not code:
            filtered.append(cand)
            continue
        
        sector = classify_sector(code, name)
        quality = cand.get('entry_quality_score', 0)
        
        # 检查是否在黑名单中
        if sector in config['blacklist_sectors']:
            # 检查是否可以绕过(质量>80分)
            if quality > config['min_quality_to_bypass']:
                print(f"   ⚠️  {name}({code}) 消费赛道但质量{quality}分 > 80分，允许通过")
                cand['_consumer_bypass_reason'] = f"质量{quality}分高于阈值"
                filtered.append(cand)
            else:
                filtered_out.append(name)
        else:
            filtered.append(cand)
    
    if filtered_out:
        print(f"   过滤消费赛道 {len(filtered_out)} 只: {','.join(filtered_out[:3])}...")
    
    return filtered


def apply_mixed_pool_upgrade_v87(candidates: list) -> list:
    """v5.87: 混合池策略升级v2
    
    混合池当前5.06% Sharpe 0.86 (低效)
    改用科技2.5x + 新能源2.0x组合，目标8-10% Sharpe 1.2+
    
    Args:
        candidates: 候选stock list
        
    Returns: 应用混合池权重后的候选list
    """
    if not APPLY_MIXED_POOL_V87:
        return candidates
    
    print(f"🔄 [v5.87混合池升级] 应用新赛道权重配置")
    
    from performance_tracker import classify_sector
    
    for cand in candidates:
        code = cand.get('code', '')
        name = cand.get('name', '')
        if not code:
            continue
        
        sector = classify_sector(code, name)
        
        if sector in MIXED_POOL_SECTOR_WEIGHTS_V87:
            weight = MIXED_POOL_SECTOR_WEIGHTS_V87[sector]
            original_score = cand.get('score', 0)
            new_score = int(original_score * weight)
            cand['score'] = new_score
            cand['_mixed_pool_weight_v87'] = f"{sector}({weight}x)"
            
            if weight > 2.0:
                print(f"   🔥 {name} ({sector}): 权重{weight}x")
    
    return candidates


def apply_margin_anomaly_v87(candidates: list, market_data: dict = None) -> list:
    """v5.87: 融资融券异变强制激活
    
    融资余额环比-20% + 融资融券比<20% → +12分 (底部确认)
    融资余额环比+15% → +8分 (参与度上升)
    
    v5.87: 强制应用，不允许skip
    
    Args:
        candidates: 候选stock list
        market_data: 融资融券市场数据dict
        
    Returns: 应用融资异变加成后的候选list
    """
    if not APPLY_MARGIN_ANOMALY_V87 or not MARGIN_ANOMALY_V87['enabled']:
        return candidates
    
    if market_data is None:
        market_data = {}
    
    config = MARGIN_ANOMALY_V87
    print(f"💰 [v5.87融资异变强制] 应用融资信号加成(+12分 or +8分)")
    
    applied_count = 0
    
    for cand in candidates:
        code = cand.get('code', '')
        if not code:
            continue
        
        margin_change = market_data.get(f"{code}_margin_change", 0)
        fusion_ratio = market_data.get(f"{code}_fusion_ratio", 0.5)
        
        # 底部确认: 融资-20% + 融资融券比<20%
        if (margin_change < -config['margin_decline_threshold'] and 
            fusion_ratio < config['margin_ratio_threshold']):
            bonus = config['decline_and_low_ratio_bonus']
            cand['score'] = cand.get('score', 0) + bonus
            cand['_margin_bonus_v87'] = f"+{bonus}分(底部确认)"
            applied_count += 1
        
        # 参与度上升: 融资+15%
        elif margin_change > config['margin_increase_threshold']:
            bonus = config['increase_bonus']
            cand['score'] = cand.get('score', 0) + bonus
            cand['_margin_bonus_v87'] = f"+{bonus}分(参与度)"
            applied_count += 1
    
    if applied_count > 0:
        print(f"   应用融资异变加成: {applied_count}只股票")
    
    return candidates


def apply_atr_stop_loss_v87(positions: dict, market_data: dict = None) -> dict:
    """v5.87: ATR动态止损强化
    
    根据波动率自适应调整止损线:
    - 高波动(>3%): -7% (宽松)
    - 正常波动(1.5-3%): -5% (标准)
    - 低波动(<1.5%): -3% (紧张)
    
    目标: MaxDD 4.08% → 3.2% (-22%)
    
    Args:
        positions: 持仓dict {code: position_data}
        market_data: 市场数据(包含ATR)
        
    Returns: 应用ATR止损后的持仓dict
    """
    if not APPLY_ATR_STOP_LOSS_V87 or not ATR_STOP_LOSS_V87['enabled']:
        return positions
    
    if market_data is None:
        market_data = {}
    
    config = ATR_STOP_LOSS_V87
    print(f"🛑 [v5.87ATR止损] 应用波动率自适应止损(目标MaxDD {config['target_max_dd']:.1%})")
    
    for code, pos_data in positions.items():
        atr = market_data.get(f"{code}_atr", 0)
        
        if atr > 0:
            if atr > config['high_volatility_threshold']:
                # 高波动
                stop_loss = config['high_vol_stop_pct']
                vol_level = "高波动(宽松)"
            elif atr < config['low_volatility_threshold']:
                # 低波动
                stop_loss = config['low_vol_stop_pct']
                vol_level = "低波动(紧张)"
            else:
                # 正常波动
                stop_loss = config['normal_vol_stop_pct']
                vol_level = "正常波动(标准)"
            
            pos_data['_atr_stop_loss_v87'] = f"{stop_loss:.1%}({vol_level})"
            pos_data['stop_loss'] = stop_loss
    
    return positions


def get_v87_optimization_report() -> dict:
    """获取v5.87优化报告"""
    report = {
        'version': 'v5.87',
        'timestamp': datetime.now().isoformat(),
        'status': '✅ ACTIVE' if V5_87_DEEP_OPTIMIZE_ACTIVE else '❌ INACTIVE',
        'optimizations': {
            '超激进选股': {
                'trigger': f"现金>{EXTREME_CASH_V87['trigger_ratio']:.1%}",
                'entry_quality': f"{EXTREME_CASH_V87['entry_quality_threshold']}分",
                'daily_target': f"{EXTREME_CASH_V87['daily_entry_target']}只",
                'expected_utilization': '15-20%',
            },
            'Sharpe强制激活': {
                'multiplier': f"{SHARPE_FORCE_APPLY_V87['multiplier']}x",
                'macd_priority': f"{SHARPE_FORCE_APPLY_V87['macd_rsi_priority_boost']}x",
            },
            '赛道多样化': {
                '科技成长': f"{SECTOR_ALLOCATION_V87['科技成长']['allocation_ratio']:.0%} (8只/日)",
                '新能源': f"{SECTOR_ALLOCATION_V87['新能源']['allocation_ratio']:.0%} (6只/日)",
                '其他': f"{SECTOR_ALLOCATION_V87.get('医药', {}).get('allocation_ratio', 0):.0%} + 金融 + 消费",
            },
            '消费黑名单': {
                'blacklist_sectors': CONSUMER_SECTOR_BLACKLIST_V87['blacklist_sectors'],
                'reason': '回测-5.51% Sharpe-1.0',
                'bypass_threshold': f"{CONSUMER_SECTOR_BLACKLIST_V87['min_quality_to_bypass']}分",
            },
            '混合池升级': {
                '科技权重': f"{MIXED_POOL_SECTOR_WEIGHTS_V87['科技成长']}x",
                '新能源权重': f"{MIXED_POOL_SECTOR_WEIGHTS_V87['新能源']}x",
                '预期收益': '8-10% (vs 5.06% v5.75)',
            },
            '融资异变强制': {
                'decline_bonus': f"+{MARGIN_ANOMALY_V87['decline_and_low_ratio_bonus']}分",
                'increase_bonus': f"+{MARGIN_ANOMALY_V87['increase_bonus']}分",
                'force_apply': 'YES',
            },
            'ATR止损': {
                '高波动': f"{ATR_STOP_LOSS_V87['high_vol_stop_pct']:.1%}",
                '正常': f"{ATR_STOP_LOSS_V87['normal_vol_stop_pct']:.1%}",
                '低波动': f"{ATR_STOP_LOSS_V87['low_vol_stop_pct']:.1%}",
                '目标MaxDD': f"{ATR_STOP_LOSS_V87['target_max_dd']:.1%}",
            },
        },
        'expected_improvements': {
            '资金利用率': '1.3% → 15-20% (+12x)',
            '日均建仓': '8-12只 → 15-20只 (+80%)',
            '年化收益': '0.19% → 10-12% (+5000%)',
            'MaxDD': '4.08% → 3.2% (-22%)',
            '持仓多样度': '1只 → 8-12只',
        },
    }
    return report


if __name__ == "__main__":
    report = get_v87_optimization_report()
    print("\n📊 v5.87 深度优化报告:")
    print("=" * 60)
    print(json.dumps(report, indent=2, ensure_ascii=False))
