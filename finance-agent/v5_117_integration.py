"""
v5.117 集成模块 - 连接新策略、赛道扩展和现有系统
将所有优化集成到 stock_picker.py / position_manager.py / daily_runner.py
"""

import json
from datetime import datetime
from v5_117_new_strategies import (
    MomentumSentimentStrategy,
    MARevertVolStrategy,
    IVArbitrageStrategy,
    ModernPortfolioOptimizer,
    SmartStopLossSystem,
    AccuracyTracker,
)
from v5_117_sector_expansion import (
    SECTOR_DEFINITIONS_V117,
    SECTOR_STRATEGY_ROUTING_V117,
    PORTFOLIO_ALLOCATION_V117,
    SECTOR_POSITION_LIMITS_V117,
    KELLY_FRACTION_BY_SENTIMENT_V117,
    SectorDiversityChecker,
)
from config import *


class V5117IntegrationManager:
    """
    v5.117优化集成管理器
    负责协调所有新模块的集成
    """
    
    def __init__(self):
        self.momentum_sentiment_strategy = MomentumSentimentStrategy()
        self.ma_revert_vol_strategy = MARevertVolStrategy()
        self.iv_arbitrage_strategy = IVArbitrageStrategy()
        self.smart_stop_loss = SmartStopLossSystem()
        self.accuracy_tracker = AccuracyTracker()
        self.portfolio_optimizer = None
        self.diversity_checker = SectorDiversityChecker()
        
        self.v117_enabled = True
        self.optimization_stats = {
            'new_strategies_activated': 3,
            'sectors_expanded': 5,
            'portfolio_optimizations': 0,
            'stop_loss_triggered': 0,
        }
    
    # ========================================================================
    # 选股集成 (供 stock_picker.py 调用)
    # ========================================================================
    
    def get_sector_for_symbol(self, symbol, name):
        """
        根据股票代码/名称判断所属赛道
        """
        for sector_id, sector_def in SECTOR_DEFINITIONS_V117.items():
            keywords = sector_def.get('keywords', [])
            target_symbols = sector_def.get('target_symbols', [])
            
            # 精确匹配目标股票
            if symbol in target_symbols:
                return sector_id
            
            # 关键词匹配
            name_lower = name.lower()
            if any(kw in name_lower for kw in keywords):
                return sector_id
        
        # 默认归类
        if '科' in name or '芯' in name or '软' in name:
            return 'TECH_GROWTH'
        elif '能' in name or '光' in name or '风' in name:
            return 'NEW_ENERGY'
        elif '消' in name or '食' in name or '酒' in name:
            return 'CONSUMER_WHITE_HORSE'
        elif '银' in name or '保' in name or '券' in name:
            return 'FINANCIAL_CYCLE'
        else:
            return 'REAL_ESTATE_HEDGE'
    
    def score_candidate_v117(self, candidate, symbol, closes, highs=None, lows=None):
        """
        使用v5.117新策略对候选股进行评分
        
        Args:
            candidate: {'code': ..., 'name': ..., 'score': ...}
            symbol: 股票代码
            closes: 收盘价列表
            highs/lows: 可选, 用于IV_ARBITRAGE
        
        Returns:
            {
                'symbol': symbol,
                'base_score': 原始分数,
                'v117_score': v5.117评分,
                'strategy_used': 使用的策略,
                'sector': 赛道,
                'details': {...}
            }
        """
        if not closes or len(closes) < 20:
            return None
        
        # 判断赛道
        sector = self.get_sector_for_symbol(symbol, candidate.get('name', ''))
        
        # 根据赛道选择策略
        sector_config = SECTOR_STRATEGY_ROUTING_V117.get(sector)
        if not sector_config:
            return None
        
        strategies_to_try = [
            sector_config['primary'],
            sector_config['secondary'],
            sector_config['tertiary'],
        ]
        weights = sector_config['weights']
        
        scores = []
        strategy_results = {}
        
        # 尝试各个策略评分
        for i, strategy_name in enumerate(strategies_to_try):
            score = 0
            
            if 'MOMENTUM_SENTIMENT' in strategy_name:
                score = self.momentum_sentiment_strategy.score(closes)
                strategy_results['MOMENTUM_SENTIMENT'] = score
            
            elif 'MA_REVERT_VOL' in strategy_name:
                score = self.ma_revert_vol_strategy.score(closes)
                strategy_results['MA_REVERT_VOL'] = score
            
            elif 'IV_ARBITRAGE' in strategy_name:
                if highs and lows:
                    score = self.iv_arbitrage_strategy.score(highs, lows, closes)
                else:
                    score = 50  # 缺少数据时中立
                strategy_results['IV_ARBITRAGE'] = score
            
            elif 'MACD+RSI' in strategy_name:
                # 使用现有的MACD+RSI评分 (兼容旧系统)
                score = candidate.get('score', 50)
            
            else:
                score = candidate.get('score', 50)
            
            scores.append(score * weights[i])
        
        # 加权平均
        v117_score = sum(scores)
        
        return {
            'symbol': symbol,
            'base_score': candidate.get('score', 0),
            'v117_score': v117_score,
            'primary_strategy': sector_config['primary'],
            'sector': sector,
            'strategy_results': strategy_results,
            'weight_multiplier': 1.0,  # 可根据Sharpe调整
        }
    
    # ========================================================================
    # 持仓管理集成 (供 position_manager.py 调用)
    # ========================================================================
    
    def adjust_positions_by_kelly_sentiment(self, current_sentiment_score, 
                                           current_positions, max_positions):
        """
        根据市场情绪调整Kelly准则系数
        
        Returns:
            {
                'kelly_fraction': 0.3-1.0,
                'max_new_positions': -0.5 到 0.3 (相对调整),
                'stop_loss_tightness': 倍数,
                'sentiment_level': 'extremely_greedy' / 'greedy' / ...
            }
        """
        for level, config in KELLY_FRACTION_BY_SENTIMENT_V117.items():
            low, high = config['sentiment_range']
            if low <= current_sentiment_score <= high:
                return {
                    'sentiment_level': level,
                    'kelly_fraction': config['kelly_fraction'],
                    'max_new_positions_adjustment': config['max_new_positions'],
                    'stop_loss_tightness': config['stop_loss_tightness'],
                    'adjusted_max_positions': int(max_positions * (1 + config['max_new_positions'])),
                }
        
        # 默认返回中立配置
        return {
            'sentiment_level': 'neutral',
            'kelly_fraction': 0.8,
            'max_new_positions_adjustment': 0.0,
            'stop_loss_tightness': 1.0,
            'adjusted_max_positions': max_positions,
        }
    
    def check_portfolio_diversity(self, holdings):
        """
        检查投资组合的赛道多样性
        
        Args:
            holdings: [{'symbol': ..., 'sector': ..., 'value': ...}, ...]
        
        Returns:
            多样性报告
        """
        holdings_by_sector = {}
        for sector in SECTOR_DEFINITIONS_V117.keys():
            holdings_by_sector[sector] = [h for h in holdings if h.get('sector') == sector]
        
        return self.diversity_checker.check_portfolio_balance(holdings_by_sector)
    
    def apply_smart_stop_loss(self, position, current_price, highs, lows, closes,
                              entry_price, portfolio_drawdown_pct):
        """
        应用智能止损
        
        Returns:
            {
                'should_stop': bool,
                'stop_loss_price': float,
                'reason': str,
                'action': 'HOLD' / 'REDUCE' / 'EXIT'
            }
        """
        atr = self.smart_stop_loss.calculate_atr(highs, lows, closes, period=14)
        stop_loss_price = self.smart_stop_loss.calculate_stop_loss(entry_price, atr)
        
        # 全局回撤保护
        drawdown, protection_level, suggested_action = self.smart_stop_loss.portfolio_drawdown_protection(
            portfolio_drawdown_pct, 1.0
        )
        
        should_stop = current_price <= stop_loss_price
        
        return {
            'should_stop': should_stop,
            'stop_loss_price': stop_loss_price,
            'current_price': current_price,
            'loss_pct': (current_price - entry_price) / entry_price * 100,
            'protection_level': protection_level,
            'suggested_action': suggested_action,
            'reason': f"ATR止损 | 保护等级 {protection_level}",
        }
    
    # ========================================================================
    # 准确率追踪集成 (供 daily_runner.py 调用)
    # ========================================================================
    
    def record_daily_picks(self, picks):
        """
        记录每日的股票推荐
        
        Args:
            picks: [
                {
                    'symbol': code,
                    'name': name,
                    'strategy': strategy_name,
                    'sector': sector,
                    'predicted_return': estimated_return,
                    'predicted_sharpe': estimated_sharpe,
                    'entry_price': current_price,
                },
                ...
            ]
        """
        for pick in picks:
            self.accuracy_tracker.record_recommendation(
                symbol=pick['symbol'],
                name=pick['name'],
                strategy=pick['strategy'],
                sector=pick['sector'],
                predicted_return=pick.get('predicted_return', 0.15),
                predicted_sharpe=pick.get('predicted_sharpe', 1.5),
                entry_price=pick.get('entry_price', 0),
            )
    
    def generate_accuracy_report(self):
        """生成准确率报告"""
        report = self.accuracy_tracker.accuracy_report()
        
        # 识别低效策略
        low_acc_strategies = self.accuracy_tracker.low_accuracy_strategies(threshold=0.45)
        
        return {
            'accuracy_by_strategy': report,
            'low_accuracy_strategies': low_acc_strategies,
            'timestamp': datetime.now().isoformat(),
        }
    
    # ========================================================================
    # 投资组合优化集成
    # ========================================================================
    
    def optimize_portfolio_allocation(self, candidates_with_returns):
        """
        使用现代投资组合理论优化配置
        
        Args:
            candidates_with_returns: {
                'symbol': [20天收益率列表],
                ...
            }
        
        Returns:
            优化后的权重分配
        """
        try:
            self.portfolio_optimizer = ModernPortfolioOptimizer(
                returns_series=candidates_with_returns,
                risk_free_rate=0.03
            )
            
            # 求解最大Sharpe组合
            optimal_weights = self.portfolio_optimizer.max_sharpe_portfolio()
            
            # 过滤权重为0的资产
            filtered_weights = {s: w for s, w in optimal_weights.items() if w > 0.01}
            
            return {
                'optimal_weights': filtered_weights,
                'optimization_method': 'MaxSharpe',
                'timestamp': datetime.now().isoformat(),
            }
        except Exception as e:
            print(f"❌ 投资组合优化失败: {e}")
            return None
    
    # ========================================================================
    # 优化统计
    # ========================================================================
    
    def get_optimization_status(self):
        """返回v5.117优化状态"""
        return {
            'version': 'v5.117',
            'enabled': self.v117_enabled,
            'timestamp': datetime.now().isoformat(),
            'stats': self.optimization_stats,
            'features': {
                'new_strategies': ['MOMENTUM_SENTIMENT', 'MA_REVERT_VOL', 'IV_ARBITRAGE'],
                'sector_expansion': list(SECTOR_DEFINITIONS_V117.keys()),
                'portfolio_optimization': 'ModernPortfolioOptimizer (MPT)',
                'risk_management': 'SmartStopLossSystem',
                'accuracy_tracking': 'AccuracyTracker',
            },
        }


# ============================================================================
# 集成函数 - 添加到 stock_picker.py
# ============================================================================

def integrate_v117_scoring_to_stock_picker(candidates, technical_data):
    """
    集成v5.117评分到stock_picker的主选股流程
    
    使用方式:
        在 stock_picker.py 的 pick_stocks() 中调用
        candidates = integrate_v117_scoring_to_stock_picker(candidates, technical_data)
    """
    manager = V5117IntegrationManager()
    
    enhanced_candidates = []
    for cand in candidates:
        symbol = cand.get('code', '')
        if not symbol or symbol not in technical_data:
            enhanced_candidates.append(cand)
            continue
        
        tech_data = technical_data[symbol]
        closes = tech_data.get('closes', [])
        highs = tech_data.get('highs', [])
        lows = tech_data.get('lows', [])
        
        v117_result = manager.score_candidate_v117(
            cand, symbol, closes, highs, lows
        )
        
        if v117_result:
            # 混合新旧评分 (60% v5.117 + 40% 原始)
            original_score = cand.get('score', 50)
            v117_score = v117_result['v117_score']
            blended_score = v117_score * 0.6 + original_score * 0.4
            
            cand['score_v117'] = v117_score
            cand['score_blended'] = blended_score
            cand['sector'] = v117_result['sector']
            cand['strategy_v117'] = v117_result['primary_strategy']
        
        enhanced_candidates.append(cand)
    
    return enhanced_candidates


# ============================================================================
# 导出函数
# ============================================================================

def export_v117_integration_config():
    """导出集成配置"""
    return {
        'sectors': SECTOR_DEFINITIONS_V117,
        'strategy_routing': SECTOR_STRATEGY_ROUTING_V117,
        'allocation': PORTFOLIO_ALLOCATION_V117,
        'position_limits': SECTOR_POSITION_LIMITS_V117,
        'kelly_config': KELLY_FRACTION_BY_SENTIMENT_V117,
    }


if __name__ == "__main__":
    manager = V5117IntegrationManager()
    status = manager.get_optimization_status()
    print(json.dumps(status, indent=2, ensure_ascii=False))
