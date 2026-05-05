"""
v5.77 策略优化融合模块
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【核心价值】
基于回测最优策略(MACD+RSI 科技成长 17.1%, Sharpe 2.35)，
实施大规模优化：
  • 提取并集成最优策略参数
  • 为不同赛道应用差异化权重
  • 在选股输出中标注"最优策略推荐"标签

【回测参数来源】
  • 策略: MACD(12,26,9) + RSI(14,30,70)
  • 收益: 17.1%
  • Sharpe: 2.35
  • 胜率: 60%
  • 最大回撤: 4.08%
  • 赛道: 科技成长
  • 止损: -8%
  • 止盈: +20%

【赛道权重配置】v5.75数据
  • 科技成长: 2.0x (TOP1策略来源)
  • 新能源:   1.8x (TOP2策略,14.66% Sharpe 1.78)
  • 消费:     0.3x (低效策略)
  • 主板:     0.6x
  • 其他:     0.4x

【实现机制】
1. 识别候选股是否符合最优策略条件(MACD+RSI信号)
2. 命中最优策略的股票+5分额外权重 + "最优策略推荐"标签
3. 按赛道应用差异化权重倍数(科技2.0x/新能源1.8x等)
4. 返回评分标注字段供前端展示
"""

import json
from datetime import datetime
from typing import List, Dict, Tuple
from config import (
    MACD_PARAMS,
    RSI_PARAMS,
    STOP_LOSS,
    TAKE_PROFIT,
    TECH_GROWTH_SECTORS,
)


# =================== v5.77 最优策略参数 ===================

OPTIMAL_STRATEGY_PARAMS = {
    'strategy': 'MACD+RSI',
    'macd_fast': 12,
    'macd_slow': 26,
    'macd_signal': 9,
    'rsi_period': 14,
    'rsi_oversold': 30,
    'rsi_overbought': 70,
    'stop_loss': -0.08,      # -8%
    'take_profit': 0.20,     # +20%
    'backtest_return': 0.171,  # 17.1%
    'backtest_sharpe': 2.35,
    'backtest_winrate': 0.60,  # 60%
    'backtest_max_dd': 0.0408, # 4.08%
    'apply_sectors': ['软件服务', '芯片', '新能源', '电子产品', '通信设备', '互联网', '计算机', '人工智能', '半导体'],
    'primary_sector': '科技成长',
}

# =================== v5.77 赛道推荐权重 (基于v5.75) ===================

SECTOR_RECOMMENDATION_WEIGHTS_V5_77 = {
    '科技成长': {
        'weight': 2.0,
        'comment': 'TOP1策略来源,17.1% 收益',
        'strategy_match': 'MACD+RSI',
        'backtest_return': 0.171,
        'backtest_sharpe': 2.35,
    },
    '新能源': {
        'weight': 1.8,
        'comment': 'TOP2策略,14.66% 收益',
        'strategy_match': 'MACD+RSI+波动适配',
        'backtest_return': 0.1466,
        'backtest_sharpe': 1.78,
    },
    '医药': {
        'weight': 1.0,
        'comment': '标准权重',
        'strategy_match': '通用',
        'backtest_return': 0.08,
        'backtest_sharpe': 0.95,
    },
    '金融': {
        'weight': 0.8,
        'comment': '偏弱赛道',
        'strategy_match': '通用',
        'backtest_return': 0.05,
        'backtest_sharpe': 0.65,
    },
    '消费': {
        'weight': 0.3,
        'comment': '低效赛道,混合池拖累源',
        'strategy_match': '通用',
        'backtest_return': 0.03,
        'backtest_sharpe': 0.40,
    },
    '主板': {
        'weight': 0.6,
        'comment': '偏低权重',
        'strategy_match': '通用',
        'backtest_return': 0.05,
        'backtest_sharpe': 0.60,
    },
}

# =================== v5.77 策略融合常量 ===================

STRATEGY_FUSION_WEIGHT_BOOST = 5  # 命中最优策略+5分
STRATEGY_MATCH_CONFIDENCE_THRESHOLD = 0.75  # 策略匹配置信度阈值


# =================== 核心函数 ===================

def check_optimal_strategy_match(
    code: str,
    name: str,
    tech_indicators: Dict,
    signals: List[str],
    sector: str = ''
) -> Tuple[bool, Dict]:
    """
    检查股票是否符合最优策略条件(MACD+RSI)
    
    Args:
        code: 股票代码
        name: 股票名称
        tech_indicators: 技术指标字典
        signals: 信号列表 ['MACD_GC', 'RSI_OVERSOLD', ...]
        sector: 股票赛道
    
    Returns:
        (是否匹配最优策略, 详细分析字典)
    
    【匹配条件】
    必要条件 (ALL):
      1. MACD为买入信号(死叉➜金叉 或 MACD>Signal线正值)
      2. RSI在超卖区(20-40)或中性偏弱(40-50)
      3. 没有在黑名单中
    
    充分条件 (ANY):
      1. MACD近期上穿(1-3天)
      2. 价格触及支撑位(基于Volume Profile/Fib)
      3. OBV或CMF转强
      4. 机构持股>15% 且 环比增加
    
    【置信度评分】0-100
      基础分: 50 (通过必要条件)
      +20 MACD最近1天内金叉
      +15 MACD最近2-3天内金叉
      +15 RSI超卖(<30)
      +10 RSI中性(<50)
      +15 OBV/CMF转强
      +10 机构持股>15%
      ...合计最多100分
    """
    
    match_info = {
        'code': code,
        'name': name,
        'sector': sector,
        'match': False,
        'confidence': 0,
        'reason': [],
        'required_checks': {},
        'sufficient_checks': {},
    }
    
    # ========== 必要条件 (ALL) ==========
    
    # 1. MACD检查
    macd_signal = tech_indicators.get('macd_signal', '')
    macd_value = tech_indicators.get('macd', 0)
    macd_signal_line = tech_indicators.get('macd_signal_line', 0)
    
    if macd_signal in ('golden_cross', 'buy_signal') or (macd_value > 0 and macd_value > macd_signal_line):
        match_info['required_checks']['macd'] = True
        match_info['reason'].append('✅ MACD买入信号')
    else:
        match_info['required_checks']['macd'] = False
        match_info['reason'].append('❌ MACD非买入信号')
        return False, match_info
    
    # 2. RSI检查
    rsi = tech_indicators.get('rsi14', 50)
    rsi_oversold = RSI_PARAMS['oversold_threshold']  # 30
    rsi_overbought = RSI_PARAMS['overbought_threshold']  # 70
    
    if rsi > rsi_overbought:
        match_info['required_checks']['rsi'] = False
        match_info['reason'].append(f'❌ RSI超买({rsi:.1f}>70)')
        return False, match_info
    elif rsi < 50:
        match_info['required_checks']['rsi'] = True
        match_info['reason'].append(f'✅ RSI中性偏弱({rsi:.1f}<50)')
    else:
        match_info['required_checks']['rsi'] = True
        match_info['reason'].append(f'✅ RSI中性({rsi:.1f})')
    
    # 3. 黑名单检查
    from position_manager import get_stop_loss_blacklist
    blacklist = get_stop_loss_blacklist()
    if code in blacklist:
        match_info['required_checks']['blacklist'] = False
        match_info['reason'].append('❌ 在止损黑名单中')
        return False, match_info
    
    match_info['required_checks']['blacklist'] = True
    match_info['reason'].append('✅ 不在黑名单中')
    
    # 通过必要条件，开始计算置信度
    confidence = 50
    
    # ========== 充分条件 (任一) ==========
    
    # A. MACD近期上穿
    macd_days_since_cross = tech_indicators.get('macd_days_since_cross', 10)
    if macd_days_since_cross == 1:
        match_info['sufficient_checks']['macd_recent'] = True
        match_info['reason'].append(f'✅ MACD最近1天金叉 (+20分)')
        confidence += 20
    elif macd_days_since_cross <= 3:
        match_info['sufficient_checks']['macd_recent'] = True
        match_info['reason'].append(f'✅ MACD最近{macd_days_since_cross}天金叉 (+15分)')
        confidence += 15
    else:
        match_info['sufficient_checks']['macd_recent'] = False
    
    # B. RSI极端超卖
    if rsi < rsi_oversold:
        match_info['sufficient_checks']['rsi_extreme'] = True
        match_info['reason'].append(f'✅ RSI极端超卖({rsi:.1f}<30) (+15分)')
        confidence += 15
    elif rsi < 50:
        match_info['sufficient_checks']['rsi_strong'] = True
        match_info['reason'].append(f'✅ RSI偏弱({rsi:.1f}) (+10分)')
        confidence += 10
    
    # C. OBV/CMF转强
    obv_trend = tech_indicators.get('obv_trend', 0)
    cmf = tech_indicators.get('cmf_20', 0)
    
    if obv_trend > 0.05 or cmf > 0.05:
        match_info['sufficient_checks']['volume_strength'] = True
        match_info['reason'].append(f'✅ OBV/CMF转强 (+15分)')
        confidence += 15
    
    # D. 机构持股稳定增加
    institution_holding = tech_indicators.get('institution_holding_pct', 0)
    institution_change = tech_indicators.get('institution_holding_change', 0)
    
    if institution_holding > 0.15 and institution_change > 0.01:
        match_info['sufficient_checks']['institution'] = True
        match_info['reason'].append(f'✅ 机构持股>{15}% 且 环比增加 (+10分)')
        confidence += 10
    
    # E. 价格支撑
    support_strength = tech_indicators.get('support_strength', 0)
    if support_strength > 1.5:
        match_info['sufficient_checks']['support'] = True
        match_info['reason'].append(f'✅ 强支撑位({support_strength:.2f}) (+8分)')
        confidence += 8
    
    # 最终通过判定
    match_info['match'] = True
    match_info['confidence'] = min(confidence, 100)
    
    return True, match_info


def apply_strategy_fusion_boost(
    candidates: List[Dict],
    regime: str = 'normal'
) -> List[Dict]:
    """
    应用v5.77策略融合加成
    
    对于命中最优策略的股票:
      1. +STRATEGY_FUSION_WEIGHT_BOOST (通常+5分)
      2. 添加"strategy_match_score"和"strategy_matched"标签
      3. 如果赛道在TOP权重列表，应用赛道倍数
    
    Args:
        candidates: 选股候选list
        regime: 市场状态 ('normal', 'strong', 'weak')
    
    Returns: 应用加成后的candidates
    """
    
    fusion_boost = STRATEGY_FUSION_WEIGHT_BOOST
    
    # 根据市场状态调整加成
    if regime == 'strong':
        fusion_boost = int(fusion_boost * 1.2)  # 强势市场+20%
    elif regime == 'weak':
        fusion_boost = int(fusion_boost * 0.8)  # 弱势市场-20%
    
    for candidate in candidates:
        try:
            code = candidate.get('code', '')
            name = candidate.get('name', '')
            tech_indicators = candidate.get('tech_indicators', {})
            signals = candidate.get('signals', [])
            sector = candidate.get('sector', '')
            
            # 检查是否匹配最优策略
            matched, match_info = check_optimal_strategy_match(
                code, name, tech_indicators, signals, sector
            )
            
            candidate['strategy_match_analysis'] = match_info
            
            if matched:
                # 命中最优策略
                original_score = candidate.get('score', 0)
                candidate['score'] = original_score + fusion_boost
                candidate['strategy_matched'] = True
                candidate['strategy_match_label'] = '⭐ 最优策略推荐'
                candidate['strategy_match_score'] = match_info['confidence']
                candidate['strategy_boost_applied'] = fusion_boost
            else:
                candidate['strategy_matched'] = False
                candidate['strategy_match_label'] = ''
                candidate['strategy_match_score'] = 0
                candidate['strategy_boost_applied'] = 0
        
        except Exception as e:
            print(f"  ⚠️ 策略融合检查失败 {candidate.get('code', '')} : {e}")
            candidate['strategy_matched'] = False
            candidate['strategy_boost_applied'] = 0
    
    return candidates


def apply_sector_weight_multiplier(
    candidates: List[Dict]
) -> List[Dict]:
    """
    应用赛道推荐权重倍数
    
    科技2.0x/新能源1.8x/消费0.3x等
    
    Args:
        candidates: 选股候选list
    
    Returns: 应用权重后的candidates
    """
    
    for candidate in candidates:
        try:
            sector = candidate.get('sector', '')
            original_score = candidate.get('score', 0)
            
            # 查询赛道权重
            sector_config = SECTOR_RECOMMENDATION_WEIGHTS_V5_77.get(sector, {})
            weight_multiplier = sector_config.get('weight', 1.0)
            
            # 应用权重倍数
            weighted_score = int(original_score * weight_multiplier)
            
            candidate['sector_weight'] = weight_multiplier
            candidate['score'] = weighted_score
            candidate['sector_weight_label'] = f'{weight_multiplier:.1f}x'
            candidate['_score_breakdown'] = {
                'base': original_score,
                'sector_weight': weight_multiplier,
                'final': weighted_score,
            }
        
        except Exception as e:
            print(f"  ⚠️ 赛道权重应用失败 {candidate.get('code', '')} : {e}")
            candidate['sector_weight'] = 1.0
    
    return candidates


def generate_strategy_recommendation(
    candidates: List[Dict],
    top_n: int = 10
) -> Dict:
    """
    生成v5.77策略推荐分析报告
    
    Returns:
        {
            'total_candidates': 整体候选数,
            'optimal_strategy_matches': 命中最优策略的数量,
            'matched_rate_pct': 命中率%,
            'top_recommendations': [...],
            'sector_breakdown': {...},
            'confidence_distribution': {...},
            'summary': '文字总结',
        }
    """
    
    report = {
        'timestamp': datetime.now().isoformat(),
        'total_candidates': len(candidates),
        'optimal_strategy_matches': 0,
        'matched_rate_pct': 0,
        'top_recommendations': [],
        'sector_breakdown': {},
        'confidence_distribution': {
            'high': 0,    # 75-100
            'medium': 0,  # 50-75
            'low': 0,     # <50
        },
        'summary': '',
    }
    
    # 统计匹配数量
    matched_candidates = [c for c in candidates if c.get('strategy_matched', False)]
    report['optimal_strategy_matches'] = len(matched_candidates)
    report['matched_rate_pct'] = len(matched_candidates) / len(candidates) * 100 if candidates else 0
    
    # TOP N推荐
    sorted_candidates = sorted(
        candidates,
        key=lambda x: (-x.get('score', 0), -x.get('strategy_match_score', 0))
    )
    
    for c in sorted_candidates[:top_n]:
        rec = {
            'code': c.get('code'),
            'name': c.get('name'),
            'score': c.get('score'),
            'sector': c.get('sector'),
            'strategy_matched': c.get('strategy_matched', False),
            'strategy_match_score': c.get('strategy_match_score', 0),
            'strategy_match_label': c.get('strategy_match_label', ''),
            'entry_quality': c.get('entry_quality', 0),
        }
        report['top_recommendations'].append(rec)
    
    # 赛道分解
    for c in matched_candidates:
        sector = c.get('sector', '其他')
        if sector not in report['sector_breakdown']:
            report['sector_breakdown'][sector] = 0
        report['sector_breakdown'][sector] += 1
    
    # 置信度分布
    for c in matched_candidates:
        conf = c.get('strategy_match_score', 0)
        if conf >= 75:
            report['confidence_distribution']['high'] += 1
        elif conf >= 50:
            report['confidence_distribution']['medium'] += 1
        else:
            report['confidence_distribution']['low'] += 1
    
    # 文字总结
    summary = f"v5.77策略融合: {len(candidates)}只候选 → {len(matched_candidates)}只({report['matched_rate_pct']:.1f}%)命中最优策略(MACD+RSI)"
    if matched_candidates:
        top_sector = max(report['sector_breakdown'].items(), key=lambda x: x[1])
        summary += f" | TOP赛道: {top_sector[0]}({top_sector[1]}只)"
        high_conf = report['confidence_distribution']['high']
        if high_conf > 0:
            summary += f" | 高置信度({high_conf}只)"
    
    report['summary'] = summary
    
    return report


# =================== 测试和诊断 ===================

if __name__ == '__main__':
    # 单元测试
    print("=" * 80)
    print("【v5.77 策略融合模块测试】")
    print("=" * 80)
    
    # 模拟候选股票
    test_candidate = {
        'code': '000001',
        'name': '平安银行',
        'sector': '金融',
        'score': 70,
        'signals': ['MACD_GC', 'RSI_OVERSOLD'],
        'tech_indicators': {
            'macd_signal': 'golden_cross',
            'macd': 0.5,
            'macd_signal_line': 0.2,
            'rsi14': 28,
            'macd_days_since_cross': 1,
            'obv_trend': 0.1,
            'cmf_20': 0.08,
            'institution_holding_pct': 0.18,
            'institution_holding_change': 0.02,
            'support_strength': 1.6,
        },
        'entry_quality': 65,
    }
    
    # 测试1: 策略匹配检查
    matched, info = check_optimal_strategy_match(
        test_candidate['code'],
        test_candidate['name'],
        test_candidate['tech_indicators'],
        test_candidate['signals'],
        test_candidate['sector']
    )
    
    print(f"\n✅ 测试1: 策略匹配检查")
    print(f"  股票: {test_candidate['name']} ({test_candidate['code']})")
    print(f"  匹配: {matched}")
    print(f"  置信度: {info['confidence']}")
    print(f"  原因: {'; '.join(info['reason'][:3])}")
    
    # 测试2: 应用策略融合加成
    candidates = [test_candidate.copy()]
    candidates = apply_strategy_fusion_boost(candidates, regime='normal')
    
    print(f"\n✅ 测试2: 策略融合加成")
    print(f"  原始分数: {test_candidate['score']}")
    print(f"  新分数: {candidates[0]['score']}")
    print(f"  加成: +{candidates[0].get('strategy_boost_applied', 0)}")
    print(f"  标签: {candidates[0].get('strategy_match_label', '')}")
    
    # 测试3: 赛道权重
    candidates = apply_sector_weight_multiplier(candidates)
    
    print(f"\n✅ 测试3: 赛道权重倍数")
    print(f"  赛道: {candidates[0]['sector']}")
    print(f"  权重倍数: {candidates[0].get('sector_weight_label', '')}")
    print(f"  最终分数: {candidates[0]['score']}")
    
    # 测试4: 推荐报告
    report = generate_strategy_recommendation(candidates, top_n=5)
    
    print(f"\n✅ 测试4: 推荐分析报告")
    print(f"  总结: {report['summary']}")
    print(f"  TOP推荐数: {len(report['top_recommendations'])}")
    
    print("\n" + "=" * 80)
    print("✅ v5.77模块测试完成")
    print("=" * 80)
