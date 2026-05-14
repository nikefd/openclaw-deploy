"""v5.104: 動態現金閾值激活 📊
根據市場情緒自動調整現金激進啟動點

邏輯:
- 高情緒(貪婪/樂觀) → 降低現金閾值, 快速建倉
- 低情緒(謹慎/恐慌) → 提高現金閾值, 防守模式
"""

import json
from typing import Dict, Tuple

class DynamicCashThresholdManager:
    """情緒聯動現金閾值管理"""
    
    # 情緒分級表 (sentiment_score → 級別)
    SENTIMENT_TIERS = {
        'greed': (80, 100, '貪婪'),      # 極度樂觀
        'optimism': (65, 79, '樂觀'),    # 積極
        'neutral': (45, 64, '中性'),     # 平衡
        'caution': (30, 44, '謹慎'),     # 風險意識提高
        'panic': (0, 29, '恐慌')         # 極度悲觀
    }
    
    # v5.104 核心配置表
    DYNAMIC_CONFIG = {
        'greed': {
            'cash_activate_threshold': 0.65,    # 現金>=65%時啟動建倉
            'target_position_count': 15,        # 目標持倉數
            'aggressive_mode': 'full',          # full/normal/defensive/locked
            'kelly_multiplier': 1.3,            # Kelly倍數
            'entry_quality_min': 45,            # 最低入場質量評分
            'max_single_position': 0.05,        # 單倉上限5%
        },
        'optimism': {
            'cash_activate_threshold': 0.75,    # 現金>=75%
            'target_position_count': 12,
            'aggressive_mode': 'normal',
            'kelly_multiplier': 1.1,
            'entry_quality_min': 50,
            'max_single_position': 0.045,
        },
        'neutral': {
            'cash_activate_threshold': 0.85,    # 現金>=85%
            'target_position_count': 8,
            'aggressive_mode': 'normal',
            'kelly_multiplier': 0.9,
            'entry_quality_min': 55,
            'max_single_position': 0.04,
        },
        'caution': {
            'cash_activate_threshold': 0.92,    # 現金>=92%
            'target_position_count': 5,
            'aggressive_mode': 'defensive',
            'kelly_multiplier': 0.7,
            'entry_quality_min': 60,
            'max_single_position': 0.03,
        },
        'panic': {
            'cash_activate_threshold': 0.98,    # 現金>=98%
            'target_position_count': 2,
            'aggressive_mode': 'locked',        # 鎖定持倉，不新增
            'kelly_multiplier': 0.5,
            'entry_quality_min': 70,
            'max_single_position': 0.02,
        }
    }
    
    @classmethod
    def classify_sentiment(cls, sentiment_score: float) -> str:
        """將情緒評分轉換為級別名稱
        
        Args:
            sentiment_score: 0-100 的情緒評分
            
        Returns:
            級別名稱 ('greed', 'optimism', 'neutral', 'caution', 'panic')
        """
        for tier_name, (min_val, max_val, _) in cls.SENTIMENT_TIERS.items():
            if min_val <= sentiment_score <= max_val:
                return tier_name
        return 'neutral'  # 默認
    
    @classmethod
    def get_dynamic_threshold(cls, sentiment_score: float) -> Dict:
        """根據情緒評分獲取動態配置
        
        Args:
            sentiment_score: 0-100 的情緒評分
            
        Returns:
            動態配置字典
        """
        tier = cls.classify_sentiment(sentiment_score)
        config = cls.DYNAMIC_CONFIG[tier]
        
        return {
            'tier': tier,
            'tier_name': cls.SENTIMENT_TIERS[tier][2],
            'sentiment_score': sentiment_score,
            'cash_activate_threshold': config['cash_activate_threshold'],
            'target_position_count': config['target_position_count'],
            'aggressive_mode': config['aggressive_mode'],
            'kelly_multiplier': config['kelly_multiplier'],
            'entry_quality_min': config['entry_quality_min'],
            'max_single_position': config['max_single_position'],
        }
    
    @classmethod
    def should_activate_aggressive_mode(cls, current_cash_ratio: float, 
                                       sentiment_score: float) -> Tuple[bool, Dict]:
        """判斷是否應激活激進建倉模式
        
        Args:
            current_cash_ratio: 當前現金佔比 (0-1)
            sentiment_score: 情緒評分 (0-100)
            
        Returns:
            (should_activate: bool, decision_info: dict)
        """
        config = cls.get_dynamic_threshold(sentiment_score)
        threshold = config['cash_activate_threshold']
        
        should_activate = current_cash_ratio >= threshold
        
        decision = {
            'should_activate': should_activate,
            'current_cash_ratio': round(current_cash_ratio, 3),
            'required_threshold': round(threshold, 3),
            'cash_margin': round(current_cash_ratio - threshold, 3),  # 超過閾值多少
            'tier': config['tier'],
            'aggressive_mode': config['aggressive_mode'],
            'target_positions': config['target_position_count'],
        }
        
        return should_activate, decision
    
    @classmethod
    def get_kelly_multiplier(cls, sentiment_score: float) -> float:
        """根據情緒獲取Kelly係數動態調整
        
        邏輯:
        - 高情緒(>75) Kelly * 1.1-1.3 (更激進)
        - 低情緒(<45) Kelly * 0.5-0.7 (保守)
        """
        config = cls.get_dynamic_threshold(sentiment_score)
        return config['kelly_multiplier']
    
    @classmethod
    def get_entry_quality_threshold(cls, sentiment_score: float) -> int:
        """根據情緒獲取入場質量最低要求
        
        高情緒允許較低質量,低情緒必須高質量
        """
        config = cls.get_dynamic_threshold(sentiment_score)
        return config['entry_quality_min']
    
    @classmethod
    def get_position_size_limit(cls, sentiment_score: float) -> float:
        """根據情緒獲取單倉上限
        
        高情緒5%,低情緒2%
        """
        config = cls.get_dynamic_threshold(sentiment_score)
        return config['max_single_position']


def get_dynamic_cash_threshold(sentiment_score: float) -> Dict:
    """一鍵獲取動態現金閾值(供position_manager調用)
    
    Usage:
        from data_collector import get_market_sentiment
        from v5_104_DYNAMIC_CASH import get_dynamic_cash_threshold
        
        sentiment = get_market_sentiment()
        cash_config = get_dynamic_cash_threshold(sentiment['sentiment_score'])
        print(f"建倉現金閾值: {cash_config['cash_activate_threshold']*100}%")
    """
    return DynamicCashThresholdManager.get_dynamic_threshold(sentiment_score)


if __name__ == '__main__':
    print("=" * 60)
    print("v5.104 動態現金閾值配置表")
    print("=" * 60)
    
    test_scores = [95, 75, 55, 35, 15]
    
    for score in test_scores:
        config = DynamicCashThresholdManager.get_dynamic_threshold(score)
        
        print(f"\n📊 情緒評分: {score}")
        print(f"   級別: {config['tier_name']}")
        print(f"   現金激活閾值: {config['cash_activate_threshold']*100:.0f}%")
        print(f"   目標持倉數: {config['target_position_count']}只")
        print(f"   模式: {config['aggressive_mode']}")
        print(f"   Kelly乘數: {config['kelly_multiplier']}x")
        print(f"   入場質量最低: {config['entry_quality_min']}分")
        print(f"   單倉上限: {config['max_single_position']*100:.1f}%")
    
    print("\n" + "=" * 60)
    print("激活判定示例")
    print("=" * 60)
    
    test_cases = [
        (0.90, 85),  # 現金90%, 情緒85 → 貪婪
        (0.80, 55),  # 現金80%, 情緒55 → 中性
        (0.75, 25),  # 現金75%, 情緒25 → 恐慌
    ]
    
    for cash_ratio, sentiment in test_cases:
        should_activate, decision = DynamicCashThresholdManager.should_activate_aggressive_mode(
            cash_ratio, sentiment
        )
        print(f"\n💰 現金{cash_ratio*100:.0f}% + 情緒{sentiment}:")
        print(f"   → 激活建倉? {'✅ 是' if should_activate else '❌ 否'}")
        print(f"   → 模式: {decision['aggressive_mode']}")
        print(f"   → 目標{decision['target_positions']}只持倉")
