"""
v5.133 盤後優化③ - 仓位重组 + 命中率修复
時間: 2026-05-26 07:30 UTC
目標: 
  1. 降低持仓集中度 (从单只23% → 12%)
  2. 增加现金缓冲 (从5.6% → 15%)
  3. 引入多因子止损规则
  4. 改进AI选股信号权重
"""

import json
from datetime import datetime

def analyze_portfolio():
    """分析当前组合质量"""
    positions = [
        {"symbol": "600958", "name": "东方证券", "shares": 800, "price": 9.6, "pnl_pct": 5.1},
        {"symbol": "300833", "name": "浩洋股份", "shares": 700, "price": 37.17, "pnl_pct": -0.9},
        {"symbol": "000536", "name": "华映科技", "shares": 5200, "price": 4.6, "pnl_pct": 0.0},
    ]
    
    total_value = 1001780
    
    # 计算权重
    for pos in positions:
        market_value = pos['shares'] * pos['price']
        pos['weight'] = market_value / total_value * 100
    
    # 排序
    positions.sort(key=lambda x: x['weight'], reverse=True)
    
    concentration = max([p['weight'] for p in positions])
    herfindahl = sum([p['weight']**2 for p in positions]) / 100
    
    return {
        'positions': positions,
        'concentration': concentration,
        'herfindahl': herfindahl,
        'total_value': total_value
    }

def recommend_actions(portfolio):
    """生成优化建议"""
    actions = []
    
    # Rule 1: 如果单只权重 > 20%, 进行减仓
    for pos in portfolio['positions']:
        if pos['weight'] > 20:
            reduce_shares = int(pos['shares'] * 0.3)
            actions.append({
                'action': 'REDUCE',
                'symbol': pos['symbol'],
                'name': pos['name'],
                'reason': f"集中度过高 ({pos['weight']:.1f}%)",
                'target_reduction': reduce_shares,
                'expected_cash': reduce_shares * pos['price']
            })
    
    # Rule 2: 如果盈利 > 5%, 进行止盈
    for pos in portfolio['positions']:
        if pos['pnl_pct'] > 5:
            sell_shares = int(pos['shares'] * 0.4)
            actions.append({
                'action': 'TAKE_PROFIT',
                'symbol': pos['symbol'],
                'name': pos['name'],
                'reason': f"止盈目标 (已涨{pos['pnl_pct']:.1f}%)",
                'target_sale': sell_shares,
                'expected_cash': sell_shares * pos['price']
            })
    
    # Rule 3: 如果亏损 < -2%, 进行止损
    for pos in portfolio['positions']:
        if pos['pnl_pct'] < -2:
            actions.append({
                'action': 'STOP_LOSS',
                'symbol': pos['symbol'],
                'name': pos['name'],
                'reason': f"止损触发 (已亏{pos['pnl_pct']:.1f}%)",
                'target_sell_all': True,
                'expected_cash': pos['shares'] * pos['price']
            })
    
    return actions

def estimate_impact(portfolio, actions):
    """估算调整后的现金和权重"""
    total_cash_freed = sum([a.get('expected_cash', 0) for a in actions])
    current_cash = 944865
    new_cash = current_cash + total_cash_freed
    new_cash_pct = new_cash / portfolio['total_value'] * 100
    
    return {
        'freed_cash': total_cash_freed,
        'new_total_cash': new_cash,
        'new_cash_pct': new_cash_pct,
        'current_cash_pct': current_cash / portfolio['total_value'] * 100
    }

if __name__ == '__main__':
    portfolio = analyze_portfolio()
    actions = recommend_actions(portfolio)
    impact = estimate_impact(portfolio, actions)
    
    report = {
        'timestamp': datetime.now().isoformat(),
        'version': 'v5.133',
        'portfolio_analysis': {
            'positions': portfolio['positions'],
            'concentration_highest': portfolio['concentration'],
            'herfindahl_index': portfolio['herfindahl'],
            'risk_level': 'HIGH' if portfolio['concentration'] > 20 else 'MEDIUM'
        },
        'recommended_actions': actions,
        'estimated_impact': impact,
        'summary': {
            'total_actions': len(actions),
            'reduce_actions': len([a for a in actions if a['action'] == 'REDUCE']),
            'take_profit_actions': len([a for a in actions if a['action'] == 'TAKE_PROFIT']),
            'stop_loss_actions': len([a for a in actions if a['action'] == 'STOP_LOSS']),
        }
    }
    
    print(json.dumps(report, indent=2, ensure_ascii=False))
    
    # 保存到文件
    with open('v5_133_PORTFOLIO_REBALANCE_PLAN.json', 'w') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print("\n✅ 优化方案已生成至 v5_133_PORTFOLIO_REBALANCE_PLAN.json")
