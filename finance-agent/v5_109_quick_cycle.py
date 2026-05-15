#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
V5.109 快速循环评估模块
=======================

功能:
  - 3天首评: 信号确认
  - 5天二评: 趋势延续
  - 7天终评: 清出弱仓

自动化规则:
  - 亏损>8% (T+3) → 止损清仓
  - 盈利>20% (T+3) → 止盈清仓
  - 持续微亏<-3% (T+7) → 周期清仓
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import logging

logger = logging.getLogger(__name__)


class QuickCycleEvaluator:
    """快速循环评估器"""
    
    def __init__(self):
        self.evaluation_log = []
    
    def evaluate_all_positions(self, portfolio: List[Dict]) -> Dict:
        """
        批量评估所有持仓
        
        Args:
            portfolio: 持仓列表 [
                {
                    'symbol': 'XXXX',
                    'entry_date': datetime,
                    'entry_price': float,
                    'current_price': float,
                    'shares': int,
                    'entry_return': float
                }
            ]
        
        Returns:
            {
                'hold': [symbol1, symbol2, ...],
                'sell': [
                    {'symbol': 'XX', 'reason': 'STOP_LOSS', 'return': -0.09, 'days': 3}
                ],
                'actions': summary
            }
        """
        today = datetime.now().date()
        
        hold_list = []
        sell_list = []
        action_summary = {
            'total_positions': len(portfolio),
            'hold_count': 0,
            'sell_count': 0,
            'by_reason': {}
        }
        
        for pos in portfolio:
            entry_date = pd.to_datetime(pos['entry_date']).date()
            hold_days = (today - entry_date).days
            current_return = pos.get('entry_return', 0)  # 今日返回率
            
            decision = self._evaluate_single_position(
                symbol=pos['symbol'],
                hold_days=hold_days,
                current_return=current_return,
                entry_price=pos.get('entry_price'),
                current_price=pos.get('current_price')
            )
            
            if decision['action'] == 'HOLD':
                hold_list.append(pos['symbol'])
                action_summary['hold_count'] += 1
            else:
                sell_list.append(decision)
                action_summary['sell_count'] += 1
                reason = decision['reason']
                action_summary['by_reason'][reason] = action_summary['by_reason'].get(reason, 0) + 1
            
            self.evaluation_log.append({
                'timestamp': datetime.now().isoformat(),
                'symbol': pos['symbol'],
                'decision': decision
            })
        
        return {
            'hold': hold_list,
            'sell': sell_list,
            'action_summary': action_summary,
            'evaluation_timestamp': datetime.now().isoformat()
        }
    
    def _evaluate_single_position(self, symbol: str, hold_days: int, current_return: float,
                                  entry_price: float = None, current_price: float = None) -> Dict:
        """
        评估单只持仓
        
        规则:
          T+0-2: HOLD (观察期)
          T+3:   止损(-8%) / 止盈(+20%)
          T+5:   信号复核
          T+7:   周期清仓(<-3%)
        """
        
        if hold_days < 3:
            return {
                'action': 'HOLD',
                'reason': 'OBSERVATION_PERIOD',
                'days': hold_days
            }
        
        # T+3 首评: 止损止盈
        if hold_days >= 3:
            if current_return <= -0.08:
                return {
                    'action': 'SELL',
                    'reason': 'QUICK_STOP_LOSS_T3',
                    'days': hold_days,
                    'return': current_return
                }
            elif current_return >= 0.20:
                return {
                    'action': 'SELL',
                    'reason': 'QUICK_TAKE_PROFIT_T3',
                    'days': hold_days,
                    'return': current_return
                }
        
        # T+5 二评: 强化止损
        if hold_days >= 5:
            if current_return <= -0.05:  # 亏损>5%,认为趋势不佳
                if self._is_downtrend_confirmed(entry_price, current_price, hold_days):
                    return {
                        'action': 'SELL',
                        'reason': 'DOWNTREND_CONFIRMED_T5',
                        'days': hold_days,
                        'return': current_return
                    }
        
        # T+7 终评: 周期清仓
        if hold_days >= 7:
            if current_return < -0.03:
                return {
                    'action': 'SELL',
                    'reason': 'CYCLE_LOSS_T7',
                    'days': hold_days,
                    'return': current_return
                }
        
        return {
            'action': 'HOLD',
            'reason': 'HOLDING',
            'days': hold_days,
            'return': current_return
        }
    
    def _is_downtrend_confirmed(self, entry_price: float, current_price: float, days: int) -> bool:
        """
        简单的下跌趋势确认
        
        逻辑: 5天内下跌幅度 > 5% 则确认下跌
        """
        if not entry_price or not current_price:
            return False
        
        decline_pct = (current_price - entry_price) / entry_price
        return decline_pct < -0.05


class QuickExitExecutor:
    """快速清仓执行器"""
    
    def __init__(self):
        self.exit_log = []
    
    def execute_quick_exits(self, exit_decisions: List[Dict]) -> Dict:
        """
        执行快速清仓交易
        
        Args:
            exit_decisions: [
                {'symbol': 'XX', 'reason': 'STOP_LOSS', 'return': -0.09}
            ]
        
        Returns:
            执行结果统计
        """
        executed = 0
        failed = 0
        total_return_recovered = 0
        
        for decision in exit_decisions:
            try:
                symbol = decision['symbol']
                reason = decision['reason']
                
                # 这里会调用实际的交易接口
                # result = sell_position(symbol, reason)
                
                executed += 1
                return_val = decision.get('return', 0)
                total_return_recovered += return_val
                
                self.exit_log.append({
                    'timestamp': datetime.now().isoformat(),
                    'symbol': symbol,
                    'reason': reason,
                    'status': 'SUCCESS',
                    'return': return_val
                })
                
            except Exception as e:
                failed += 1
                logger.error(f"Failed to execute exit for {decision['symbol']}: {e}")
        
        return {
            'total_exits': len(exit_decisions),
            'executed': executed,
            'failed': failed,
            'total_return_saved': total_return_recovered,
            'timestamp': datetime.now().isoformat()
        }


class QuickCycleMetrics:
    """快速循环绩效指标"""
    
    @staticmethod
    def calculate_cycle_metrics(evaluation_results: Dict, execution_results: Dict = None) -> Dict:
        """
        计算快速循环的关键指标
        
        KPI:
          - 清仓成功率
          - 平均持仓周期
          - 止损触发率
          - 止盈触发率
          - 周期清仓率
        """
        
        action_summary = evaluation_results.get('action_summary', {})
        by_reason = action_summary.get('by_reason', {})
        
        total_positions = action_summary.get('total_positions', 1)
        hold_count = action_summary.get('hold_count', 0)
        sell_count = action_summary.get('sell_count', 0)
        
        metrics = {
            'evaluation_timestamp': evaluation_results.get('evaluation_timestamp'),
            'total_positions': total_positions,
            'hold_rate': hold_count / total_positions if total_positions > 0 else 0,
            'exit_rate': sell_count / total_positions if total_positions > 0 else 0,
            'exit_breakdown': {
                'stop_loss': by_reason.get('QUICK_STOP_LOSS_T3', 0),
                'take_profit': by_reason.get('QUICK_TAKE_PROFIT_T3', 0),
                'downtrend': by_reason.get('DOWNTREND_CONFIRMED_T5', 0),
                'cycle_loss': by_reason.get('CYCLE_LOSS_T7', 0)
            },
            'health_check': {
                'too_many_exits': sell_count > total_positions * 0.5,  # 清仓超50%为警告
                'stop_loss_frequency': by_reason.get('QUICK_STOP_LOSS_T3', 0) / total_positions if total_positions > 0 else 0,
                'status': 'HEALTHY' if sell_count <= total_positions * 0.3 else 'WARNING'
            }
        }
        
        if execution_results:
            metrics['execution'] = execution_results
        
        return metrics


def demo_quick_cycle_evaluation():
    """演示快速循环评估"""
    
    print("\n" + "="*70)
    print("🔄 V5.109 快速循环评估演示")
    print("="*70)
    
    # 模拟持仓
    portfolio = [
        {
            'symbol': 'TEST001',
            'entry_date': datetime.now() - timedelta(days=3),
            'entry_price': 10.0,
            'current_price': 9.2,
            'entry_return': -0.08  # 亏损8% - 应触发止损
        },
        {
            'symbol': 'TEST002',
            'entry_date': datetime.now() - timedelta(days=3),
            'entry_price': 10.0,
            'current_price': 12.1,
            'entry_return': 0.21  # 盈利21% - 应触发止盈
        },
        {
            'symbol': 'TEST003',
            'entry_date': datetime.now() - timedelta(days=7),
            'entry_price': 10.0,
            'current_price': 9.71,
            'entry_return': -0.029  # 微亏2.9% T+7 - 应触发周期清仓
        },
        {
            'symbol': 'TEST004',
            'entry_date': datetime.now() - timedelta(days=2),
            'entry_price': 10.0,
            'current_price': 10.05,
            'entry_return': 0.005  # 微盈 - 观察期,保持
        }
    ]
    
    evaluator = QuickCycleEvaluator()
    results = evaluator.evaluate_all_positions(portfolio)
    
    print("\n📊 评估结果:")
    print(f"持仓总数: {results['action_summary']['total_positions']}")
    print(f"持仓: {len(results['hold'])}")
    print(f"清仓: {len(results['sell'])}")
    print(f"\n清仓原因分布: {results['action_summary']['by_reason']}")
    
    print("\n💼 清仓详情:")
    for sell_decision in results['sell']:
        print(f"  {sell_decision['symbol']}: {sell_decision['reason']} (收益: {sell_decision.get('return', 'N/A')})")
    
    # 计算指标
    metrics = QuickCycleMetrics.calculate_cycle_metrics(results)
    print("\n📈 快速循环指标:")
    print(f"  持仓率: {metrics['hold_rate']:.1%}")
    print(f"  清仓率: {metrics['exit_rate']:.1%}")
    print(f"  清仓原因: {metrics['exit_breakdown']}")
    print(f"  状态: {metrics['health_check']['status']}")


if __name__ == '__main__':
    demo_quick_cycle_evaluation()
