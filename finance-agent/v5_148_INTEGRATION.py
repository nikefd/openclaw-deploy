"""
v5.148 集成模块 - 将深度优化V⁴级别集成到stock_picker.py和daily_runner.py

集成点：
  1. stock_picker.py: score_and_rank() → 使用多因子融合3.5替代简单加权
  2. daily_runner.py: 在每日选股前执行Kelly动态调整
  3. position_manager.py: 监听强制减仓机制
  4. daily_runner.py: 资金配置优化影响选股门槛
"""

import sqlite3
import json
from datetime import datetime
from typing import Dict, List, Tuple

try:
    from v5_148_DEEP_OPTIMIZE_V4 import (
        KellyDynamicAdjustment,
        MultiFactorSignalFusion35,
        ForcedPositionReduction,
        DynamicCashOptimization,
        execute_v5_148_deep_optimize
    )
    V5_148_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ v5.148模块未加载: {e}")
    V5_148_AVAILABLE = False


class V5148Handler:
    """v5.148优化处理器"""
    
    def __init__(self, config_path: str = 'config.py'):
        self.kelly_engine = KellyDynamicAdjustment()
        self.fusion_engine = MultiFactorSignalFusion35()
        self.reducer_engine = ForcedPositionReduction()
        self.cash_engine = DynamicCashOptimization()
        self.optimization_log = []
    
    def get_kelly_adjustment(self,
                           recent_trades: List[Dict],
                           current_sentiment: float,
                           cash_ratio: float) -> Dict:
        """获取Kelly系数调整建议"""
        
        if not recent_trades or len(recent_trades) < 5:
            return {
                'kelly_multiplier': 1.0,
                'kelly_applied': 1.75,
                'reason': '交易数据不足，使用基础Kelly'
            }
        
        # 计算统计指标
        wins = sum(1 for t in recent_trades[-20:] if t.get('is_win', False))
        win_rate = wins / min(20, len(recent_trades)) if recent_trades else 0.60
        
        recent_drawdowns = [t.get('pnl_pct', 0) for t in recent_trades[-10:]]
        recent_dd = min(recent_drawdowns) if recent_drawdowns else -0.02
        
        # 计算连亏
        consecutive_losses = 0
        for t in reversed(recent_trades[-10:]):
            if t.get('is_win', False):
                break
            consecutive_losses += 1
        
        volatility_atr = 0.022  # 应从市场数据实时计算
        
        result = self.kelly_engine.calculate_kelly_multiplier(
            win_rate=win_rate,
            recent_drawdown=recent_dd,
            volatility_atr=volatility_atr,
            sentiment_score=current_sentiment,
            cash_ratio=cash_ratio,
            consecutive_losses=consecutive_losses
        )
        
        self.optimization_log.append({
            'type': 'kelly_adjustment',
            'timestamp': datetime.now().isoformat(),
            'result': result
        })
        
        return result
    
    def apply_multi_factor_fusion(self,
                                 symbol: str,
                                 technical_signals: Dict,
                                 fund_signals: Dict,
                                 sentiment_signals: Dict,
                                 sector_signals: Dict,
                                 sentiment_score: float) -> Dict:
        """应用多因子融合3.5获取综合评分"""
        
        fusion_result = self.fusion_engine.fuse_signals(
            symbol=symbol,
            technical_signals=technical_signals,
            fund_flow_signals=fund_signals,
            sentiment_signals=sentiment_signals,
            sector_signals=sector_signals,
            sentiment_score=sentiment_score
        )
        
        return fusion_result
    
    def check_forced_reductions(self,
                               positions: Dict,
                               market_data: Dict,
                               sentiment_score: float) -> List[Dict]:
        """检查强制减仓机制"""
        
        actions = self.reducer_engine.check_forced_reductions(
            positions=positions,
            market_data=market_data,
            sentiment_score=sentiment_score
        )
        
        if actions:
            self.optimization_log.append({
                'type': 'forced_reductions',
                'timestamp': datetime.now().isoformat(),
                'actions': actions
            })
        
        return actions
    
    def optimize_cash_allocation(self,
                                cash_ratio: float,
                                total_value: float,
                                recent_win_rate: float,
                                sentiment_score: float,
                                kelly: float) -> Dict:
        """资金配置动态优化"""
        
        result = self.cash_engine.optimize_cash_allocation(
            cash_ratio=cash_ratio,
            total_value=total_value,
            recent_win_rate=recent_win_rate,
            sentiment_score=sentiment_score,
            kelly=kelly
        )
        
        self.optimization_log.append({
            'type': 'cash_optimization',
            'timestamp': datetime.now().isoformat(),
            'result': result
        })
        
        return result
    
    def get_entry_quality_threshold_adjustment(self, cash_ratio: float) -> int:
        """根据现金比例获取入场质量阈值调整"""
        
        cash_modes = {
            'ULTRA_AGGRESSIVE': -50,
            'AGGRESSIVE': -25,
            'NORMAL': 0,
            'CONSERVATIVE': 25,
            'DEFENSIVE': 50
        }
        
        for mode, (min_ratio, max_ratio) in [
            ('ULTRA_AGGRESSIVE', (0.95, 1.0)),
            ('AGGRESSIVE', (0.70, 0.95)),
            ('NORMAL', (0.50, 0.70)),
            ('CONSERVATIVE', (0.30, 0.50)),
            ('DEFENSIVE', (0.0, 0.30))
        ]:
            if min_ratio <= cash_ratio < max_ratio:
                return cash_modes[mode]
        
        return 0  # 默认无调整
    
    def save_optimization_log(self, db_path: str = 'data/trading.db'):
        """保存优化日志到数据库"""
        
        try:
            conn = sqlite3.connect(db_path)
            c = conn.cursor()
            
            # 创建表 (如果不存在)
            c.execute("""
                CREATE TABLE IF NOT EXISTS optimization_logs (
                    id INTEGER PRIMARY KEY,
                    timestamp TEXT,
                    version TEXT,
                    optimization_type TEXT,
                    details TEXT
                )
            """)
            
            for log in self.optimization_log:
                c.execute("""
                    INSERT INTO optimization_logs (timestamp, version, optimization_type, details)
                    VALUES (?, ?, ?, ?)
                """, (
                    log['timestamp'],
                    'v5.148',
                    log['type'],
                    json.dumps(log, default=str)
                ))
            
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"⚠️ 保存优化日志失败: {e}")


# =================== 集成函数供daily_runner.py使用 ===================

def integrate_v5_148_pre_picking(
    cash_available: float,
    total_portfolio_value: float,
    recent_trades: List[Dict],
    current_sentiment: float,
    current_positions: Dict = None
) -> Dict:
    """
    在选股前执行v5.148优化
    
    供daily_runner.py在start_of_day()时调用
    
    返回: {
        'kelly_adjustment': {...},
        'cash_optimization': {...},
        'entry_quality_adjust': int,
        'forced_reductions': List[Dict],
        'ready_to_pick': bool
    }
    """
    
    if not V5_148_AVAILABLE:
        return {'ready_to_pick': True, 'version': 'fallback'}
    
    handler = V5148Handler()
    
    # 计算现金比例
    cash_ratio = cash_available / total_portfolio_value if total_portfolio_value > 0 else 1.0
    
    # ① Kelly动态调整
    kelly_result = handler.get_kelly_adjustment(
        recent_trades=recent_trades,
        current_sentiment=current_sentiment,
        cash_ratio=cash_ratio
    )
    
    # ② 资金配置优化
    recent_win_rate = sum(1 for t in recent_trades[-20:] if t.get('is_win', False)) / min(20, len(recent_trades)) if recent_trades else 0.60
    cash_result = handler.optimize_cash_allocation(
        cash_ratio=cash_ratio,
        total_value=total_portfolio_value,
        recent_win_rate=recent_win_rate,
        sentiment_score=current_sentiment,
        kelly=kelly_result['kelly_applied']
    )
    
    # ③ 入场质量阈值调整
    entry_quality_adjust = handler.get_entry_quality_threshold_adjustment(cash_ratio)
    
    # ④ 强制减仓检查 (如果有现有持仓)
    forced_reductions = []
    if current_positions:
        market_data = {}  # 应从实时数据获取
        forced_reductions = handler.check_forced_reductions(
            positions=current_positions,
            market_data=market_data,
            sentiment_score=current_sentiment
        )
    
    # 保存日志
    handler.save_optimization_log()
    
    return {
        'kelly_adjustment': kelly_result,
        'cash_optimization': cash_result,
        'entry_quality_adjust': entry_quality_adjust,
        'forced_reductions': forced_reductions,
        'ready_to_pick': True,
        'version': 'v5.148',
        'timestamp': datetime.now().isoformat()
    }


def integrate_v5_148_score_adjustment(
    base_score: float,
    cash_ratio: float,
    signal_fusion_result: Dict,
    sentiment_score: float
) -> Dict:
    """
    调整基础评分 (用于stock_picker.py中的score_and_rank)
    
    返回: {
        'adjusted_score': float,
        'fusion_quality': float,
        'false_signal_risk': float,
        'adjustment_reason': str
    }
    """
    
    if not V5_148_AVAILABLE or not signal_fusion_result:
        return {'adjusted_score': base_score, 'version': 'fallback'}
    
    # 基础分数来自多因子融合
    fusion_score = signal_fusion_result.get('composite_score', base_score)
    
    # 虚假信号风险调整
    false_signal_risk = signal_fusion_result.get('false_signal_risk', 0)
    risk_adjusted = fusion_score * (1 - false_signal_risk)
    
    # 现金比例调整
    cash_handler = V5148Handler()
    entry_quality_adjust = cash_handler.get_entry_quality_threshold_adjustment(cash_ratio)
    final_score = risk_adjusted + entry_quality_adjust
    
    return {
        'adjusted_score': final_score,
        'fusion_score': fusion_score,
        'false_signal_risk': false_signal_risk,
        'risk_adjusted_score': risk_adjusted,
        'cash_adjust': entry_quality_adjust,
        'adjustment_reason': f'多因子融合({fusion_score:.1f}) -> 风险调整({risk_adjusted:.1f}) -> 现金调整({entry_quality_adjust:+d}分) = {final_score:.1f}分'
    }


if __name__ == '__main__':
    # 演示：集成函数使用
    print("v5.148集成模块已加载")
    print(f"v5.148可用: {V5_148_AVAILABLE}")
    
    if V5_148_AVAILABLE:
        # 模拟选股前优化
        result = integrate_v5_148_pre_picking(
            cash_available=500000,
            total_portfolio_value=1000000,
            recent_trades=[
                {'pnl_pct': 0.05, 'is_win': True},
                {'pnl_pct': -0.03, 'is_win': False},
                {'pnl_pct': 0.08, 'is_win': True},
            ],
            current_sentiment=78.5
        )
        
        print("\n选股前v5.148优化结果:")
        print(json.dumps(result, indent=2, default=str))
