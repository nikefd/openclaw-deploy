"""
v5.162 盤前優化② — 集成到 position_manager 中的 Sharpe 基礎止損

只需在 check_dynamic_stop() 的 return 前添加以下代碼:

    # === v5.162: Sharpe基礎止損保護層 ===
    actions = _apply_sharpe_based_protection_v162(positions, actions, sentiment_score)
"""

from datetime import datetime, date


def _apply_sharpe_based_protection_v162(positions: list, actions: list, sentiment_score: int) -> list:
    """
    【v5.162 新增】Sharpe基礎止損保護層
    
    規則:
    1. Sharpe>1.5 的激進持倉: 利潤>5%時主動鎖定80%利潤
    2. Sharpe<1.0 的風險持倉: 提前觸發止損 (-5% vs -7%)
    3. 情緒極端時 (>85 or <30): 所有持倉Sharpe折扣20%
    """
    
    high_sharpe_threshold = 1.5
    profit_lock_threshold = 0.05  # 5%利潤
    profit_lock_ratio = 0.80      # 鎖定80%
    
    sharpe_protection_actions = []
    
    for pos in positions:
        sharpe = pos.get('sharpe_ratio', 0.8)
        current_price = pos.get('current_price', 0)
        avg_cost = pos.get('avg_cost', 0)
        
        if not current_price or not avg_cost:
            continue
        
        pnl_pct = (current_price - avg_cost) / avg_cost
        
        # 情緒極端時 Sharpe 折扣
        if sentiment_score > 85 or sentiment_score < 30:
            sharpe_adjusted = sharpe * 0.8  # 折扣20%
        else:
            sharpe_adjusted = sharpe
        
        # 規則1: 激進持倉快速止盈
        if sharpe_adjusted > high_sharpe_threshold and pnl_pct > profit_lock_threshold:
            locked_profit = pnl_pct * profit_lock_ratio
            sharpe_protection_actions.append({
                "action": "PARTIAL_SELL",
                "symbol": pos['symbol'],
                "name": pos['name'],
                "shares": int(pos['shares'] * 0.5),
                "price": current_price,
                "reason": f"高Sharpe({sharpe:.2f})激進止盈: 已盈利{pnl_pct*100:.1f}%, 鎖定{locked_profit*100:.1f}%利潤",
                "priority": 10  # 高優先級
            })
        
        # 規則2: 風險持倉提前止損
        elif sharpe_adjusted < 1.0 and pnl_pct < -0.05:
            sharpe_protection_actions.append({
                "action": "SELL",
                "symbol": pos['symbol'],
                "name": pos['name'],
                "shares": pos['shares'],
                "price": current_price,
                "reason": f"低Sharpe({sharpe:.2f})風險持倉提前止損: 虧損{pnl_pct*100:.1f}%",
                "priority": 9  # 高優先級
            })
    
    # 合併動作 (但 Sharpe 保護優先級高於一般止損)
    actions.extend(sharpe_protection_actions)
    
    return actions


# ============================================================
# 集成指南: 在 position_manager.py 的 check_dynamic_stop() 中
# ============================================================
"""
在 check_dynamic_stop() 函數的最後 return 前, 添加:

    # v5.162: Sharpe基礎止損保護層
    from v5_162_OPTIMIZE_CACHE_MARGIN import _apply_sharpe_based_protection_v162
    actions = _apply_sharpe_based_protection_v162(positions, actions, int(sentiment_score))
    
    return actions
"""
