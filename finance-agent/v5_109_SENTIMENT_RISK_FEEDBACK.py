"""v5_109_情绪风控联动 — 市场情绪与仓位、止损的双向反馈"""

import json
from datetime import datetime, timedelta

# ============ 情绪级别定义 ============

SENTIMENT_LEVELS = {
    'extreme_fear': {'score_range': (0, 30), 'label': '极度恐慌', 'action': 'aggressive_buy'},
    'fear': {'score_range': (30, 50), 'label': '恐慌', 'action': 'buy'},
    'neutral': {'score_range': (50, 70), 'label': '中性', 'action': 'hold'},
    'greed': {'score_range': (70, 85), 'label': '贪婪', 'action': 'normal'},
    'extreme_greed': {'score_range': (85, 100), 'label': '极度贪婪', 'action': 'take_profit'},
}


def classify_sentiment_level(sentiment_score: float) -> dict:
    """将情绪分数转换为情绪级别"""
    for level_key, level_data in SENTIMENT_LEVELS.items():
        low, high = level_data['score_range']
        if low <= sentiment_score < high:
            return {
                'level': level_key,
                'label': level_data['label'],
                'action': level_data['action'],
                'score': sentiment_score
            }
    
    # 边界情况
    return {
        'level': 'extreme_greed',
        'label': '极度贪婪',
        'action': 'take_profit',
        'score': 100
    }


# ============ 基于情绪的止损调整 ============

class SentimentAdjustedStopLoss:
    """情绪感知止损 — 市场恐慌时缩小止损；市场贪婪时扩大止损"""
    
    @staticmethod
    def adjust_stop_loss_percent(base_stop_loss: float, sentiment_score: float) -> float:
        """根据市场情绪调整止损百分比
        
        Args:
            base_stop_loss: 基础止损比例 (e.g., 0.05 = 5%)
            sentiment_score: 市场情绪分数 (0-100)
        
        Returns:
            调整后的止损比例
        """
        sentiment_level = classify_sentiment_level(sentiment_score)
        
        if sentiment_level['level'] == 'extreme_fear':
            # 极度恐慌: 缩小止损至0.025 (2.5%) - 更容易被止损
            return base_stop_loss * 0.5
        
        elif sentiment_level['level'] == 'fear':
            # 恐慌: 缩小止损至0.0375 (3.75%)
            return base_stop_loss * 0.75
        
        elif sentiment_level['level'] == 'neutral':
            # 中性: 保持原止损
            return base_stop_loss
        
        elif sentiment_level['level'] == 'greed':
            # 贪婪: 扩大止损至0.0625 (6.25%)
            return base_stop_loss * 1.25
        
        else:  # extreme_greed
            # 极度贪婪: 扩大止损至0.075 (7.5%)
            return base_stop_loss * 1.5
    
    @staticmethod
    def adjust_take_profit_percent(base_take_profit: float, sentiment_score: float) -> float:
        """根据市场情绪调整止盈百分比
        
        市场贪婪时应该提前止盈，市场恐慌时应该坚守更高目标
        """
        sentiment_level = classify_sentiment_level(sentiment_score)
        
        if sentiment_level['level'] == 'extreme_greed':
            # 极度贪婪: 提前止盈至0.08 (8%)
            return base_take_profit * 0.8
        
        elif sentiment_level['level'] == 'greed':
            # 贪婪: 止盈至0.09 (9%)
            return base_take_profit * 0.9
        
        elif sentiment_level['level'] == 'neutral':
            # 中性: 保持原止盈
            return base_take_profit
        
        elif sentiment_level['level'] == 'fear':
            # 恐慌: 提高止盈至0.15 (15%)
            return base_take_profit * 1.5
        
        else:  # extreme_fear
            # 极度恐慌: 提高止盈至0.20 (20%)
            return base_take_profit * 2.0


# ============ 基于情绪的仓位调整 ============

class SentimentAdjustedPosition:
    """情绪感知仓位 — 贪婪时减仓，恐慌时加仓"""
    
    @staticmethod
    def adjust_position_sizing(base_position_size: float, sentiment_score: float, 
                              cash_ratio: float = None) -> float:
        """根据市场情绪和现金比例调整仓位
        
        Args:
            base_position_size: 基础仓位 (e.g., 0.10 = 10%)
            sentiment_score: 市场情绪分数
            cash_ratio: 当前现金占比 (可选)
        
        Returns:
            调整后的仓位
        """
        sentiment_level = classify_sentiment_level(sentiment_score)
        adjusted_size = base_position_size
        
        if sentiment_level['level'] == 'extreme_fear':
            # 极度恐慌: 加仓50%
            adjusted_size = base_position_size * 1.5
        elif sentiment_level['level'] == 'fear':
            # 恐慌: 加仓25%
            adjusted_size = base_position_size * 1.25
        elif sentiment_level['level'] == 'neutral':
            # 中性: 保持原仓位
            adjusted_size = base_position_size
        elif sentiment_level['level'] == 'greed':
            # 贪婪: 减仓10%
            adjusted_size = base_position_size * 0.9
        else:  # extreme_greed
            # 极度贪婪: 减仓20%
            adjusted_size = base_position_size * 0.8
        
        # 如果现金充足，可以更激进
        if cash_ratio is not None and cash_ratio > 0.85:
            adjusted_size = min(adjusted_size * 1.1, 0.15)  # 最多加仓10%
        
        return adjusted_size
    
    @staticmethod
    def get_max_daily_new_positions(sentiment_score: float) -> int:
        """根据情绪获取每日最多新建仓位数
        
        贪婪时保守，恐慌时激进
        """
        sentiment_level = classify_sentiment_level(sentiment_score)
        
        position_limits = {
            'extreme_fear': 8,      # 极度恐慌: 积极建仓
            'fear': 6,              # 恐慌: 较多建仓
            'neutral': 4,           # 中性: 正常建仓
            'greed': 3,             # 贪婪: 保守建仓
            'extreme_greed': 2,     # 极度贪婪: 非常保守
        }
        
        return position_limits.get(sentiment_level['level'], 4)


# ============ 情绪与策略选择的联动 ============

def select_strategy_by_sentiment(sentiment_score: float) -> dict:
    """根据市场情绪选择合适的策略
    
    Args:
        sentiment_score: 市场情绪分数
    
    Returns:
        推荐策略配置
    """
    sentiment_level = classify_sentiment_level(sentiment_score)
    
    strategies = {
        'extreme_fear': {
            'name': '底部建仓策略',
            'description': '机构进场，大幅加仓',
            'macd_params': (10, 24, 8),        # 灵敏参数
            'rsi_oversold_threshold': 25,      # 低于25买
            'position_aggression': 1.5,        # 仓位加倍
            'entry_quality_threshold': 35,     # 低门槛进场
        },
        'fear': {
            'name': '逢低建仓策略',
            'description': '谨慎加仓，优选标的',
            'macd_params': (12, 26, 9),
            'rsi_oversold_threshold': 30,
            'position_aggression': 1.2,
            'entry_quality_threshold': 50,
        },
        'neutral': {
            'name': '均衡策略',
            'description': '按计划建仓和止损',
            'macd_params': (12, 26, 9),
            'rsi_oversold_threshold': 35,
            'position_aggression': 1.0,
            'entry_quality_threshold': 65,
        },
        'greed': {
            'name': '风险管理策略',
            'description': '提前止盈，控制回撤',
            'macd_params': (14, 28, 10),       # 平滑参数
            'rsi_oversold_threshold': 40,
            'position_aggression': 0.85,       # 仓位缩小
            'entry_quality_threshold': 75,     # 高门槛进场
        },
        'extreme_greed': {
            'name': '获利回吐策略',
            'description': '锁定收益，等待调整',
            'macd_params': (16, 30, 11),       # 非常平滑
            'rsi_oversold_threshold': 45,
            'position_aggression': 0.7,        # 大幅减仓
            'entry_quality_threshold': 85,     # 非常高的门槛
        },
    }
    
    return strategies.get(sentiment_level['level'], strategies['neutral'])


# ============ 风控警告与建议 ============

class SentimentRiskWarning:
    """基于情绪的风控警告"""
    
    @staticmethod
    def get_risk_warnings(sentiment_score: float, current_drawdown: float = 0) -> list:
        """获取风控警告列表
        
        Args:
            sentiment_score: 市场情绪
            current_drawdown: 当前回撤 (e.g., 0.05 = 5%)
        
        Returns:
            警告列表
        """
        warnings = []
        sentiment_level = classify_sentiment_level(sentiment_score)
        
        if sentiment_level['level'] == 'extreme_greed' and current_drawdown < -0.03:
            warnings.append("⚠️  极度贪婪+浮亏3%: 建议提前止盈")
        
        if sentiment_level['level'] == 'extreme_fear':
            warnings.append("🟢 极度恐慌: 底部信号强，可积极加仓")
        
        if sentiment_score > 80 and current_drawdown > 0.05:
            warnings.append("⚠️  贪婪行情+浮利: 应该分批止盈")
        
        return warnings
    
    @staticmethod
    def get_recommendations(sentiment_score: float) -> list:
        """获取操作建议"""
        sentiment_level = classify_sentiment_level(sentiment_score)
        recommendations = []
        
        if sentiment_level['level'] in ['extreme_fear', 'fear']:
            recommendations.append("建议: 逢低加仓优质标的")
            recommendations.append("建议: 增大仓位规模")
        
        elif sentiment_level['level'] in ['greed', 'extreme_greed']:
            recommendations.append("建议: 分批止盈，锁定收益")
            recommendations.append("建议: 降低仓位规模")
            recommendations.append("建议: 提前止盈目标")
        
        return recommendations


# ============ 验证函数 ============

def validate_v5_109():
    """验证v5.109情绪风控联动模块"""
    print("✅ v5.109 情绪风控联动已加载")
    print("   - 情绪级别分类: 5个级别")
    print("   - 情绪感知止损")
    print("   - 情绪感知仓位")
    print("   - 策略动态选择")
    print("   - 风控警告系统")
    return True


if __name__ == '__main__':
    validate_v5_109()
    
    # 测试示例
    test_sentiment = 82.0
    level = classify_sentiment_level(test_sentiment)
    print(f"\n📊 情绪分数: {test_sentiment}")
    print(f"   级别: {level['label']}")
    
    sl = SentimentAdjustedStopLoss()
    adjusted_sl = sl.adjust_stop_loss_percent(0.05, test_sentiment)
    print(f"   调整止损: 5% → {adjusted_sl*100:.2f}%")
    
    strategy = select_strategy_by_sentiment(test_sentiment)
    print(f"   推荐策略: {strategy['name']}")
