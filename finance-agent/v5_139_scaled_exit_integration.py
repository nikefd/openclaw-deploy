"""v5.139②: 多级止盈核心逻辑 - 从position_manager中提取并增强"""

import sys
sys.path.insert(0, '/home/nikefd/finance-agent')

from config import *
from datetime import datetime

class ScaledExitManager:
    """多级止盈管理器 - 替代全清单逻辑"""
    
    SCALED_EXIT_CONFIG = {
        'defensive': {  # 消费白马/金融/医药 (低风险)
            'targets': [
                {'profit': 0.03, 'exit_pct': 0.15},    # 3% → 卖15%
                {'profit': 0.08, 'exit_pct': 0.25},    # 8% → 卖25%
                {'profit': 0.15, 'exit_pct': 0.35},    # 15% → 卖35%
                # 15%+: 持有25%参与
            ]
        },
        'offensive': {  # 科技成长 (高风险)
            'targets': [
                {'profit': 0.05, 'exit_pct': 0.17},    # 5% → 卖17%
                {'profit': 0.10, 'exit_pct': 0.33},    # 10% → 卖33%
                {'profit': 0.18, 'exit_pct': 0.25},    # 18% → 卖25%
                # 20%+: 持有25%参与
            ]
        }
    }
    
    @staticmethod
    def calculate_scaled_exit_qty(
        position_qty: int,
        current_price: float,
        entry_price: float,
        category: str = 'offensive'
    ) -> list:
        """计算分级止盈数量
        
        Returns: [
            {'at_profit': 0.05, 'qty': 102, 'price': 9.70},
            {'at_profit': 0.10, 'qty': 198, 'price': 10.15},
            ...
        ]
        """
        profit_pct = (current_price - entry_price) / entry_price
        config = ScaledExitManager.SCALED_EXIT_CONFIG.get(category, 
                                ScaledExitManager.SCALED_EXIT_CONFIG['offensive'])
        
        exits = []
        remaining_qty = position_qty
        
        for target in config['targets']:
            if profit_pct >= target['profit']:
                exit_qty = int(position_qty * target['exit_pct'])
                exits.append({
                    'at_profit': f"{target['profit']*100:.0f}%",
                    'exit_qty': exit_qty,
                    'exit_price': round(current_price, 2),
                    'est_gain': round(exit_qty * (current_price - entry_price), 2)
                })
                remaining_qty -= exit_qty
        
        if remaining_qty > 0:
            exits.append({
                'at_profit': 'Hold',
                'hold_qty': remaining_qty,
                'hold_price': round(entry_price, 2),
                'note': f'参与{profit_pct*100:.1f}%+涨幅'
            })
        
        return exits
    
    @staticmethod
    def test_scaled_exit():
        """测试东方证券案例: 600股 @ 9.23元"""
        print("\n" + "="*60)
        print("📊 多级止盈案例测试: 东方证券(601198)")
        print("="*60)
        
        # 东方证券数据
        entry_price = 9.23
        position_qty = 600
        test_prices = [10.00, 10.50, 11.00, 12.00]
        
        for price in test_prices:
            profit_pct = (price - entry_price) / entry_price
            exits = ScaledExitManager.calculate_scaled_exit_qty(
                position_qty, price, entry_price, 'defensive'
            )
            
            print(f"\n📈 当前价格: ¥{price} (利润{profit_pct*100:.1f}%)")
            total_gain = 0
            for e in exits:
                if 'exit_qty' in e:
                    total_gain += e['est_gain']
                    print(f"   ✅ {e['at_profit']}: 卖{e['exit_qty']}股 @ ¥{e['exit_price']} → ¥{e['est_gain']:.0f}")
                else:
                    print(f"   ⏱️  {e['at_profit']}: 持有{e['hold_qty']}股 @ ¥{e['hold_price']} ({e['note']})")
            
            if total_gain > 0:
                print(f"   💰 累计止盈: ¥{total_gain:.0f}")


if __name__ == '__main__':
    ScaledExitManager.test_scaled_exit()
    print("\n✅ 多级止盈模块就绪")
