"""
v5.56 入场质量评分系统重构 — 5维×20分模型
评估"现在买这只股票好不好" (当下时机而非股票本身)

v5.56 重构:
- 从4维25分 → 5维20分 (总分仍为100)
- 新增"机构稳定性"维度,预防踩坑,提高连板准确率
- 权重均衡化,更公正的多因子评估

预期效果: 踩坑率-30%, 连板命中率+20%
"""

from config import ENTRY_QUALITY_SCORE_WEIGHTS, INSTITUTION_HOLDING_THRESHOLDS


def get_institution_holding_score(tech_indicators: dict) -> int:
    """
    获取机构持仓稳定性评分 (0-20分)
    
    评分点:
    - 机构持股比 > 20%: +15分
    - 机构持股环比增加: +8分  
    - 融资余额 < 流通市值2%: +5分
    - 北向持股稳定 (±5%以内): +5分
    """
    score = 0
    
    # 机构持股比
    institution_pct = tech_indicators.get('institution_holding_pct', 0)
    if institution_pct > INSTITUTION_HOLDING_THRESHOLDS['high_hold_pct']:
        score += 15  # 机构持股>20%
    elif institution_pct > 0.15:
        score += 10  # 机构持股>15%
    elif institution_pct > 0.10:
        score += 5   # 机构持股>10%
    
    # 机构环比增加
    institution_change = tech_indicators.get('institution_holding_change', 0)
    if institution_change > 0.02:  # 环比增加>2%
        score += INSTITUTION_HOLDING_THRESHOLDS['institution_increase_bonus']
    elif institution_change > 0.01:
        score += 4
    
    # 融资余额占比
    margin_balance_ratio = tech_indicators.get('margin_balance_ratio', 0.05)
    if margin_balance_ratio < INSTITUTION_HOLDING_THRESHOLDS['margin_balance_pct']:
        score += 5
    
    # 北向持股稳定性
    northbound_change = abs(tech_indicators.get('northbound_change', 0.1))
    if northbound_change <= INSTITUTION_HOLDING_THRESHOLDS['northbound_stable_range']:
        score += 5  # ±5%以内稳定
    elif northbound_change <= 0.10:
        score += 3  # ±10%以内稳定
    
    return min(score, 20)


def calculate_entry_quality_score(tech_indicators: dict, market_context: dict = None) -> tuple:
    """
    评估入场时机质量 (0-100分)
    五维评估: 趋势对齐(20) + 位置优势(20) + 量价确认(20) + 动量确认(20) + 机构稳定(20)
    
    v5.56 重构:
    - 从4维25分 → 5维20分 (总分仍为100)
    - 新增"机构稳定性"维度,预防踩坑
    - 权重均衡化,更公正的多因子评估
    
    Returns: (total_score, scores_breakdown)
    """
    if not tech_indicators or not isinstance(tech_indicators, dict):
        return 0, {'trend': 0, 'position': 0, 'volume': 0, 'momentum': 0, 'institution': 0}
    
    scores = {'trend': 0, 'position': 0, 'volume': 0, 'momentum': 0, 'institution': 0}
    
    # ========== Dimension 1: 趋势对齐 (0-20分, 从25→20) ==========
    # 日线+周线+MACD+RSI四个维度同向
    dimensions_bullish = 0
    
    trend = tech_indicators.get('trend', '')
    if trend in ['多头', '强势', '上升']:
        dimensions_bullish += 1
    
    weekly_trend = tech_indicators.get('weekly_trend', '')
    if weekly_trend in ['上升', '多头', '强势']:
        dimensions_bullish += 1
    
    macd_signal = tech_indicators.get('macd_signal', '')
    if macd_signal in ['bullish', 'golden_cross', 'fresh_golden']:
        dimensions_bullish += 1
    
    rsi = tech_indicators.get('rsi14', 50)
    if 40 < rsi < 70:
        dimensions_bullish += 1
    
    scores['trend'] = int((dimensions_bullish / 4.0) * 20)  # 20分
    
    # ========== Dimension 2: 位置优势 (0-20分) ==========
    position_bonus = 0
    
    if tech_indicators.get('near_support'):
        position_bonus += 8
    
    z_score = tech_indicators.get('price_z_score', 0)
    if z_score < -1.5:
        position_bonus += 6
    elif z_score < -1.0:
        position_bonus += 3
    
    if tech_indicators.get('near_fib_support'):
        position_bonus += 5
    
    if tech_indicators.get('near_vp_support'):
        position_bonus += 4
    
    scores['position'] = min(position_bonus, 20)
    
    # ========== Dimension 3: 量价确认 (0-20分) ==========
    volume_bonus = 0
    
    obv_trend = tech_indicators.get('obv_trend', 0)
    if obv_trend > 10:
        volume_bonus += 8
    elif obv_trend > 0:
        volume_bonus += 4
    
    cmf_20 = tech_indicators.get('cmf_20', 0)
    if cmf_20 > 0.15:
        volume_bonus += 8
    elif cmf_20 > 0.05:
        volume_bonus += 5
    
    volume_ratio = tech_indicators.get('volume_ratio', 1.0)
    if volume_ratio > 1.5:
        volume_bonus += 4
    elif volume_ratio > 1.2:
        volume_bonus += 2
    
    scores['volume'] = min(volume_bonus, 20)
    
    # ========== Dimension 4: 动量确认 (0-20分) ==========
    momentum_bonus = 0
    
    macd_signal = tech_indicators.get('macd_signal', '')
    if macd_signal == 'golden_cross':
        momentum_bonus += 10
    elif macd_signal == 'fresh_golden':
        momentum_bonus += 6
    elif macd_signal == 'bullish':
        momentum_bonus += 4
    
    williams_r = tech_indicators.get('williams_r', -50)
    if williams_r > -20:
        momentum_bonus += 2
    elif -50 < williams_r < -30:
        momentum_bonus += 4
    
    adx = tech_indicators.get('adx', 20)
    if adx > 30:
        momentum_bonus += 6
    elif adx > 25:
        momentum_bonus += 4
    
    scores['momentum'] = min(momentum_bonus, 20)
    
    # ========== Dimension 5: 机构稳定性 (0-20分, 新增维度) ==========
    # v5.56 新增: 机构持仓能有效预防踩坑,提高连板准确率
    scores['institution'] = get_institution_holding_score(tech_indicators)
    
    # ========== 总分计算 ==========
    # 20+20+20+20+20 = 100分
    total_score = sum(scores.values())
    return total_score, scores


def filter_by_entry_quality(candidates: list, threshold: int = 65, market_context: dict = None) -> list:
    """
    使用入场质量评分过滤候选股
    
    Args:
        candidates: 候选股列表 (包含technical指标)
        threshold: 通过门槛 (默认65分)
        market_context: 市场上下文 (非必需)
    
    Returns: 过滤后的候选股 (添加entry_quality字段)
    """
    filtered = []
    
    for cand in candidates:
        if 'technical' not in cand or not cand['technical']:
            cand['entry_quality_score'] = 50
            filtered.append(cand)
            continue
        
        tech = cand['technical']
        score, breakdown = calculate_entry_quality_score(tech, market_context)
        cand['entry_quality_score'] = score
        cand['entry_quality_breakdown'] = breakdown
        
        if score >= threshold:
            filtered.append(cand)
    
    return filtered


def adjust_score_by_entry_quality(candidates: list, multiplier_range: tuple = (0.7, 1.3)) -> list:
    """
    根据入场质量调整候选股的总分
    (而非简单过滤,而是用乘数调权)
    """
    min_mult, max_mult = multiplier_range
    
    for cand in candidates:
        if 'entry_quality_score' not in cand:
            tech = cand.get('technical', {})
            score, _ = calculate_entry_quality_score(tech)
            cand['entry_quality_score'] = score
        
        eq_score = cand.get('entry_quality_score', 50)
        mult = min_mult + (eq_score / 100.0) * (max_mult - min_mult)
        
        orig_score = cand.get('score', 0)
        cand['score'] = int(orig_score * mult)
        cand['_eq_multiplier'] = round(mult, 2)
    
    return candidates


# ============================================================
# v5.54 现存: 动态入场质量阈值
# ============================================================

def get_dynamic_entry_quality_threshold(cash_ratio: float = None) -> int:
    """
    v5.54 盘前优化①: 根据现金占比动态调整入场质量阈值
    
    现金占比 < 75% → 65分 (正常严格模式)
    现金占比 75-95% → 55分 (宽松模式, -10分)
    现金占比 > 95% → 45分 (激进模式, -20分快速消耗现金)
    """
    try:
        from config import ENTRY_QUALITY_DYNAMIC_THRESHOLDS
        
        if cash_ratio is None:
            try:
                import sqlite3
                from config import DB_PATH
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute('SELECT SUM(cash_after) FROM trades ORDER BY id DESC LIMIT 1')
                current_cash = c.fetchone()[0] or 1_000_000
                c.execute('SELECT SUM(quantity*price) FROM positions WHERE status="OPEN"')
                current_holdings = c.fetchone()[0] or 0
                conn.close()
                total_value = current_cash + current_holdings
                cash_ratio = current_cash / total_value if total_value > 0 else 0.98
            except:
                cash_ratio = 0.95
        
        if cash_ratio > 0.95:
            thresh = ENTRY_QUALITY_DYNAMIC_THRESHOLDS.get('extreme_cash', 45)
        elif cash_ratio > 0.75:
            thresh = ENTRY_QUALITY_DYNAMIC_THRESHOLDS.get('high_cash', 55)
        else:
            thresh = ENTRY_QUALITY_DYNAMIC_THRESHOLDS.get('normal', 65)
        
        return thresh
    except:
        return 65


def enrich_candidates_with_entry_quality(candidates: list) -> list:
    """
    为候选股添加入场质量评分
    v5.54: 支持动态阈值 (根据现金占比自动调整)
    """
    for cand in candidates:
        if 'technical' not in cand:
            cand['entry_quality_score'] = 50
            continue
        
        score, breakdown = calculate_entry_quality_score(cand['technical'])
        cand['entry_quality_score'] = score
        cand['entry_quality_breakdown'] = breakdown
    
    dynamic_threshold = get_dynamic_entry_quality_threshold()
    for cand in candidates:
        cand['_entry_quality_threshold'] = dynamic_threshold
    
    return candidates
