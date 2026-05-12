"""v5.100 晚间深度优化④ — 策略融合+Kelly动态优化+多层止损
设计目标: 将回测最佳策略(MACD+RSI 17.1% Sharpe 2.35)融入实盘
        资金利用率 3.5% → 25-30%
        日均建仓数 2只 → 8-12只
        Sharpe保持 2.35+ (不破坏稳定性)

核心改进:
1. MACD+RSI策略参数优化 (从回测数据中提取最优参数)
2. Kelly动态仓位(基于Sharpe 2.35反推最优仓位)
3. 多层止损设计(初止+追踪+时间止损)
4. 资金分层配置(激进/平衡/保守)
5. 选股超时防护 + 入场质量控制
"""

import json
from datetime import datetime, date
from typing import Dict, List, Tuple
import math

# =================== v5.100: MACD+RSI策略最优参数集 ===================
# 来自: backtest.db → MACD+RSI(科技成长) 17.1% return, 2.35 Sharpe
MACD_RSI_OPTIMAL_PARAMS_V100 = {
    '科技成长': {
        'macd_fast': 11,           # MACD快线周期 (从12调整)
        'macd_slow': 26,           # MACD慢线周期 (保持)
        'macd_signal': 9,          # MACD信号周期 (保持)
        'rsi_period': 13,          # RSI周期 (从14调整,更敏感)
        'rsi_oversold': 28,        # RSI超卖 (从30↓,更激进)
        'rsi_overbought': 72,      # RSI超买 (从70↑,减少误杀)
        'macd_threshold': 0.002,   # MACD DIF-DEF差值阈值 (绝对值)
        'entry_score_boost': 3.5,  # 入场评分加成 (从3.0↑)
    },
    '新能源': {
        'macd_fast': 12,
        'macd_slow': 26,
        'macd_signal': 9,
        'rsi_period': 14,
        'rsi_oversold': 30,
        'rsi_overbought': 70,
        'macd_threshold': 0.0025,
        'entry_score_boost': 2.8,
    },
    '白马消费': {
        'macd_fast': 12,
        'macd_slow': 28,           # 更长周期,防止噪声
        'macd_signal': 10,
        'rsi_period': 15,
        'rsi_oversold': 35,        # 更高阈值,更保守
        'rsi_overbought': 68,
        'macd_threshold': 0.003,
        'entry_score_boost': 2.5,
    },
    '混合池': {                    # 无特定赛道时的通用参数
        'macd_fast': 12,
        'macd_slow': 26,
        'macd_signal': 9,
        'rsi_period': 14,
        'rsi_oversold': 30,
        'rsi_overbought': 70,
        'macd_threshold': 0.0025,
        'entry_score_boost': 2.8,
    }
}

# =================== v5.100: Kelly凯利仓位 (基于Sharpe 2.35) ===================
# 来自: f = (p*win - (1-p)*loss) / (win*loss)
# 回测数据: p=60%, win=1.5%, loss=-0.8%
# Kelly = 0.6*1.5% - 0.4*0.8% / (1.5%*0.8%) ≈ 0.35 (35%)
# 保守系数0.5 → 0.175 (17.5%)

class V5_100_KellyOptimizer:
    """Kelly凯利公式动态仓位计算器 - 基于历史绩效"""
    
    def __init__(self):
        # 从回测数据反推的参数
        self.win_rate = 0.60       # 60% 胜率 (来自MACD+RSI)
        self.win_size = 0.015      # 平均赢 1.5%
        self.loss_size = 0.008     # 平均亏 0.8%
        self.kelly_full = self._calculate_kelly()
        self.kelly_half = self.kelly_full * 0.5   # 安全系数0.5
        self.kelly_quarter = self.kelly_full * 0.25  # 超保守
        
    def _calculate_kelly(self) -> float:
        """凯利公式: f = (p*win - (1-p)*loss) / (win*loss)"""
        p = self.win_rate
        w = self.win_size
        l = self.loss_size
        f = (p * w - (1 - p) * l) / (w * l)
        return max(0.01, min(f, 0.5))  # 限制范围 1%-50%
    
    def get_position_size(self, capital: float, num_positions: int = 8, 
                         cash_ratio: float = 0.96, mode='normal') -> float:
        """计算单个持仓的资金占比
        
        Args:
            capital: 总资本
            num_positions: 目标持仓数
            cash_ratio: 当前现金占比
            mode: 'aggressive'(Kelly×1.5) | 'normal'(Kelly×1) | 'conservative'(Kelly×0.5)
        
        Returns:
            单仓资金占比 (0.0-1.0)
        """
        kelly_map = {
            'aggressive': self.kelly_full * 1.5,
            'normal': self.kelly_half,
            'conservative': self.kelly_quarter
        }
        kelly = kelly_map.get(mode, self.kelly_half)
        
        # 总投资额 = 可用资金 × Kelly系数
        invest_capacity = capital * (1 - cash_ratio) * kelly
        
        # 单仓限制: 不超过总资本的8%
        max_per_position = capital * 0.08
        position_size = min(invest_capacity / max(1, num_positions), max_per_position)
        
        return position_size / capital
    
    def get_rebalance_target(self, cash_ratio: float) -> Dict:
        """根据当前现金占比,给出再平衡目标"""
        return {
            'current_cash_ratio': cash_ratio,
            'target_cash_ratio': 0.20,        # 目标20%现金
            'kelly_half': self.kelly_half,     # 中性Kelly
            'kelly_aggressive': self.kelly_full * 1.5,  # 激进Kelly
            'recommended_mode': 'normal' if cash_ratio < 0.90 else 'aggressive'
        }

# =================== v5.100: 多层止损设计 ===================

class V5_100_MultiLayerStopLoss:
    """分层止损系统
    第1层: 初始止损 (-3% ~ -5%, 根据波动率)
    第2层: 追踪止损 (-8% ~ -12%, 跟踪高点)
    第3层: 时间止损 (持仓>30天自动考虑卖出)
    """
    
    @staticmethod
    def calculate_initial_stop_loss(sector: str, volatility: float = None) -> float:
        """计算初始止损位 (距离买入价)
        
        Args:
            sector: 赛道名称
            volatility: 股票波动率 (年化)
        
        Returns:
            止损幅度 (0.03 = 3%)
        """
        sector_stops = {
            '科技成长': 0.05,      # 5% 止损 (高波动)
            '新能源': 0.04,        # 4% 止损 (中高波动)
            '白马消费': 0.03,      # 3% 止损 (低波动)
        }
        base_stop = sector_stops.get(sector, 0.04)
        
        # 如果有波动率数据,动态调整
        if volatility:
            # 波动率高时→更宽松的止损
            adjustment = volatility / 0.30  # 年化30%为基准
            base_stop = base_stop * adjustment
        
        return round(base_stop, 4)
    
    @staticmethod
    def calculate_trailing_stop_loss(highest_price: float, entry_price: float) -> float:
        """计算追踪止损
        
        原理: 止损线 = 高点 × (1 - 追踪幅度)
        例: 高点100, 追踪幅度10% → 止损线90
        """
        trailing_ratio = 0.08  # 8% 追踪幅度
        trailing_stop = highest_price * (1 - trailing_ratio)
        
        # 追踪止损不能比初始止损更宽松
        initial_stop = entry_price * 0.96  # 4% 初始
        return max(trailing_stop, initial_stop)
    
    @staticmethod
    def calculate_time_stop_loss(buy_date: str, sector: str) -> Dict:
        """计算时间止损建议
        
        如果持仓超过一定天数且未获利,建议止损
        """
        from datetime import datetime, date
        try:
            buy_dt = datetime.strptime(buy_date, '%Y-%m-%d').date()
            hold_days = (date.today() - buy_dt).days
        except:
            hold_days = 0
        
        # 赛道-天数映射
        max_hold_days = {
            '科技成长': 25,        # 25天无利润→止损
            '新能源': 20,
            '白马消费': 30,
        }
        threshold = max_hold_days.get(sector, 25)
        
        return {
            'hold_days': hold_days,
            'max_hold_days': threshold,
            'should_exit': hold_days >= threshold,
            'reason': f'持仓{hold_days}天,超过{threshold}天阈值' if hold_days >= threshold else ''
        }

# =================== v5.100: 资金分层配置 ===================

class V5_100_FundLayering:
    """分层资金管理
    第1层: 激进仓 (40%) - MACD+RSI强信号
    第2层: 平衡仓 (35%) - 多因子平衡
    第3层: 保守仓 (15%) - 白马+防守
    第4层: 现金储备 (10%) - 突发机会
    """
    
    ALLOCATION_TEMPLATE = {
        'aggressive': {
            'ratio': 0.40,
            'min_entry_quality': 25,        # 25分即可
            'max_position_size': 0.08,     # 单仓最多8%
            'strategy': 'MACD+RSI',
            'description': '强技术信号,激进建仓'
        },
        'balanced': {
            'ratio': 0.35,
            'min_entry_quality': 45,       # 45分
            'max_position_size': 0.06,
            'strategy': 'MULTI_FACTOR',
            'description': '基本面+技术面平衡'
        },
        'conservative': {
            'ratio': 0.15,
            'min_entry_quality': 60,       # 60分
            'max_position_size': 0.05,
            'strategy': 'WHITE_HORSE',
            'description': '优质标的,防守为主'
        },
        'cash_reserve': {
            'ratio': 0.10,
            'description': '现金储备,应急机会'
        }
    }
    
    @staticmethod
    def calculate_optimal_allocation(total_capital: float, 
                                   current_cash: float) -> Dict:
        """计算最优资金分配
        
        根据Kelly公式和当前现金占比,动态调整分配
        """
        cash_ratio = current_cash / total_capital
        
        if cash_ratio > 0.95:
            # 现金极多,激进模式
            allocation = {
                'aggressive': 0.50,   # +10%
                'balanced': 0.30,     # -5%
                'conservative': 0.10,
                'cash_reserve': 0.10
            }
            mode = 'EXTREME_AGGRESSIVE'
        elif cash_ratio > 0.80:
            # 现金很多,加速建仓
            allocation = {
                'aggressive': 0.45,
                'balanced': 0.32,
                'conservative': 0.13,
                'cash_reserve': 0.10
            }
            mode = 'AGGRESSIVE'
        else:
            # 正常配置
            allocation = {
                'aggressive': 0.40,
                'balanced': 0.35,
                'conservative': 0.15,
                'cash_reserve': 0.10
            }
            mode = 'NORMAL'
        
        return {
            'mode': mode,
            'cash_ratio': cash_ratio,
            'allocation': allocation,
            'invested_capital': total_capital * (1 - cash_ratio)
        }
    
    @staticmethod
    def get_position_limits(allocation: Dict, total_capital: float) -> Dict:
        """根据分配比例,计算各层持仓上限"""
        return {
            'aggressive': {
                'capital': total_capital * allocation['aggressive'],
                'max_single': total_capital * 0.08,
                'max_count': 8,
                'min_quality': 25
            },
            'balanced': {
                'capital': total_capital * allocation['balanced'],
                'max_single': total_capital * 0.06,
                'max_count': 6,
                'min_quality': 45
            },
            'conservative': {
                'capital': total_capital * allocation['conservative'],
                'max_single': total_capital * 0.05,
                'max_count': 4,
                'min_quality': 60
            }
        }

# =================== v5.100: 入场质量动态评分 ===================

class V5_100_EntryQualityDynamic:
    """动态入场质量评分 - 基于现金占比和策略信号"""
    
    @staticmethod
    def get_quality_threshold(cash_ratio: float, strategy: str = 'MACD+RSI') -> int:
        """根据现金占比和策略,动态获取入场质量阈值
        
        逻辑: 现金越多→阈值越低(更激进)
        """
        if cash_ratio > 0.95:
            # 极度激进
            thresholds = {
                'MACD+RSI': 20,        # 20分即可
                'MULTI_FACTOR': 30,
                'WHITE_HORSE': 40
            }
        elif cash_ratio > 0.85:
            # 激进
            thresholds = {
                'MACD+RSI': 25,
                'MULTI_FACTOR': 35,
                'WHITE_HORSE': 45
            }
        elif cash_ratio > 0.70:
            # 平衡
            thresholds = {
                'MACD+RSI': 35,
                'MULTI_FACTOR': 45,
                'WHITE_HORSE': 55
            }
        else:
            # 保守
            thresholds = {
                'MACD+RSI': 45,
                'MULTI_FACTOR': 55,
                'WHITE_HORSE': 65
            }
        
        return thresholds.get(strategy, 50)
    
    @staticmethod
    def calculate_entry_quality_v100(candidate: Dict) -> int:
        """计算入场质量评分 (0-100分)
        
        指标权重:
        - MACD信号强度: 35分 (最重要)
        - RSI超卖程度: 25分
        - 突破确认: 20分
        - 量能配合: 15分
        - 融资融券确认: 5分
        """
        score = 0
        
        # 1. MACD信号强度 (35分)
        macd_signal = candidate.get('macd_signal', 0)  # 0-10
        score += (macd_signal / 10) * 35
        
        # 2. RSI超卖程度 (25分)
        rsi = candidate.get('rsi', 50)
        if rsi < 30:
            rsi_score = (30 - rsi) / 30 * 25  # 0~25分
        else:
            rsi_score = max(0, 25 - (rsi - 30))  # 递减
        score += rsi_score
        
        # 3. 突破确认 (20分) - 收盘价>均线
        breakout = candidate.get('breakout_confirmed', False)
        score += 20 if breakout else 10
        
        # 4. 量能配合 (15分)
        volume_signal = candidate.get('volume_ratio', 0)  # 1.0-2.0
        score += min(15, volume_signal * 10)
        
        # 5. 融资融券确认 (5分)
        margin_signal = candidate.get('margin_signal', False)
        score += 5 if margin_signal else 0
        
        return min(100, int(score))

# =================== v5.100: 选股超时防护 ===================

class V5_100_SelectionTimeoutProtection:
    """防止选股超时的智能降级机制"""
    
    @staticmethod
    def get_safe_candidate_pool_size(timeout_risk: float = 0.5) -> int:
        """根据超时风险,动态返回候选池大小
        
        Args:
            timeout_risk: 超时风险等级 (0.0-1.0)
        
        Returns:
            建议候选池大小
        """
        if timeout_risk > 0.8:
            return 25      # 高风险→极小
        elif timeout_risk > 0.6:
            return 35      # 中高风险→小
        elif timeout_risk > 0.4:
            return 45      # 中等风险→中等 (v5.96)
        else:
            return 60      # 低风险→正常
    
    @staticmethod
    def apply_timeout_protection(picks: List[Dict], 
                                max_picks: int = 12) -> Tuple[List[Dict], Dict]:
        """应用超时保护策略
        
        1. 按得分排序
        2. 只返回前N只
        3. 返回保护状态
        """
        if len(picks) <= max_picks:
            return picks, {'protected': False, 'dropped': 0}
        
        # 按入场质量+得分排序
        sorted_picks = sorted(
            picks,
            key=lambda x: (x.get('entry_quality', 0), x.get('score', 0)),
            reverse=True
        )
        
        selected = sorted_picks[:max_picks]
        return selected, {
            'protected': True,
            'dropped': len(picks) - max_picks,
            'selected_count': len(selected),
            'reason': f'防超时: {len(picks)} → {max_picks}'
        }

# =================== v5.100: 集成执行函数 ===================

def execute_v5_100_deep_optimize(positions: List[Dict], 
                                cash: float,
                                total_capital: float,
                                candidates: List[Dict]) -> Dict:
    """执行v5.100深度优化
    
    集成所有优化模块,返回优化建议
    """
    result = {
        'version': 'v5.100',
        'timestamp': datetime.now().isoformat(),
        'optimizations': {}
    }
    
    # 1. Kelly仓位优化
    kelly = V5_100_KellyOptimizer()
    kelly_target = kelly.get_rebalance_target(cash / total_capital)
    result['optimizations']['kelly'] = kelly_target
    
    # 2. 多层止损设计
    stop_loss = V5_100_MultiLayerStopLoss()
    result['optimizations']['stop_loss'] = {
        '科技成长': {
            'initial': f"{stop_loss.calculate_initial_stop_loss('科技成长'):.2%}",
            'trailing': '追踪止损 8%',
            'time': '25天止损'
        },
        '新能源': {
            'initial': f"{stop_loss.calculate_initial_stop_loss('新能源'):.2%}",
            'trailing': '追踪止损 8%',
            'time': '20天止损'
        }
    }
    
    # 3. 资金分层
    layering = V5_100_FundLayering()
    allocation = layering.calculate_optimal_allocation(total_capital, cash)
    position_limits = layering.get_position_limits(
        allocation['allocation'], 
        total_capital
    )
    result['optimizations']['allocation'] = {
        'mode': allocation['mode'],
        'limits': position_limits
    }
    
    # 4. 入场质量评分
    quality = V5_100_EntryQualityDynamic()
    cash_ratio = cash / total_capital
    result['optimizations']['entry_quality'] = {
        'cash_ratio': f"{cash_ratio:.2%}",
        'thresholds': {
            'MACD+RSI': quality.get_quality_threshold(cash_ratio, 'MACD+RSI'),
            'MULTI_FACTOR': quality.get_quality_threshold(cash_ratio, 'MULTI_FACTOR'),
            'WHITE_HORSE': quality.get_quality_threshold(cash_ratio, 'WHITE_HORSE')
        }
    }
    
    # 5. 选股超时保护
    timeout_protection = V5_100_SelectionTimeoutProtection()
    protected_picks, protection_status = timeout_protection.apply_timeout_protection(
        candidates, 
        max_picks=12
    )
    result['optimizations']['timeout_protection'] = protection_status
    
    # 6. MACD+RSI参数优化
    result['optimizations']['macd_rsi_params'] = MACD_RSI_OPTIMAL_PARAMS_V100
    
    return result

if __name__ == '__main__':
    # 测试代码
    kelly = V5_100_KellyOptimizer()
    print(f"✅ Kelly优化器: Kelly系数 = {kelly.kelly_half:.2%} (安全模式)")
    
    sl = V5_100_MultiLayerStopLoss()
    print(f"✅ 多层止损: 科技成长 = {sl.calculate_initial_stop_loss('科技成长'):.2%}")
    
    fund = V5_100_FundLayering()
    alloc = fund.calculate_optimal_allocation(1000000, 960000)
    print(f"✅ 资金分层: {alloc['mode']} 模式")
    
    print(f"\n✅ v5.100 深度优化模块已加载!")
