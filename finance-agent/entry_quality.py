"""
v5.53 入场质量评分系统 — 4维×25分模型
评估"现在买这只股票好不好" (当下时机而非股票本身)
"""

def calculate_entry_quality_score(tech_indicators: dict, market_context: dict = None) -> tuple:
    """
    评估入场时机质量 (0-100分)
    四维评估: 趋势对齐(25) + 位置优势(25) + 量价确认(25) + 动量确认(25)
    
    Returns: (total_score, scores_breakdown)
    """
    if not tech_indicators or not isinstance(tech_indicators, dict):
        return 0, {'trend': 0, 'position': 0, 'volume': 0, 'momentum': 0}
    
    scores = {'trend': 0, 'position': 0, 'volume': 0, 'momentum': 0}
    
    # ========== Dimension 1: 趋势对齐 (0-25) ==========
    # 日线+周线+MACD+RSI四个维度同向
    dimensions_bullish = 0
    
    # 日线趋势
    trend = tech_indicators.get('trend', '')
    if trend in ['多头', '强势', '上升']:
        dimensions_bullish += 1
    
    # 周线趋势
    weekly_trend = tech_indicators.get('weekly_trend', '')
    if weekly_trend in ['上升', '多头', '强势']:
        dimensions_bullish += 1
    
    # MACD趋势
    macd_signal = tech_indicators.get('macd_signal', '')
    if macd_signal in ['bullish', 'golden_cross', 'fresh_golden']:
        dimensions_bullish += 1
    
    # RSI安全区
    rsi = tech_indicators.get('rsi14', 50)
    if 40 < rsi < 70:  # RSI适中，安全区
        dimensions_bullish += 1
    
    scores['trend'] = int((dimensions_bullish / 4.0) * 25)
    
    # ========== Dimension 2: 位置优势 (0-25) ==========
    # 支撑位/超卖区/FIB支撑 任一达成
    position_bonus = 0
    
    if tech_indicators.get('near_support'):
        position_bonus += 10  # 接近支撑位+10
    
    z_score = tech_indicators.get('price_z_score', 0)
    if z_score < -1.5:
        position_bonus += 8   # 统计超卖<-1.5 +8
    elif z_score < -1.0:
        position_bonus += 4   # 超卖区 +4
    
    if tech_indicators.get('near_fib_support'):
        position_bonus += 7   # FIB支撑+7
    
    if tech_indicators.get('near_vp_support'):
        position_bonus += 5   # Volume Profile支撑+5
    
    scores['position'] = min(position_bonus, 25)
    
    # ========== Dimension 3: 量价确认 (0-25) ==========
    # OBV/CMF/成交量配合
    volume_bonus = 0
    
    obv_trend = tech_indicators.get('obv_trend', 0)
    if obv_trend > 10:
        volume_bonus += 10  # OBV上升+10
    elif obv_trend > 0:
        volume_bonus += 5
    
    cmf_20 = tech_indicators.get('cmf_20', 0)
    if cmf_20 > 0.15:
        volume_bonus += 10  # CMF正向强流入+10
    elif cmf_20 > 0.05:
        volume_bonus += 6   # CMF正向+6
    
    volume_ratio = tech_indicators.get('volume_ratio', 1.0)
    if volume_ratio > 1.5:
        volume_bonus += 5   # 放量+5
    elif volume_ratio > 1.2:
        volume_bonus += 3
    
    scores['volume'] = min(volume_bonus, 25)
    
    # ========== Dimension 4: 动量确认 (0-25) ==========
    # MACD+RSI+ADX同向
    momentum_bonus = 0
    
    macd_signal = tech_indicators.get('macd_signal', '')
    if macd_signal == 'golden_cross':
        momentum_bonus += 12
    elif macd_signal == 'fresh_golden':
        momentum_bonus += 8
    elif macd_signal == 'bullish':
        momentum_bonus += 5
    
    williams_r = tech_indicators.get('williams_r', -50)
    if williams_r > -20:  # WR超买区但没有完全卖出
        momentum_bonus += 3
    elif -50 < williams_r < -30:
        momentum_bonus += 5  # WR超卖回升
    
    adx = tech_indicators.get('adx', 20)
    if adx > 30:
        momentum_bonus += 8   # 强趋势确认+8
    elif adx > 25:
        momentum_bonus += 5   # 趋势确认+5
    
    scores['momentum'] = min(momentum_bonus, 25)
    
    # ========== 总分计算 ==========
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
            # 如果没有技术指标,直接保留(避免误伤)
            cand['entry_quality_score'] = 50  # 中等评分
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
    
    Args:
        candidates: 候选股列表
        multiplier_range: 乘数范围 (最低0.7x ~ 最高1.3x)
    
    Returns: 分数已调权的候选股
    """
    min_mult, max_mult = multiplier_range
    
    for cand in candidates:
        if 'entry_quality_score' not in cand:
            # 计算入场质量
            tech = cand.get('technical', {})
            score, _ = calculate_entry_quality_score(tech)
            cand['entry_quality_score'] = score
        
        eq_score = cand.get('entry_quality_score', 50)
        # 0-100 → 0.7x-1.3x 线性映射
        mult = min_mult + (eq_score / 100.0) * (max_mult - min_mult)
        
        orig_score = cand.get('score', 0)
        cand['score'] = int(orig_score * mult)
        cand['_eq_multiplier'] = round(mult, 2)
    
    return candidates


# ============================================================
# 集成函数: 在stock_picker中调用
# ============================================================

def enrich_candidates_with_entry_quality(candidates: list) -> list:
    """
    为候选股添加入场质量评分
    集成点: stock_picker.py multi_strategy_pick() 之后
    """
    for cand in candidates:
        if 'technical' not in cand:
            cand['entry_quality_score'] = 50
            continue
        
        score, breakdown = calculate_entry_quality_score(cand['technical'])
        cand['entry_quality_score'] = score
        cand['entry_quality_breakdown'] = breakdown
    
    return candidates
