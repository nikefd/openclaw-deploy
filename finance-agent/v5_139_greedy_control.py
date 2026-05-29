"""v5.139 盤前優化①②: 貪婪行情風控自適應 + 多級止盈快速集成"""

import sys
sys.path.insert(0, '/home/nikefd/finance-agent')

from config import *
from data_collector import get_market_sentiment
import json
from datetime import datetime

class GreedyAdaptiveControl:
    """在贪婪(>85)行情下自动启用"止盈加速+仓位减速"模式"""
    
    @staticmethod
    def get_sentiment_level() -> str:
        """获取当前情绪等级"""
        s = get_market_sentiment()
        score = s.get('sentiment_score', 50)
        if score > 92: return 'extreme_greed'
        if score > 85: return 'greed'
        if score > 60: return 'normal'
        if score > 40: return 'fear'
        return 'extreme_fear'
    
    @staticmethod
    def get_greedy_position_limit(current_positions: int) -> int:
        """计算贪婪行情下的仓位上限
        
        贪婪(>85)时，减速新建仓位，保留收益头寸
        """
        level = GreedyAdaptiveControl.get_sentiment_level()
        
        if level == 'extreme_greed':
            # >92分：停止新建，仅止盈+持有
            return max(current_positions, int(MAX_POSITIONS * 0.6))
        elif level == 'greed':
            # 85-92分：减缓新建，最多保留原有+2只
            return min(current_positions + 2, MAX_POSITIONS - 3)
        else:
            return MAX_POSITIONS
    
    @staticmethod
    def get_greedy_scaled_exit_config(current_profit_pct: float) -> dict:
        """在贪婪行情下加速止盈
        
        盈利>8%时分次出场，锁定收益，规避高位回调
        """
        level = GreedyAdaptiveControl.get_sentiment_level()
        
        if level == 'extreme_greed' and current_profit_pct > 0.08:
            return {
                'enabled': True,
                'targets': [
                    {'profit': 0.05, 'exit_pct': 0.25},   # 5% → 卖25%
                    {'profit': 0.10, 'exit_pct': 0.30},   # 10% → 卖30%
                    {'profit': 0.18, 'exit_pct': 0.25},   # 18% → 卖25%
                    # 20%+: 持有20%参与
                ]
            }
        elif level == 'greed' and current_profit_pct > 0.10:
            return {
                'enabled': True,
                'targets': [
                    {'profit': 0.08, 'exit_pct': 0.20},   # 8% → 卖20%
                    {'profit': 0.15, 'exit_pct': 0.30},   # 15% → 卖30%
                    # 20%+: 持有50%参与
                ]
            }
        else:
            return {'enabled': False}

    @staticmethod
    def get_aggressive_trailing_stop() -> float:
        """在贪婪时启用更紧的尾随止损"""
        level = GreedyAdaptiveControl.get_sentiment_level()
        
        if level == 'extreme_greed':
            return 0.03  # 从4%紧至3% (快速锁定)
        elif level == 'greed':
            return 0.035  # 从4%紧至3.5%
        else:
            return TRAILING_STOP_PCT  # 保持默认4%


def test_greedy_control():
    """测试贪婪风控"""
    s = get_market_sentiment()
    level = GreedyAdaptiveControl.get_sentiment_level()
    
    print(f"\n📊 当前市场情绪: {s['sentiment_score']:.1f} ({s['sentiment_label']}) → {level}")
    print(f"   涨停/跌停: {s['limit_up_count']}/{s['limit_down_count']}")
    
    print(f"\n⚙️  贪婪风控参数:")
    pos_limit = GreedyAdaptiveControl.get_greedy_position_limit(10)
    print(f"   当前10只持仓 → 仓位上限: {pos_limit}只")
    
    if level in ['greed', 'extreme_greed']:
        print(f"   ⚠️  {level}: 启用加速止盈模式")
        config = GreedyAdaptiveControl.get_greedy_scaled_exit_config(0.12)
        if config.get('enabled'):
            for t in config['targets']:
                print(f"      利润{t['profit']*100:.0f}% → 卖{t['exit_pct']*100:.0f}%")
    
    ts = GreedyAdaptiveControl.get_aggressive_trailing_stop()
    print(f"   尾随止损: {TRAILING_STOP_PCT*100:.1f}% → {ts*100:.1f}%")
    
    return {'level': level, 'sentiment': s['sentiment_score']}


if __name__ == '__main__':
    result = test_greedy_control()
    print(f"\n✅ 贪婪风控模块就绪")
    print(json.dumps(result, indent=2))
