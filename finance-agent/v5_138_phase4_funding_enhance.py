
# v5.138 Phase 4: 龙虎榜缺失补偿 + 资金面增强

def calculate_volume_signal(symbol, current_vol, volume_ma5):
    """
    成交量突增信号 (0-25分)
    
    条件:
        - 当日成交量 > 日均(5天) × 1.5
        - 返回20分 (基础) + 额外5分 (如果 > 2倍)
    """
    threshold = volume_ma5 * 1.5
    
    if current_vol < threshold:
        return 0
    
    # 基础分: 20分
    score = 20
    
    # 额外分: 成交量越大越多
    if current_vol > volume_ma5 * 2.0:
        score += 5
    
    return min(score, 25)

def calculate_institutional_signal(large_order_count, avg_order_size):
    """
    机构参与信号 (0-20分)
    
    条件:
        - 单日大单数(>100万) 多于往日平均 × 1.2
        - 返回15分 (基础) + 额外5分 (如果异常活跃)
    """
    # 简化版: 假设large_order_count为当日大单数
    threshold = avg_order_size * 1.2
    
    if large_order_count < threshold:
        return 0
    
    score = 15
    if large_order_count > avg_order_size * 1.5:
        score += 5
    
    return min(score, 20)

def calculate_margin_signal(margin_balance_change_pct):
    """
    融资净买入信号 (0-5分)
    
    条件:
        - 融资余额日增 > 3%
        - 返回5分
    """
    if margin_balance_change_pct >= 0.03:
        return 5
    elif margin_balance_change_pct >= 0.01:
        return 3
    return 0

def calculate_enhanced_funding_score(symbol, volume_data, order_data, margin_data):
    """
    增强的资金面评分 (0-100)
    
    = 基础50分 (无龙虎榜时) 
      + 成交量突增(0-25)
      + 机构参与(0-20)
      + 融资净买(0-5)
    
    龙虎榜有数据时, 则使用龙虎榜数据替代
    """
    
    base_score = 50  # 无龙虎榜时的基础分
    
    # 成交量信号
    vol_signal = calculate_volume_signal(
        symbol,
        volume_data['current'],  # 当日成交量
        volume_data['ma5']       # 5日均量
    )
    
    # 机构信号
    inst_signal = calculate_institutional_signal(
        order_data['large_order_count'],
        order_data['avg_large_order_size']
    )
    
    # 融资信号
    margin_signal = calculate_margin_signal(
        margin_data['balance_change_pct']
    )
    
    total = base_score + vol_signal + inst_signal + margin_signal
    
    return min(total, 100), {
        'base': base_score,
        'volume': vol_signal,
        'institutional': inst_signal,
        'margin': margin_signal
    }

# 测试案例
if __name__ == '__main__':
    # 华映科技: 小盘股, 龙虎榜常缺失
    symbol = '000536'
    
    volume_data = {'current': 5000000, 'ma5': 3000000}
    order_data = {'large_order_count': 15, 'avg_large_order_size': 10}
    margin_data = {'balance_change_pct': 0.05}
    
    score, breakdown = calculate_enhanced_funding_score(
        symbol, volume_data, order_data, margin_data
    )
    
    print(f"华映科技({symbol}) 资金面评分")
    print(f"总分: {score:.0f}/100")
    print(f"分项:")
    print(f"  基础: {breakdown['base']}")
    print(f"  成交量突增: {breakdown['volume']}")
    print(f"  机构参与: {breakdown['institutional']}")
    print(f"  融资净买: {breakdown['margin']}")
