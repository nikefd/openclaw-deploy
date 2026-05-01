"""v5.79 stock_picker集成模块 — 快速评估 + 候选池扩展

该模块集成到 stock_picker.py score_and_rank() 函数中
"""

from v5_79_DEEP_OPTIMIZE import (
    batch_entry_assessment,
    detect_margin_anomaly,
    V5_79_PARAMS
)

def integrate_v5_79_quick_assessment(candidates_ranked: list) -> list:
    """v5.79: 集成快速评估引擎到选股排名
    
    在 stock_picker.score_and_rank() 完成后调用
    
    Args:
        candidates_ranked: score_and_rank()返回的排序候选
    
    Returns: 应用v5.79评估后的候选列表
    """
    print(f"\n[v5.79快速评估] 对{len(candidates_ranked)}只候选进行快速评分...")
    
    # 1. 对每个候选检测融资异变
    for candidate in candidates_ranked:
        code = candidate.get('code', '')
        if code:
            margin_anomaly = detect_margin_anomaly(code)
            candidate['margin_status'] = margin_anomaly
    
    # 2. 快速评分 (<0.5秒)
    candidates_ranked = batch_entry_assessment(candidates_ranked)
    
    # 3. 按v5.79评分重新排序
    candidates_ranked.sort(key=lambda x: -x.get('_v5_79_score', 0))
    
    # 4. 统计信息输出
    v5_79_scores = [c.get('_v5_79_score', 0) for c in candidates_ranked]
    v5_79_confidences = [c.get('_v5_79_confidence', 0) for c in candidates_ranked]
    
    print(f"✅ v5.79评分完成:")
    print(f"   评分分布: 最高{max(v5_79_scores):.0f}分 / 平均{sum(v5_79_scores)/len(v5_79_scores) if v5_79_scores else 0:.0f}分")
    print(f"   置信度分布: 最高{max(v5_79_confidences):.2f} / 平均{sum(v5_79_confidences)/len(v5_79_confidences) if v5_79_confidences else 0:.2f}")
    
    # 5. 过滤置信度<65%的低质量候选
    high_confidence = [c for c in candidates_ranked 
                       if c.get('_v5_79_confidence', 0) >= V5_79_PARAMS['min_signal_confidence']]
    low_confidence_count = len(candidates_ranked) - len(high_confidence)
    
    if low_confidence_count > 0:
        print(f"⚠️  过滤低置信度候选{low_confidence_count}只 (置信度<{V5_79_PARAMS['min_signal_confidence']*100:.0f}%)")
    
    return high_confidence


def v5_79_entry_recommendation(candidates: list, cash_available: float, current_positions: list) -> dict:
    """v5.79: 生成建仓推荐列表
    
    Args:
        candidates: 评分排序的候选列表
        cash_available: 可用现金
        current_positions: 当前持仓
    
    Returns: {
        'entries': [{'code', 'name', 'shares', 'reason'}, ...],
        'total_amount': 建仓总金额,
        'expected_positions': 预期持仓数,
        'sector_allocation': 赛道配置,
        'summary': 建议摘要
    }
    """
    from v5_79_DEEP_OPTIMIZE import (
        diversified_position_builder,
        calculate_dynamic_position_size,
        V5_79_PARAMS
    )
    
    print(f"\n[v5.79多样化建仓] 为{len(candidates)}只候选生成建仓推荐...")
    
    # 1. 多样化建仓
    entries = diversified_position_builder(
        candidates,
        current_positions,
        cash_available,
        V5_79_PARAMS['sector_diversification']
    )
    
    # 2. 计算总建仓额
    total_amount = sum(e.get('amount', 0) for e in entries)
    expected_positions = len(current_positions) + len(entries)
    
    # 3. 生成赛道配置统计
    sector_allocation = {}
    for entry in entries:
        sector = entry.get('sector', '其他')
        if sector not in sector_allocation:
            sector_allocation[sector] = []
        sector_allocation[sector].append({
            'code': entry['code'],
            'name': entry['name'],
            'amount': entry['amount'],
        })
    
    # 4. 生成推荐摘要
    summary = {
        'entry_count': len(entries),
        'total_amount': total_amount,
        'cash_ratio_before': cash_available / (cash_available + sum(p.get('value', 0) for p in current_positions)) if (cash_available + sum(p.get('value', 0) for p in current_positions)) > 0 else 1.0,
        'cash_ratio_after': (cash_available - total_amount) / (cash_available + sum(p.get('value', 0) for p in current_positions)) if (cash_available + sum(p.get('value', 0) for p in current_positions)) > 0 else 1.0,
        'expected_positions': expected_positions,
        'recommendation': 'GO'如果len(entries) > 0 else 'WAIT',
    }
    
    return {
        'entries': entries,
        'total_amount': total_amount,
        'expected_positions': expected_positions,
        'sector_allocation': sector_allocation,
        'summary': summary,
    }


def apply_v5_79_stop_loss_settings(entries: list) -> list:
    """v5.79: 为建仓的股票应用ATR动态止损
    
    Args:
        entries: 建仓推荐列表
    
    Returns: 应用止损设置后的列表
    """
    from v5_79_DEEP_OPTIMIZE import calculate_atr_dynamic_stop_loss
    
    print(f"\n[v5.79止损设置] 为{len(entries)}只建仓股应用ATR动态止损...")
    
    for entry in entries:
        stop_loss_config = calculate_atr_dynamic_stop_loss(
            entry['code'],
            entry['price'],
            entry.get('sector', '')
        )
        entry['stop_loss_pct'] = stop_loss_config['stop_loss_pct']
        entry['stop_loss_price'] = stop_loss_config['stop_loss_price']
        entry['stop_loss_rationale'] = stop_loss_config['rationale']
    
    return entries


# =================== 集成到daily_runner.py的调用示例 ===================

def v5_79_build_recommendation():
    """v5.79: 完整的推荐生成流程
    
    在 daily_runner.py pick_and_trade() 中调用:
    
    # 获取排序候选
    candidates = stock_picker.get_ranked_candidates(limit=100)
    
    # 应用v5.79快速评估
    candidates = integrate_v5_79_quick_assessment(candidates)
    
    # 生成建仓推荐
    recommendation = v5_79_entry_recommendation(
        candidates,
        account.cash,
        account.positions
    )
    
    # 应用止损设置
    recommendation['entries'] = apply_v5_79_stop_loss_settings(recommendation['entries'])
    
    # 执行建仓 (通过trading_engine.buy())
    for entry in recommendation['entries']:
        trading_engine.buy(
            entry['code'],
            entry['name'],
            entry['shares'],
            reason=entry['reason'],
            stop_loss=entry['stop_loss_price']
        )
    """
    pass
