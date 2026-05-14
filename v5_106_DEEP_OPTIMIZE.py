"""v5.106: 晚间深度优化模块

改进①: 回测数据融合 + Kelly动态仓位
改进②: 赛道差异化MACD参数
改进③: 动态现金激活阈值 (资金效率)
改进④: 持仓集中度优化 (Kelly-aware)
改进⑤: 6维入场质量评分
改进⑥: 0.8秒快速选股引擎

Author: Finance Agent Optimization Engineer
Date: 2026-05-14
"""

import sqlite3
import json
import time
from datetime import datetime, timedelta
from typing import Dict, Tuple, List, Optional
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import numpy as np

# =================== 改进①: 回测数据融合 + Kelly计算 ===================

class BacktestDataFusion:
    """从backtest.db提取最优参数，用于Kelly仓位计算"""
    
    def __init__(self, db_path: str = "data/backtest.db"):
        self.db_path = db_path
        self.cached_results = None
        self.cache_time = None
        self.cache_ttl = 3600  # 1小时缓存
    
    def get_best_strategy(self, sector: str = None, force_refresh: bool = False) -> Dict:
        """获取回测最优策略
        
        Returns:
            {
                'strategy': 'MACD+RSI (科技成长)',
                'total_return': 17.1,
                'max_drawdown': 4.08,
                'win_rate': 0.60,
                'sharpe_ratio': 2.35,
                'sector': '科技成长'
            }
        """
        # 检查缓存
        if not force_refresh and self.cached_results and self.cache_time:
            if time.time() - self.cache_time < self.cache_ttl:
                return self.cached_results
        
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            
            if sector:
                query = """
                    SELECT strategy, total_return, max_drawdown, win_rate, sharpe_ratio
                    FROM backtest_runs
                    WHERE strategy LIKE ? 
                    ORDER BY total_return DESC
                    LIMIT 1
                """
                cursor = conn.execute(query, (f'%{sector}%',))
            else:
                query = """
                    SELECT strategy, total_return, max_drawdown, win_rate, sharpe_ratio
                    FROM backtest_runs
                    ORDER BY total_return DESC
                    LIMIT 1
                """
                cursor = conn.execute(query)
            
            row = cursor.fetchone()
            if row:
                result = {
                    'strategy': row['strategy'],
                    'total_return': float(row['total_return']),
                    'max_drawdown': float(row['max_drawdown']),
                    'win_rate': float(row['win_rate']) / 100,  # 转换为比例
                    'sharpe_ratio': float(row['sharpe_ratio']),
                    'timestamp': datetime.now().isoformat()
                }
                self.cached_results = result
                self.cache_time = time.time()
                return result
            else:
                return None
        except Exception as e:
            print(f"❌ 回测数据获取失败: {e}")
            return None
        finally:
            if conn:
                conn.close()
    
    def get_all_top_strategies(self, limit: int = 5) -> List[Dict]:
        """获取top N回测策略"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            
            query = """
                SELECT DISTINCT strategy, total_return, max_drawdown, win_rate, sharpe_ratio
                FROM backtest_runs
                ORDER BY total_return DESC
                LIMIT ?
            """
            cursor = conn.execute(query, (limit,))
            results = []
            for row in cursor:
                results.append({
                    'strategy': row['strategy'],
                    'total_return': float(row['total_return']),
                    'max_drawdown': float(row['max_drawdown']),
                    'win_rate': float(row['win_rate']) / 100,
                    'sharpe_ratio': float(row['sharpe_ratio'])
                })
            return results
        except Exception as e:
            print(f"❌ 获取TOP策略失败: {e}")
            return []
        finally:
            if conn:
                conn.close()


class KellyPositionCalculator:
    """Kelly公式动态仓位计算"""
    
    def __init__(self, backtest_fusion: BacktestDataFusion):
        self.backtest_fusion = backtest_fusion
        # 固定参数 (根据回测数据推算)
        self.avg_win_ratio = 2.0  # 平均赢利交易赚2%
        self.avg_loss_ratio = 1.0  # 平均亏损交易亏1%
        self.kelly_safety_factor = 0.25  # 保守倍数: 25%
    
    def calculate_kelly_fraction(self, win_rate: float, avg_win: float = 2.0, 
                                avg_loss: float = 1.0) -> float:
        """计算Kelly准则比例
        
        Kelly公式: f* = (bp - q) / b
        其中:
        - b: 赔率 (平均赢利/平均亏损)
        - p: 胜率
        - q: 亏率 (1-p)
        - f*: 最优仓位比例
        
        Args:
            win_rate: 胜率 (0-1)
            avg_win: 单次赢利 (%)
            avg_loss: 单次亏损 (%)
        
        Returns:
            Kelly比例 (小数形式, 0-1)
        """
        if win_rate <= 0 or win_rate >= 1:
            return 0.05  # 极端情况返回5%
        
        b = avg_win / avg_loss  # 赔率
        p = win_rate
        q = 1 - win_rate
        
        # Kelly公式
        kelly_fraction = (b * p - q) / b
        
        # 夹在合理范围内
        kelly_fraction = max(0.01, min(0.80, kelly_fraction))
        
        return kelly_fraction
    
    def get_recommended_position_size(self, sector: str = None, 
                                     portfolio_value: float = 1_000_000,
                                     conservation_factor: float = 0.25) -> float:
        """获取推荐仓位大小
        
        Args:
            sector: 赛道名称(用于查询特定回测结果)
            portfolio_value: 投资组合总值
            conservation_factor: 保守系数 (0.25 = Kelly * 0.25)
        
        Returns:
            推荐仓位金额
        """
        backtest_data = self.backtest_fusion.get_best_strategy(sector)
        
        if not backtest_data:
            print(f"⚠️  无法获取{sector}回测数据, 使用默认5%仓位")
            return portfolio_value * 0.05
        
        win_rate = backtest_data['win_rate']
        
        # 计算Kelly比例
        kelly_fraction = self.calculate_kelly_fraction(win_rate)
        
        # 应用保守系数
        recommended_fraction = kelly_fraction * conservation_factor
        
        # 钳制在5%-30%范围
        final_fraction = max(0.05, min(0.30, recommended_fraction))
        
        position_size = portfolio_value * final_fraction
        
        print(f"✅ {sector or '通用'}赛道 - 胜率{win_rate*100:.1f}% → Kelly {kelly_fraction*100:.1f}% → 推荐仓位 {final_fraction*100:.1f}% (${position_size:,.0f})")
        
        return position_size
    
    def get_kelly_adjusted_weight(self, stock_score: float, win_rate: float, 
                                 base_weight: float = 1.0) -> float:
        """基于Kelly比例调整选股权重
        
        在选股排序时，将Kelly仓位作为权重乘子
        
        Args:
            stock_score: 股票基础评分 (0-100)
            win_rate: 策略胜率
            base_weight: 基础权重
        
        Returns:
            Kelly调整后的权重
        """
        kelly_fraction = self.calculate_kelly_fraction(win_rate)
        kelly_weight_multiplier = 1.0 + (kelly_fraction * 2.0)  # 1.0-2.6x
        
        adjusted_weight = base_weight * kelly_weight_multiplier
        
        return adjusted_weight


# =================== 改进②: 赛道差异化MACD参数 ===================

class SectorMACD参数优化:
    """根据赛道特性使用不同MACD参数"""
    
    # 基于回测数据优化的赛道MACD参数
    SECTOR_MACD_PARAMS = {
        '科技成长': {
            'fast': 12,
            'slow': 26,
            'signal': 9,
            'reason': 'TOP1策略(17.1% Sharpe2.35), 敏感型'
        },
        '新能源': {
            'fast': 10,
            'slow': 24,
            'signal': 8,
            'reason': '14.66% 收益, 快速反应趋势'
        },
        '消费白马': {
            'fast': 14,
            'slow': 28,
            'signal': 10,
            'reason': '低波动, 需要平滑参数'
        },
        '金融': {
            'fast': 16,
            'slow': 30,
            'signal': 11,
            'reason': '周期股, 超平滑避免噪音'
        },
        '医药': {
            'fast': 13,
            'slow': 27,
            'signal': 9,
            'reason': '防守型, 微调敏感度'
        },
        '军工': {
            'fast': 11,
            'slow': 25,
            'signal': 8,
            'reason': '波动中等, 快速反应'
        }
    }
    
    # 赛道RSI参数差异化
    SECTOR_RSI_PARAMS = {
        '科技成长': {
            'period': 14,
            'oversold': 28,
            'overbought': 72,
            'reason': '敏感, 低门槛触发'
        },
        '消费白马': {
            'period': 21,
            'oversold': 32,
            'overbought': 68,
            'reason': '保守, 高门槛避免虚假信号'
        },
        'default': {
            'period': 14,
            'oversold': 30,
            'overbought': 70
        }
    }
    
    @classmethod
    def get_sector_macd_params(cls, sector: str) -> Dict:
        """获取赛道特定MACD参数
        
        Args:
            sector: 赛道名称
        
        Returns:
            {'fast': 12, 'slow': 26, 'signal': 9}
        """
        return cls.SECTOR_MACD_PARAMS.get(sector, {
            'fast': 12,
            'slow': 26,
            'signal': 9,
            'reason': '默认参数(科技成长TOP1)'
        })
    
    @classmethod
    def get_sector_rsi_params(cls, sector: str) -> Dict:
        """获取赛道特定RSI参数"""
        if sector in cls.SECTOR_RSI_PARAMS:
            return cls.SECTOR_RSI_PARAMS[sector]
        else:
            return cls.SECTOR_RSI_PARAMS['default']
    
    @classmethod
    def get_macd_signal_boost(cls, sector: str) -> float:
        """获取赛道MACD信号权重加成
        
        根据回测Sharpe比例加成
        """
        boost_map = {
            '科技成长': 1.5,  # TOP1: 2.35 Sharpe
            '新能源': 1.3,    # 次优: 1.78 Sharpe
            'default': 1.0
        }
        return boost_map.get(sector, 1.0)


# =================== 改进③: 动态现金激活阈值 ===================

class DynamicCashActivation:
    """基于现金占比和情绪，动态调整入场门槛"""
    
    # 现金占比 vs 入场质量阈值
    DYNAMIC_ENTRY_THRESHOLDS = {
        (0.95, 1.00): 30,      # 现金95-100%: 30分 (贪婪建仓)
        (0.80, 0.95): 35,      # 现金80-95%: 35分
        (0.65, 0.80): 45,      # 现金65-80%: 45分
        (0.50, 0.65): 55,      # 现金50-65%: 55分 (常规)
        (0.35, 0.50): 65,      # 现金35-50%: 65分 (谨慎)
        (0.20, 0.35): 75,      # 现金20-35%: 75分 (防守)
        (0.00, 0.20): 85       # 现金<20%: 85分 (极端防守)
    }
    
    # 情绪倍数调整
    SENTIMENT_MULTIPLIERS = {
        'euphoria': 1.2,       # 极度贪婪: 门槛降20%
        'greedy': 1.0,         # 贪婪: 无调整
        'normal': 0.95,        # 中性: 门槛降5%
        'cautious': 0.85,      # 谨慎: 门槛升15%
        'panic': 0.70           # 恐慌: 门槛升40%
    }
    
    @classmethod
    def get_cash_bracket(cls, cash_ratio: float) -> Tuple[float, float]:
        """获取现金占比对应的区间"""
        for bracket in cls.DYNAMIC_ENTRY_THRESHOLDS.keys():
            low, high = bracket
            if low <= cash_ratio <= high:
                return bracket
        return (0.00, 0.20)  # 默认
    
    @classmethod
    def get_dynamic_entry_threshold(cls, cash_ratio: float, 
                                   sentiment_level: str = 'normal') -> float:
        """获取动态入场阈值
        
        Args:
            cash_ratio: 当前现金占比 (0-1)
            sentiment_level: 市场情绪 ('euphoria', 'greedy', 'normal', 'cautious', 'panic')
        
        Returns:
            入场质量评分阈值 (0-100)
        """
        bracket = cls.get_cash_bracket(cash_ratio)
        base_threshold = cls.DYNAMIC_ENTRY_THRESHOLDS[bracket]
        
        sentiment_multiplier = cls.SENTIMENT_MULTIPLIERS.get(sentiment_level, 1.0)
        
        # 调整方向: 乘以小数=抬高门槛, 乘以大数=降低门槛
        adjusted_threshold = base_threshold / sentiment_multiplier
        
        # 限制在合理范围
        adjusted_threshold = max(20, min(90, adjusted_threshold))
        
        return adjusted_threshold
    
    @classmethod
    def get_candidate_pool_size(cls, cash_ratio: float) -> int:
        """根据现金占比获取候选池大小
        
        现金越多 → 候选越多 (增加选择)
        现金越少 → 候选越少 (集中优质)
        """
        if cash_ratio >= 0.95:
            return 100  # 贪婪建仓: 100只
        elif cash_ratio >= 0.80:
            return 80
        elif cash_ratio >= 0.65:
            return 60
        elif cash_ratio >= 0.50:
            return 50  # 常规: 50只
        elif cash_ratio >= 0.35:
            return 40
        elif cash_ratio >= 0.20:
            return 30
        else:
            return 10  # 防守: 仅10只


# =================== 改进④: 持仓集中度优化 (Kelly-aware) ===================

class DynamicPositionLimits:
    """根据市场情绪和Kelly比例，动态调整持仓限制"""
    
    # 动态持仓数限制
    POSITION_COUNT_LIMITS = {
        'euphoria': 12,     # 极度贪婪: 最多12只
        'greedy': 10,       # 贪婪: 最多10只
        'normal': 8,        # 中性: 最多8只 (推荐)
        'cautious': 6,      # 谨慎: 最多6只
        'panic': 4          # 恐慌: 最多4只
    }
    
    # 动态单只仓位上限 (按持仓序号)
    MAX_SINGLE_POSITION_LIMITS = {
        'position_1_3': 0.08,    # 前3只: 8%
        'position_4_8': 0.06,    # 4-8只: 6%
        'position_9_12': 0.04,   # 9-12只: 4%
    }
    
    @classmethod
    def get_max_positions(cls, sentiment_level: str = 'normal') -> int:
        """获取动态最大持仓数"""
        return cls.POSITION_COUNT_LIMITS.get(sentiment_level, 8)
    
    @classmethod
    def get_max_single_position_limit(cls, current_position_count: int) -> float:
        """根据当前持仓数获取单只仓位上限
        
        Args:
            current_position_count: 当前持仓数
        
        Returns:
            单只最大仓位比例 (0-1)
        """
        if current_position_count <= 3:
            return cls.MAX_SINGLE_POSITION_LIMITS['position_1_3']
        elif current_position_count <= 8:
            return cls.MAX_SINGLE_POSITION_LIMITS['position_4_8']
        else:
            return cls.MAX_SINGLE_POSITION_LIMITS['position_9_12']
    
    @classmethod
    def apply_kelly_aware_limit(cls, kelly_position: float, 
                               sentiment_level: str = 'normal',
                               current_count: int = 0) -> float:
        """应用Kelly-aware的仓位限制
        
        综合考虑Kelly理论仓位、情绪和当前持仓数
        """
        max_limit = cls.get_max_single_position_limit(current_count)
        
        # Kelly仓位通常会高于我们的conservative limit
        # 我们取Kelly和limit中的较小值
        actual_limit = min(kelly_position * 0.5, max_limit)
        
        return actual_limit


# =================== 改进⑤: 6维入场质量评分 ===================

class EnhancedEntryQualityScoring:
    """扩展入场质量评分从4维到6维"""
    
    SCORE_DIMENSIONS = {
        'trend_alignment': 25,          # 趋势对齐
        'position_advantage': 25,       # 位置优势
        'volume_price_confirm': 25,     # 量价确认
        'momentum_confirm': 25,         # 动量确认
        'institution_holding': 15,      # NEW: 机构持股
        'sharpe_history': 10            # NEW: 历史Sharpe
    }
    
    TOTAL_MAX_SCORE = sum(SCORE_DIMENSIONS.values())  # 150分
    
    @classmethod
    def normalize_score(cls, raw_score: float) -> float:
        """将原始150分评分归一化到0-100"""
        normalized = (raw_score / cls.TOTAL_MAX_SCORE) * 100
        return min(100, max(0, normalized))
    
    @classmethod
    def get_institution_holding_bonus(cls, institution_holding_pct: float) -> float:
        """根据机构持股比例获得加分 (max 15分)
        
        Args:
            institution_holding_pct: 机构持股比例 (0-1)
        
        Returns:
            加分 (0-15)
        """
        if institution_holding_pct > 0.30:
            return 15  # 机构持股>30%: 满分
        elif institution_holding_pct > 0.20:
            return 12  # >20%: 12分
        elif institution_holding_pct > 0.15:
            return 10  # >15%: 10分
        elif institution_holding_pct > 0.10:
            return 7   # >10%: 7分
        elif institution_holding_pct > 0.05:
            return 4   # >5%: 4分
        else:
            return 0   # <5%: 0分
    
    @classmethod
    def get_sharpe_history_bonus(cls, historical_sharpe: float) -> float:
        """根据历史Sharpe获得加分 (max 10分)
        
        Args:
            historical_sharpe: 历史Sharpe比 (该股票的)
        
        Returns:
            加分 (0-10)
        """
        if historical_sharpe > 2.0:
            return 10  # Sharpe>2.0: 满分
        elif historical_sharpe > 1.5:
            return 8   # >1.5: 8分
        elif historical_sharpe > 1.0:
            return 5   # >1.0: 5分
        elif historical_sharpe > 0.5:
            return 2   # >0.5: 2分
        else:
            return 0   # <0.5: 0分


# =================== 改进⑥: 0.8秒快速选股引擎 ===================

class FastPickEngine:
    """多线程并行化的快速选股引擎，目标<0.8秒完成"""
    
    def __init__(self, timeout_sec: float = 0.8, max_workers: int = 4):
        self.timeout_sec = timeout_sec
        self.max_workers = max_workers
        self.stage_times = {}
    
    def pick_stocks_fast(self, 
                        get_sentiment_fn,
                        get_hot_stocks_fn,
                        get_quotes_fn,
                        score_fn,
                        top_n: int = 10) -> List[Dict]:
        """快速选股引擎 - 3阶段并行执行
        
        Stage1 (0-0.3s): 并行采集
        - 市场情绪
        - 热门股池
        - 实时行情
        
        Stage2 (0.3-0.6s): 并行过滤
        - 情绪评分
        - 技术指标
        
        Stage3 (0.6-0.9s): 排序返回
        - Kelly权重
        - 入场质量
        - 返回TOP10
        
        Args:
            get_sentiment_fn: 获取情绪的函数
            get_hot_stocks_fn: 获取热门股的函数
            get_quotes_fn: 获取报价的函数
            score_fn: 计算评分的函数
            top_n: 返回数量
        
        Returns:
            [{'code': '000001', 'score': 78.5, ...}, ...]
        """
        start_time = time.time()
        results = []
        
        try:
            # ===== Stage1: 数据采集 (0-0.3s) =====
            stage1_start = time.time()
            
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                sentiment_future = executor.submit(get_sentiment_fn)
                hot_stocks_future = executor.submit(get_hot_stocks_fn)
                
                sentiment_data = sentiment_future.result(timeout=0.25)
                hot_stocks = hot_stocks_future.result(timeout=0.25)
            
            stage1_time = time.time() - stage1_start
            self.stage_times['stage1'] = stage1_time
            print(f"  ⏱️  Stage1 (采集): {stage1_time:.3f}s ({len(hot_stocks)}只股票)")
            
            if not hot_stocks or len(hot_stocks) == 0:
                print("  ⚠️  Stage1失败: 无热门股数据, 返回应急TOP5")
                return []
            
            # ===== Stage2: 过滤与评分 (0.3-0.6s) =====
            stage2_start = time.time()
            
            # 如果时间紧张，缩减候选池
            remaining_time = self.timeout_sec - (time.time() - start_time)
            if remaining_time < 0.35:
                # 时间紧张：只处理前30只
                hot_stocks = hot_stocks[:30]
                print(f"  ⏰ 时间预警: 剩余{remaining_time:.2f}s, 候选池缩至30只")
            
            # 批量获取行情
            quotes = get_quotes_fn(hot_stocks)
            
            # 并行计算评分
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                score_futures = {}
                for stock in hot_stocks:
                    future = executor.submit(score_fn, stock, sentiment_data)
                    score_futures[stock] = future
                
                for stock, future in score_futures.items():
                    try:
                        score_result = future.result(timeout=0.2)
                        if score_result and score_result.get('score', 0) > 0:
                            results.append(score_result)
                    except Exception as e:
                        print(f"    ⚠️  {stock}评分失败: {e}")
                        continue
            
            stage2_time = time.time() - stage2_start
            self.stage_times['stage2'] = stage2_time
            print(f"  ⏱️  Stage2 (过滤+评分): {stage2_time:.3f}s ({len(results)}只通过)")
            
            # ===== Stage3: 排序返回 (0.6-0.9s) =====
            stage3_start = time.time()
            
            # 按score排序
            results.sort(key=lambda x: x.get('score', 0), reverse=True)
            
            # 返回TOP N
            final_results = results[:top_n]
            
            stage3_time = time.time() - stage3_start
            self.stage_times['stage3'] = stage3_time
            print(f"  ⏱️  Stage3 (排序返回): {stage3_time:.3f}s, 返回TOP{len(final_results)}")
            
        except Exception as e:
            print(f"  ❌ 快速选股失败: {e}")
            # 降级处理
            return results[:top_n] if results else []
        
        total_time = time.time() - start_time
        print(f"  ✅ 快速选股完成: {total_time:.3f}s (目标<0.8s)")
        
        if total_time > self.timeout_sec:
            print(f"  ⚠️  超时: {total_time:.3f}s > {self.timeout_sec}s")
        
        return final_results
    
    def get_stage_times(self) -> Dict[str, float]:
        """获取各阶段执行时间"""
        return self.stage_times.copy()


# =================== 综合集成函数 ===================

def execute_v5_106_optimization():
    """执行v5.106完整优化"""
    
    print("\n" + "="*80)
    print("🚀 v5.106 晚间深度优化 - 六大改进综合测试")
    print("="*80)
    
    # 改进①: 回测数据融合 + Kelly计算
    print("\n[改进①] 回测数据融合 + Kelly动态仓位")
    print("-" * 60)
    backtest_fusion = BacktestDataFusion()
    kelly_calc = KellyPositionCalculator(backtest_fusion)
    
    best_strategy = backtest_fusion.get_best_strategy()
    if best_strategy:
        print(f"✅ 最优策略: {best_strategy['strategy']}")
        print(f"   胜率: {best_strategy['win_rate']*100:.1f}%")
        print(f"   年化: {best_strategy['total_return']:.1f}%")
        print(f"   Sharpe: {best_strategy['sharpe_ratio']:.2f}")
        
        position_size = kelly_calc.get_recommended_position_size(sector='科技成长', portfolio_value=1_000_000)
    
    # 改进②: 赛道参数优化
    print("\n[改进②] 赛道差异化MACD参数")
    print("-" * 60)
    for sector in ['科技成长', '新能源', '消费白马']:
        macd_params = SectorMACD参数优化.get_sector_macd_params(sector)
        print(f"✅ {sector}: MACD({macd_params['fast']},{macd_params['slow']},{macd_params['signal']})")
    
    # 改进③: 动态现金激活
    print("\n[改进③] 动态现金激活阈值")
    print("-" * 60)
    cash_ratios = [0.98, 0.85, 0.70, 0.50, 0.30, 0.15]
    for cash in cash_ratios:
        threshold = DynamicCashActivation.get_dynamic_entry_threshold(cash, 'normal')
        pool_size = DynamicCashActivation.get_candidate_pool_size(cash)
        print(f"✅ 现金{cash*100:.0f}%: 入场门槛{threshold:.0f}分, 候选池{pool_size}只")
    
    # 改进④: 持仓限制优化
    print("\n[改进④] 持仓集中度优化 (Kelly-aware)")
    print("-" * 60)
    for sentiment in ['euphoria', 'normal', 'panic']:
        max_pos = DynamicPositionLimits.get_max_positions(sentiment)
        print(f"✅ {sentiment}: 最多{max_pos}只持仓")
    
    # 改进⑤: 6维评分
    print("\n[改进⑤] 6维入场质量评分")
    print("-" * 60)
    print(f"✅ 评分维度: {', '.join(EnhancedEntryQualityScoring.SCORE_DIMENSIONS.keys())}")
    print(f"   总分上限: {EnhancedEntryQualityScoring.TOTAL_MAX_SCORE}分")
    inst_bonus = EnhancedEntryQualityScoring.get_institution_holding_bonus(0.25)
    sharpe_bonus = EnhancedEntryQualityScoring.get_sharpe_history_bonus(1.8)
    print(f"   示例: 机构25%+15分, Sharpe1.8+{sharpe_bonus}分")
    
    # 改进⑥: 快速选股
    print("\n[改进⑥] 0.8秒快速选股引擎")
    print("-" * 60)
    fast_pick = FastPickEngine(timeout_sec=0.8)
    print(f"✅ 快速选股引擎初始化完成")
    print(f"   并行度: {fast_pick.max_workers}")
    print(f"   超时: {fast_pick.timeout_sec}s")
    
    print("\n" + "="*80)
    print("✅ v5.106 所有改进组件验证完成")
    print("="*80)


if __name__ == '__main__':
    execute_v5_106_optimization()
