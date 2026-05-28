
# v5.138 Phase 2: 市值分层的参数自适应

def get_market_cap_tier(stock_market_cap_yuan):
    """
    根据市值确定参数等级
    
    参数:
        stock_market_cap_yuan: 股票总市值(元)
    
    返回:
        'large_cap' | 'mid_cap' | 'small_cap'
    """
    # 转换为亿元
    market_cap_billion = stock_market_cap_yuan / 1_000_000_000
    
    if market_cap_billion >= 2000:
        return 'large_cap'
    elif market_cap_billion >= 500:
        return 'mid_cap'
    else:
        return 'small_cap'

def get_adaptive_macd_params(stock_market_cap_yuan, base_params=None):
    """
    根据市值返回自适应的MACD参数
    
    例:
        蓝筹: (12, 26, 9)   - 平稳, 信号稳定
        中盘: (9, 21, 7)    - 敏感, 科技成长
        小盘: (7, 17, 5)    - 快速, 新能源/创新
    """
    from config import MACD_PARAMS_BY_MARKET_CAP
    
    tier = get_market_cap_tier(stock_market_cap_yuan)
    return MACD_PARAMS_BY_MARKET_CAP.get(tier, MACD_PARAMS_BY_MARKET_CAP['mid_cap'])

def get_adaptive_rsi_period(stock_market_cap_yuan):
    """
    根据市值返回自适应的RSI周期
    """
    from config import RSI_PERIOD_BY_MARKET_CAP
    
    tier = get_market_cap_tier(stock_market_cap_yuan)
    return RSI_PERIOD_BY_MARKET_CAP.get(tier, 12)

def calculate_adaptive_signals(symbol, price_series, volume_series, market_cap):
    """
    使用自适应参数计算MACD+RSI信号
    
    参数:
        symbol: 股票代码
        price_series: 价格序列 (numpy array)
        volume_series: 成交量序列
        market_cap: 市值(元)
    
    返回:
        {
            'macd': {...},
            'rsi': {...},
            'tier': 'large_cap' | 'mid_cap' | 'small_cap',
            'adapted_params': {...}
        }
    """
    import numpy as np
    from ta.momentum import macd, rsi
    
    tier = get_market_cap_tier(market_cap)
    macd_params = get_adaptive_macd_params(market_cap)
    rsi_period = get_adaptive_rsi_period(market_cap)
    
    # 计算MACD
    macd_line = macd(
        close=price_series,
        window_fast=macd_params['fast'],
        window_slow=macd_params['slow'],
        window_sign=macd_params['signal']
    )
    
    # 计算RSI
    rsi_line = rsi(price_series, window=rsi_period)
    
    return {
        'symbol': symbol,
        'tier': tier,
        'macd_params': macd_params,
        'rsi_period': rsi_period,
        'macd': {
            'value': macd_line.iloc[-1],
            'signal': macd_line.iloc[-1],  # 简化版
        },
        'rsi': {
            'value': rsi_line.iloc[-1],
            'oversold': rsi_line.iloc[-1] < 30,
            'overbought': rsi_line.iloc[-1] > 70
        }
    }

# 测试案例
if __name__ == '__main__':
    # 东方证券: 600958, 市值约180亿 (mid_cap)
    cap_east_securities = 180_000_000_000
    print(f"东方证券(600958): {get_market_cap_tier(cap_east_securities)}")
    print(f"  MACD参数: {get_adaptive_macd_params(cap_east_securities)}")
    print(f"  RSI周期: {get_adaptive_rsi_period(cap_east_securities)}")
    
    # 华映科技: 000536, 市值约20亿 (small_cap)
    cap_huaying = 20_000_000_000
    print(f"\n华映科技(000536): {get_market_cap_tier(cap_huaying)}")
    print(f"  MACD参数: {get_adaptive_macd_params(cap_huaying)}")
    print(f"  RSI周期: {get_adaptive_rsi_period(cap_huaying)}")
