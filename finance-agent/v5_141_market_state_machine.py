#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v5.141 市场状态机 - 完整的市场态状转移和配置管理
五种市场状态 + 自动转移逻辑 + 状态相关配置
"""

import json
from enum import Enum
from typing import Dict, List, Tuple, Optional
from datetime import datetime


class MarketState(Enum):
    """市场状态枚举"""
    EXTREME_GREED = 'extreme_greed'      # 极度贪婪 (>92)
    GREED = 'greed'                      # 贪婪 (80-92)
    NEUTRAL = 'neutral'                  # 中性 (40-80)
    FEAR = 'fear'                        # 恐惧 (20-40)
    EXTREME_FEAR = 'extreme_fear'        # 极度恐惧 (<20)


class MarketStateMachine:
    """
    市场状态机
    根据情绪分数和波动率自动转移状态，并应用对应配置
    """
    
    def __init__(self):
        # 状态定义 (情绪分数范围)
        self.state_ranges = {
            MarketState.EXTREME_GREED: (92, 100),
            MarketState.GREED: (80, 92),
            MarketState.NEUTRAL: (40, 80),
            MarketState.FEAR: (20, 40),
            MarketState.EXTREME_FEAR: (0, 20),
        }
        
        # 状态配置字典
        self.state_configs = self._build_state_configs()
        
        # 状态转移历史
        self.state_history = []
        
        # 当前状态
        self.current_state = MarketState.NEUTRAL
        self.current_sentiment = 50
        self.transition_timestamp = None
    
    def _build_state_configs(self) -> Dict:
        """
        构建各市场状态的配置参数
        """
        return {
            MarketState.EXTREME_GREED: {
                'description': '极度贪婪 - 风控优先',
                'sentiment_range': (92, 100),
                'priority': '风控',
                'position_management': {
                    'max_positions': 3,               # 最多持仓数
                    'position_size': 0.10,            # 单笔最大仓位
                    'add_position_enabled': False,    # 禁止加仓
                    'new_entry_enabled': False,       # 禁止新建头寸
                },
                'stop_loss': {
                    'trailing_stop_pct': 0.025,       # 尾随止损 2.5%
                    'fixed_stop_pct': None,           # 无固定止损
                    'urgency_level': 'high',          # 快速止损
                },
                'profit_taking': {
                    'enabled': True,
                    'levels': [
                        {'profit': 0.05, 'sell_ratio': 0.25},   # 5% 卖25%
                        {'profit': 0.10, 'sell_ratio': 0.30},   # 10% 卖30%
                        {'profit': 0.18, 'sell_ratio': 0.25},   # 18% 卖25%
                    ],
                },
                'kelly_coefficient': 1.35,           # Kelly系数 (保守)
                'min_cash_ratio': 0.15,              # 最低现金 15%
                'entry_quality_threshold': 25,       # 进场门槛 (高)
            },
            
            MarketState.GREED: {
                'description': '贪婪 - 技术+资金平衡',
                'sentiment_range': (80, 92),
                'priority': '平衡',
                'position_management': {
                    'max_positions': 5,
                    'position_size': 0.12,
                    'add_position_enabled': True,
                    'new_entry_enabled': True,
                    'add_position_limit': 0.5,        # 加仓限制 (最多加50%)
                },
                'stop_loss': {
                    'trailing_stop_pct': 0.04,        # 尾随止损 4%
                    'fixed_stop_pct': 0.07,           # 固定止损 7%
                    'urgency_level': 'normal',
                },
                'profit_taking': {
                    'enabled': True,
                    'levels': [
                        {'profit': 0.03, 'sell_ratio': 0.17},   # 3% 卖17%
                        {'profit': 0.08, 'sell_ratio': 0.33},   # 8% 卖33%
                        {'profit': 0.15, 'sell_ratio': 0.25},   # 15% 卖25%
                    ],
                },
                'kelly_coefficient': 1.60,           # Kelly系数 (平衡)
                'min_cash_ratio': 0.08,              # 最低现金 8%
                'entry_quality_threshold': 15,       # 进场门槛 (中等)
            },
            
            MarketState.NEUTRAL: {
                'description': '中性 - 技术面主导',
                'sentiment_range': (40, 80),
                'priority': '进攻',
                'position_management': {
                    'max_positions': 8,
                    'position_size': 0.15,
                    'add_position_enabled': True,
                    'new_entry_enabled': True,
                    'add_position_limit': 1.0,        # 加仓无限制
                },
                'stop_loss': {
                    'trailing_stop_pct': 0.05,        # 尾随止损 5%
                    'fixed_stop_pct': 0.08,           # 固定止损 8%
                    'urgency_level': 'low',
                },
                'profit_taking': {
                    'enabled': True,
                    'levels': [
                        {'profit': 0.05, 'sell_ratio': 0.20},   # 5% 卖20%
                        {'profit': 0.10, 'sell_ratio': 0.30},   # 10% 卖30%
                        {'profit': 0.20, 'sell_ratio': 0.20},   # 20% 卖20%
                    ],
                },
                'kelly_coefficient': 1.75,           # Kelly系数 (激进)
                'min_cash_ratio': 0.05,              # 最低现金 5%
                'entry_quality_threshold': 12,       # 进场门槛 (低)
            },
            
            MarketState.FEAR: {
                'description': '恐惧 - 基本面+技术',
                'sentiment_range': (20, 40),
                'priority': '加仓防御',
                'position_management': {
                    'max_positions': 10,
                    'position_size': 0.08,            # 单笔仓位减小
                    'add_position_enabled': True,
                    'new_entry_enabled': True,
                    'add_position_limit': 2.0,        # 加仓可以翻倍
                    'bottom_fish_enabled': True,      # 扫底买入
                },
                'stop_loss': {
                    'trailing_stop_pct': 0.06,        # 尾随止损 6%
                    'fixed_stop_pct': 0.10,           # 固定止损 10%
                    'urgency_level': 'low',
                    'ma_breakout_stop': True,         # 均线破位止损
                },
                'profit_taking': {
                    'enabled': False,                 # 恐惧下不止盈, 持股待涨
                    'levels': [],
                },
                'kelly_coefficient': 1.90,           # Kelly系数 (最激进)
                'min_cash_ratio': 0.02,              # 最低现金 2%
                'entry_quality_threshold': 8,        # 进场门槛 (极低)
            },
            
            MarketState.EXTREME_FEAR: {
                'description': '极度恐惧 - 基本面优先满仓防御',
                'sentiment_range': (0, 20),
                'priority': '满仓防御',
                'position_management': {
                    'max_positions': 12,
                    'position_size': 0.06,            # 单笔仓位最小
                    'add_position_enabled': True,
                    'new_entry_enabled': True,
                    'add_position_limit': 3.0,        # 加仓可翻3倍
                    'bottom_fish_enabled': True,
                    'all_in_enabled': True,           # 允许满仓
                },
                'stop_loss': {
                    'trailing_stop_pct': 0.08,        # 尾随止损 8%
                    'fixed_stop_pct': 0.12,           # 固定止损 12%
                    'urgency_level': 'minimal',       # 最小化止损
                    'ma_breakout_stop': True,
                },
                'profit_taking': {
                    'enabled': False,                 # 不止盈
                    'levels': [],
                },
                'kelly_coefficient': 2.00,           # Kelly系数 (最大)
                'min_cash_ratio': 0.00,              # 可以满仓
                'entry_quality_threshold': 5,        # 进场门槛 (极低)
            },
        }
    
    def get_state(self, sentiment_score: float) -> MarketState:
        """
        根据情绪分数获取市场状态
        """
        for state, (min_score, max_score) in self.state_ranges.items():
            if min_score <= sentiment_score < max_score:
                return state
        
        # 默认中性
        return MarketState.NEUTRAL
    
    def transition(self, new_sentiment_score: float, 
                  volatility: float = 25.0) -> Tuple[bool, str]:
        """
        执行状态转移
        
        Args:
            new_sentiment_score: 新的情绪分数
            volatility: 市场波动率
            
        Returns:
            (是否发生转移, 转移描述)
        """
        new_state = self.get_state(new_sentiment_score)
        
        # 检测是否发生转移
        if new_state != self.current_state:
            old_state = self.current_state
            self.current_state = new_state
            self.current_sentiment = new_sentiment_score
            self.transition_timestamp = datetime.now()
            
            # 记录转移历史
            self.state_history.append({
                'timestamp': self.transition_timestamp.isoformat(),
                'from_state': old_state.value,
                'to_state': new_state.value,
                'sentiment': new_sentiment_score,
                'volatility': volatility,
            })
            
            message = f'状态转移: {old_state.value} → {new_state.value} (情绪: {new_sentiment_score:.1f})'
            return True, message
        else:
            # 状态未改变，仅更新情绪分数
            self.current_sentiment = new_sentiment_score
            return False, f'状态未变化, 保持 {self.current_state.value}'
    
    def get_current_config(self) -> Dict:
        """
        获取当前市场状态的配置
        """
        return self.state_configs[self.current_state]
    
    def get_config_by_state(self, state: MarketState) -> Dict:
        """
        获取指定市场状态的配置
        """
        return self.state_configs[state]
    
    def get_state_description(self) -> str:
        """
        获取当前状态的描述
        """
        config = self.get_current_config()
        return config['description']
    
    def get_action_recommendations(self) -> Dict[str, str]:
        """
        根据当前状态获取建议的操作
        """
        state = self.current_state
        
        recommendations = {
            MarketState.EXTREME_GREED: {
                'position': '禁止新建头寸 | 减少加仓',
                'stop_loss': '激活快速止损 (2.5%)',
                'profit_taking': '启用多级止盈 (5% → 10% → 18%)',
                'cash_management': '保留充足现金 (15%+)',
                'risk_control': '最大限度风控，准备回调',
            },
            MarketState.GREED: {
                'position': '适度建仓 | 加仓限制50%',
                'stop_loss': '标准止损 (4%)',
                'profit_taking': '启用多级止盈 (3% → 8% → 15%)',
                'cash_management': '保留适量现金 (8%)',
                'risk_control': '平衡进攻与防守',
            },
            MarketState.NEUTRAL: {
                'position': '积极建仓 | 加仓无限制',
                'stop_loss': '标准止损 (5%)',
                'profit_taking': '适度止盈 (5% → 10% → 20%)',
                'cash_management': '最低现金保留 (5%)',
                'risk_control': '关注技术面信号',
            },
            MarketState.FEAR: {
                'position': '加仓优先 | 扫底买入',
                'stop_loss': '宽松止损 (6%) | 均线破位',
                'profit_taking': '不止盈，持股待涨',
                'cash_management': '少量现金 (2%)',
                'risk_control': '基本面+技术面双核驱动',
            },
            MarketState.EXTREME_FEAR: {
                'position': '满仓防御 | 全力加仓',
                'stop_loss': '最宽松 (8%) | 均线保护',
                'profit_taking': '不止盈，坚定持股',
                'cash_management': '可满仓 (0%)',
                'risk_control': '等待情绪反转做多',
            },
        }
        
        return recommendations[state]
    
    def get_state_history_summary(self) -> Dict:
        """
        获取状态转移历史总结
        """
        if not self.state_history:
            return {'count': 0, 'message': '无状态转移记录'}
        
        # 统计各状态转移次数
        transitions_count = {}
        for record in self.state_history:
            key = f"{record['from_state']} → {record['to_state']}"
            transitions_count[key] = transitions_count.get(key, 0) + 1
        
        return {
            'total_transitions': len(self.state_history),
            'transitions_count': transitions_count,
            'current_state': self.current_state.value,
            'current_sentiment': self.current_sentiment,
            'last_transition_time': self.state_history[-1]['timestamp'] if self.state_history else None,
        }


class StateConfigurationManager:
    """
    状态配置管理器
    用于获取、验证、修改状态配置
    """
    
    def __init__(self, state_machine: MarketStateMachine):
        self.state_machine = state_machine
    
    def get_position_config(self) -> Dict:
        """获取当前状态的仓位配置"""
        config = self.state_machine.get_current_config()
        return config['position_management']
    
    def get_stop_loss_config(self) -> Dict:
        """获取当前状态的止损配置"""
        config = self.state_machine.get_current_config()
        return config['stop_loss']
    
    def get_profit_taking_config(self) -> Dict:
        """获取当前状态的止盈配置"""
        config = self.state_machine.get_current_config()
        return config['profit_taking']
    
    def get_kelly_coefficient(self) -> float:
        """获取当前状态的Kelly系数"""
        config = self.state_machine.get_current_config()
        return config['kelly_coefficient']
    
    def get_min_cash_ratio(self) -> float:
        """获取当前状态的最低现金比例"""
        config = self.state_machine.get_current_config()
        return config['min_cash_ratio']
    
    def get_entry_quality_threshold(self) -> float:
        """获取当前状态的进场门槛"""
        config = self.state_machine.get_current_config()
        return config['entry_quality_threshold']
    
    def can_add_position(self) -> bool:
        """判断是否可以加仓"""
        config = self.get_position_config()
        return config['add_position_enabled']
    
    def can_open_new_position(self) -> bool:
        """判断是否可以新建头寸"""
        config = self.get_position_config()
        return config['new_entry_enabled']


# ============================================================
# 测试用例
# ============================================================

if __name__ == '__main__':
    print("=" * 80)
    print("市场状态机 - 完整测试")
    print("=" * 80)
    
    fsm = MarketStateMachine()
    config_mgr = StateConfigurationManager(fsm)
    
    # 测试场景：模拟情绪分数的变化
    sentiment_scores = [
        (50, '初始中性'),
        (75, '进入贪婪'),
        (88, '深度贪婪'),
        (95, '极度贪婪'),
        (85, '回到贪婪'),
        (55, '回到中性'),
        (30, '进入恐惧'),
        (15, '极度恐惧'),
    ]
    
    for sentiment, description in sentiment_scores:
        print(f"\n📊 {description} (情绪: {sentiment})")
        print("-" * 80)
        
        transitioned, message = fsm.transition(sentiment)
        print(f"✓ {message}")
        
        current_config = fsm.get_current_config()
        print(f"当前状态: {current_config['description']}")
        print(f"优先级: {current_config['priority']}")
        print(f"Kelly系数: {current_config['kelly_coefficient']}")
        print(f"最低现金: {current_config['min_cash_ratio']*100:.0f}%")
        
        recommendations = fsm.get_action_recommendations()
        print("\n📋 操作建议:")
        for key, value in recommendations.items():
            print(f"  {key}: {value}")
    
    # 总结
    print("\n" + "=" * 80)
    print("状态转移历史总结")
    print("=" * 80)
    
    history_summary = fsm.get_state_history_summary()
    print(json.dumps(history_summary, indent=2, ensure_ascii=False))
    
    print("\n✅ 市场状态机测试完成")
