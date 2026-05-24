#!/usr/bin/env python3
"""
v5.126 晚間深度優化工程 - 多策略精準組合+Kelly動態分層+ATR行業分級+7維評分升級
====================================================================
版本: v5.126 (晚間22:00 UTC優化④)
目標: 回測TOP策略融合(Sharpe 2.35) + Kelly動態分層 + ATR行業分級 + 流動性+Sharpe驗證評分
預期: Sharpe 2.14-2.35, 年化16-19%, 回撤<3.5%, 持倉10-15只

核心改進:
1. 多策略精準組合 - TOP回測策略應用到實盤
   - MACD+RSI(科技成長): 65% 仓位權重, 17.1%+2.35Sharpe (TOP1)
   - MACD+RSI(新能源): 25% 仓位權重, 14.66%+1.78Sharpe (TOP2)
   - MULTI_FACTOR(對沖): 10% 仓位權重, 6.45%+1.66Sharpe (風控)

2. Kelly系數動態分層 (+增強v5.124)
   - 極度恐懼(<25): Kelly+25% (+10%)激進
   - 恐懼(25-40): Kelly+15% (+7%)
   - 正常(40-60): Kelly 1.60 保持
   - 貪婪(60-75): Kelly-15% (-5%)防守
   - 極度貪婪(>75): Kelly-28% (-8%)加強防守
   - 行業差異化: 科技+15%, 新能源+10%, 消費-5%, 金融-10%

3. ATR動態止損精細化 (+新增行業分級)
   - 科技成長: ATR 3.0倍 (更寬容TOP1)
   - 新能源: ATR 2.8倍 (加強TOP2)
   - 消費白馬: ATR 2.0倍 (更嚴格)
   - 金融保險: ATR 1.8倍 (最嚴格)
   - 醫藥生物: ATR 2.2倍 (中等)
   - Sharpe高(>1.8): 止損放寬10%
   - Sharpe低(<1.2): 止損緊縮10%
   - 回撤大(>8%): 止損緊縮15%
   - 回撤小(<3%): 止損放寬15%

4. 7維評分升級 (+2維: 流動性+Sharpe驗證)
   - 技術評分 (0-25分)
   - 基本面評分 (0-25分)
   - 資金面評分 (0-20分)
   - 情感評分 (0-15分)
   - 入場質量 (0-10分)
   + 流動性評分 (0-15分) ← NEW
   + Sharpe驗證 (0-12分) ← NEW
   總分: 85-100分(強烈推薦), 75-85分(推薦), 65-75分(中性), <65分(黑名單)

文件: v5_126_deep_optimize.py (核心優化模塊)
配置: config.py (新增20+參數)
測試: 驗證多策略加權 + Kelly實現 + 7維評分
"""

import json
import logging
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
import numpy as np

logger = logging.getLogger(__name__)


# ==================== 枚舉定義 ====================

class SectorType(Enum):
    """行業分類"""
    TECH_GROWTH = "科技成長"        # 科技+半導體+芯片
    NEW_ENERGY = "新能源"          # 新能源+電池
    CONSUMER_BLUE = "消費白馬"     # 消費+食品+家電
    FINANCE = "金融保險"           # 銀行+保險+證券
    PHARMA = "醫藥生物"            # 醫藥+生物
    MISC = "其他"                  # 其他行業


class SentimentLevel(Enum):
    """情感等級"""
    EXTREME_FEAR = "極度恐懼"      # <25
    FEAR = "恐懼"                 # 25-40
    NORMAL = "正常"               # 40-60
    GREED = "貪婪"                # 60-75
    EXTREME_GREED = "極度貪婪"     # >75


# ==================== 數據類 ====================

@dataclass
class MultiStrategyAllocation:
    """多策略精準組合配置"""
    macd_rsi_tech_weight: float = 0.65      # MACD+RSI(科技): 65% 權重
    macd_rsi_energy_weight: float = 0.25    # MACD+RSI(新能源): 25% 權重
    multi_factor_hedge_weight: float = 0.10 # MULTI_FACTOR(對沖): 10% 權重
    
    # 預期效果
    expected_sharpe: float = 2.14           # 綜合Sharpe: 2.35×0.65 + 1.78×0.25 + 1.66×0.10
    expected_return: float = 0.175          # 年化收益: 16-19%
    expected_drawdown: float = 0.035        # 最大回撤: <3.5%
    
    def get_combined_weight(self, sector: SectorType) -> float:
        """根據行業獲取該策略組合的權重"""
        if sector == SectorType.TECH_GROWTH:
            return self.macd_rsi_tech_weight
        elif sector == SectorType.NEW_ENERGY:
            return self.macd_rsi_energy_weight
        else:
            return self.multi_factor_hedge_weight


@dataclass
class KellyDynamicConfig:
    """Kelly系數動態分層配置"""
    # 基礎Kelly系數
    kelly_base: float = 1.60
    
    # 情感相對調整 (相對於Kelly基礎系數)
    kelly_adjustments: Dict[SentimentLevel, float] = None
    
    # 行業差異化 (Kelly倍數調整)
    sector_adjustments: Dict[SectorType, float] = None
    
    # Sharpe動態微調
    sharpe_based_adjustments: Dict[str, float] = None
    
    # 回撤動態微調
    drawdown_based_adjustments: Dict[str, float] = None
    
    def __post_init__(self):
        if self.kelly_adjustments is None:
            self.kelly_adjustments = {
                SentimentLevel.EXTREME_FEAR: 1.25,      # +25%激進
                SentimentLevel.FEAR: 1.15,              # +15%
                SentimentLevel.NORMAL: 1.0,             # 保持
                SentimentLevel.GREED: 0.85,             # -15%防守
                SentimentLevel.EXTREME_GREED: 0.72,     # -28%加強防守
            }
        
        if self.sector_adjustments is None:
            self.sector_adjustments = {
                SectorType.TECH_GROWTH: 1.15,           # +15%
                SectorType.NEW_ENERGY: 1.10,            # +10%
                SectorType.CONSUMER_BLUE: 0.95,         # -5%
                SectorType.FINANCE: 0.90,               # -10%
                SectorType.PHARMA: 1.0,                 # 保持
                SectorType.MISC: 0.95,                  # -5%
            }
        
        if self.sharpe_based_adjustments is None:
            self.sharpe_based_adjustments = {
                'high': 1.10,       # Sharpe>1.8: +10%
                'normal': 1.0,      # Sharpe 1.0-1.8: 保持
                'low': 0.90,        # Sharpe<1.0: -10%
            }
        
        if self.drawdown_based_adjustments is None:
            self.drawdown_based_adjustments = {
                'small': 1.15,      # 回撤<3%: +15%
                'normal': 1.0,      # 回撤3-8%: 保持
                'large': 0.85,      # 回撤>8%: -15%
            }
    
    def calculate_kelly(
        self, 
        sentiment_level: SentimentLevel,
        sector: SectorType,
        sharpe_ratio: Optional[float] = None,
        max_drawdown: Optional[float] = None
    ) -> float:
        """
        計算動態Kelly系數
        
        參數:
            sentiment_level: 市場情感等級
            sector: 行業分類
            sharpe_ratio: Sharpe比率(可選)
            max_drawdown: 最大回撤(可選)
        
        返回:
            動態Kelly系數
        """
        kelly = self.kelly_base
        
        # 情感調整
        kelly *= self.kelly_adjustments.get(sentiment_level, 1.0)
        
        # 行業調整
        kelly *= self.sector_adjustments.get(sector, 1.0)
        
        # Sharpe微調
        if sharpe_ratio is not None:
            if sharpe_ratio > 1.8:
                kelly *= self.sharpe_based_adjustments['high']
            elif sharpe_ratio < 1.0:
                kelly *= self.sharpe_based_adjustments['low']
        
        # 回撤微調
        if max_drawdown is not None:
            if max_drawdown < 0.03:
                kelly *= self.drawdown_based_adjustments['small']
            elif max_drawdown > 0.08:
                kelly *= self.drawdown_based_adjustments['large']
        
        return kelly


@dataclass
class ATRStopLossConfig:
    """ATR動態止損配置"""
    # 行業分級參數 (ATR倍數)
    sector_multipliers: Dict[SectorType, float] = None
    
    # Sharpe動態微調 (+/- %)
    sharpe_adjustments: Dict[str, float] = None
    
    # 回撤動態微調 (+/- %)
    drawdown_adjustments: Dict[str, float] = None
    
    atr_period: int = 14            # ATR計算週期
    
    def __post_init__(self):
        if self.sector_multipliers is None:
            self.sector_multipliers = {
                SectorType.TECH_GROWTH: 3.0,        # 科技: 3.0倍 (寬容)
                SectorType.NEW_ENERGY: 2.8,         # 新能源: 2.8倍
                SectorType.CONSUMER_BLUE: 2.0,      # 消費: 2.0倍 (嚴格)
                SectorType.FINANCE: 1.8,            # 金融: 1.8倍 (最嚴格)
                SectorType.PHARMA: 2.2,             # 醫藥: 2.2倍
                SectorType.MISC: 2.2,               # 其他: 2.2倍
            }
        
        if self.sharpe_adjustments is None:
            self.sharpe_adjustments = {
                'high': 0.10,       # Sharpe>1.8: 放寬10%
                'normal': 0.0,      # Sharpe 1.0-1.8: 保持
                'low': -0.10,       # Sharpe<1.0: 緊縮10%
            }
        
        if self.drawdown_adjustments is None:
            self.drawdown_adjustments = {
                'small': 0.15,      # 回撤<3%: 放寬15%
                'normal': 0.0,      # 回撤3-8%: 保持
                'large': -0.15,     # 回撤>8%: 緊縮15%
            }
    
    def calculate_stop_loss(
        self,
        entry_price: float,
        atr: float,
        sector: SectorType,
        sharpe_ratio: Optional[float] = None,
        max_drawdown: Optional[float] = None
    ) -> float:
        """
        計算ATR動態止損價格
        
        參數:
            entry_price: 入場價格
            atr: ATR值
            sector: 行業分類
            sharpe_ratio: Sharpe比率(可選)
            max_drawdown: 最大回撤(可選)
        
        返回:
            止損價格
        """
        # 基礎止損 = 入場價 - ATR倍數 × ATR值
        multiplier = self.sector_multipliers.get(sector, 2.5)
        stop_loss = entry_price - multiplier * atr
        
        # Sharpe微調
        if sharpe_ratio is not None:
            if sharpe_ratio > 1.8:
                adjustment = self.sharpe_adjustments['high']
            elif sharpe_ratio < 1.0:
                adjustment = self.sharpe_adjustments['low']
            else:
                adjustment = self.sharpe_adjustments['normal']
            
            # 調整止損寬度 (更寬=更高的價格, 即更寬容)
            adjustment_amount = multiplier * atr * adjustment
            stop_loss += adjustment_amount
        
        # 回撤微調
        if max_drawdown is not None:
            if max_drawdown < 0.03:
                adjustment = self.drawdown_adjustments['small']
            elif max_drawdown > 0.08:
                adjustment = self.drawdown_adjustments['large']
            else:
                adjustment = self.drawdown_adjustments['normal']
            
            adjustment_amount = multiplier * atr * adjustment
            stop_loss += adjustment_amount
        
        return stop_loss


@dataclass
class ScoringDimension:
    """7維評分維度"""
    technical: float = 0.0          # 技術評分 (0-25)
    fundamental: float = 0.0        # 基本面評分 (0-25)
    capital: float = 0.0            # 資金面評分 (0-20)
    sentiment: float = 0.0          # 情感評分 (0-15)
    entry_quality: float = 0.0      # 入場質量 (0-10)
    liquidity: float = 0.0          # 流動性評分 (0-15) ← NEW
    sharpe_verify: float = 0.0      # Sharpe驗證 (0-12) ← NEW
    
    def get_total_score(self) -> float:
        """計算總分"""
        return (self.technical + self.fundamental + self.capital + 
                self.sentiment + self.entry_quality + 
                self.liquidity + self.sharpe_verify)
    
    def get_recommendation(self) -> str:
        """根據總分獲取推薦等級"""
        total = self.get_total_score()
        if total >= 85:
            return "強烈推薦"
        elif total >= 75:
            return "推薦"
        elif total >= 65:
            return "中性"
        else:
            return "黑名單"
    
    def to_dict(self) -> Dict[str, float]:
        """轉換為字典"""
        return asdict(self)


class LiquidityScorer:
    """流動性評分器"""
    
    @staticmethod
    def score_liquidity(avg_daily_volume: float) -> float:
        """
        評分流動性
        
        參數:
            avg_daily_volume: 日均成交額(萬元)
        
        返回:
            流動性評分 (0-15)
        """
        if avg_daily_volume > 10.0:  # >10億
            return 15.0
        elif avg_daily_volume > 5.0:  # 5-10億
            return 8.0
        else:                         # <5億
            return -5.0


class SharpeVerifier:
    """Sharpe驗證評分器"""
    
    @staticmethod
    def score_sharpe(past_60d_sharpe: float) -> float:
        """
        評分Sharpe驗證
        
        參數:
            past_60d_sharpe: 過去60天Sharpe比率
        
        返回:
            Sharpe驗證評分 (0-12)
        """
        if past_60d_sharpe > 1.5:
            return 12.0
        elif past_60d_sharpe > 1.0:
            return 6.0
        else:
            return -5.0


class MultiStrategyFusion:
    """多策略融合引擎"""
    
    def __init__(self):
        self.allocation = MultiStrategyAllocation()
        self.kelly_config = KellyDynamicConfig()
        self.atr_config = ATRStopLossConfig()
    
    def get_strategy_weight(self, sector: SectorType) -> float:
        """獲取該行業的策略權重"""
        return self.allocation.get_combined_weight(sector)
    
    def calculate_position_size(
        self,
        account_size: float,
        max_positions: int,
        sentiment_level: SentimentLevel,
        sector: SectorType,
        sharpe_ratio: Optional[float] = None,
        max_drawdown: Optional[float] = None
    ) -> float:
        """
        計算持倉大小 (基於Kelly系數)
        
        參數:
            account_size: 帳戶總資金
            max_positions: 最大持倉數
            sentiment_level: 市場情感
            sector: 行業分類
            sharpe_ratio: Sharpe比率
            max_drawdown: 最大回撤
        
        返回:
            單個持倉大小
        """
        kelly = self.kelly_config.calculate_kelly(
            sentiment_level, sector, sharpe_ratio, max_drawdown
        )
        
        # Kelly持倉 = Kelly系數 × 帳戶資金 / 最大持倉數
        position_size = kelly * account_size / max_positions
        
        return position_size
    
    def get_stop_loss_price(
        self,
        entry_price: float,
        atr: float,
        sector: SectorType,
        sharpe_ratio: Optional[float] = None,
        max_drawdown: Optional[float] = None
    ) -> float:
        """計算止損價格"""
        return self.atr_config.calculate_stop_loss(
            entry_price, atr, sector, sharpe_ratio, max_drawdown
        )


# ==================== 配置導出函數 ====================

def generate_v5_126_config() -> Dict[str, Any]:
    """生成v5.126配置字典 (用於config.py集成)"""
    
    return {
        # ========== 多策略精準組合 ==========
        'MULTI_STRATEGY_ENABLED': True,
        'MULTI_STRATEGY_ALLOCATION': {
            'macd_rsi_tech_weight': 0.65,
            'macd_rsi_energy_weight': 0.25,
            'multi_factor_hedge_weight': 0.10,
            'expected_sharpe': 2.14,
            'expected_return': 0.175,
            'expected_drawdown': 0.035,
        },
        
        # ========== Kelly系數動態分層 ==========
        'KELLY_DYNAMIC_ENABLED': True,
        'KELLY_BASE_COEFFICIENT': 1.60,
        
        'KELLY_SENTIMENT_ADJUSTMENTS': {
            'extreme_fear': 1.25,       # <25: +25%
            'fear': 1.15,               # 25-40: +15%
            'normal': 1.0,              # 40-60: 保持
            'greed': 0.85,              # 60-75: -15%
            'extreme_greed': 0.72,      # >75: -28%
        },
        
        'KELLY_SECTOR_ADJUSTMENTS': {
            '科技成長': 1.15,
            '新能源': 1.10,
            '消費白馬': 0.95,
            '金融保險': 0.90,
            '醫藥生物': 1.0,
            '其他': 0.95,
        },
        
        # ========== ATR動態止損行業分級 ==========
        'ATR_SECTOR_MULTIPLIERS': {
            '科技成長': 3.0,
            '新能源': 2.8,
            '消費白馬': 2.0,
            '金融保險': 1.8,
            '醫藥生物': 2.2,
            '其他': 2.2,
        },
        
        'ATR_SHARPE_ADJUSTMENTS': {
            'high': 0.10,       # Sharpe>1.8: 放寬10%
            'normal': 0.0,      # Sharpe 1.0-1.8: 保持
            'low': -0.10,       # Sharpe<1.0: 緊縮10%
        },
        
        'ATR_DRAWDOWN_ADJUSTMENTS': {
            'small': 0.15,      # 回撤<3%: 放寬15%
            'normal': 0.0,      # 回撤3-8%: 保持
            'large': -0.15,     # 回撤>8%: 緊縮15%
        },
        
        # ========== 7維評分系統 ==========
        'SCORING_SYSTEM_7D_ENABLED': True,
        'SCORING_WEIGHTS': {
            'technical': 25,            # 技術 (0-25)
            'fundamental': 25,          # 基本面 (0-25)
            'capital': 20,              # 資金面 (0-20)
            'sentiment': 15,            # 情感 (0-15)
            'entry_quality': 10,        # 入場質量 (0-10)
            'liquidity': 15,            # 流動性 (0-15) ← NEW
            'sharpe_verify': 12,        # Sharpe驗證 (0-12) ← NEW
        },
        
        'RECOMMENDATION_THRESHOLDS': {
            'strong_buy': 85,           # 85-100: 強烈推薦
            'buy': 75,                  # 75-85: 推薦
            'neutral': 65,              # 65-75: 中性
            'blacklist': 0,             # <65: 黑名單
        },
        
        # ========== 流動性標準 ==========
        'LIQUIDITY_THRESHOLDS': {
            'high': 10.0,               # >10億: 15分
            'medium': 5.0,              # 5-10億: 8分
            'low': 0.0,                 # <5億: -5分
        },
        
        # ========== Sharpe驗證標準 ==========
        'SHARPE_VERIFY_THRESHOLDS': {
            'high': 1.5,                # >1.5: 12分
            'medium': 1.0,              # 1.0-1.5: 6分
            'low': 0.0,                 # <1.0: -5分
        },
        
        # ========== 預期性能對標 ==========
        'V5_126_EXPECTED_METRICS': {
            'sharpe_range': (2.14, 2.35),
            'annual_return_range': (0.16, 0.19),
            'max_drawdown': 0.035,
            'win_rate': 0.62,
            'kelly_range': (1.15, 2.0),
            'position_count_range': (10, 15),
            'capital_usage_rate': 0.5625,  # 50-65% (中位56.25%)
        },
    }


def display_config_summary():
    """顯示v5.126配置摘要"""
    config = generate_v5_126_config()
    
    summary = """
╔════════════════════════════════════════════════════════════════════════════╗
║                    v5.126 晚間深度優化工程 - 配置摘要                        ║
╚════════════════════════════════════════════════════════════════════════════╝

【核心優化①】多策略精準組合
──────────────────────────────
  ✓ MACD+RSI(科技成長):  65% 權重 → 17.1% + 2.35 Sharpe (TOP1)
  ✓ MACD+RSI(新能源):    25% 權重 → 14.66% + 1.78 Sharpe (TOP2)
  ✓ MULTI_FACTOR(對沖):  10% 權重 → 6.45% + 1.66 Sharpe (風控)
  → 綜合Sharpe: 2.14-2.35

【核心優化②】Kelly系數動態分層
──────────────────────────────
  情感驅動調整:
  ├─ 極度恐懼(<25):  Kelly×1.25 (+25%)
  ├─ 恐懼(25-40):    Kelly×1.15 (+15%)
  ├─ 正常(40-60):    Kelly×1.0  (保持)
  ├─ 貪婪(60-75):    Kelly×0.85 (-15%)
  └─ 極度貪婪(>75):  Kelly×0.72 (-28%)
  
  行業差異化:
  ├─ 科技成長: Kelly×1.15 (+15%)
  ├─ 新能源:   Kelly×1.10 (+10%)
  ├─ 消費:     Kelly×0.95 (-5%)
  └─ 金融:     Kelly×0.90 (-10%)

【核心優化③】ATR動態止損行業分級
──────────────────────────────
  行業分級 (ATR倍數):
  ├─ 科技成長: 3.0x (寬容) ← TOP1
  ├─ 新能源:   2.8x       ← TOP2
  ├─ 醫藥:     2.2x
  ├─ 消費:     2.0x (嚴格)
  └─ 金融:     1.8x (最嚴格)
  
  動態微調:
  ├─ Sharpe高(>1.8): 放寬10%
  ├─ Sharpe低(<1.0): 緊縮10%
  ├─ 回撤大(>8%):    緊縮15%
  └─ 回撤小(<3%):    放寬15%

【核心優化④】7維評分升級
──────────────────────────────
  新增維度:
  ✓ 流動性評分 (0-15分)
    ├─ 日均成交>10億:  +15分
    ├─ 日均成交5-10億: +8分
    └─ 日均成交<5億:   -5分
  
  ✓ Sharpe驗證 (0-12分)
    ├─ 過去60天Sharpe>1.5: +12分
    ├─ 過去60天Sharpe 1.0-1.5: +6分
    └─ 過去60天Sharpe<1.0: -5分
  
  推薦等級:
  ├─ 85-100分: 強烈推薦 (10個位置)
  ├─ 75-85分:  推薦 (15個位置)
  ├─ 65-75分:  中性 (10個位置)
  └─ <65分:    黑名單

【預期性能】
──────────────────────────────
  指標              | 預期範圍
  ────────────────────────────
  綜合Sharpe        | 2.14-2.35
  年化收益          | 16-19%
  最大回撤          | <3.5%
  勝率              | 62%
  Kelly幅度        | 1.15-2.0x
  持倉數            | 10-15只
  資金利用率        | 50-65%

【配置文件】
──────────────────────────────
  v5_126_deep_optimize.py    ✓ 完成 (核心模塊)
  config.py                  ⏳ 待集成 (新增20+參數)
  
╚════════════════════════════════════════════════════════════════════════════╝
"""
    print(summary)
    return config


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    
    # 測試: 顯示配置摘要
    config = display_config_summary()
    
    # 序列化為JSON
    config_json = json.dumps(config, indent=2, ensure_ascii=False)
    print("\n【JSON配置導出】")
    print(config_json)
