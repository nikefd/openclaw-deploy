"""v5.141集成 - 将优化应用到daily_runner和stock_picker中"""

from v5_141_DEEP_EVENING_OPTIMIZE_V import (
    apply_v5_141_optimization_if_enabled,
    IntegratedOptimizer141
)


def integrate_v5_141_to_stock_picker(picks: list, cash_ratio: float, market_sentiment: float = 50) -> list:
    """在stock_picker.py的multi_strategy_pick后调用此函数优化选股结果
    
    使用示例:
    ```python
    # 在stock_picker.py中
    picks = multi_strategy_pick()  # 原有逻辑
    picks = integrate_v5_141_to_stock_picker(picks, cash_ratio, market_sentiment)
    ```
    """
    
    account_state = {
        'cash_ratio': cash_ratio,
        'total_value': 1000000  # 模拟值
    }
    
    result = apply_v5_141_optimization_if_enabled(picks, account_state, market_sentiment)
    
    if result and result['status'] == 'success':
        return result['picks']
    else:
        return picks


def integrate_v5_141_to_daily_runner(picks: list, account_info: dict) -> list:
    """在daily_runner.py中调用此函数应用v5.141优化
    
    使用示例:
    ```python
    # 在daily_runner.py的主选股流程中
    picks = stock_picker.pick()
    picks = integrate_v5_141_to_daily_runner(picks, account)
    ```
    """
    
    cash_ratio = account_info.get('cash_ratio', 0.5)
    market_sentiment = account_info.get('market_sentiment', 50)
    
    return integrate_v5_141_to_stock_picker(picks, cash_ratio, market_sentiment)


def get_v5_141_optimizer():
    """获取v5.141优化器单例"""
    return IntegratedOptimizer141()
