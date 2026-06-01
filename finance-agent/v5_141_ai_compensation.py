#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v5.141 龙虎榜缺失AI补偿模块
解决小盘股龙虎榜缺失问题 - 通过AI特征补偿评分
"""

import json
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta


class AICompensationScorer:
    """
    龙虎榜缺失AI补偿评分器
    当龙虎榜数据不可用时，通过多维信号AI补偿
    """
    
    def __init__(self):
        # 基础评分 (无龙虎榜数据时)
        self.base_score = 20
        
        # 补偿信号权重
        self.compensation_weights = {
            'volume_surge': 0.25,        # 成交量突增 (最高+25分)
            'institutional_activity': 0.20,  # 机构参与 (最高+20分)
            'margin_buying': 0.10,       # 融资净买 (最高+10分)
            'emotion_correlation': 0.15, # 情绪同步度 (最高+15分)
            'sector_momentum': 0.10,     # 板块联动 (最高+10分)
        }
        
        # 信号阈值
        self.thresholds = {
            'volume_surge_multiplier': 1.5,    # 成交量突增倍数
            'volume_surge_minutes': 5,         # 检查周期(分钟)
            'institutional_min_count': 3,      # 机构参与最少笔数
            'margin_increase_pct': 0.03,       # 融资净买增幅
            'correlation_threshold': 0.65,     # 情绪相关性阈值
            'sector_momentum_pct': 0.70,       # 板块联动比例
        }
    
    def calculate_volume_signal(self, current_volume: float,
                               avg_volume_5m: float,
                               market_state: str = 'normal') -> float:
        """
        计算成交量突增信号评分 (0-25)
        
        Args:
            current_volume: 当前成交量 (最近5分钟)
            avg_volume_5m: 过去10个5分钟的平均成交量
            market_state: 市场状态 ('normal', 'volume_surge', 'limited')
            
        Returns:
            成交量信号评分 (0-25)
        """
        if avg_volume_5m == 0:
            return 0
        
        multiplier = current_volume / avg_volume_5m
        
        # 分档评分
        if multiplier < 1.2:
            return 0
        elif multiplier < 1.5:
            return 5
        elif multiplier < 2.0:
            return 12
        elif multiplier < 3.0:
            return 18
        else:  # >= 3.0
            return 25
    
    def calculate_institutional_signal(self, 
                                      large_order_count: int,
                                      large_order_ratio: float,
                                      institutional_buying_pct: float) -> float:
        """
        计算机构参与信号评分 (0-20)
        
        Args:
            large_order_count: 大单数量 (金额>100万)
            large_order_ratio: 大单占比 (0-1)
            institutional_buying_pct: 机构买入占比 (0-1)
            
        Returns:
            机构参与信号评分 (0-20)
        """
        score = 0
        
        # 大单数量评分 (0-10)
        if large_order_count >= 5:
            score += 10
        elif large_order_count >= 3:
            score += 7
        elif large_order_count >= 1:
            score += 3
        
        # 大单占比评分 (0-5)
        if large_order_ratio > 0.4:
            score += 5
        elif large_order_ratio > 0.25:
            score += 3
        elif large_order_ratio > 0.1:
            score += 1
        
        # 机构买入占比评分 (0-5)
        if institutional_buying_pct > 0.6:
            score += 5
        elif institutional_buying_pct > 0.4:
            score += 3
        elif institutional_buying_pct > 0.2:
            score += 1
        
        return min(20, score)
    
    def calculate_margin_signal(self, margin_balance: float,
                               margin_balance_yesterday: float,
                               margin_growth_rate: float = None) -> float:
        """
        计算融资净买信号评分 (0-10)
        
        Args:
            margin_balance: 融资余额 (当前)
            margin_balance_yesterday: 融资余额 (昨日)
            margin_growth_rate: 融资增长率 (可选)
            
        Returns:
            融资净买信号评分 (0-10)
        """
        if margin_balance_yesterday == 0:
            return 0
        
        # 计算增长率
        if margin_growth_rate is None:
            margin_growth_rate = (margin_balance - margin_balance_yesterday) / margin_balance_yesterday
        
        # 分档评分
        if margin_growth_rate < 0.01:
            return 0
        elif margin_growth_rate < 0.03:
            return 2
        elif margin_growth_rate < 0.05:
            return 5
        elif margin_growth_rate < 0.08:
            return 8
        else:  # >= 8%
            return 10
    
    def calculate_emotion_correlation(self, 
                                     stock_daily_returns: List[float],
                                     sentiment_daily_scores: List[float],
                                     lookback_days: int = 10) -> float:
        """
        计算股票与情绪指数的同步度相关性 (0-15)
        
        Args:
            stock_daily_returns: 股票日收益率列表 (最近N天)
            sentiment_daily_scores: 情绪分数列表 (最近N天)
            lookback_days: 回溯天数
            
        Returns:
            情绪同步度信号评分 (0-15)
        """
        if len(stock_daily_returns) < 3 or len(sentiment_daily_scores) < 3:
            return 0
        
        # 计算皮尔逊相关系数
        try:
            correlation = self._pearson_correlation(
                stock_daily_returns[-lookback_days:],
                sentiment_daily_scores[-lookback_days:]
            )
        except:
            return 0
        
        # 相关性转评分 (0.65以上为正相关)
        if correlation < 0.5:
            return 0
        elif correlation < 0.65:
            return 3
        elif correlation < 0.75:
            return 8
        elif correlation < 0.85:
            return 12
        else:  # >= 0.85
            return 15
    
    def calculate_sector_momentum(self, 
                                 stock_return_pct: float,
                                 sector_return_pct: float,
                                 sector_gainers_pct: float) -> float:
        """
        计算板块联动强度信号 (0-10)
        
        Args:
            stock_return_pct: 股票日涨幅 (%)
            sector_return_pct: 板块日涨幅 (%)
            sector_gainers_pct: 板块内上涨个股占比 (0-1)
            
        Returns:
            板块联动信号评分 (0-10)
        """
        # 如果个股跌但板块涨, 不加分
        if stock_return_pct < sector_return_pct:
            return 0
        
        # 板块内上涨占比评分
        if sector_gainers_pct >= 0.70:
            # 强板块
            if stock_return_pct > sector_return_pct:
                return 10  # 在强板块中超越
            else:
                return 6
        elif sector_gainers_pct >= 0.50:
            # 中等板块
            if stock_return_pct > sector_return_pct:
                return 7
            else:
                return 4
        else:
            # 弱板块
            return 2
    
    def ai_compensation_score(self,
                             volume_signal: float,
                             institutional_signal: float,
                             margin_signal: float,
                             emotion_correlation: float,
                             sector_momentum: float) -> Tuple[float, Dict]:
        """
        计算AI补偿总分
        
        Returns:
            (总分(0-100), 详细breakdown)
        """
        signals = {
            'volume_surge': volume_signal,
            'institutional_activity': institutional_signal,
            'margin_buying': margin_signal,
            'emotion_correlation': emotion_correlation,
            'sector_momentum': sector_momentum,
        }
        
        # 加权求和
        weighted_sum = sum(
            signals[key] * self.compensation_weights[key]
            for key in self.compensation_weights.keys()
        )
        
        # 基础分 + 加权信号
        total_score = self.base_score + weighted_sum
        
        # 上限100分
        total_score = min(100, total_score)
        
        # 详细分解
        breakdown = {
            'base_score': self.base_score,
            'weighted_signals': signals,
            'signal_weights': self.compensation_weights,
            'contributions': {
                key: signals[key] * self.compensation_weights[key]
                for key in self.compensation_weights.keys()
            },
            'total_compensation': weighted_sum,
            'final_score': round(total_score, 2),
        }
        
        return total_score, breakdown
    
    def _pearson_correlation(self, x: List[float], 
                            y: List[float]) -> float:
        """
        计算皮尔逊相关系数
        """
        if len(x) != len(y) or len(x) < 2:
            return 0
        
        mean_x = sum(x) / len(x)
        mean_y = sum(y) / len(y)
        
        numerator = sum(
            (x[i] - mean_x) * (y[i] - mean_y)
            for i in range(len(x))
        )
        
        denominator_x = sum((xi - mean_x) ** 2 for xi in x) ** 0.5
        denominator_y = sum((yi - mean_y) ** 2 for yi in y) ** 0.5
        
        if denominator_x == 0 or denominator_y == 0:
            return 0
        
        return numerator / (denominator_x * denominator_y)


class AICompensationReportGenerator:
    """
    AI补偿分析报告生成器
    """
    
    def __init__(self, scorer: AICompensationScorer):
        self.scorer = scorer
    
    def generate_report(self,
                       stock_code: str,
                       stock_name: str,
                       market_cap: float,
                       has_longhu_data: bool,
                       volume_data: Dict,
                       institutional_data: Dict,
                       margin_data: Dict,
                       emotion_data: Dict,
                       sector_data: Dict) -> Dict:
        """
        生成完整的AI补偿分析报告
        
        Args:
            stock_code: 股票代码
            stock_name: 股票名称
            market_cap: 市值 (亿元)
            has_longhu_data: 是否有龙虎榜数据
            volume_data: 成交量数据
            institutional_data: 机构数据
            margin_data: 融资数据
            emotion_data: 情绪数据
            sector_data: 板块数据
            
        Returns:
            完整报告字典
        """
        
        # 如果有龙虎榜数据，直接返回龙虎榜评分 (不需要AI补偿)
        if has_longhu_data:
            return {
                'stock_code': stock_code,
                'stock_name': stock_name,
                'market_cap_billion': market_cap,
                'data_source': 'longhu_ranking',
                'score': volume_data.get('longhu_score', 0),
                'compensation_used': False,
                'note': '使用龙虎榜官方数据，无需AI补偿',
            }
        
        # 无龙虎榜数据 - 计算AI补偿分数
        volume_signal = self.scorer.calculate_volume_signal(
            volume_data.get('current_volume', 0),
            volume_data.get('avg_volume_5m', 0),
        )
        
        institutional_signal = self.scorer.calculate_institutional_signal(
            institutional_data.get('large_order_count', 0),
            institutional_data.get('large_order_ratio', 0),
            institutional_data.get('institutional_buying_pct', 0),
        )
        
        margin_signal = self.scorer.calculate_margin_signal(
            margin_data.get('margin_balance', 0),
            margin_data.get('margin_balance_yesterday', 0),
        )
        
        emotion_correlation = self.scorer.calculate_emotion_correlation(
            emotion_data.get('stock_returns', []),
            emotion_data.get('sentiment_scores', []),
        )
        
        sector_momentum = self.scorer.calculate_sector_momentum(
            sector_data.get('stock_return_pct', 0),
            sector_data.get('sector_return_pct', 0),
            sector_data.get('sector_gainers_pct', 0),
        )
        
        # 计算最终补偿分数
        total_score, breakdown = self.scorer.ai_compensation_score(
            volume_signal,
            institutional_signal,
            margin_signal,
            emotion_correlation,
            sector_momentum,
        )
        
        report = {
            'stock_code': stock_code,
            'stock_name': stock_name,
            'market_cap_billion': market_cap,
            'timestamp': datetime.now().isoformat(),
            'data_source': 'ai_compensation',
            'compensation_used': True,
            'signal_scores': {
                'volume_surge': round(volume_signal, 2),
                'institutional_activity': round(institutional_signal, 2),
                'margin_buying': round(margin_signal, 2),
                'emotion_correlation': round(emotion_correlation, 2),
                'sector_momentum': round(sector_momentum, 2),
            },
            'compensation_breakdown': breakdown,
            'final_score': round(total_score, 2),
            'recommendation': self._get_recommendation(total_score),
            'confidence': self._get_confidence_level(total_score),
        }
        
        return report
    
    def _get_recommendation(self, score: float) -> str:
        """根据评分生成建议"""
        if score >= 80:
            return '强烈推荐 🟢'
        elif score >= 65:
            return '推荐关注 🟢'
        elif score >= 50:
            return '中立关注 🟡'
        elif score >= 35:
            return '谨慎关注 🟡'
        else:
            return '暂不推荐 🔴'
    
    def _get_confidence_level(self, score: float) -> str:
        """根据评分确定置信度"""
        if score >= 85:
            return '非常高 ⭐⭐⭐⭐⭐'
        elif score >= 70:
            return '高 ⭐⭐⭐⭐'
        elif score >= 55:
            return '中等 ⭐⭐⭐'
        elif score >= 40:
            return '一般 ⭐⭐'
        else:
            return '低 ⭐'


# ============================================================
# 测试用例
# ============================================================

if __name__ == '__main__':
    scorer = AICompensationScorer()
    report_gen = AICompensationReportGenerator(scorer)
    
    print("=" * 80)
    print("龙虎榜缺失AI补偿模块 - 测试")
    print("=" * 80)
    
    # 测试场景: 华映科技 (200亿市值, 无龙虎榜)
    print("\n📊 测试案例: 华映科技 (200亿市值, 无龙虎榜数据)")
    print("-" * 80)
    
    # 模拟数据
    volume_data = {
        'current_volume': 1500000,  # 最近5分钟成交
        'avg_volume_5m': 900000,    # 过去10个5分钟平均
    }
    
    institutional_data = {
        'large_order_count': 4,      # 大单笔数
        'large_order_ratio': 0.35,   # 大单占比
        'institutional_buying_pct': 0.55,  # 机构买入占比
    }
    
    margin_data = {
        'margin_balance': 5000000,        # 融资余额
        'margin_balance_yesterday': 4750000,  # 昨日融资余额
    }
    
    emotion_data = {
        'stock_returns': [0.02, 0.015, 0.01, 0.025, 0.018, -0.005, 0.012, 0.008, 0.015, 0.020],
        'sentiment_scores': [85, 87, 88, 90, 89, 75, 80, 82, 85, 88],
    }
    
    sector_data = {
        'stock_return_pct': 2.1,      # 今日股票涨幅
        'sector_return_pct': 1.8,     # 板块涨幅
        'sector_gainers_pct': 0.72,   # 板块内上涨占比
    }
    
    report = report_gen.generate_report(
        stock_code='000536',
        stock_name='华映科技',
        market_cap=200,
        has_longhu_data=False,
        volume_data=volume_data,
        institutional_data=institutional_data,
        margin_data=margin_data,
        emotion_data=emotion_data,
        sector_data=sector_data,
    )
    
    print(json.dumps(report, indent=2, ensure_ascii=False))
    
    print("\n" + "=" * 80)
    print("✅ AI补偿模块测试完成")
