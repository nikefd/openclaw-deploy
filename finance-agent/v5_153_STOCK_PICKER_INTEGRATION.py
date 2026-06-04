
# ============================================================
# v5.153集成: stock_picker.py中添加以下代码
# ============================================================

# 在文件顶部导入模块后添加:
try:
    from v5_153_DEEP_EVENING_OPTIMIZE import (
        BacktestDrivenOptimization,
        SectorParameterRefinement,
        SmartCashAllocationV3,
        AdaptiveStopLossSystemV3,
        PerformanceAccelerationV3
    )
    V5_153_AVAILABLE = True
except ImportError:
    V5_153_AVAILABLE = False

# 在pick_stocks()函数中添加:
def score_and_rank_v5_153(candidates: list, market_sentiment: dict = None):
    """v5.153版本的排序函数 - 集成所有优化"""
    
    if market_sentiment is None:
        market_sentiment = get_market_sentiment()
    
    # 应用回测TOP1信号权重
    for stock in candidates:
        base_score = stock.get('score', 0)
        
        # 应用MACD+RSI信号权重
        if 'MACD' in str(stock.get('signals', [])):
            boost = 2.2  # MACD_RSI_SIGNAL_BOOST
            stock['score'] = int(base_score * boost)
        
        # 赛道差异化权重
        sector = stock.get('sector', 'mixed')
        sector_weights = SectorParameterRefinement.apply_dynamic_sector_weights(market_sentiment)
        
        if sector in sector_weights:
            stock['score'] = int(stock['score'] * (1 + sector_weights.get(sector, 0)))
    
    # 应用快速选股加速
    if V5_153_AVAILABLE:
        candidates = PerformanceAccelerationV3.fast_stock_pick(
            candidates, 
            timeout_sec=0.5
        )
    
    # 排序并返回前20
    candidates.sort(key=lambda x: -x.get('score', 0))
    return candidates[:20]
