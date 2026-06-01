#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v5.141 信号融合引擎 v2.0 - 动态权重优化
根据市场情绪/波动率自动调整信号权重
"""

import json
import numpy as np
from typing import Dict, List, Tuple


class SignalWeightOptimizer:
    """
    动态权重优化器
    核心: 根据市场状态自适应调整信号权重
    """
    
    def __init__(self):
        # 默认权重 (基础配置)
        self.base_weights = {
            'technical': 0.40,    # 技术指标
            'funding': 0.30,      # 资金面
            'sentiment': 0.20,    # 情绪指标
            'fundamental': 0.10,  # 基本面
        }
        
        # 情绪状态权重矩阵 (由情绪分数驱动)
        self.emotion_weight_matrix = {
            'extreme_greed': {      # 情绪>92
                'technical': 0.30,
                'funding': 0.40,    # ↑ 资金面优先
                'sentiment': 0.20,
                'fundamental': 0.10,
                'description': '极度贪婪: 资金面+风控优先',
            },
            'greed': {              # 情绪80-92
                'technical': 0.35,
                'funding': 0.35,
                'sentiment': 0.20,
                'fundamental': 0.10,
                'description': '贪婪: 技术+资金平衡',
            },
            'neutral': {            # 情绪40-80
                'technical': 0.45,  # ↑ 技术面
                'funding': 0.25,
                'sentiment': 0.15,
                'fundamental': 0.15,
                'description': '中性: 技术面主导',
            },
            'fear': {               # 情绪20-40
                'technical': 0.45,
                'funding': 0.25,
                'sentiment': 0.10,
                'fundamental': 0.20, # ↑ 基本面
                'description': '恐惧: 基本面+技术',
            },
            'extreme_fear': {       # 情绪<20
                'technical': 0.40,
                'funding': 0.25,
                'sentiment': 0.05,
                'fundamental': 0.30, # ↑ 基本面
                'description': '极度恐惧: 基本面优先',
            },
        }
        
        # 波动率调整因子
        self.volatility_multiplier = {
            'low': 1.0,      # 低波动 (<=15): 无调整
            'normal': 1.0,   # 常规 (15-30): 无调整
            'high': 0.85,    # 高波动 (30-50): 技术权重-15%
            'extreme': 0.70, # 极高波动 (>50): 技术权重-30%
        }
    
    def get_emotion_state(self, sentiment_score: float) -> str:
        """
        根据情绪分数获取情绪状态
        """
        if sentiment_score > 92:
            return 'extreme_greed'
        elif sentiment_score >= 80:
            return 'greed'
        elif sentiment_score >= 40:
            return 'neutral'
        elif sentiment_score >= 20:
            return 'fear'
        else:
            return 'extreme_fear'
    
    def get_volatility_level(self, volatility: float) -> str:
        """
        根据波动率等级获取调整因子
        """
        if volatility <= 15:
            return 'low'
        elif volatility <= 30:
            return 'normal'
        elif volatility <= 50:
            return 'high'
        else:
            return 'extreme'
    
    def get_dynamic_weights(self, sentiment_score: float, 
                           volatility: float = 25.0) -> Dict[str, float]:
        """
        计算动态权重
        
        Args:
            sentiment_score: 情绪分数 (0-100)
            volatility: 市场波动率 (百分比) 默认25%
            
        Returns:
            动态权重字典
        """
        # 获取情绪状态
        emotion = self.get_emotion_state(sentiment_score)
        base_weights = self.emotion_weight_matrix[emotion].copy()
        base_weights.pop('description', None)  # 移除描述字段
        
        # 获取波动率调整因子
        vol_level = self.get_volatility_level(volatility)
        volatility_factor = self.volatility_multiplier[vol_level]
        
        # 应用波动率调整 (只调整技术面权重)
        if volatility_factor < 1.0:
            reduction = base_weights['technical'] * (1 - volatility_factor)
            base_weights['technical'] *= volatility_factor
            base_weights['funding'] += reduction * 0.7  # 转移70%给资金面
            base_weights['fundamental'] += reduction * 0.3  # 转移30%给基本面
        
        # 归一化 (确保和为1.0)
        total = sum(base_weights.values())
        normalized = {k: v / total for k, v in base_weights.items()}
        
        return normalized
    
    def optimize_signal_score(self, signals: Dict[str, float], 
                             sentiment_score: float,
                             volatility: float = 25.0) -> float:
        """
        应用动态权重计算优化后的信号评分
        
        Args:
            signals: 原始信号评分 {'technical': xx, 'funding': xx, ...}
            sentiment_score: 情绪分数
            volatility: 波动率
            
        Returns:
            加权后的总体评分 (0-100)
        """
        weights = self.get_dynamic_weights(sentiment_score, volatility)
        
        # 加权求和
        optimized_score = sum(
            signals.get(category, 0) * weight 
            for category, weight in weights.items()
        )
        
        return min(100, max(0, optimized_score))
    
    def get_signal_boost(self, sentiment_score: float) -> Dict[str, float]:
        """
        获取当前情绪下各信号的加权倍数 (用于显示和分析)
        
        返回: {'technical': 0.75, 'funding': 1.33, ...}
        """
        weights = self.get_dynamic_weights(sentiment_score)
        base = self.base_weights
        
        # 计算相对于基础权重的倍数
        boost = {
            category: weights[category] / base[category]
            for category in base.keys()
        }
        
        return boost


class SignalFusionReportGenerator:
    """
    信号融合分析报告生成器
    """
    
    def __init__(self, optimizer: SignalWeightOptimizer):
        self.optimizer = optimizer
    
    def generate_report(self, 
                       signals: Dict[str, float],
                       sentiment_score: float,
                       volatility: float = 25.0,
                       stock_name: str = "示例股票") -> Dict:
        """
        生成详细的信号融合分析报告
        """
        emotion = self.optimizer.get_emotion_state(sentiment_score)
        weights = self.optimizer.get_dynamic_weights(sentiment_score, volatility)
        optimized_score = self.optimizer.optimize_signal_score(
            signals, sentiment_score, volatility
        )
        boost = self.optimizer.get_signal_boost(sentiment_score)
        
        report = {
            'stock': stock_name,
            'timestamp': '2026-05-29',
            'market_state': {
                'sentiment_score': sentiment_score,
                'emotion': emotion,
                'volatility': volatility,
            },
            'original_signals': signals,
            'dynamic_weights': weights,
            'signal_boost': boost,
            'optimized_score': round(optimized_score, 2),
            'recommendation': self._get_recommendation(optimized_score),
            'breakdown': self._calculate_breakdown(signals, weights),
        }
        
        return report
    
    def _calculate_breakdown(self, signals: Dict[str, float], 
                            weights: Dict[str, float]) -> Dict[str, float]:
        """
        计算各类信号对最终评分的贡献
        """
        breakdown = {}
        for category in signals.keys():
            contribution = signals[category] * weights[category]
            breakdown[f'{category}_contribution'] = round(contribution, 2)
        
        return breakdown
    
    def _get_recommendation(self, score: float) -> str:
        """
        根据评分生成建议
        """
        if score >= 75:
            return '强烈买入 🟢'
        elif score >= 60:
            return '建议买入 🟢'
        elif score >= 45:
            return '关注 🟡'
        elif score >= 30:
            return '减持 🔴'
        else:
            return '卖出 🔴'


# ============================================================
# 测试用例
# ============================================================

if __name__ == '__main__':
    optimizer = SignalWeightOptimizer()
    report_gen = SignalFusionReportGenerator(optimizer)
    
    # 测试场景1: 极度贪婪 (情绪92)
    print("=" * 70)
    print("测试场景1: 极度贪婪行情 (情绪92)")
    print("=" * 70)
    
    signals_1 = {
        'technical': 65,
        'funding': 80,
        'sentiment': 75,
        'fundamental': 55,
    }
    
    report_1 = report_gen.generate_report(signals_1, 92)
    print(json.dumps(report_1, indent=2, ensure_ascii=False))
    
    print("\n" + "=" * 70)
    print("测试场景2: 中性行情 (情绪60)")
    print("=" * 70)
    
    signals_2 = {
        'technical': 70,
        'funding': 60,
        'sentiment': 50,
        'fundamental': 65,
    }
    
    report_2 = report_gen.generate_report(signals_2, 60)
    print(json.dumps(report_2, indent=2, ensure_ascii=False))
    
    print("\n" + "=" * 70)
    print("测试场景3: 恐惧行情 (情绪30, 高波动)")
    print("=" * 70)
    
    signals_3 = {
        'technical': 75,
        'funding': 45,
        'sentiment': 25,
        'fundamental': 80,
    }
    
    report_3 = report_gen.generate_report(signals_3, 30, volatility=45)
    print(json.dumps(report_3, indent=2, ensure_ascii=False))
    
    # 总结对比
    print("\n" + "=" * 70)
    print("权重对比总结")
    print("=" * 70)
    
    emotions = ['extreme_greed', 'greed', 'neutral', 'fear', 'extreme_fear']
    print(f"{'情绪状态':<15} {'技术':<10} {'资金':<10} {'情绪':<10} {'基本':<10}")
    print("-" * 50)
    
    for emotion in emotions:
        sentiment_map = {
            'extreme_greed': 95,
            'greed': 85,
            'neutral': 60,
            'fear': 30,
            'extreme_fear': 10,
        }
        weights = optimizer.get_dynamic_weights(sentiment_map[emotion])
        print(f"{emotion:<15} {weights['technical']:.2f}     {weights['funding']:.2f}     {weights['sentiment']:.2f}     {weights['fundamental']:.2f}")
    
    print("\n✅ 信号融合引擎测试完成")
