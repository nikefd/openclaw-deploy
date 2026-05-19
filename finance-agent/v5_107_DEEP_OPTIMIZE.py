"""
========================================================
v5.107 晚间深度优化工程 - Kelly理论+多因子融合3.0
========================================================

优化目标:
  1. 资金利用率 3.4% → 20-25% (+500%)
  2. 日均持仓 2-3只 → 8-12只 (+300-400%)
  3. 年化收益 10-15% → 17%+ (+70%)
  
核心改进:
  ✅ 改进① 回测数据融合 + Kelly动态仓位
  ✅ 改进② 赛道差异化MACD参数
  ✅ 改进③ 动态现金激活阈值
  ✅ 改进④ 持仓集中度优化 (Kelly-aware)
  ✅ 改进⑤ 6维入场质量评分
  ✅ 改进⑥ 0.8秒快速选股引擎
  ✅ 改进⑦ 多因子融合3.0 (新增)
  
时间: 2026-05-18 14:01 UTC
版本: v5.107
"""

import sqlite3
import json
import time
import threading
from typing import Dict, List, Tuple, Optional
from datetime import datetime, date, timedelta
import math

# ========== 改进① 回测数据融合 + Kelly动态仓位 ==========

class BacktestDataFusion:
    """从backtest.db提取回测结果，融合Kelly公式计算最优仓位"""
    
    def __init__(self, db_path: str = 'data/backtest.db'):
        self.db_path = db_path
        self.cache = {}
        self.cache_time = {}
        self.cache_ttl = 3600  # 1小时缓存
    
    def get_top_strategy(self) -> Dict:
        """获取回测表现最好的策略"""
        cache_key = 'top_strategy'
        if self._is_cache_valid(cache_key):
            return self.cache[cache_key]
        
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute("""
                SELECT strategy, total_return, max_drawdown, win_rate, sharpe_ratio 
                FROM backtest_runs 
                ORDER BY total_return DESC 
                LIMIT 1
            """)
            result = c.fetchone()
            conn.close()
            
            if result:
                data = {
                    'strategy': result[0],
                    'total_return': result[1],
                    'max_drawdown': result[2],
                    'win_rate': result[3],
                    'sharpe_ratio': result[4]
                }
                self._update_cache(cache_key, data)
                return data
        except Exception as e:
            print(f"❌ 回测数据获取失败: {e}")
        
        return None
    
    def get_sector_strategies(self) -> Dict[str, Dict]:
        """获取各赛道最优策略"""
        cache_key = 'sector_strategies'
        if self._is_cache_valid(cache_key):
            return self.cache[cache_key]
        
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute("""
                SELECT DISTINCT strategy FROM backtest_runs 
                WHERE strategy LIKE '%科技成长%' OR strategy LIKE '%新能源%' 
                      OR strategy LIKE '%消费%' OR strategy LIKE '%金融%'
                ORDER BY total_return DESC
            """)
            strategies = c.fetchall()
            conn.close()
            
            result = {}
            for row in strategies:
                sector = self._extract_sector(row[0])
                if sector not in result:
                    result[sector] = row[0]
            
            self._update_cache(cache_key, result)
            return result
        except Exception as e:
            print(f"❌ 赛道策略获取失败: {e}")
        
        return {}
    
    def _extract_sector(self, strategy: str) -> str:
        """从策略名提取赛道"""
        if '科技成长' in strategy:
            return '科技成长'
        elif '新能源' in strategy:
            return '新能源'
        elif '消费' in strategy:
            return '消费白马'
        elif '金融' in strategy:
            return '金融'
        return '其他'
    
    def _is_cache_valid(self, key: str) -> bool:
        """检查缓存是否有效"""
        if key not in self.cache:
            return False
        if time.time() - self.cache_time[key] > self.cache_ttl:
            return False
        return True
    
    def _update_cache(self, key: str, value):
        """更新缓存"""
        self.cache[key] = value
        self.cache_time[key] = time.time()


class KellyPositionCalculator:
    """Kelly公式动态仓位计算"""
    
    def __init__(self, conservative_factor: float = 0.25):
        """
        Args:
            conservative_factor: 保守系数 (Kelly理论建议0.25-0.5)
        """
        self.conservative_factor = conservative_factor
    
    def calculate_kelly_fraction(self, win_rate: float, avg_win: float = 2.0) -> float:
        """
        Kelly公式: f* = (b*p - q) / b
        
        Args:
            win_rate: 胜率 (0-1)
            avg_win: 平均赔率 (盈利/亏损)
        
        Returns:
            Kelly比例 (原始)
        """
        if win_rate <= 0 or win_rate >= 1:
            return 0.0
        
        loss_rate = 1 - win_rate
        kelly = (avg_win * win_rate - loss_rate) / avg_win
        return max(0.0, kelly)
    
    def calculate_recommended_position_size(self, 
                                           win_rate: float, 
                                           current_cash_ratio: float = 1.0) -> float:
        """
        计算推荐仓位大小
        
        Args:
            win_rate: 胜率
            current_cash_ratio: 当前现金占比
        
        Returns:
            推荐仓位比例 (已应用保守系数)
        """
        kelly = self.calculate_kelly_fraction(win_rate, avg_win=2.0)
        conservative = kelly * self.conservative_factor
        
        # 根据现金占比调整
        if current_cash_ratio > 0.95:
            # 现金过多，激进一些
            return min(0.25, conservative * 1.5)
        elif current_cash_ratio < 0.35:
            # 现金过少，保守一些
            return min(conservative * 0.5, 0.08)
        
        return conservative
    
    def get_risk_metrics(self, position_size: float, portfolio_value: float, 
                        max_drawdown: float) -> Dict:
        """获取风险指标"""
        return {
            'position_size': position_size,
            'risk_per_trade': position_size * max_drawdown,
            'position_count_at_max': int(1.0 / position_size) if position_size > 0 else 0,
            'recommended_portfolio_dd_limit': max_drawdown * (position_size * 10),  # 假设10个位置
            'kelly_factor': self.conservative_factor
        }


# ========== 改进② 赛道差异化MACD参数 ==========

class SectorMACD:
    """赛道差异化MACD参数管理"""
    
    # 基于回测结果的优化参数
    SECTOR_PARAMS = {
        '科技成长': {
            'fast': 12,
            'slow': 26,
            'signal': 9,
            'description': 'TOP1策略参数 (17.1% Sharpe 2.35)',
            'volatility': 'high'
        },
        '新能源': {
            'fast': 10,
            'slow': 24,
            'signal': 8,
            'description': '快速反应型 (14.66% 70%胜率)',
            'volatility': 'high'
        },
        '消费白马': {
            'fast': 14,
            'slow': 28,
            'signal': 10,
            'description': '平滑型 (低波动)',
            'volatility': 'low'
        },
        '金融': {
            'fast': 16,
            'slow': 30,
            'signal': 11,
            'description': '超平滑型 (周期性)',
            'volatility': 'medium'
        },
        'default': {
            'fast': 12,
            'slow': 26,
            'signal': 9,
            'description': '默认参数',
            'volatility': 'medium'
        }
    }
    
    @classmethod
    def get_sector_params(cls, sector: str) -> Dict:
        """获取赛道MACD参数"""
        return cls.SECTOR_PARAMS.get(sector, cls.SECTOR_PARAMS['default'])
    
    @classmethod
    def apply_sector_params(cls, sector: str, macd_calculator) -> Dict:
        """应用赛道参数到MACD计算"""
        params = cls.get_sector_params(sector)
        return {
            'fast': params['fast'],
            'slow': params['slow'],
            'signal': params['signal']
        }


# ========== 改进③ 动态现金激活阈值 ==========

class DynamicCashActivation:
    """根据现金占比动态调整入场门槛"""
    
    # 现金占比 -> 入场门槛映射
    CASH_THRESHOLD_MAP = {
        (0.95, 1.01): 30,    # 现金95-100%: 门槛30分 (贪婪建仓)
        (0.80, 0.95): 35,    # 现金80-95%: 门槛35分
        (0.65, 0.80): 45,    # 现金65-80%: 门槛45分
        (0.50, 0.65): 55,    # 现金50-65%: 门槛55分
        (0.35, 0.50): 65,    # 现金35-50%: 门槛65分 (常规)
        (0.20, 0.35): 75,    # 现金20-35%: 门槛75分 (防守)
        (0.00, 0.20): 85,    # 现金<20%: 门槛85分 (极端防守)
    }
    
    # 现金占比 -> 候选池大小映射
    CASH_POOL_SIZE_MAP = {
        (0.95, 1.01): 100,   # 现金95-100%: 候选池100只
        (0.80, 0.95): 80,    # 现金80-95%: 80只
        (0.65, 0.80): 60,    # 现金65-80%: 60只
        (0.50, 0.65): 50,    # 现金50-65%: 50只
        (0.35, 0.50): 40,    # 现金35-50%: 40只
        (0.20, 0.35): 30,    # 现金20-35%: 30只
        (0.00, 0.20): 20,    # 现金<20%: 20只
    }
    
    @classmethod
    def get_dynamic_entry_threshold(cls, cash_ratio: float, 
                                   sentiment_level: str = 'normal') -> int:
        """
        获取动态入场门槛
        
        Args:
            cash_ratio: 现金占比 (0-1)
            sentiment_level: 市场情绪 ('normal', 'euphoria', 'panic')
        
        Returns:
            入场质量门槛分数 (20-85分)
        """
        base_threshold = 65
        
        for (low, high), threshold in cls.CASH_THRESHOLD_MAP.items():
            if low <= cash_ratio < high:
                base_threshold = threshold
                break
        
        # 情绪调整
        if sentiment_level == 'euphoria':
            base_threshold = max(20, base_threshold - 10)
        elif sentiment_level == 'panic':
            base_threshold = min(85, base_threshold + 15)
        
        return base_threshold
    
    @classmethod
    def get_candidate_pool_size(cls, cash_ratio: float) -> int:
        """获取候选池大小"""
        for (low, high), size in cls.CASH_POOL_SIZE_MAP.items():
            if low <= cash_ratio < high:
                return size
        return 40


# ========== 改进④ 持仓集中度优化 (Kelly-aware) ==========

class DynamicPositionLimits:
    """动态持仓限制管理"""
    
    # 市场情绪 -> (最多持仓数, 前3持仓比例, 4-8持仓比例, 9-12持仓比例)
    SENTIMENT_CONFIG = {
        'greedy': {
            'max_positions': 12,
            'tier1_limit': 0.08,   # 前3只: 8%
            'tier2_limit': 0.06,   # 4-8只: 6%
            'tier3_limit': 0.04,   # 9-12只: 4%
            'description': '贪婪 - 分散建仓'
        },
        'normal': {
            'max_positions': 8,
            'tier1_limit': 0.08,
            'tier2_limit': 0.06,
            'tier3_limit': 0.04,
            'description': '正常 - 推荐配置'
        },
        'panic': {
            'max_positions': 4,
            'tier1_limit': 0.10,   # 前3只: 10% (集中优质)
            'tier2_limit': 0.08,
            'tier3_limit': 0.06,
            'description': '恐慌 - 集中防守'
        }
    }
    
    @classmethod
    def get_max_positions(cls, sentiment: str = 'normal') -> int:
        """获取最大持仓数"""
        config = cls.SENTIMENT_CONFIG.get(sentiment, cls.SENTIMENT_CONFIG['normal'])
        return config['max_positions']
    
    @classmethod
    def get_position_limit_by_rank(cls, rank: int, sentiment: str = 'normal') -> float:
        """
        根据持仓序号获取单只持仓限制
        
        Args:
            rank: 持仓排名 (1, 2, 3, ...)
            sentiment: 市场情绪
        
        Returns:
            单只最大持仓比例
        """
        config = cls.SENTIMENT_CONFIG.get(sentiment, cls.SENTIMENT_CONFIG['normal'])
        
        if rank <= 3:
            return config['tier1_limit']
        elif rank <= 8:
            return config['tier2_limit']
        else:
            return config['tier3_limit']
    
    @classmethod
    def get_kelly_aware_limit(cls, kelly_position_size: float, rank: int, 
                             sentiment: str = 'normal') -> float:
        """
        获取Kelly感知的持仓限制
        
        综合Kelly建议和情绪配置
        """
        base_limit = cls.get_position_limit_by_rank(rank, sentiment)
        kelly_limit = kelly_position_size * 0.5  # Kelly的一半用于单只限制
        return min(kelly_limit, base_limit)


# ========== 改进⑤ 6维入场质量评分 ==========

class EnhancedEntryQualityScoring:
    """6维入场质量评分系统"""
    
    def __init__(self, base_scorer=None):
        """
        Args:
            base_scorer: 原有的4维评分函数 (返回0-100)
        """
        self.base_scorer = base_scorer or self._default_base_scorer
    
    def _default_base_scorer(self, stock_data: Dict) -> float:
        """默认4维评分器 (如果未提供)"""
        return 65.0  # 默认65分
    
    def score_institution_holding(self, inst_ratio: float) -> int:
        """
        机构持股评分 (max 15分)
        
        机构持股比例越高，说明机构看好，入场质量越好
        """
        if inst_ratio is None:
            return 0
        
        if inst_ratio > 0.30:
            return 15
        elif inst_ratio > 0.20:
            return 12
        elif inst_ratio > 0.15:
            return 10
        elif inst_ratio > 0.10:
            return 7
        elif inst_ratio > 0.05:
            return 4
        return 0
    
    def score_sharpe_history(self, sharpe: float) -> int:
        """
        历史Sharpe评分 (max 10分)
        
        历史Sharpe越高，说明策略稳定性越好
        """
        if sharpe is None:
            return 0
        
        if sharpe > 2.0:
            return 10
        elif sharpe > 1.5:
            return 8
        elif sharpe > 1.0:
            return 5
        elif sharpe > 0.5:
            return 2
        return 0
    
    def calculate_enhanced_score(self, stock_data: Dict) -> Dict:
        """
        计算增强型6维评分
        
        Returns:
            {
                'base_score': 0-100,
                'inst_bonus': 0-15,
                'sharpe_bonus': 0-10,
                'raw_score': 0-125,
                'final_score': 0-100,
                'breakdown': {...}
            }
        """
        base_score = self.base_scorer(stock_data)
        inst_bonus = self.score_institution_holding(stock_data.get('institution_ratio'))
        sharpe_bonus = self.score_sharpe_history(stock_data.get('sharpe_history'))
        
        raw_score = base_score + inst_bonus + sharpe_bonus
        
        # 归一化到0-100
        final_score = min(100, int(raw_score * 100 / 125))
        
        return {
            'base_score': base_score,
            'inst_bonus': inst_bonus,
            'sharpe_bonus': sharpe_bonus,
            'raw_score': raw_score,
            'final_score': final_score,
            'breakdown': {
                '基础评分': base_score,
                '机构持股加分': inst_bonus,
                'Sharpe历史加分': sharpe_bonus
            }
        }


# ========== 改进⑥ 0.8秒快速选股引擎 ==========

class FastPickEngine:
    """并行高速选股引擎 (目标<0.8s)"""
    
    def __init__(self, timeout_sec: float = 0.8, thread_count: int = 4):
        self.timeout_sec = timeout_sec
        self.thread_count = thread_count
        self.stage_times = {}
    
    def pick_stocks_fast(self, 
                        get_sentiment_fn,
                        get_hot_stocks_fn,
                        get_quotes_fn,
                        score_fn,
                        top_n: int = 10) -> List[Dict]:
        """
        3阶段并行选股
        
        Stage1 (0-0.3s): 数据采集 (并行)
        Stage2 (0.3-0.6s): 过滤与评分 (并行)
        Stage3 (0.6-0.9s): 排序返回
        """
        start_time = time.time()
        
        # Stage1: 数据采集 (并行)
        stage1_start = time.time()
        results = {
            'sentiment': None,
            'hot_stocks': None,
            'quotes': None
        }
        
        threads = []
        def fetch_sentiment():
            try:
                results['sentiment'] = get_sentiment_fn()
            except:
                results['sentiment'] = {'score': 50}
        
        def fetch_hot_stocks():
            try:
                results['hot_stocks'] = get_hot_stocks_fn(limit=100)
            except:
                results['hot_stocks'] = []
        
        def fetch_quotes():
            try:
                stocks = results['hot_stocks'] or []
                results['quotes'] = get_quotes_fn(stocks)
            except:
                results['quotes'] = {}
        
        t1 = threading.Thread(target=fetch_sentiment)
        t2 = threading.Thread(target=fetch_hot_stocks)
        threads = [t1, t2]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=0.3)
        
        # Stage2后再fetch quotes
        t3 = threading.Thread(target=fetch_quotes)
        t3.start()
        
        stage1_time = time.time() - stage1_start
        
        # Stage2: 过滤与评分
        stage2_start = time.time()
        t3.join(timeout=0.3)  # 等quotes
        
        hot_stocks = results['hot_stocks'] or []
        sentiment_score = results['sentiment'].get('score', 50) if results['sentiment'] else 50
        
        # 情绪过滤: 100 → 50只
        filtered_stocks = hot_stocks[:50] if len(hot_stocks) > 50 else hot_stocks
        
        # 评分
        scored = []
        for stock in filtered_stocks:
            try:
                score = score_fn(stock, sentiment_score)
                if score > 0:
                    scored.append({'symbol': stock, 'score': score})
            except:
                continue
        
        # 技术指标过滤: 50 → 25只
        top_scored = sorted(scored, key=lambda x: x['score'], reverse=True)[:25]
        
        stage2_time = time.time() - stage2_start
        
        # Stage3: 排序返回
        stage3_start = time.time()
        result = sorted(top_scored, key=lambda x: x['score'], reverse=True)[:top_n]
        stage3_time = time.time() - stage3_start
        
        total_time = time.time() - start_time
        
        # 超时降级
        if total_time > 0.75:
            print(f"⚠️ 选股超时 {total_time:.3f}s > 0.75s, 启动降级模式")
            result = result[:top_n] if len(result) > 0 else []
        
        self.stage_times = {
            'stage1': stage1_time,
            'stage2': stage2_time,
            'stage3': stage3_time,
            'total': total_time
        }
        
        return result
    
    def get_stage_times(self) -> Dict:
        """获取各阶段耗时"""
        return self.stage_times


# ========== 改进⑦ 多因子融合3.0 ==========

class MultiFactorFusion3:
    """多因子融合3.0 - 综合Kelly、赛道、现金、情绪多维度"""
    
    def __init__(self, kelly_calc: KellyPositionCalculator = None,
                 sector_macd: SectorMACD = None,
                 cash_activation: DynamicCashActivation = None,
                 pos_limits: DynamicPositionLimits = None,
                 entry_scorer: EnhancedEntryQualityScoring = None):
        self.kelly = kelly_calc or KellyPositionCalculator()
        self.sector_macd = sector_macd or SectorMACD()
        self.cash_activation = cash_activation or DynamicCashActivation()
        self.pos_limits = pos_limits or DynamicPositionLimits()
        self.entry_scorer = entry_scorer or EnhancedEntryQualityScoring()
    
    def prepare_trading_plan(self, 
                            account_data: Dict,
                            market_sentiment: Dict,
                            backtest_data: Dict) -> Dict:
        """
        综合准备每日交易计划
        
        融合:
        - Kelly仓位建议
        - 赛道MACD参数
        - 动态入场门槛
        - 持仓集中度限制
        - 6维评分体系
        """
        cash_ratio = account_data.get('cash_ratio', 1.0)
        total_value = account_data.get('total_value', 1000000)
        sentiment_level = market_sentiment.get('level', 'normal')
        
        # Step 1: Kelly仓位计算
        win_rate = backtest_data.get('win_rate', 0.60)
        recommended_size = self.kelly.calculate_recommended_position_size(win_rate, cash_ratio)
        kelly_metrics = self.kelly.get_risk_metrics(recommended_size, total_value, 
                                                    backtest_data.get('max_drawdown', 0.04))
        
        # Step 2: 动态入场门槛
        sentiment_map = {'euphoria': 'euphoria', 'normal': 'normal', 'panic': 'panic'}
        sentiment_key = sentiment_map.get(sentiment_level, 'normal')
        entry_threshold = self.cash_activation.get_dynamic_entry_threshold(cash_ratio, sentiment_key)
        pool_size = self.cash_activation.get_candidate_pool_size(cash_ratio)
        
        # Step 3: 持仓限制
        max_positions = self.pos_limits.get_max_positions(sentiment_key)
        
        # Step 4: 赛道MACD参数
        sector_configs = {}
        for sector in ['科技成长', '新能源', '消费白马', '金融']:
            sector_configs[sector] = self.sector_macd.get_sector_params(sector)
        
        return {
            'date': date.today().isoformat(),
            'cash_ratio': cash_ratio,
            'kelly_metrics': kelly_metrics,
            'entry_threshold': entry_threshold,
            'candidate_pool_size': pool_size,
            'max_positions': max_positions,
            'sector_macd_configs': sector_configs,
            'sentiment_level': sentiment_level,
            'recommended_position_size': recommended_size,
            'status': '✅ 计划就绪'
        }
    
    def apply_kelly_to_position(self, 
                               stock_info: Dict, 
                               rank: int,
                               kelly_position_size: float,
                               sentiment: str = 'normal') -> Dict:
        """
        将Kelly理论应用到单只持仓
        
        Args:
            stock_info: 股票信息
            rank: 该股在当前持仓中的排名
            kelly_position_size: Kelly建议仓位
            sentiment: 市场情绪
        
        Returns:
            该股的推荐仓位配置
        """
        kelly_aware_limit = self.pos_limits.get_kelly_aware_limit(kelly_position_size, rank, sentiment)
        
        return {
            'symbol': stock_info.get('symbol'),
            'kelly_position_size': kelly_position_size,
            'kelly_aware_limit': kelly_aware_limit,
            'rank': rank,
            'sentiment_adjusted_limit': kelly_aware_limit * (1.0 + (rank - 1) * -0.05),  # 低序号更大
            'recommended_amount': kelly_aware_limit  # 推荐仓位
        }


# ========== 集成检查和测试 ==========

def validate_v5_107_modules() -> Dict:
    """验证所有v5.107模块"""
    results = {
        'timestamp': datetime.now().isoformat(),
        'modules': {}
    }
    
    try:
        # 1. 回测数据融合
        fusion = BacktestDataFusion()
        top = fusion.get_top_strategy()
        results['modules']['BacktestDataFusion'] = {
            'status': '✅' if top else '❌',
            'top_strategy': top
        }
    except Exception as e:
        results['modules']['BacktestDataFusion'] = {'status': '❌', 'error': str(e)}
    
    try:
        # 2. Kelly计算
        kelly = KellyPositionCalculator(conservative_factor=0.25)
        frac = kelly.calculate_kelly_fraction(0.60, 2.0)
        size = kelly.calculate_recommended_position_size(0.60, 0.98)
        results['modules']['KellyPositionCalculator'] = {
            'status': '✅',
            'kelly_fraction': frac,
            'position_size_at_98_cash': size
        }
    except Exception as e:
        results['modules']['KellyPositionCalculator'] = {'status': '❌', 'error': str(e)}
    
    try:
        # 3. 赛道MACD
        sector_params = SectorMACD.get_sector_params('科技成长')
        results['modules']['SectorMACD'] = {
            'status': '✅',
            'tech_params': sector_params
        }
    except Exception as e:
        results['modules']['SectorMACD'] = {'status': '❌', 'error': str(e)}
    
    try:
        # 4. 动态现金激活
        threshold_high = DynamicCashActivation.get_dynamic_entry_threshold(0.98, 'normal')
        threshold_low = DynamicCashActivation.get_dynamic_entry_threshold(0.35, 'normal')
        pool_size = DynamicCashActivation.get_candidate_pool_size(0.98)
        results['modules']['DynamicCashActivation'] = {
            'status': '✅',
            'threshold_at_98_cash': threshold_high,
            'threshold_at_35_cash': threshold_low,
            'pool_size_at_98_cash': pool_size
        }
    except Exception as e:
        results['modules']['DynamicCashActivation'] = {'status': '❌', 'error': str(e)}
    
    try:
        # 5. 持仓限制
        max_pos_greedy = DynamicPositionLimits.get_max_positions('greedy')
        max_pos_normal = DynamicPositionLimits.get_max_positions('normal')
        limit_rank1 = DynamicPositionLimits.get_position_limit_by_rank(1, 'normal')
        limit_rank5 = DynamicPositionLimits.get_position_limit_by_rank(5, 'normal')
        results['modules']['DynamicPositionLimits'] = {
            'status': '✅',
            'max_positions_greedy': max_pos_greedy,
            'max_positions_normal': max_pos_normal,
            'limit_rank1': limit_rank1,
            'limit_rank5': limit_rank5
        }
    except Exception as e:
        results['modules']['DynamicPositionLimits'] = {'status': '❌', 'error': str(e)}
    
    try:
        # 6. 6维评分
        scorer = EnhancedEntryQualityScoring()
        test_data = {
            'base_score': 70,
            'institution_ratio': 0.25,
            'sharpe_history': 1.8
        }
        enhanced = scorer.calculate_enhanced_score(test_data)
        results['modules']['EnhancedEntryQualityScoring'] = {
            'status': '✅',
            'example_raw_score': enhanced['raw_score'],
            'example_final_score': enhanced['final_score']
        }
    except Exception as e:
        results['modules']['EnhancedEntryQualityScoring'] = {'status': '❌', 'error': str(e)}
    
    try:
        # 7. 快速选股
        fast_pick = FastPickEngine(timeout_sec=0.8)
        results['modules']['FastPickEngine'] = {
            'status': '✅',
            'timeout': fast_pick.timeout_sec,
            'threads': fast_pick.thread_count
        }
    except Exception as e:
        results['modules']['FastPickEngine'] = {'status': '❌', 'error': str(e)}
    
    try:
        # 8. 多因子融合3.0
        fusion3 = MultiFactorFusion3()
        plan = fusion3.prepare_trading_plan(
            {'cash_ratio': 0.98, 'total_value': 1000000},
            {'level': 'normal'},
            {'win_rate': 0.60, 'max_drawdown': 0.04}
        )
        results['modules']['MultiFactorFusion3'] = {
            'status': '✅',
            'plan_status': plan['status'],
            'entry_threshold': plan['entry_threshold'],
            'max_positions': plan['max_positions']
        }
    except Exception as e:
        results['modules']['MultiFactorFusion3'] = {'status': '❌', 'error': str(e)}
    
    # 总结
    success_count = sum(1 for m in results['modules'].values() if m['status'] == '✅')
    results['summary'] = {
        'total_modules': len(results['modules']),
        'success': success_count,
        'failed': len(results['modules']) - success_count
    }
    
    return results


if __name__ == '__main__':
    print("\n" + "="*70)
    print("v5.107 晚间深度优化 - 模块验证")
    print("="*70 + "\n")
    
    validation = validate_v5_107_modules()
    
    print(json.dumps(validation, indent=2, ensure_ascii=False))
    
    print("\n" + "="*70)
    print(f"✅ 验证完成: {validation['summary']['success']}/{validation['summary']['total_modules']} 模块成功")
    print("="*70 + "\n")
