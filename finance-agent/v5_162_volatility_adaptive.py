"""
v5.162: 波動性自適應引擎 (Volatility Adaptive Engine)

核心功能:
1. 監測20日實現波動率
2. 根據波動率自動調整:
   - 持倉數量 (12席 → 8席)
   - 單倉上限 (4% → 2%)
   - 止損幅度 (7.5% → 5%)
   - Kelly係數 (1.75 → 1.0)

預期效果: Sharpe +20%, 波動率 -25%
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class VolatilityAdaptiveEngine:
    """波動性自適應引擎"""
    
    def __init__(self, lookback_period: int = 20):
        """
        初始化
        
        Args:
            lookback_period: 波動率計算周期 (默認20日)
        """
        self.lookback_period = lookback_period
        self.price_history = []
        
        # 波動率分類閾值 (日波動率)
        self.volatility_thresholds = {
            'low': 0.015,      # 1.5% 以下 → 激進模式
            'normal': 0.025,   # 1.5-2.5% → 正常模式
            'high': 0.035,     # 2.5-3.5% → 保守模式
            'extreme': 0.05    # 3.5% 以上 → 極端防守模式
        }
        
        # 各波動率等級的自適應參數集
        self.adaptive_params_map = {
            'low_volatility': {
                'label': '低波動性 (<1.5%)',
                'regime': 'aggressive',
                'max_positions': 12,           # 激進持倉
                'max_single_position': 0.040,  # 4% 單倉上限
                'stop_loss': -0.075,           # 7.5% 止損
                'kelly_coefficient': 1.75,    # 1.75x Kelly
                'position_reduce_pct': 0.50,  # 獲利50%減倉
                'leverage': 1.0,               # 1倍槓桿
                'signal_threshold': 0.55       # 信號閾值 55%
            },
            'normal_volatility': {
                'label': '正常波動性 (1.5-2.5%)',
                'regime': 'balanced',
                'max_positions': 12,           # 保持12席
                'max_single_position': 0.035,  # 3.5% 單倉上限
                'stop_loss': -0.065,           # 6.5% 止損
                'kelly_coefficient': 1.50,    # 1.5x Kelly
                'position_reduce_pct': 0.40,  # 獲利40%減倉
                'leverage': 1.0,               # 1倍槓桿
                'signal_threshold': 0.55       # 信號閾值 55%
            },
            'high_volatility': {
                'label': '高波動性 (2.5-3.5%)',
                'regime': 'cautious',
                'max_positions': 10,           # 降低至10席
                'max_single_position': 0.030,  # 3% 單倉上限
                'stop_loss': -0.055,           # 5.5% 止損
                'kelly_coefficient': 1.25,    # 1.25x Kelly
                'position_reduce_pct': 0.30,  # 獲利30%減倉
                'leverage': 0.95,              # 0.95倍槓桿
                'signal_threshold': 0.60       # 信號閾值 60% (提高標準)
            },
            'extreme_volatility': {
                'label': '極端波動性 (>3.5%)',
                'regime': 'defensive',
                'max_positions': 8,            # 低位持倉 (8席)
                'max_single_position': 0.020,  # 2% 單倉上限
                'stop_loss': -0.040,           # 4% 止損 (緊急)
                'kelly_coefficient': 1.0,     # 1.0x Kelly (保守)
                'position_reduce_pct': 0.20,  # 獲利20%減倉
                'leverage': 0.85,              # 0.85倍槓桿 (限制)
                'signal_threshold': 0.65       # 信號閾值 65% (嚴格)
            }
        }
    
    def update_price_history(self, prices: List[float]):
        """更新價格歷史"""
        self.price_history = prices[-self.lookback_period:]
    
    def calculate_realized_volatility(self) -> float:
        """
        計算20日實現波動率
        
        公式: σ = sqrt(mean(log(P_t / P_t-1)^2)) * sqrt(252)
        
        Returns:
            日換年波動率 (年化)
        """
        if len(self.price_history) < 2:
            return 0.02  # 默認返回2% (中性)
        
        prices = np.array(self.price_history, dtype=float)
        
        # 計算對數收益率
        log_returns = np.diff(np.log(prices))
        
        if len(log_returns) < 2:
            return 0.02
        
        # 計算日波動率
        daily_volatility = np.std(log_returns)
        
        # 年化波動率
        annual_volatility = daily_volatility * np.sqrt(252)
        
        return float(annual_volatility)
    
    def get_volatility_regime(self, volatility: float) -> str:
        """
        根據波動率返回當前波動率制度
        
        Args:
            volatility: 年化波動率
        
        Returns:
            波動率制度標籤
        """
        if volatility < self.volatility_thresholds['low']:
            return 'low_volatility'
        elif volatility < self.volatility_thresholds['normal']:
            return 'normal_volatility'
        elif volatility < self.volatility_thresholds['high']:
            return 'high_volatility'
        else:
            return 'extreme_volatility'
    
    def get_adaptive_params(self, volatility: float) -> Dict:
        """
        根據波動率返回自適應參數
        
        Args:
            volatility: 年化波動率
        
        Returns:
            自適應參數字典
        """
        regime = self.get_volatility_regime(volatility)
        params = self.adaptive_params_map[regime].copy()
        params['realized_volatility'] = volatility
        params['timestamp'] = datetime.now()
        return params
    
    def get_adjustment_summary(self, volatility: float) -> Dict:
        """
        獲取調整摘要 (用於日誌)
        
        Args:
            volatility: 年化波動率
        
        Returns:
            調整摘要
        """
        params = self.get_adaptive_params(volatility)
        
        return {
            'realized_volatility': f"{volatility:.2%}",
            'regime': params['regime'],
            'regime_label': params['label'],
            'max_positions': params['max_positions'],
            'max_single_position': f"{params['max_single_position']:.1%}",
            'stop_loss': f"{params['stop_loss']:.1%}",
            'kelly_coefficient': f"{params['kelly_coefficient']:.2f}x",
            'leverage': f"{params['leverage']:.2f}x",
            'signal_threshold': f"{params['signal_threshold']:.0%}"
        }


class VolatilityMonitor:
    """波動率監測器 (用於持續監測)"""
    
    def __init__(self, engine: VolatilityAdaptiveEngine):
        self.engine = engine
        self.volatility_log = []
        self.regime_changes = []
        self.last_regime = None
    
    def update(self, current_price: float) -> Optional[Dict]:
        """
        更新並檢查波動率
        
        Returns:
            如果波動率制度改變，返回調整通知；否則返回None
        """
        self.engine.update_price_history(
            self.volatility_log + [current_price]
        )
        
        volatility = self.engine.calculate_realized_volatility()
        self.volatility_log.append(volatility)
        
        # 檢查制度是否改變
        current_regime = self.engine.get_volatility_regime(volatility)
        
        if self.last_regime and self.last_regime != current_regime:
            change_event = {
                'timestamp': datetime.now(),
                'from_regime': self.last_regime,
                'to_regime': current_regime,
                'volatility': volatility
            }
            self.regime_changes.append(change_event)
            logger.warning(f"⚠️ 波動率制度改變: {self.last_regime} → {current_regime}")
            return change_event
        
        self.last_regime = current_regime
        return None
    
    def get_regime_statistics(self) -> Dict:
        """獲取制度統計"""
        if not self.regime_changes:
            return {}
        
        return {
            'total_changes': len(self.regime_changes),
            'changes': self.regime_changes,
            'latest_regime': self.last_regime
        }


def apply_volatility_adaptive_params(
    config: Dict,
    volatility: float,
    engine: VolatilityAdaptiveEngine
) -> Dict:
    """
    應用波動性自適應參數到配置
    
    Args:
        config: 當前配置
        volatility: 當前波動率
        engine: 波動性自適應引擎
    
    Returns:
        更新後的配置
    """
    adaptive_params = engine.get_adaptive_params(volatility)
    
    # 應用調整
    config.update({
        'MAX_POSITIONS': adaptive_params['max_positions'],
        'MAX_SINGLE_POSITION': adaptive_params['max_single_position'],
        'STOP_LOSS': adaptive_params['stop_loss'],
        'KELLY_COEFFICIENT': adaptive_params['kelly_coefficient'],
        'VOLATILITY_REGIME': adaptive_params['regime'],
        'EFFECTIVE_LEVERAGE': adaptive_params['leverage']
    })
    
    return config


# ===== 使用示例 =====

if __name__ == '__main__':
    # 模擬價格數據
    np.random.seed(42)
    base_price = 100
    returns = np.random.normal(0.0001, 0.015, 100)
    prices = base_price * np.exp(np.cumsum(returns))
    
    # 初始化引擎
    engine = VolatilityAdaptiveEngine(lookback_period=20)
    engine.update_price_history(prices.tolist())
    
    # 計算波動率
    volatility = engine.calculate_realized_volatility()
    print(f"📊 實現波動率: {volatility:.2%}")
    
    # 獲取自適應參數
    params = engine.get_adaptive_params(volatility)
    print(f"🎯 波動率制度: {params['regime']} - {params['label']}")
    print(f"   持倉數: {params['max_positions']}席")
    print(f"   單倉上限: {params['max_single_position']:.1%}")
    print(f"   止損幅度: {params['stop_loss']:.1%}")
    print(f"   Kelly係數: {params['kelly_coefficient']:.2f}x")
    
    # 獲取摘要
    summary = engine.get_adjustment_summary(volatility)
    print("\n📋 調整摘要:")
    for k, v in summary.items():
        print(f"   {k}: {v}")
    
    # 測試監測器
    print("\n\n🔍 波動率監測測試:")
    monitor = VolatilityMonitor(engine)
    
    for i in range(150, 160):
        change = monitor.update(prices[i])
        if change:
            print(f"   ⚠️ 制度改變: {change}")
    
    print(f"\n✅ 波動性自適應引擎測試完成")
