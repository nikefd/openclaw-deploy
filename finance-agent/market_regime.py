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
    
    新增: 转换期检测(bear→sideways / bear→bull 过渡)
    
    返回: {regime, confidence, details, transition}
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
        
        # === 转换期检测 ===
        # 熊市→震荡/牛市的过渡期: MACD柱线由负转正趋势+DIF向上穿DEA
        transition = 'none'
        transition_details = []
        if regime == REGIME_BEAR:
            # 检查是否在底部企稳过渡
            macd_val = tech.get('macd', 0)
            macd_dif = tech.get('macd_dif', 0)
            macd_dea = tech.get('macd_dea', 0)
            rsi_val = tech.get('rsi14', 50)
            
            # MACD柱线虽然还为负但在收窄(DIF在向DEA靠拢)
            dif_rising = macd_dif > macd_dea * 0.8 if macd_dea < 0 else False
            # RSI从超低区回升
            rsi_recovering = 35 < rsi_val < 55
            # 近5日涨幅转正
            if len(close) >= 5:
                ret_5d = (close.iloc[-1] - close.iloc[-5]) / close.iloc[-5] * 100
                short_bounce = ret_5d > 1
            else:
                short_bounce = False
            
            signals = sum([dif_rising, rsi_recovering, short_bounce])
            if signals >= 2:
                transition = 'bear_to_sideways'
                transition_details.append('熊市企稳过渡期')
                if dif_rising:
                    transition_details.append('MACD收窄')
                if rsi_recovering:
                    transition_details.append(f'RSI回升({rsi_val:.0f})')
                if short_bounce:
                    transition_details.append(f'短期反弹{ret_5d:.1f}%')
        
        elif regime == REGIME_SIDEWAYS:
            # 震荡→牛市过渡
            if bull_score > bear_score and tech.get('macd_signal') in ('golden_cross', 'bullish'):
                transition = 'sideways_to_bull'
                transition_details.append('震荡向上突破倾向')
        
        return {
            'regime': regime,
            'confidence': round(confidence, 2),
            'bull_score': round(bull_score, 1),
            'bear_score': round(bear_score, 1),
            'details': ' | '.join(details),
            'transition': transition,
            'transition_details': ' | '.join(transition_details) if transition_details else '',
            'tech': {k: v for k, v in tech.items() if k in ['ma20', 'ma60', 'macd', 'rsi14', 'trend', 'macd_dif', 'macd_dea']},
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


def get_market_breadth() -> dict:
    """市场宽度指标 — 个股涨跌比辨别真假行情
    
    即使大盘指数涨，如果多数个股下跌，说明是权重股拉升的假行情
    Returns: {advance_count, decline_count, breadth_ratio, breadth_signal}
    """
    try:
        import requests
        # 用东方财富全A股涨跌统计
        url = "https://push2.eastmoney.com/api/qt/clist/get"
        params = {
            'fid': 'f3', 'po': 1, 'pz': 1, 'pn': 1, 'np': 1, 'fltt': 2,
            'invt': 2, 'fs': 'm:0+t:6+f:!2,m:0+t:13+f:!2,m:0+t:80+f:!2,m:1+t:2+f:!2,m:1+t:23+f:!2,m:0+t:7+f:!2,m:1+t:3+f:!2',
            'fields': 'f2,f3',  # 最新价,涨跌幅
        }
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        total = data.get('data', {}).get('total', 0)
        
        # 简化: 用板块涨跌家数近似
        # 或者直接用涨停/跌停比来判断
        # 这里用一个更可靠的方法: 上证/深证成分股涨跌比
        url2 = 'https://qt.gtimg.cn/q=sh000001,sz399001'
        r2 = requests.get(url2, timeout=10)
        advance = 0
        decline = 0
        for line in r2.text.strip().split(';'):
            line = line.strip()
            if not line or '=' not in line:
                continue
            data = line.split('=')[1].strip('"').split('~')
            if len(data) > 40:
                try:
                    advance += int(data[37]) if data[37] else 0  # 上涨家数
                    decline += int(data[38]) if data[38] else 0  # 下跌家数
                except:
                    pass
        
        if advance + decline > 0:
            ratio = advance / (advance + decline)
        else:
            ratio = 0.5
        
        if ratio > 0.65:
            signal = 'strong'  # 普涨, 真行情
        elif ratio > 0.5:
            signal = 'neutral'
        elif ratio > 0.35:
            signal = 'weak'    # 多数下跌, 谨慎
        else:
            signal = 'very_weak'  # 普跌, 不宜做多
        
        return {
            'advance': advance, 'decline': decline,
            'breadth_ratio': round(ratio, 3),
            'breadth_signal': signal,
        }
    except Exception as e:
        return {'advance': 0, 'decline': 0, 'breadth_ratio': 0.5, 'breadth_signal': 'neutral'}


if __name__ == "__main__":
    print("=== 市场状态检测 ===")
    result = detect_market_regime()
    print(f"状态: {result['regime']}")
    print(f"信心: {result['confidence']}")
    print(f"详情: {result['details']}")
