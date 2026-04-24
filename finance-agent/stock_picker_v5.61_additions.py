"""
v5.61 股票选择器增强函数
这些函数应该被集成到 stock_picker.py 的 score_and_rank() 之前

功能:
1. apply_sharpe_ranking_multiplier() - 强制应用2.5x Sharpe权重
2. sector_intelligent_routing() - 赛道差异化策略路由
3. margin_adjustment_evaluation() - 融资融券异变信号评分
"""

# =================== v5.61 新增函数①: 强制应用Sharpe权重倍数 ===================
def apply_sharpe_ranking_multiplier(candidates: list) -> list:
    """
    v5.61新增: 强制应用2.5x Sharpe权重倍数到候选股排名中
    确保回测最优的策略(MACD+RSI Sharpe2.35)权重被完整应用
    
    应用逻辑:
    - 识别每个候选的策略类型(MACD_RSI/MULTI_FACTOR/TREND_FOLLOW/MA_CROSS)
    - 查询该策略的Sharpe系数
    - 应用倍数: score *= (Sharpe_coefficient * multiplier)
    - 确保Sharpe倍数2.5x被充分激活
    """
    try:
        from config import SHARPE_WEIGHT_MULTIPLIER_V3, SHARPE_RISK_THRESHOLDS
        import sqlite3
        from config import DB_PATH
        
        # 获取最近的策略性能数据(Sharpe等)
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""
            SELECT strategy, AVG(sharpe_ratio) as avg_sharpe 
            FROM strategy_performance 
            WHERE record_date >= DATE('now', '-30 days')
            GROUP BY strategy
        """)
        strategy_sharpe = {row[0]: row[1] for row in c.fetchall()}
        conn.close()
        
        # 默认Sharpe值(来自回测数据)
        default_sharpe = {
            'MACD_RSI': 2.35,      # 17.1% 收益回测最优
            'MULTI_FACTOR': 1.51,
            'TREND_FOLLOW': 0.97,
            'MA_CROSS': 0.85,
        }
        
        # 应用Sharpe权重倍数
        for cand in candidates:
            strategy = cand.get('_strategy_type', 'MULTI_FACTOR')
            
            # 从实时数据或默认值获取Sharpe
            sharpe = strategy_sharpe.get(strategy, default_sharpe.get(strategy, 1.5))
            
            # 确定Sharpe等级 (高质量策略权重提升)
            if sharpe >= SHARPE_RISK_THRESHOLDS.get('high_quality', 1.5):
                sharpe_weight = SHARPE_WEIGHT_MULTIPLIER_V3  # 2.5x
            elif sharpe >= SHARPE_RISK_THRESHOLDS.get('medium_quality', 1.0):
                sharpe_weight = SHARPE_WEIGHT_MULTIPLIER_V3 * 0.7  # 1.75x
            else:
                sharpe_weight = 1.0  # 正常
            
            # 应用倍数
            orig_score = cand.get('score', 0)
            cand['score'] = int(orig_score * sharpe_weight)
            cand['_sharpe_weight_applied'] = round(sharpe_weight, 2)
            cand['_sharpe_value'] = round(sharpe, 2)
        
        return candidates
    except Exception as e:
        print(f"  ⚠️ Sharpe权重应用异常: {e}")
        return candidates


# =================== v5.61 新增函数②: 赛道差异化策略路由 ===================
def sector_intelligent_routing(candidates: list, sector_data: dict = None) -> list:
    """
    v5.61新增: 按赛道实施差异化策略权重路由
    
    科技成长: MACD_RSI 2.5x (最优17.1%Sharpe2.35) + 多因子1.5x
    新能源: MACD_RSI 2.0x (14.66%Sharpe1.78) + 多因子1.3x  
    白马消费: 多因子1.5x + 趋势1.3x
    """
    try:
        from config import SECTOR_STRATEGY_ROUTING_V2
        from performance_tracker import classify_sector
        
        for cand in candidates:
            sector = cand.get('sector', '其他')
            
            # 分类赛道
            if not sector or sector == '其他':
                sector = classify_sector(cand.get('code', ''), cand.get('signals', []))
            
            # 获取该赛道的路由权重
            route = SECTOR_STRATEGY_ROUTING_V2.get(sector, SECTOR_STRATEGY_ROUTING_V2.get('主板', {'primary': ('MULTI_FACTOR', 1.0), 'secondary': ('TREND_FOLLOW', 1.0), 'hedge': ('MA_CROSS', 1.0)}))
            strategy = cand.get('_strategy_type', 'MULTI_FACTOR')
            
            # 找到对应的权重
            weight = 1.0
            if route['primary'][0] == strategy:
                weight = route['primary'][1]
            elif route['secondary'][0] == strategy:
                weight = route['secondary'][1]
            elif route['hedge'][0] == strategy:
                weight = route['hedge'][1]
            
            # 应用赛道权重
            orig_score = cand.get('score', 0)
            cand['score'] = int(orig_score * weight)
            cand['_sector'] = sector
            cand['_sector_weight'] = round(weight, 2)
        
        return candidates
    except Exception as e:
        print(f"  ⚠️ 赛道路由异常: {e}")
        return candidates


# =================== v5.61 新增函数③: 融资融券异变信号评分 ===================
def margin_adjustment_evaluation(candidates: list, market_context: dict = None) -> list:
    """
    v5.61新增: 检测融资融券异变,作为独立入场信号
    
    融资余额环比-20% + 融资融券比<20% → +12分 (底部确认)
    融资余额环比+15% + 融资余额创新高 → +8分 (参与度上升)
    
    这个信号在市场底部特别有效(股灾后融资减仓,但优质股融资增加)
    """
    try:
        from config import MARGIN_SIGNAL_V2
        import sqlite3
        from config import DB_PATH
        from datetime import date, timedelta
        
        # 获取最近2天的融资融券数据,计算环比
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        for cand in candidates:
            code = cand.get('code', '')
            if not code:
                continue
            
            # 查询最近两天的融资余额数据
            today = date.today().isoformat()
            yesterday = (date.today() - timedelta(days=1)).isoformat()
            
            try:
                c.execute("""
                    SELECT margin_balance, margin_securities_balance FROM money_flow_snapshots 
                    WHERE symbol=? AND snapshot_date IN (?, ?)
                    ORDER BY snapshot_date DESC LIMIT 2
                """, (code, today, yesterday))
                rows = c.fetchall()
                
                margin_bonus = 0
                if len(rows) >= 2:
                    today_margin, today_margin_securities = rows[0]
                    yesterday_margin, yesterday_margin_securities = rows[1]
                    
                    if yesterday_margin and yesterday_margin > 0:
                        margin_change = (today_margin - yesterday_margin) / yesterday_margin if today_margin else 0
                        total_change_margin = today_margin + today_margin_securities
                        total_prev_margin = yesterday_margin + yesterday_margin_securities
                        
                        # 底部确认信号: 融资减仓 + 融资融券比低
                        if margin_change <= -MARGIN_SIGNAL_V2['margin_decline_threshold']:
                            if total_change_margin > 0 and (today_margin / total_change_margin) < MARGIN_SIGNAL_V2['margin_ratio_threshold']:
                                margin_bonus += MARGIN_SIGNAL_V2['margin_decline_premium']  # +12分
                        
                        # 参与度上升信号: 融资增仓 + 创新高
                        elif margin_change >= MARGIN_SIGNAL_V2['margin_increase_threshold']:
                            if total_change_margin > total_prev_margin * 1.1:  # 融资融券比创新高
                                margin_bonus += MARGIN_SIGNAL_V2['margin_increase_premium']  # +8分
                
                # 应用融资融券奖励
                if margin_bonus > 0:
                    cand['score'] = int(cand.get('score', 0) * (1 + margin_bonus / 100.0))
                    cand['_margin_bonus'] = margin_bonus
            except:
                pass
        
        conn.close()
        return candidates
    except Exception as e:
        print(f"  ⚠️ 融资融券评分异常: {e}")
        return candidates
