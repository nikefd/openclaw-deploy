"""市场状态检测器 — 自动识别牛市/熊市/震荡市，动态调整策略"""

from datetime import datetime
from data_collector import get_stock_daily, calculate_technical_indicators


# 市场状态定义
REGIME_BULL = 'bull'       # 牛市: 趋势向上，适合追涨
REGIME_BEAR = 'bear'       # 熊市: 趋势向下，现金为王
REGIME_SIDEWAYS = 'sideways'  # 震荡: 高抛低吸

# 各状态下的策略权重调节
REGIME_STRATEGY_MULTIPLIERS = {
    REGIME_BULL: {
        'macd_rsi': 1.3,       # 牛市MACD+RSI强
        'trend_follow': 1.4,   # 趋势跟踪最强
        'multi_factor': 1.1,
        'ma_cross': 1.2,
        'momentum': 1.3,       # 动量策略在牛市好用
        'money_flow': 1.1,
        'strong': 1.2,
        'institution': 1.0,
    },
    REGIME_BEAR: {
        'macd_rsi': 0.6,       # 熊市技术面失灵
        'trend_follow': 0.5,
        'multi_factor': 0.7,
        'ma_cross': 0.6,
        'momentum': 0.4,       # 熊市动量是陷阱
        'money_flow': 0.7,
        'strong': 0.5,         # 熊市强势股可能是最后的疯狂
        'institution': 1.2,    # 机构推荐在熊市相对可靠
    },
    REGIME_SIDEWAYS: {
        'macd_rsi': 1.0,
        'trend_follow': 0.8,
        'multi_factor': 1.2,   # 震荡市多因子最稳
        'ma_cross': 1.1,
        'momentum': 0.8,
        'money_flow': 1.1,
        'strong': 0.9,
        'institution': 1.1,
    },
}

# 各状态下的仓位上限
REGIME_POSITION_CAPS = {
    REGIME_BULL: 0.85,      # 牛市可以85%仓位
    REGIME_BEAR: 0.40,      # 熊市最多40%
    REGIME_SIDEWAYS: 0.65,  # 震荡市65%
}

# 各状态下的止损调整
REGIME_STOP_LOSS = {
    REGIME_BULL: -0.10,     # 牛市放宽止损
    REGIME_BEAR: -0.05,     # 熊市收紧止损
    REGIME_SIDEWAYS: -0.08, # 震荡市正常
}


def detect_market_regime() -> dict:
    """检测当前市场状态
    
    使用上证指数的技术指标来判断:
    - MA20 > MA60 且 MACD > 0 → 牛市
    - MA20 < MA60 且 MACD < 0 → 熊市
    - 其他 → 震荡
    
    返回: {regime, confidence, details}
    """
    # 用上证指数判断大盘状态
    # 上证指数代码: 000001 (需要特殊处理，用sh000001)
    try:
        import requests
        url = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sh000001,day,,,120,qfq'
        r = requests.get(url, timeout=15)
        data = r.json()
        stock_data = data.get('data', {}).get('sh000001', {})
        klines = stock_data.get('qfqday', stock_data.get('day', []))
        
        if not klines or len(klines) < 60:
            return {'regime': REGIME_SIDEWAYS, 'confidence': 0.3, 'details': '数据不足，默认震荡'}
        
        import pandas as pd
        cols = ['日期', '开盘', '收盘', '最高', '最低', '成交量']
        df = pd.DataFrame(klines)
        df = df.iloc[:, :min(len(df.columns), 6)]
        df.columns = cols[:len(df.columns)]
        for col in ['开盘', '收盘', '最高', '最低', '成交量']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        tech = calculate_technical_indicators(df)
        if not tech:
            return {'regime': REGIME_SIDEWAYS, 'confidence': 0.3, 'details': '指标计算失败'}
        
        # 综合评分
        bull_score = 0
        bear_score = 0
        details = []
        
        # MA趋势
        ma20 = tech.get('ma20', 0)
        ma60 = tech.get('ma60', 0)
        if ma20 > 0 and ma60 > 0:
            if ma20 > ma60:
                bull_score += 2
                details.append(f'MA20({ma20:.0f})>MA60({ma60:.0f})')
            else:
                bear_score += 2
                details.append(f'MA20({ma20:.0f})<MA60({ma60:.0f})')
        
        # MACD方向
        macd = tech.get('macd', 0)
        if macd > 0:
            bull_score += 1.5
            details.append(f'MACD正({macd:.2f})')
        else:
            bear_score += 1.5
            details.append(f'MACD负({macd:.2f})')
        
        # RSI位置
        rsi = tech.get('rsi14', 50)
        if rsi > 60:
            bull_score += 1
            details.append(f'RSI偏高({rsi:.0f})')
        elif rsi < 40:
            bear_score += 1
            details.append(f'RSI偏低({rsi:.0f})')
        
        # 趋势判断
        trend = tech.get('trend', '')
        if '多头' in trend:
            bull_score += 1.5
            details.append('多头排列')
        elif '空头' in trend:
            bear_score += 1.5
            details.append('空头排列')
        
        # 近20日涨跌幅
        close = df['收盘'].astype(float)
        if len(close) >= 20:
            ret_20d = (close.iloc[-1] - close.iloc[-20]) / close.iloc[-20] * 100
            if ret_20d > 5:
                bull_score += 1
                details.append(f'20日涨{ret_20d:.1f}%')
            elif ret_20d < -5:
                bear_score += 1
                details.append(f'20日跌{ret_20d:.1f}%')
        
        # 判定
        total = bull_score + bear_score
        if total == 0:
            regime = REGIME_SIDEWAYS
            confidence = 0.5
        elif bull_score >= bear_score * 2:
            regime = REGIME_BULL
            confidence = min(bull_score / (total + 1), 0.95)
        elif bear_score >= bull_score * 2:
            regime = REGIME_BEAR
            confidence = min(bear_score / (total + 1), 0.95)
        else:
            regime = REGIME_SIDEWAYS
            confidence = 1 - abs(bull_score - bear_score) / (total + 1)
        
        return {
            'regime': regime,
            'confidence': round(confidence, 2),
            'bull_score': round(bull_score, 1),
            'bear_score': round(bear_score, 1),
            'details': ' | '.join(details),
            'tech': {k: v for k, v in tech.items() if k in ['ma20', 'ma60', 'macd', 'rsi14', 'trend']},
        }
    
    except Exception as e:
        print(f"市场状态检测失败: {e}")
        return {'regime': REGIME_SIDEWAYS, 'confidence': 0.3, 'details': f'检测失败: {e}'}


def get_regime_strategy_multiplier(regime: str, strategy_key: str) -> float:
    """获取当前市场状态下某策略的权重乘数"""
    multipliers = REGIME_STRATEGY_MULTIPLIERS.get(regime, {})
    return multipliers.get(strategy_key, 1.0)


def get_regime_position_cap(regime: str) -> float:
    """获取当前市场状态下的仓位上限"""
    return REGIME_POSITION_CAPS.get(regime, 0.65)


def get_regime_stop_loss(regime: str) -> float:
    """获取当前市场状态下的止损线"""
    return REGIME_STOP_LOSS.get(regime, -0.08)


if __name__ == "__main__":
    print("=== 市场状态检测 ===")
    result = detect_market_regime()
    print(f"状态: {result['regime']}")
    print(f"信心: {result['confidence']}")
    print(f"详情: {result['details']}")
