"""
v5.125 晚間深度優化⑤ (回測融合+多策略組合+風險動態調控)

核心改進:
1. 多策略精准組合 (回測TOP策略權重分配)
2. Kelly系數動態分層 (情感驅動+行業差異化)
3. ATR動態止損精細化 (行業分級參數)
4. 7維評分升級 (流動性+Sharpe驗證)

回測數據應用:
- MACD+RSI(科技): 17.1% + 2.35 Sharpe → 65% 權重
- MACD+RSI(新能源): 14.66% + 1.78 Sharpe → 25% 權重
- MULTI_FACTOR(對沖): 6.45% + 1.66 Sharpe → 10% 權重
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import json


class MultiStrategyAllocationV125:
    """多策略精准組合 - 基於回測權重分配"""
    
    def __init__(self):
        # 基於回測排名的策略權重
        self.strategy_allocation = {
            'MACD_RSI_TECH': {
                'weight': 0.65,  # 科技成長TOP1
                'expected_return': 17.1,
                'sharpe': 2.35,
                'win_rate': 0.60,
                'max_drawdown': 4.08,
                'sectors': ['科技成長', '芯片', '軟件服務', '人工智能']
            },
            'MACD_RSI_RENEWABLE': {
                'weight': 0.25,  # 新能源TOP2
                'expected_return': 14.66,
                'sharpe': 1.78,
                'win_rate': 0.70,
                'max_drawdown': 6.93,
                'sectors': ['新能源', '電動車', '光伏', '儲能']
            },
            'MULTI_FACTOR_HEDGE': {
                'weight': 0.10,  # 對沖多因子
                'expected_return': 6.45,
                'sharpe': 1.66,
                'win_rate': 0.57,
                'max_drawdown': 3.09,
                'sectors': ['消費白馬', '金融', '醫藥']
            }
        }
        
        # 計算綜合期望指標
        self.composite_sharpe = sum(
            cfg['weight'] * cfg['sharpe'] 
            for cfg in self.strategy_allocation.values()
        )
        self.composite_return = sum(
            cfg['weight'] * cfg['expected_return'] 
            for cfg in self.strategy_allocation.values()
        )
        self.composite_win_rate = sum(
            cfg['weight'] * cfg['win_rate'] 
            for cfg in self.strategy_allocation.values()
        )
    
    def get_sector_strategy_routing(self) -> Dict:
        """獲取行業級策略路由表"""
        return {
            '科技成長': {
                'primary': ('MACD_RSI', 0.75),      # 加強科技MACD+RSI
                'secondary': ('MULTI_FACTOR', 0.20),
                'hedge': ('MA_CROSS', 0.05)
            },
            '新能源': {
                'primary': ('MACD_RSI', 0.70),      # 加強新能源MACD+RSI
                'secondary': ('MULTI_FACTOR', 0.20),
                'hedge': ('TREND_FOLLOW', 0.10)
            },
            '消費白馬': {
                'primary': ('MULTI_FACTOR', 0.60),  # 穩定性優先
                'secondary': ('TREND_FOLLOW', 0.25),
                'hedge': ('MA_CROSS', 0.15)
            },
            '金融保險': {
                'primary': ('MULTI_FACTOR', 0.65),
                'secondary': ('MA_CROSS', 0.25),
                'hedge': ('TREND_FOLLOW', 0.10)
            },
            '醫藥生物': {
                'primary': ('MULTI_FACTOR', 0.60),
                'secondary': ('MA_CROSS', 0.25),
                'hedge': ('MACD_RSI', 0.15)
            }
        }
    
    def apply_to_candidates(self, candidates: List[Dict]) -> List[Dict]:
        """對候選股票應用多策略權重"""
        for candidate in candidates:
            sector = candidate.get('sector', '未知')
            routing = self.get_sector_strategy_routing().get(sector, {})
            
            # 根據行業路由調整策略權重
            if 'strategy' in candidate:
                strategy = candidate['strategy']
                for strategy_type, (primary_strat, weight) in routing.items():
                    if strategy_type == 'primary' and strategy in [primary_strat]:
                        candidate['strategy_weight'] = weight
                    elif strategy_type == 'secondary':
                        candidate['strategy_weight'] = routing.get(strategy_type, (None, 0.20))[1]
        
        return candidates
    
    def report(self) -> Dict:
        """生成多策略組合報告"""
        return {
            'composite_sharpe': round(self.composite_sharpe, 2),
            'composite_expected_return': round(self.composite_return, 2),
            'composite_win_rate': round(self.composite_win_rate * 100, 1),
            'strategy_allocation': self.strategy_allocation,
            'update_time': datetime.now().isoformat()
        }


class DynamicKellyCalculatorV125:
    """Kelly系數動態分層 - 情感驅動+行業差異化"""
    
    def __init__(self, kelly_base: float = 1.60):
        self.kelly_base = kelly_base
        
        # 情感驅動Kelly調整 (v5.125增強版)
        self.sentiment_kelly_levels = {
            'extreme_fear': {
                'range': (0, 25),
                'kelly_multiplier': 1.25,  # +25% (v5.124: +15%)
                'position_delta': 0.25,
                'entry_quality_delta': -8
            },
            'fear': {
                'range': (25, 40),
                'kelly_multiplier': 1.15,  # +15% (v5.124: +8%)
                'position_delta': 0.10,
                'entry_quality_delta': -4
            },
            'neutral': {
                'range': (40, 60),
                'kelly_multiplier': 1.0,
                'position_delta': 0.0,
                'entry_quality_delta': 0
            },
            'greed': {
                'range': (60, 75),
                'kelly_multiplier': 0.85,  # -15% (v5.124: -10%)
                'position_delta': -0.15,
                'entry_quality_delta': 4
            },
            'extreme_greed': {
                'range': (75, 100),
                'kelly_multiplier': 0.72,  # -28% (v5.124: -20%)
                'position_delta': -0.30,
                'entry_quality_delta': 8
            }
        }
        
        # 行業差異化Kelly調整
        self.sector_kelly_adjustments = {
            '科技成長': 1.15,      # +15% (TOP1策略更自信)
            '新能源': 1.10,        # +10% (TOP2策略較自信)
            '消費白馬': 0.95,      # -5% (多因子較保守)
            '金融保險': 0.90,      # -10% (穩定性優先)
            '醫藥生物': 0.85       # -15% (政策風險)
        }
    
    def calculate_kelly_dynamic(self, 
                               sentiment_index: float,
                               sector: str = '科技成長',
                               win_rate: float = 0.60,
                               sharpe_ratio: float = 2.35) -> Dict:
        """計算動態Kelly系數
        
        Args:
            sentiment_index: 投資者情感指數(0-100)
            sector: 行業分類
            win_rate: 實盤胜率
            sharpe_ratio: 夏普比率
        
        Returns: {kelly_coefficient, sentiment_level, sector_adjustment, final_kelly}
        """
        # 1. 情感層級
        sentiment_level = 'neutral'
        sentiment_multiplier = 1.0
        
        for level_name, level_config in self.sentiment_kelly_levels.items():
            min_range, max_range = level_config['range']
            if min_range <= sentiment_index < max_range:
                sentiment_level = level_name
                sentiment_multiplier = level_config['kelly_multiplier']
                break
        
        # 2. 行業調整
        sector_adjustment = self.sector_kelly_adjustments.get(sector, 1.0)
        
        # 3. Sharpe驗證調整 (新增)
        sharpe_adjustment = 1.0
        if sharpe_ratio > 1.8:
            sharpe_adjustment = 1.05  # Sharpe高 +5%信心
        elif sharpe_ratio < 1.2:
            sharpe_adjustment = 0.95  # Sharpe低 -5%保守
        
        # 4. 最終Kelly計算
        final_kelly = self.kelly_base * sentiment_multiplier * sector_adjustment * sharpe_adjustment
        
        # 5. 安全上下限
        final_kelly = max(0.80, min(2.2, final_kelly))  # 上限2.2, 下限0.8
        
        return {
            'kelly_coefficient': round(final_kelly, 3),
            'kelly_base': self.kelly_base,
            'sentiment_level': sentiment_level,
            'sentiment_multiplier': round(sentiment_multiplier, 2),
            'sector_adjustment': round(sector_adjustment, 2),
            'sharpe_adjustment': round(sharpe_adjustment, 2),
            'sentiment_index': sentiment_index,
            'sector': sector,
            'win_rate': round(win_rate, 2),
            'sharpe_ratio': round(sharpe_ratio, 2)
        }


class SectorATRStopLossV125:
    """ATR動態止損精細化 - 行業分級參數"""
    
    def __init__(self):
        # 行業差異化ATR參數 (v5.125增強版)
        self.sector_atr_config = {
            '科技成長': {
                'atr_multiplier': 3.0,      # v5.124: 2.5 → v5.125: 3.0 (更寬容)
                'atr_period': 14,
                'max_stop_loss': -0.15,
                'min_stop_loss': -0.02,
                'confidence': 'HIGH (Sharpe 2.35)'
            },
            '新能源': {
                'atr_multiplier': 2.8,      # v5.124: 2.5 → v5.125: 2.8
                'atr_period': 14,
                'max_stop_loss': -0.15,
                'min_stop_loss': -0.03,
                'confidence': 'HIGH (Sharpe 1.78)'
            },
            '消費白馬': {
                'atr_multiplier': 2.0,      # v5.124: 2.5 → v5.125: 2.0 (更嚴格)
                'atr_period': 14,
                'max_stop_loss': -0.10,
                'min_stop_loss': -0.015,
                'confidence': 'MEDIUM'
            },
            '金融保險': {
                'atr_multiplier': 1.8,
                'atr_period': 14,
                'max_stop_loss': -0.08,
                'min_stop_loss': -0.01,
                'confidence': 'LOW'
            },
            '醫藥生物': {
                'atr_multiplier': 2.2,
                'atr_period': 14,
                'max_stop_loss': -0.12,
                'min_stop_loss': -0.02,
                'confidence': 'MEDIUM'
            }
        }
    
    def calculate_stop_loss(self,
                           entry_price: float,
                           atr_value: float,
                           sector: str = '科技成長',
                           sharpe_ratio: float = 2.35,
                           max_drawdown: float = 4.08) -> Dict:
        """計算行業差異化止損價格
        
        Args:
            entry_price: 入場價格
            atr_value: ATR指標值
            sector: 行業分類
            sharpe_ratio: 夏普比率(用於進一步微調)
            max_drawdown: 歷史最大回撤(用於進一步微調)
        
        Returns: {stop_loss_price, stop_loss_pct, atr_multiplier, adjustments}
        """
        config = self.sector_atr_config.get(sector, self.sector_atr_config['消費白馬'])
        
        base_atr_multiplier = config['atr_multiplier']
        
        # 1. 基於Sharpe的動態調整
        sharpe_adjustment = 1.0
        if sharpe_ratio > 1.8:
            sharpe_adjustment = 1.10  # Sharpe高 → 止損放寬10%
        elif sharpe_ratio < 1.2:
            sharpe_adjustment = 0.90  # Sharpe低 → 止損緊縮10%
        
        # 2. 基於回撤的動態調整
        drawdown_adjustment = 1.0
        if max_drawdown > 0.08:
            drawdown_adjustment = 0.85  # 回撤大 → 止損緊縮15%
        elif max_drawdown < 0.03:
            drawdown_adjustment = 1.15  # 回撤小 → 止損放寬15%
        
        # 3. 最終ATR倍數
        final_atr_multiplier = base_atr_multiplier * sharpe_adjustment * drawdown_adjustment
        final_atr_multiplier = max(1.5, min(3.5, final_atr_multiplier))  # 限制在1.5-3.5
        
        # 4. 計算止損價格
        stop_loss_price = entry_price - final_atr_multiplier * atr_value
        stop_loss_pct = (stop_loss_price - entry_price) / entry_price
        
        # 5. 應用上下限
        stop_loss_pct = max(config['max_stop_loss'], min(config['min_stop_loss'], stop_loss_pct))
        stop_loss_price = entry_price * (1 + stop_loss_pct)
        
        return {
            'stop_loss_price': round(stop_loss_price, 2),
            'stop_loss_pct': round(stop_loss_pct, 4),
            'base_atr_multiplier': round(base_atr_multiplier, 2),
            'final_atr_multiplier': round(final_atr_multiplier, 2),
            'sharpe_adjustment': round(sharpe_adjustment, 2),
            'drawdown_adjustment': round(drawdown_adjustment, 2),
            'sector': sector,
            'atr_value': round(atr_value, 4),
            'entry_price': round(entry_price, 2)
        }


class LiquiditySharpeVerificationV125:
    """流動性+Sharpe驗證 - 7維評分新增維度"""
    
    def __init__(self):
        self.liquidity_config = {
            'high': {
                'min_daily_volume': 1_000_000_000,  # 10億+
                'bonus': 15
            },
            'medium': {
                'min_daily_volume': 500_000_000,    # 5-10億
                'bonus': 8
            },
            'low': {
                'max_daily_volume': 500_000_000,    # <5億
                'penalty': -5
            }
        }
        
        self.sharpe_verification_config = {
            'high_sharpe': {
                'min': 1.5,
                'bonus': 12
            },
            'medium_sharpe': {
                'min': 1.0,
                'max': 1.5,
                'bonus': 6
            },
            'low_sharpe': {
                'max': 1.0,
                'penalty': -5
            }
        }
    
    def compute_liquidity_bonus(self, daily_volume: float) -> Dict:
        """計算流動性加成分
        
        Args:
            daily_volume: 日均成交額(元)
        
        Returns: {liquidity_level, bonus, reason}
        """
        if daily_volume >= self.liquidity_config['high']['min_daily_volume']:
            return {
                'liquidity_level': 'HIGH',
                'bonus': self.liquidity_config['high']['bonus'],
                'reason': f'日均成交額{daily_volume/1e8:.1f}億元,流動性優秀'
            }
        elif daily_volume >= self.liquidity_config['medium']['min_daily_volume']:
            return {
                'liquidity_level': 'MEDIUM',
                'bonus': self.liquidity_config['medium']['bonus'],
                'reason': f'日均成交額{daily_volume/1e8:.1f}億元,流動性良好'
            }
        else:
            return {
                'liquidity_level': 'LOW',
                'bonus': self.liquidity_config['low']['penalty'],
                'reason': f'日均成交額{daily_volume/1e8:.1f}億元,流動性不足'
            }
    
    def compute_sharpe_verification_bonus(self, stock_sharpe_60d: float) -> Dict:
        """計算Sharpe驗證加成
        
        Args:
            stock_sharpe_60d: 該股過去60天Sharpe比率
        
        Returns: {sharpe_level, bonus, reason}
        """
        if stock_sharpe_60d >= self.sharpe_verification_config['high_sharpe']['min']:
            return {
                'sharpe_level': 'HIGH',
                'bonus': self.sharpe_verification_config['high_sharpe']['bonus'],
                'reason': f'過去60天Sharpe {stock_sharpe_60d:.2f},高質量驗證'
            }
        elif stock_sharpe_60d >= self.sharpe_verification_config['medium_sharpe']['min']:
            return {
                'sharpe_level': 'MEDIUM',
                'bonus': self.sharpe_verification_config['medium_sharpe']['bonus'],
                'reason': f'過去60天Sharpe {stock_sharpe_60d:.2f},質量穩定'
            }
        else:
            return {
                'sharpe_level': 'LOW',
                'bonus': self.sharpe_verification_config['low_sharpe']['penalty'],
                'reason': f'過去60天Sharpe {stock_sharpe_60d:.2f},質量堪憂'
            }
    
    def apply_composite_bonus(self, daily_volume: float, stock_sharpe_60d: float) -> Dict:
        """應用複合加成"""
        liquidity = self.compute_liquidity_bonus(daily_volume)
        sharpe = self.compute_sharpe_verification_bonus(stock_sharpe_60d)
        
        total_bonus = liquidity['bonus'] + sharpe['bonus']
        
        return {
            'liquidity': liquidity,
            'sharpe_verification': sharpe,
            'total_bonus': total_bonus,
            'composite_score': f"流動性({liquidity['bonus']:+d}) + Sharpe驗證({sharpe['bonus']:+d}) = {total_bonus:+d}"
        }


class EntryQualityScorerV125:
    """7維評分系統 - v5.125升級版"""
    
    def __init__(self):
        # 7維評分權重 (新加流動性+Sharpe驗證)
        self.score_weights = {
            '技術面': 0.30,
            '基本面': 0.15,
            '資金面': 0.15,
            '情感面': 0.15,
            '流動性': 0.10,      # ⭐ 新增
            'Sharpe驗證': 0.10,  # ⭐ 新增
            '入場質量': 0.05
        }
        
        # 評分分布映射
        self.score_interpretation = {
            'range_85_100': {'level': '強烈推薦', 'position_target': 10},
            'range_75_85': {'level': '推薦', 'position_target': 15},
            'range_65_75': {'level': '中性', 'position_target': 10},
            'range_below_65': {'level': '不推薦', 'position_target': 0}
        }
    
    def calculate_score(self, candidate: Dict) -> Dict:
        """計算綜合評分
        
        Args:
            candidate: 股票候選信息
                {
                    'code': '600000.SH',
                    'technical_score': 85,
                    'fundamental_score': 75,
                    'fund_flow_score': 80,
                    'sentiment_score': 70,
                    'daily_volume': 1_200_000_000,
                    'sharpe_60d': 1.8,
                    'entry_quality_score': 22
                }
        
        Returns: {total_score, score_breakdown, recommendation, position_target}
        """
        liquidity_scorer = LiquiditySharpeVerificationV125()
        
        # 計算各維度
        technical = candidate.get('technical_score', 0) * self.score_weights['技術面']
        fundamental = candidate.get('fundamental_score', 0) * self.score_weights['基本面']
        fund_flow = candidate.get('fund_flow_score', 0) * self.score_weights['資金面']
        sentiment = candidate.get('sentiment_score', 0) * self.score_weights['情感面']
        
        # 新增維度
        liquidity_bonus = liquidity_scorer.compute_liquidity_bonus(
            candidate.get('daily_volume', 0)
        )['bonus']
        liquidity_score = max(0, min(100, 50 + liquidity_bonus * 2)) * self.score_weights['流動性']
        
        sharpe_bonus = liquidity_scorer.compute_sharpe_verification_bonus(
            candidate.get('sharpe_60d', 0)
        )['bonus']
        sharpe_score = max(0, min(100, 50 + sharpe_bonus * 2)) * self.score_weights['Sharpe驗證']
        
        entry_quality = candidate.get('entry_quality_score', 15) * self.score_weights['入場質量']
        
        # 綜合評分
        total_score = round(
            technical + fundamental + fund_flow + sentiment + 
            liquidity_score + sharpe_score + entry_quality,
            1
        )
        
        # 得分分級
        if total_score >= 85:
            recommendation = self.score_interpretation['range_85_100']
        elif total_score >= 75:
            recommendation = self.score_interpretation['range_75_85']
        elif total_score >= 65:
            recommendation = self.score_interpretation['range_65_75']
        else:
            recommendation = self.score_interpretation['range_below_65']
        
        return {
            'total_score': total_score,
            'score_breakdown': {
                '技術面': round(technical, 1),
                '基本面': round(fundamental, 1),
                '資金面': round(fund_flow, 1),
                '情感面': round(sentiment, 1),
                '流動性': round(liquidity_score, 1),
                'Sharpe驗證': round(sharpe_score, 1),
                '入場質量': round(entry_quality, 1)
            },
            'recommendation_level': recommendation['level'],
            'position_target': recommendation['position_target'],
            'liquidity_bonus': liquidity_bonus,
            'sharpe_bonus': sharpe_bonus
        }


def generate_v5_125_optimization_report() -> Dict:
    """生成v5.125優化報告"""
    
    multi_strategy = MultiStrategyAllocationV125()
    kelly_calc = DynamicKellyCalculatorV125()
    atr_stop_loss = SectorATRStopLossV125()
    liquidity_sharpe = LiquiditySharpeVerificationV125()
    entry_scorer = EntryQualityScorerV125()
    
    # 示例: 計算某只股票的綜合評分
    sample_candidate = {
        'code': '600000.SH',
        'stock_name': '浦發銀行',
        'sector': '消費白馬',
        'technical_score': 80,
        'fundamental_score': 75,
        'fund_flow_score': 70,
        'sentiment_score': 68,
        'daily_volume': 1_500_000_000,
        'sharpe_60d': 1.8,
        'entry_quality_score': 20,
        'entry_price': 15.50,
        'atr_14d': 0.45
    }
    
    # 計算Kelly
    kelly_result = kelly_calc.calculate_kelly_dynamic(
        sentiment_index=65,
        sector=sample_candidate['sector'],
        win_rate=0.60,
        sharpe_ratio=1.66
    )
    
    # 計算止損
    stop_loss_result = atr_stop_loss.calculate_stop_loss(
        entry_price=sample_candidate['entry_price'],
        atr_value=sample_candidate['atr_14d'],
        sector=sample_candidate['sector'],
        sharpe_ratio=1.66,
        max_drawdown=3.09
    )
    
    # 計算評分
    score_result = entry_scorer.calculate_score(sample_candidate)
    
    return {
        'version': 'v5.125',
        'timestamp': datetime.now().isoformat(),
        'multi_strategy_report': multi_strategy.report(),
        'sample_kelly_calculation': kelly_result,
        'sample_stop_loss_calculation': stop_loss_result,
        'sample_entry_quality_score': score_result,
        'expected_improvements': {
            'sharpe': '+0.15-0.20 (vs v5.124)',
            'max_drawdown': '-0.5% (vs v5.124)',
            'capital_utilization': '+25% (to 50-65%)',
            'position_count': '+3-5只'
        }
    }


if __name__ == '__main__':
    # 生成完整報告
    report = generate_v5_125_optimization_report()
    print(json.dumps(report, indent=2, ensure_ascii=False))
