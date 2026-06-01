#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v5.141 深度优化集成测试
整合3大核心模块：信号融合 + AI补偿 + 市场状态机
"""

import json
import sys
from typing import Dict

# 导入各模块
from v5_141_signal_fusion_engine import SignalWeightOptimizer, SignalFusionReportGenerator
from v5_141_ai_compensation import AICompensationScorer, AICompensationReportGenerator
from v5_141_market_state_machine import MarketStateMachine, StateConfigurationManager


class DeepOptimizationIntegration:
    """
    v5.141深度优化集成系统
    """
    
    def __init__(self):
        # 初始化3大模块
        self.signal_optimizer = SignalWeightOptimizer()
        self.signal_report_gen = SignalFusionReportGenerator(self.signal_optimizer)
        
        self.ai_scorer = AICompensationScorer()
        self.ai_report_gen = AICompensationReportGenerator(self.ai_scorer)
        
        self.state_machine = MarketStateMachine()
        self.config_manager = StateConfigurationManager(self.state_machine)
    
    def run_full_stock_analysis(self, 
                               stock_code: str,
                               stock_name: str,
                               market_cap: float,
                               sentiment_score: float,
                               volatility: float,
                               signals: Dict[str, float],
                               has_longhu_data: bool,
                               volume_data: Dict,
                               institutional_data: Dict,
                               margin_data: Dict,
                               emotion_data: Dict,
                               sector_data: Dict) -> Dict:
        """
        运行完整的股票分析流程
        
        Returns:
            包含所有3个模块结果的完整报告
        """
        
        print(f"\n🔍 分析开始: {stock_name} ({stock_code})")
        print("=" * 80)
        
        # ========== 步骤1: 市场状态机 ==========
        print("\n[1/4] 市场状态转移...")
        transitioned, state_msg = self.state_machine.transition(sentiment_score, volatility)
        print(f"  → {state_msg}")
        
        current_state_desc = self.state_machine.get_state_description()
        print(f"  → 当前状态: {current_state_desc}")
        
        # ========== 步骤2: 动态权重优化 ==========
        print("\n[2/4] 信号融合引擎...")
        signal_report = self.signal_report_gen.generate_report(
            signals=signals,
            sentiment_score=sentiment_score,
            volatility=volatility,
            stock_name=stock_name
        )
        
        optimized_score = signal_report['optimized_score']
        recommendation = signal_report['recommendation']
        print(f"  → 原始信号平均: {sum(signals.values())/len(signals):.1f}")
        print(f"  → 优化后评分: {optimized_score:.1f}")
        print(f"  → 推荐意见: {recommendation}")
        
        # ========== 步骤3: AI补偿评分 ==========
        print("\n[3/4] 龙虎榜AI补偿...")
        ai_report = self.ai_report_gen.generate_report(
            stock_code=stock_code,
            stock_name=stock_name,
            market_cap=market_cap,
            has_longhu_data=has_longhu_data,
            volume_data=volume_data,
            institutional_data=institutional_data,
            margin_data=margin_data,
            emotion_data=emotion_data,
            sector_data=sector_data,
        )
        
        if ai_report['compensation_used']:
            print(f"  → AI补偿评分: {ai_report['final_score']:.1f}")
            print(f"  → 置信度: {ai_report['confidence']}")
        else:
            print(f"  → 使用龙虎榜数据: {ai_report['final_score']:.1f}")
        
        # ========== 步骤4: 配置生成 ==========
        print("\n[4/4] 配置推荐...")
        config = self.state_machine.get_current_config()
        recommendations = self.state_machine.get_action_recommendations()
        
        print(f"  → Kelly系数: {config['kelly_coefficient']}")
        print(f"  → 止损设置: {config['stop_loss']['trailing_stop_pct']*100:.1f}%")
        print(f"  → 最低现金: {config['min_cash_ratio']*100:.0f}%")
        print(f"  → 可加仓: {'是' if self.config_manager.can_add_position() else '否'}")
        print(f"  → 可新建: {'是' if self.config_manager.can_open_new_position() else '否'}")
        
        # ========== 综合评分 ==========
        print("\n" + "=" * 80)
        print("📊 综合评分")
        print("=" * 80)
        
        # 加权融合 (信号75% + AI补偿25%)
        final_score = optimized_score * 0.75 + ai_report['final_score'] * 0.25
        
        print(f"信号融合评分: {optimized_score:.1f} (权重75%)")
        print(f"AI补偿评分: {ai_report['final_score']:.1f} (权重25%)")
        print(f"─" * 40)
        print(f"最终综合评分: {final_score:.1f}")
        print(f"最终推荐: {self._final_recommendation(final_score)}")
        
        # 完整报告
        full_report = {
            'stock_code': stock_code,
            'stock_name': stock_name,
            'market_cap_billion': market_cap,
            'timestamp': '2026-05-29',
            'market_state': {
                'state': self.state_machine.current_state.value,
                'description': current_state_desc,
                'sentiment_score': sentiment_score,
                'volatility': volatility,
            },
            'signal_fusion': signal_report,
            'ai_compensation': ai_report,
            'state_config': {
                'kelly_coefficient': config['kelly_coefficient'],
                'min_cash_ratio': config['min_cash_ratio'],
                'entry_quality_threshold': config['entry_quality_threshold'],
                'can_add_position': self.config_manager.can_add_position(),
                'can_open_new': self.config_manager.can_open_new_position(),
            },
            'action_recommendations': recommendations,
            'final_score': round(final_score, 2),
            'final_recommendation': self._final_recommendation(final_score),
        }
        
        return full_report
    
    def _final_recommendation(self, score: float) -> str:
        """生成最终推荐"""
        if score >= 80:
            return '强烈推荐 🟢🟢🟢'
        elif score >= 70:
            return '推荐 🟢🟢'
        elif score >= 60:
            return '关注 🟡'
        elif score >= 50:
            return '中立关注 🟡'
        elif score >= 40:
            return '谨慎关注 🟠'
        else:
            return '不推荐 🔴'


# ============================================================
# 完整测试场景
# ============================================================

def test_extreme_greed_scenario():
    """测试场景：极度贪婪 + 小盘股"""
    print("\n" + "=" * 100)
    print("🚀 测试场景1: 极度贪婪 + 小盘股 (华映科技)")
    print("=" * 100)
    
    integration = DeepOptimizationIntegration()
    
    # 模拟华映科技在极度贪婪行情下的数据
    report = integration.run_full_stock_analysis(
        stock_code='000536',
        stock_name='华映科技',
        market_cap=20,  # 20亿小盘股
        sentiment_score=94,  # 极度贪婪
        volatility=35,  # 高波动
        signals={
            'technical': 72,      # 技术面强
            'funding': 85,        # 资金面热
            'sentiment': 82,      # 情绪面强
            'fundamental': 55,    # 基本面一般
        },
        has_longhu_data=False,  # 无龙虎榜
        volume_data={
            'current_volume': 2000000,
            'avg_volume_5m': 800000,
        },
        institutional_data={
            'large_order_count': 5,
            'large_order_ratio': 0.40,
            'institutional_buying_pct': 0.60,
        },
        margin_data={
            'margin_balance': 8000000,
            'margin_balance_yesterday': 7500000,
        },
        emotion_data={
            'stock_returns': [0.03, 0.02, 0.015, 0.025, 0.020, 0.01, 0.015, 0.025, 0.02, 0.025],
            'sentiment_scores': [88, 90, 91, 92, 93, 94, 94, 95, 94, 94],
        },
        sector_data={
            'stock_return_pct': 3.2,
            'sector_return_pct': 2.8,
            'sector_gainers_pct': 0.75,
        },
    )
    
    return report


def test_fear_scenario():
    """测试场景：恐惧 + 中盘股"""
    print("\n" + "=" * 100)
    print("📉 测试场景2: 恐惧 + 中盘股 (东方证券)")
    print("=" * 100)
    
    integration = DeepOptimizationIntegration()
    
    # 模拟东方证券在恐惧行情下的数据
    report = integration.run_full_stock_analysis(
        stock_code='600675',
        stock_name='东方证券',
        market_cap=180,  # 180亿中盘股
        sentiment_score=32,  # 恐惧
        volatility=28,  # 中等波动
        signals={
            'technical': 65,      # 技术面中等
            'funding': 58,        # 资金面弱
            'sentiment': 35,      # 情绪面弱
            'fundamental': 72,    # 基本面强
        },
        has_longhu_data=True,  # 有龙虎榜
        volume_data={
            'current_volume': 1200000,
            'avg_volume_5m': 900000,
            'longhu_score': 65,
        },
        institutional_data={
            'large_order_count': 2,
            'large_order_ratio': 0.20,
            'institutional_buying_pct': 0.35,
        },
        margin_data={
            'margin_balance': 3000000,
            'margin_balance_yesterday': 3200000,
        },
        emotion_data={
            'stock_returns': [-0.01, -0.005, 0.01, -0.02, -0.015, 0.005, -0.01, 0.01, 0.005, 0.015],
            'sentiment_scores': [35, 33, 32, 30, 32, 33, 32, 31, 32, 32],
        },
        sector_data={
            'stock_return_pct': -0.5,
            'sector_return_pct': -1.2,
            'sector_gainers_pct': 0.35,
        },
    )
    
    return report


def test_neutral_scenario():
    """测试场景：中性 + 大盘股"""
    print("\n" + "=" * 100)
    print("📊 测试场景3: 中性 + 大盘股 (贵州茅台)")
    print("=" * 100)
    
    integration = DeepOptimizationIntegration()
    
    # 模拟贵州茅台在中性行情下的数据
    report = integration.run_full_stock_analysis(
        stock_code='600519',
        stock_name='贵州茅台',
        market_cap=2500,  # 2500亿大盘股
        sentiment_score=58,  # 中性
        volatility=18,  # 低波动
        signals={
            'technical': 68,      # 技术面一般
            'funding': 62,        # 资金面一般
            'sentiment': 55,      # 情绪面中立
            'fundamental': 75,    # 基本面强
        },
        has_longhu_data=True,  # 有龙虎榜
        volume_data={
            'current_volume': 5000000,
            'avg_volume_5m': 4500000,
            'longhu_score': 72,
        },
        institutional_data={
            'large_order_count': 8,
            'large_order_ratio': 0.50,
            'institutional_buying_pct': 0.55,
        },
        margin_data={
            'margin_balance': 15000000,
            'margin_balance_yesterday': 14500000,
        },
        emotion_data={
            'stock_returns': [0.005, 0.01, 0.005, 0.008, 0.012, 0.010, 0.006, 0.008, 0.010, 0.009],
            'sentiment_scores': [55, 57, 58, 60, 59, 58, 57, 58, 59, 58],
        },
        sector_data={
            'stock_return_pct': 1.2,
            'sector_return_pct': 0.9,
            'sector_gainers_pct': 0.60,
        },
    )
    
    return report


if __name__ == '__main__':
    print("\n" + "=" * 100)
    print("v5.141 深度优化集成测试 - 开始")
    print("=" * 100)
    
    # 运行3个测试场景
    try:
        report1 = test_extreme_greed_scenario()
        print("\n✅ 场景1测试完成")
        print(f"   最终评分: {report1['final_score']:.1f}")
        print(f"   推荐: {report1['final_recommendation']}")
    except Exception as e:
        print(f"❌ 场景1测试失败: {e}")
    
    try:
        report2 = test_fear_scenario()
        print("\n✅ 场景2测试完成")
        print(f"   最终评分: {report2['final_score']:.1f}")
        print(f"   推荐: {report2['final_recommendation']}")
    except Exception as e:
        print(f"❌ 场景2测试失败: {e}")
    
    try:
        report3 = test_neutral_scenario()
        print("\n✅ 场景3测试完成")
        print(f"   最终评分: {report3['final_score']:.1f}")
        print(f"   推荐: {report3['final_recommendation']}")
    except Exception as e:
        print(f"❌ 场景3测试失败: {e}")
    
    print("\n" + "=" * 100)
    print("✅ 所有测试完成")
    print("=" * 100)
