"""
v5.67 深度优化函数集
======================================

包含4个新函数:
1. strategy_performance_weighting() - Sharpe/MaxDD权重调整
2. max_drawdown_penalty_check() - 回撤惩罚机制
3. sector_concentration_limit() - 赛道集中度限制
4. apply_sharpe_ranking_multiplier_v2() - Sharpe倍数强制应用

集成点:
- stock_picker.py: score_and_rank() 后调用
- position_manager.py: check_dynamic_stop() 替换为v2版本
"""

import json
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional


def strategy_performance_weighting(ranked: list, backtest_metrics: dict = None) -> list:
    """v5.67: 基于回测Sharpe/MaxDD动态调整赛道权重
    
    融合回测TOP3数据:
    - MACD+RSI(科技成长): 17.1% Return, 2.35 Sharpe, 4.08% MaxDD
    - 新能源策略: 14.66% Return, 1.78 Sharpe, 6.93% MaxDD
    - 白马消费: Sharpe 0.85
    
    权重规则:
    - Sharpe >= 2.0: 权重×1.3
    - Sharpe 1.5-2.0: 权重×1.0
    - Sharpe 1.0-1.5: 权重×0.8
    - Sharpe < 1.0: 权重×0.3 (严厉削弱)
    - MaxDD > 5%: 再×0.8 (双重惩罚)
    
    Args:
        ranked: score_and_rank()输出的排序候选list
        backtest_metrics: 回测性能字典
            {
                'MACD_RSI': {'return': 0.171, 'sharpe': 2.35, 'maxdd': 0.0408},
                'MULTI_FACTOR': {'return': ..., 'sharpe': ..., 'maxdd': ...},
                'TREND_FOLLOW': {...},
                'MA_CROSS': {...}
            }
    
    Returns: 应用权重后的排序list
    """
    try:
        if not ranked or not backtest_metrics:
            return ranked
        
        # 权重映射表
        SHARPE_WEIGHT_MAP = {
            'excellent': (2.0, 1.3),       # Sharpe >= 2.0: 权重×1.3
            'good': (1.5, 1.0),            # Sharpe 1.5-2.0: 权重×1.0
            'normal': (1.0, 0.8),          # Sharpe 1.0-1.5: 权重×0.8
            'weak': (0.5, 0.3),            # Sharpe < 1.0: 权重×0.3
        }
        MAXDD_PENALTY = 0.8                # MaxDD > 5%: 再×0.8
        
        for stock in ranked:
            try:
                signals = stock.get('signals', [])
                original_score = stock.get('score', 0)
                
                # 判定策略类型
                strategy_type = 'MULTI_FACTOR'  # 默认多因子
                if any('MACD' in str(s) or 'RSI' in str(s) for s in signals):
                    strategy_type = 'MACD_RSI'
                elif any('趋势' in str(s) or 'TREND' in str(s) for s in signals):
                    strategy_type = 'TREND_FOLLOW'
                elif any('MA' in str(s) or 'EMA' in str(s) for s in signals):
                    strategy_type = 'MA_CROSS'
                
                # 查询该策略的Sharpe
                metrics = backtest_metrics.get(strategy_type, {})
                sharpe = metrics.get('sharpe', 1.0)
                maxdd = metrics.get('maxdd', 0.04)
                
                # 应用Sharpe权重
                weight_multiplier = 1.0
                sharpe_tier = 'normal'
                
                for tier, (threshold, multiplier) in SHARPE_WEIGHT_MAP.items():
                    if tier == 'excellent' and sharpe >= threshold:
                        weight_multiplier = multiplier
                        sharpe_tier = tier
                        break
                    elif tier == 'good' and sharpe >= threshold:
                        if sharpe < 2.0:  # 确保只在1.5-2.0范围
                            weight_multiplier = multiplier
                            sharpe_tier = tier
                            break
                    elif tier == 'normal' and sharpe >= threshold:
                        if sharpe < 1.5:  # 确保只在1.0-1.5范围
                            weight_multiplier = multiplier
                            sharpe_tier = tier
                            break
                    elif tier == 'weak' and sharpe < 1.0:
                        weight_multiplier = multiplier
                        sharpe_tier = tier
                        break
                
                # MaxDD惩罚
                if maxdd > 0.05:
                    weight_multiplier *= MAXDD_PENALTY
                
                new_score = int(original_score * weight_multiplier)
                stock['score'] = new_score
                stock['_performance_weight'] = {
                    'original_score': original_score,
                    'strategy': strategy_type,
                    'sharpe': round(sharpe, 2),
                    'sharpe_tier': sharpe_tier,
                    'maxdd': round(maxdd, 4),
                    'weight_multiplier': round(weight_multiplier, 2),
                    'new_score': new_score
                }
            except Exception as e:
                # 单只股票处理失败，跳过该权重调整
                stock['_performance_weight_error'] = str(e)
                continue
        
        # 重新排序
        ranked.sort(key=lambda x: -x.get('score', 0))
        return ranked
    
    except Exception as e:
        print(f"⚠️ strategy_performance_weighting异常: {e}")
        return ranked


def max_drawdown_penalty_check(ranked: list, sector_metrics: dict) -> list:
    """v5.67: MaxDD > 5%时自动降低策略权重 + 赛道禁用检查
    
    目标: 降低最大回撤 4.08% → 3.2% (-21%)
    
    规则:
    - 科技成长 MaxDD 4.08% → 权重保持 100%
    - 新能源 MaxDD 6.93% → 权重降0.9x
    - 白马消费 MaxDD > 5% → 权重降至0.5x
    - 混合池 MaxDD > 7% → 禁用
    
    Args:
        ranked: score_and_rank()输出
        sector_metrics: 赛道性能指标字典
            {
                '科技成长': {'maxdd': 0.0408, 'sharpe': 2.35, ...},
                '新能源': {'maxdd': 0.0693, 'sharpe': 1.78, ...},
                '白马消费': {'maxdd': 0.052, 'sharpe': 0.85, ...},
            }
    
    Returns: 应用MaxDD惩罚后的list (可能包含被排除的股票)
    """
    try:
        if not ranked or not sector_metrics:
            return ranked
        
        MAXDD_PENALTY_MAP = {
            '科技成长': (0.05, 1.0),    # MaxDD > 5%: 权重×1.0 (保持)
            '新能源': (0.06, 0.9),      # MaxDD > 6%: 权重×0.9
            '白马消费': (0.05, 0.5),    # MaxDD > 5%: 权重×0.5
            '混合池': (0.07, 0.0),      # MaxDD > 7%: 禁用
        }
        
        filtered_result = []
        excluded_result = []
        
        for stock in ranked:
            try:
                code = stock.get('code', '')
                sector = stock.get('_sector', '科技成长')  # 默认科技成长
                original_score = stock.get('score', 0)
                
                # 查询该赛道的MaxDD
                sector_info = sector_metrics.get(sector, {})
                maxdd = sector_info.get('maxdd', 0.04)
                
                # 查找该赛道的惩罚规则
                penalty_threshold, penalty_multiplier = MAXDD_PENALTY_MAP.get(sector, (0.05, 1.0))
                
                if maxdd > penalty_threshold:
                    if penalty_multiplier == 0.0:  # 禁用
                        stock['_maxdd_excluded'] = True
                        stock['_maxdd_reason'] = f"赛道{sector} MaxDD {maxdd:.2%} > {penalty_threshold:.1%}，禁用"
                        excluded_result.append(stock)
                        continue
                    else:  # 降权
                        new_score = int(original_score * penalty_multiplier)
                        stock['score'] = new_score
                        stock['_maxdd_penalty'] = {
                            'sector': sector,
                            'maxdd': round(maxdd, 4),
                            'threshold': penalty_threshold,
                            'multiplier': penalty_multiplier,
                            'original_score': original_score,
                            'new_score': new_score
                        }
                
                filtered_result.append(stock)
            
            except Exception as e:
                stock['_maxdd_penalty_error'] = str(e)
                filtered_result.append(stock)
                continue
        
        # 重新排序过滤后的结果
        filtered_result.sort(key=lambda x: -x.get('score', 0))
        
        # 合并: 未被排除的在前，被排除的在后
        return filtered_result + excluded_result
    
    except Exception as e:
        print(f"⚠️ max_drawdown_penalty_check异常: {e}")
        return ranked


def sector_concentration_limit(ranked: list, positions: list) -> list:
    """v5.67: 赛道集中度限制 - 防止单赛道风险
    
    限制规则:
    - 科技成长: 最多8只
    - 新能源: 最多6只
    - 其他赛道: 最多3只
    
    目的: 分散风险，避免单赛道黑天鹅导致大幅回撤
    
    Args:
        ranked: 排序后的候选list
        positions: 当前持仓list
    
    Returns: 应用集中度限制后的list (包含_excluded_reason的被过滤项)
    """
    try:
        from performance_tracker import classify_sector
        
        if not ranked:
            return ranked
        
        # 赛道集中度限制
        SECTOR_LIMITS = {
            '科技成长': 8,
            '新能源': 6,
            '白马消费': 3,
            '其他': 3
        }
        
        # 统计当前持仓赛道分布
        sector_count = {}
        for pos in (positions or []):
            try:
                code = pos.get('symbol', '')
                name = pos.get('name', '')
                if not code:
                    continue
                sector = classify_sector(code, name)
                sector_count[sector] = sector_count.get(sector, 0) + 1
            except:
                continue
        
        filtered_result = []
        excluded_result = []
        
        for stock in ranked:
            try:
                code = stock.get('code', '')
                name = stock.get('name', '')
                if not code:
                    filtered_result.append(stock)
                    continue
                
                sector = classify_sector(code, name)
                stock['_sector'] = sector  # 记录赛道分类
                
                limit = SECTOR_LIMITS.get(sector, 3)
                current_count = sector_count.get(sector, 0)
                
                if current_count >= limit:
                    stock['_concentration_excluded'] = True
                    stock['_excluded_reason'] = f"赛道{sector}已达集中度上限({limit}只)，当前{current_count}只"
                    excluded_result.append(stock)
                    continue
                
                filtered_result.append(stock)
                sector_count[sector] = current_count + 1
            
            except Exception as e:
                stock['_concentration_error'] = str(e)
                filtered_result.append(stock)
                continue
        
        # 返回: 通过的在前，排除的在后
        return filtered_result + excluded_result
    
    except Exception as e:
        print(f"⚠️ sector_concentration_limit异常: {e}")
        return ranked


def apply_sharpe_ranking_multiplier_v2(ranked: list, cash_ratio: float = 0.75, 
                                       extreme_mode: bool = False) -> list:
    """v5.67: 强制在score_and_rank中应用Sharpe倍数
    
    确保Sharpe权重被充分利用，不被其他权重掩盖。
    
    倍数规则:
    - 超激进模式(现金>98%): 2.8x (v5.67新增)
    - 高现金(现金90-98%): 2.5x
    - 中等(现金75-90%): 2.0x
    - 正常(现金<75%): 1.5x
    
    Args:
        ranked: score_and_rank()输出的排序候选list
        cash_ratio: 当前现金占比 (0-1)
        extreme_mode: 是否已确认超激进模式
    
    Returns: 应用Sharpe倍数后的排序list
    """
    try:
        if not ranked:
            return ranked
        
        # 根据现金占比或显式extreme_mode参数选择Sharpe倍数
        SHARPE_MULTIPLIER_MAP = {
            'extreme': 2.8,     # 超激进: 2.8x
            'very_high': 2.5,   # 很高: 2.5x (90-98%)
            'high': 2.0,        # 高: 2.0x (75-90%)
            'normal': 1.5,      # 正常: 1.5x (<75%)
        }
        
        mode = 'normal'
        if extreme_mode or cash_ratio > 0.98:
            mode = 'extreme'
        elif cash_ratio > 0.90:
            mode = 'very_high'
        elif cash_ratio > 0.75:
            mode = 'high'
        
        sharpe_multiplier = SHARPE_MULTIPLIER_MAP.get(mode, 1.5)
        
        for stock in ranked:
            try:
                signals = stock.get('signals', [])
                original_score = stock.get('score', 0)
                
                # MACD+RSI策略应用更高的Sharpe倍数
                is_macd_rsi = any('MACD' in str(s) or 'RSI' in str(s) for s in signals)
                
                if is_macd_rsi:
                    new_score = int(original_score * sharpe_multiplier)
                    stock['score'] = new_score
                    stock['_sharpe_multiplier_v2'] = {
                        'mode': mode,
                        'cash_ratio': round(cash_ratio, 4),
                        'multiplier': sharpe_multiplier,
                        'original_score': original_score,
                        'new_score': new_score,
                        'strategy': 'MACD_RSI'
                    }
            except Exception as e:
                stock['_sharpe_multiplier_error'] = str(e)
                continue
        
        # 重新排序
        ranked.sort(key=lambda x: -x.get('score', 0))
        return ranked
    
    except Exception as e:
        print(f"⚠️ apply_sharpe_ranking_multiplier_v2异常: {e}")
        return ranked


def check_dynamic_stop_v2(positions: list, quotes: dict, regime: str = "", 
                          backtest_metrics: dict = None) -> list:
    """v5.67: 追踪止损v2 - 基于Sharpe等级自动调整止损线
    
    目标: MaxDD 4.08% → 3.2% (-21%)
    
    止损规则 (基于Sharpe等级分化):
    - 高风险(Sharpe<1.0): 回撤4.0%快速止损
    - 中风险(Sharpe 1.0-1.5): 回撤4.5%止损
    - 低风险(Sharpe>1.5): 回撤5.0%止损
    - 时间止损: 15天无新高自动止损 (避免僵尸持仓)
    
    Args:
        positions: 当前持仓list
        quotes: 最新行情字典 {code: {price, ...}}
        regime: 市场状态 ('bull'/'bear'/etc)
        backtest_metrics: 可选的回测指标 {strategy: {sharpe: ...}}
    
    Returns: 需要止损的持仓list [{symbol, action, reason, price}]
    """
    results = []
    
    try:
        for pos in (positions or []):
            try:
                symbol = pos.get('symbol', '')
                if not symbol:
                    continue
                
                quote = quotes.get(symbol, {})
                current_price = quote.get('price') or pos.get('current_price', 0)
                if current_price <= 0:
                    continue
                
                buy_price = pos.get('buy_price', pos.get('avg_cost', 0))
                peak_price = pos.get('peak_price', buy_price)
                if peak_price <= 0:
                    continue
                
                # 计算回撤百分比
                profit_pct = (current_price - peak_price) / peak_price if peak_price else 0
                
                # 获取该持仓的Sharpe等级 (从entry_quality_score推断或直接查询)
                sharpe_level = pos.get('_sharpe_level', 'medium')  # default: medium
                entry_quality = pos.get('entry_quality_score', 50)
                
                # 根据entry_quality反推Sharpe等级 (简化估计)
                if entry_quality >= 70:
                    sharpe_level = 'high'      # Sharpe > 1.5
                elif entry_quality >= 50:
                    sharpe_level = 'medium'    # Sharpe 1.0-1.5
                else:
                    sharpe_level = 'low'       # Sharpe < 1.0
                
                # 选择回撤阈值
                if sharpe_level == 'high':
                    aggressive_retracement = 0.05
                elif sharpe_level == 'medium':
                    aggressive_retracement = 0.045
                else:  # low
                    aggressive_retracement = 0.04
                
                # 追踪止损检查: 从峰值回撤超过阈值
                if profit_pct < -aggressive_retracement:
                    results.append({
                        'symbol': symbol,
                        'action': 'sell',
                        'reason': f'追踪止损[{sharpe_level}]: 回撤{profit_pct:.2%} < -{aggressive_retracement:.1%}',
                        'price': current_price,
                        'details': {
                            'sharpe_level': sharpe_level,
                            'peak_price': peak_price,
                            'current_price': current_price,
                            'retracement': profit_pct,
                            'threshold': -aggressive_retracement
                        }
                    })
                    continue
                
                # 时间止损: N天无新高自动止损 (避免僵尸持仓)
                try:
                    from position_manager import _trading_days_since
                    hold_days = _trading_days_since(pos.get('buy_date', ''))
                    
                    if hold_days >= 15:
                        days_since_peak = pos.get('_days_since_peak', 0)
                        # 持仓15+天、浮盈<5%、且15天无新高 → 止损
                        if days_since_peak >= 15 and profit_pct < 0.05:
                            results.append({
                                'symbol': symbol,
                                'action': 'sell',
                                'reason': f'时间止损: 持仓{hold_days}天无新高(15+天无进展)',
                                'price': current_price,
                                'details': {
                                    'hold_days': hold_days,
                                    'days_since_peak': days_since_peak,
                                    'profit_pct': profit_pct
                                }
                            })
                except:
                    pass  # _trading_days_since不可用，跳过时间止损检查
            
            except Exception as e:
                # 单只持仓处理失败，继续处理下一只
                print(f"⚠️ 止损检查异常[{pos.get('symbol')}]: {e}")
                continue
    
    except Exception as e:
        print(f"⚠️ check_dynamic_stop_v2异常: {e}")
    
    return results


# =================== 工具函数 ===================

def merge_stock_picker_enhancements(ranked: list, backtest_metrics: dict = None,
                                    positions: list = None, cash_ratio: float = 0.75,
                                    sector_metrics: dict = None) -> list:
    """v5.67: 完整的stock_picker增强管道
    
    集成所有权重调整、惩罚检查、集中度限制
    
    执行顺序:
    1. strategy_performance_weighting() - 基础Sharpe/MaxDD权重
    2. max_drawdown_penalty_check() - MaxDD超限惩罚
    3. sector_concentration_limit() - 赛道集中度限制
    4. apply_sharpe_ranking_multiplier_v2() - 最终Sharpe倍数
    
    Args:
        ranked: score_and_rank()原始输出
        backtest_metrics: 回测指标
        positions: 当前持仓
        cash_ratio: 现金占比
        sector_metrics: 赛道指标
    
    Returns: 最终排序的候选list
    """
    try:
        result = ranked
        
        # 步骤1: 策略性能权重
        if backtest_metrics:
            result = strategy_performance_weighting(result, backtest_metrics)
        
        # 步骤2: MaxDD惩罚
        if sector_metrics:
            result = max_drawdown_penalty_check(result, sector_metrics)
        
        # 步骤3: 赛道集中度
        if positions is not None:
            result = sector_concentration_limit(result, positions)
        
        # 步骤4: Sharpe倍数
        extreme_mode = cash_ratio > 0.98
        result = apply_sharpe_ranking_multiplier_v2(result, cash_ratio, extreme_mode)
        
        return result
    
    except Exception as e:
        print(f"⚠️ merge_stock_picker_enhancements异常: {e}")
        return ranked


# =================== v5.67 兼容性检查 ===================

def is_v5_67_compatible():
    """检查环境是否支持v5.67"""
    try:
        # 检查必需的导入
        from performance_tracker import classify_sector
        return True
    except:
        return False


if __name__ == '__main__':
    print("v5.67 优化函数集已加载")
    print(f"兼容性检查: {is_v5_67_compatible()}")
