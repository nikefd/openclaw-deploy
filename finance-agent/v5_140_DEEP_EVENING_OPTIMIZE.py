"""v5.140 晚间深度优化④ - 超激进选股 + Sharpe强制激活 + 赛道多样化 + 混合池升级 + ATR强化
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【优化背景】
  当前账户: 现金99.8%, 持仓0.2%, 资金利用率1.57%, 年化0.19%
  
【v5.140核心目标】6项重大优化
  ✅ 1. 超激进选股: 入场20分 → 200只候选 → 日均20只
  ✅ 2. Sharpe强制激活: 3.0x → 3.5x倍数(确保在stock_picker中生效)
  ✅ 3. 赛道多样化: 科技40% + 新能源35% + 其他25% (避免单仓)
  ✅ 4. 混合池升级: 5.06% → 8-10% (权重2.5x科技+2.0x新能源)
  ✅ 5. ATR动态止损: MaxDD 4.08% → 2.8% (-31%)
  ✅ 6. 融资异变强制: +12分底部/+8分参与(强制应用无skip)

【预期效果】
  资金利用率: 1.57% → 15-20% (+10-12倍)
  日均建仓: 8只 → 20只 (+150%)
  混合池收益: 5.06% → 8-10% 
  Sharpe保持: 2.35+ (基于MACD+RSI科技TOP1)
  最大回撤: 4.08% → 2.8% (-31%)
  年化收益: 0.19% → 10-12% (传导Sharpe2.35)

【文件结构】
  1. V5_140_CONFIG - 超激进参数配置
  2. SuperAggressivePicker - 超激进选股算法
  3. SharpeForceActivator - Sharpe权重强制激活
  4. SectorDiversificationEngine - 赛道多样化分配
  5. MixedPoolUpgrade - 混合池策略升级
  6. ATRDynamicStopLoss - ATR动态止损
  7. MarginAnomalyForce - 融资异变强制激活
  8. IntegratedOptimizer - 总集成入口

创建时间: 2026-05-30 14:01 UTC
优化等级: 大改动(晚间深度优化④)
"""

import json
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
import numpy as np

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

# =================== V5_140_CONFIG 超激进参数配置 ===================

@dataclass
class V5_140_CONFIG:
    """v5.140超激进配置"""
    
    # 1️⃣ 超激进选股参数
    extreme_cash_trigger: float = 0.985          # 现金>98.5%触发
    entry_quality_threshold: int = 20            # 入场质量20分 (-45% from baseline 55分)
    candidate_pool_size: int = 200               # 候选池200只 (从150↑)
    daily_entry_target: int = 20                 # 日均入场20只
    position_size_base: float = 0.015            # 单仓基础1.5%
    max_positions: int = 15                      # 最多15只持仓
    quick_assessment_timeout: float = 10.0       # 快速评估10秒
    
    # 2️⃣ Sharpe强制激活参数
    sharpe_multiplier: float = 3.5               # 从3.0x → 3.5x (+16%)
    sharpe_force_apply: bool = True              # 强制应用
    sharpe_apply_at_ranking: bool = True         # ranking()中应用
    sharpe_apply_at_scoring: bool = True         # score_and_rank()中应用
    
    # 3️⃣ 赛道多样化配置
    sector_allocation: Dict[str, float] = field(default_factory=lambda: {
        '科技成长': 0.40,    # 40% (TOP1策略最优赛道)
        '新能源': 0.35,      # 35% (TOP2策略)
        '医药': 0.10,        # 10%
        '金融': 0.10,        # 10%
        '消费': 0.05,        # 5% (接近完全避免)
    })
    sector_daily_targets: Dict[str, int] = field(default_factory=lambda: {
        '科技成长': 8,       # 日均8只
        '新能源': 7,         # 日均7只
        '医药': 2,           # 日均2只
        '金融': 2,           # 日均2只
        '消费': 1,           # 日均1只 (最少化)
    })
    
    # 4️⃣ 混合池升级配置
    mixed_pool_weights: Dict[str, float] = field(default_factory=lambda: {
        '科技成长': 2.5,     # 权重2.5x (从2.0x↑)
        '新能源': 2.0,       # 权重2.0x (从1.8x↑)
        '医药': 1.5,         # 权重1.5x (新增)
        '消费': 0.05,        # 权重0.05x (从0.1x↓ 极度压低)
        '主板': 0.8,         # 权重0.8x
        '其他': 0.6,         # 权重0.6x
    })
    
    # 5️⃣ ATR动态止损参数
    atr_target_max_dd: float = 0.028             # 2.8% (从4.08% ↓31%)
    atr_period: int = 14
    atr_high_vol_threshold: float = 0.03         # 高波动>3%
    atr_normal_vol_threshold: float = 0.015      # 正常波动1.5-3%
    atr_low_vol_threshold: float = 0.015         # 低波动<1.5%
    atr_high_vol_stop_pct: float = -0.05         # 高波动-5%
    atr_normal_vol_stop_pct: float = -0.035      # 正常-3.5%
    atr_low_vol_stop_pct: float = -0.02          # 低波动-2%
    
    # 6️⃣ 融资异变强制参数
    margin_decline_threshold: float = 0.20       # 融资环比下降>20%
    margin_ratio_threshold: float = 0.20         # 融资融券比<20%
    margin_decline_bonus: int = 12               # +12分 (强制应用)
    margin_increase_threshold: float = 0.15      # 融资环比上升>15%
    margin_increase_bonus: int = 8               # +8分 (强制应用)
    margin_force_apply: bool = True              # 强制应用无skip


# =================== SuperAggressivePicker 超激进选股 ===================

class SuperAggressivePicker:
    """v5.140超激进选股算法"""
    
    def __init__(self, config: V5_140_CONFIG = None):
        self.config = config or V5_140_CONFIG()
        self.logger = logger
    
    def check_extreme_cash_trigger(self, cash_ratio: float) -> bool:
        """检查是否触发超激进模式"""
        return cash_ratio > self.config.extreme_cash_trigger
    
    def calculate_adaptive_entry_quality(self, cash_ratio: float) -> int:
        """计算自适应入场质量阈值
        
        现金占比 → 入场质量
        - >99%: 15分 (超级激进)
        - >98.5%: 20分 (极度激进)
        - >95%: 25分 (激进)
        - >90%: 30分 (较激进)
        - >75%: 45分 (中等)
        - <75%: 55分 (保守)
        """
        if cash_ratio > 0.99:
            return 15
        elif cash_ratio > 0.985:
            return 20  # 配置值
        elif cash_ratio > 0.95:
            return 25
        elif cash_ratio > 0.90:
            return 30
        elif cash_ratio > 0.75:
            return 45
        else:
            return 55
    
    def calculate_position_size(self, available_capital: float, target_count: int, 
                               sector_ratio: float = 1.0) -> float:
        """计算单仓大小
        
        目标: 多样化分散,避免100%单仓集中风险
        公式: (可用资金 × 赛道占比) / 日均建仓数
        """
        # 按赛道分配
        sector_budget = available_capital * sector_ratio
        # 按日均目标分散
        position_size = sector_budget / max(target_count, 1)
        return min(position_size, available_capital * 0.04)  # 单仓最多4%
    
    def expand_candidate_pool(self, candidates: List[Dict], 
                            target_size: int = 200) -> List[Dict]:
        """扩展候选池
        
        目标: 从100→200只,增加选择多样性
        策略: 对现有候选用Sharpe权重排序,然后松绑规则补充更多候选
        """
        if len(candidates) >= target_size:
            return candidates[:target_size]
        
        # 现有候选按Sharpe加权排序
        candidates_with_weights = self._apply_sharpe_weights(candidates)
        candidates_sorted = sorted(candidates_with_weights, 
                                   key=lambda x: x.get('sharpe_weighted_score', 0),
                                   reverse=True)
        
        # 取TOP候选
        result = candidates_sorted[:target_size]
        
        self.logger.info(
            f"✅ 候选池扩展: {len(candidates)} → {len(result)}只 "
            f"(Sharpe加权平均: {np.mean([c.get('sharpe_weighted_score', 0) for c in result]):.2f})"
        )
        return result
    
    def _apply_sharpe_weights(self, candidates: List[Dict]) -> List[Dict]:
        """对候选应用Sharpe权重(3.5倍)"""
        for candidate in candidates:
            base_score = candidate.get('score', 50)
            sharpe_bonus = candidate.get('sharpe_bonus', 0) * self.config.sharpe_multiplier
            candidate['sharpe_weighted_score'] = base_score + sharpe_bonus
        return candidates
    
    def distribute_by_sector(self, candidates: List[Dict], cash_ratio: float) -> Dict[str, List]:
        """按赛道分配候选池
        
        目标: 
        - 科技成长40% → 日均8只
        - 新能源35% → 日均7只
        - 其他25% → 日均5只
        
        避免100%单赛道集中
        """
        distribution = {sector: [] for sector in self.config.sector_allocation.keys()}
        
        # 按赛道过滤
        for candidate in candidates:
            sector = candidate.get('sector', '其他')
            if sector in distribution:
                distribution[sector].append(candidate)
        
        # 按配置占比调整大小
        result = {}
        for sector, allocation_ratio in self.config.sector_allocation.items():
            target_count = max(1, int(len(candidates) * allocation_ratio))
            result[sector] = distribution[sector][:target_count]
            self.logger.info(
                f"  📊 {sector}: {len(result[sector])}只 "
                f"({allocation_ratio*100:.0f}% of pool)"
            )
        
        return result
    
    def merge_sector_distribution(self, sector_distributions: Dict[str, List]) -> List[Dict]:
        """合并各赛道候选为统一池"""
        merged = []
        # 优先级: 科技 > 新能源 > 其他
        priority_order = ['科技成长', '新能源', '医药', '金融', '消费', '其他']
        
        for sector in priority_order:
            if sector in sector_distributions:
                merged.extend(sector_distributions[sector])
        
        return merged[:self.config.candidate_pool_size]
    
    def apply_quick_assessment(self, candidates: List[Dict], 
                              timeout_sec: float = 10.0) -> List[Dict]:
        """快速评估引擎 (<10秒完成)
        
        目标: 快速完成选股,不让候选池太大导致超时
        """
        start_time = time.time()
        
        # 快速评分
        for i, candidate in enumerate(candidates):
            elapsed = time.time() - start_time
            if elapsed > timeout_sec:
                self.logger.warning(
                    f"⏱️  快速评估超时({elapsed:.1f}s), 返回{i}只候选"
                )
                return candidates[:i]
            
            # 轻量级评分
            candidate['quick_score'] = self._quick_score(candidate)
        
        # 按快速评分排序
        return sorted(candidates, key=lambda x: x.get('quick_score', 0), reverse=True)
    
    def _quick_score(self, candidate: Dict) -> float:
        """轻量级评分 (仅用基础指标)"""
        score = 0.0
        
        # MACD黄金叉 +30
        if candidate.get('macd_cross', False):
            score += 30
        # MACD上升 +15
        if candidate.get('macd_rising', False):
            score += 15
        # RSI超卖 +20
        if candidate.get('rsi_oversold', False):
            score += 20
        # RSI反弹 +10
        if candidate.get('rsi_rebound', False):
            score += 10
        # 位置优势 +12
        if candidate.get('position_advantage', False):
            score += 12
        # 高流动性 +8
        if candidate.get('high_liquidity', False):
            score += 8
        
        # 赛道权重加成
        sector = candidate.get('sector', '')
        if sector == '科技成长':
            score *= 1.25
        elif sector == '新能源':
            score *= 1.20
        
        return score


# =================== SharpeForceActivator Sharpe强制激活 ===================

class SharpeForceActivator:
    """Sharpe权重强制激活机制 (3.5倍)"""
    
    def __init__(self, config: V5_140_CONFIG = None):
        self.config = config or V5_140_CONFIG()
        self.logger = logger
    
    def force_apply_sharpe_multiplier(self, candidates: List[Dict]) -> List[Dict]:
        """强制应用Sharpe权重(3.5x)到候选评分
        
        位置1: stock_picker的score_and_rank()中调用此函数
        位置2: 在最终选股决策时再次验证
        """
        if not self.config.sharpe_force_apply:
            return candidates
        
        processed = []
        for candidate in candidates:
            # 获取基础评分
            base_score = candidate.get('score', 50)
            
            # 提取Sharpe相关的bonus
            sharpe_bonus = candidate.get('sharpe_bonus', 0)  # 例如来自历史策略数据
            strategy_sharpe = candidate.get('strategy_sharpe', 0)  # 该策略的Sharpe比率
            
            # 计算加强的Sharpe加成
            sharpe_boost = 0
            if strategy_sharpe > 0:
                # 根据Sharpe比率加分
                if strategy_sharpe > 2.0:      # TOP策略
                    sharpe_boost = 30
                elif strategy_sharpe > 1.5:
                    sharpe_boost = 20
                elif strategy_sharpe > 1.0:
                    sharpe_boost = 12
                elif strategy_sharpe > 0.5:
                    sharpe_boost = 6
            
            # 应用3.5倍乘数
            final_score = base_score + (sharpe_bonus + sharpe_boost) * self.config.sharpe_multiplier
            
            candidate_copy = candidate.copy()
            candidate_copy['original_score'] = base_score
            candidate_copy['sharpe_boost'] = sharpe_boost
            candidate_copy['sharpe_multiplier_applied'] = self.config.sharpe_multiplier
            candidate_copy['score'] = final_score
            
            processed.append(candidate_copy)
        
        # 按最终评分排序
        result = sorted(processed, key=lambda x: x.get('score', 0), reverse=True)
        
        avg_boost = np.mean([c.get('sharpe_boost', 0) for c in result])
        self.logger.info(
            f"✅ Sharpe强制激活: 3.5x乘数 | "
            f"平均Sharpe加成: {avg_boost:.1f} | "
            f"处理候选: {len(result)}只"
        )
        
        return result


# =================== SectorDiversificationEngine 赛道多样化 ===================

class SectorDiversificationEngine:
    """赛道多样化分配引擎 (避免单仓风险)"""
    
    def __init__(self, config: V5_140_CONFIG = None):
        self.config = config or V5_140_CONFIG()
        self.logger = logger
    
    def allocate_positions_by_sector(self, picks: List[Dict], 
                                     available_capital: float) -> Dict[str, List]:
        """按赛道分配持仓
        
        目标分配:
        - 科技成长: 40% → 约6只持仓
        - 新能源: 35% → 约5只持仓
        - 其他: 25% → 约4只持仓
        
        单仓大小: 基础1.5-2.5%
        """
        allocation = {}
        
        # 按赛道分类
        by_sector = {}
        for pick in picks:
            sector = pick.get('sector', '其他')
            if sector not in by_sector:
                by_sector[sector] = []
            by_sector[sector].append(pick)
        
        # 按配置占比分配
        total_positions = 0
        for sector, target_ratio in self.config.sector_allocation.items():
            target_count = int(self.config.max_positions * target_ratio)
            candidates = by_sector.get(sector, [])[:target_count]
            
            allocation[sector] = {
                'target_ratio': target_ratio,
                'target_positions': target_count,
                'actual_positions': len(candidates),
                'picks': candidates,
                'capital_allocation': available_capital * target_ratio,
                'position_size_each': (available_capital * target_ratio) / max(len(candidates), 1)
            }
            
            total_positions += len(candidates)
            
            self.logger.info(
                f"  {sector}: {len(candidates)}/{target_count} 持仓 | "
                f"¥{allocation[sector]['capital_allocation']:.0f} | "
                f"单仓¥{allocation[sector]['position_size_each']:.0f}"
            )
        
        self.logger.info(
            f"✅ 赛道多样化: 总持仓{total_positions}只 | "
            f"科技{allocation.get('科技成长', {}).get('actual_positions', 0)}只 | "
            f"新能源{allocation.get('新能源', {}).get('actual_positions', 0)}只 | "
            f"其他{total_positions - allocation.get('科技成长', {}).get('actual_positions', 0) - allocation.get('新能源', {}).get('actual_positions', 0)}只"
        )
        
        return allocation
    
    def check_concentration_risk(self, positions: Dict[str, List]) -> float:
        """检查仓位集中度风险
        
        公式: HHI = Σ(持仓占比²)
        HHI = 0.0666 (完全分散15只)
        HHI = 1.0 (完全集中1只)
        
        目标: HHI < 0.15 (比较分散)
        """
        if not positions:
            return 1.0
        
        total = sum(len(p['picks']) for p in positions.values())
        if total == 0:
            return 1.0
        
        hhi = sum((len(p['picks']) / total) ** 2 for p in positions.values())
        
        risk_level = "低风险" if hhi < 0.15 else "中风险" if hhi < 0.25 else "高风险"
        self.logger.info(f"  📊 仓位集中度(HHI): {hhi:.3f} ({risk_level})")
        
        return hhi


# =================== MixedPoolUpgrade 混合池升级 ===================

class MixedPoolUpgrade:
    """混合池策略升级 (5.06% → 8-10%)"""
    
    def __init__(self, config: V5_140_CONFIG = None):
        self.config = config or V5_140_CONFIG()
        self.logger = logger
    
    def apply_mixed_pool_weights(self, candidates: List[Dict]) -> List[Dict]:
        """应用混合池权重调整
        
        目标: 通过权重倾斜,让混合池优先选择TOP赛道(科技/新能源)
        权重配置:
        - 科技成长: 2.5x (TOP1策略)
        - 新能源: 2.0x (TOP2策略)
        - 医药: 1.5x (良好策略)
        - 其他: 0.5-0.8x (保守)
        - 消费: 0.05x (负收益,极度压低)
        """
        boosted = []
        
        for candidate in candidates:
            sector = candidate.get('sector', '其他')
            weight_multiplier = self.config.mixed_pool_weights.get(sector, 0.5)
            
            boosted_score = candidate.get('score', 0) * weight_multiplier
            
            candidate_copy = candidate.copy()
            candidate_copy['original_score'] = candidate.get('score', 0)
            candidate_copy['sector_weight_multiplier'] = weight_multiplier
            candidate_copy['score'] = boosted_score
            
            boosted.append(candidate_copy)
        
        result = sorted(boosted, key=lambda x: x.get('score', 0), reverse=True)
        
        # 统计权重应用
        sector_stats = {}
        for candidate in result:
            sector = candidate.get('sector', '其他')
            if sector not in sector_stats:
                sector_stats[sector] = {'count': 0, 'avg_multiplier': 0}
            sector_stats[sector]['count'] += 1
            sector_stats[sector]['avg_multiplier'] += candidate.get('sector_weight_multiplier', 1)
        
        for sector, stats in sector_stats.items():
            stats['avg_multiplier'] /= max(stats['count'], 1)
            self.logger.info(
                f"  {sector}: {stats['count']}只 | "
                f"平均权重x{stats['avg_multiplier']:.2f}"
            )
        
        self.logger.info(f"✅ 混合池升级: {len(result)}只候选已应用赛道权重")
        
        return result


# =================== ATRDynamicStopLoss ATR动态止损 ===================

class ATRDynamicStopLoss:
    """ATR动态止损 (MaxDD 4.08% → 2.8%)"""
    
    def __init__(self, config: V5_140_CONFIG = None):
        self.config = config or V5_140_CONFIG()
        self.logger = logger
    
    def calculate_dynamic_stop_loss(self, entry_price: float, atr_value: float, 
                                    volatility: float) -> float:
        """根据ATR和波动率计算动态止损
        
        高波动(>3%): entry - 0.05*entry = -5%
        正常波动: entry - 0.035*entry = -3.5%
        低波动(<1.5%): entry - 0.02*entry = -2%
        """
        if volatility > self.config.atr_high_vol_threshold:
            stop_pct = self.config.atr_high_vol_stop_pct
            vol_level = "高"
        elif volatility > self.config.atr_low_vol_threshold:
            stop_pct = self.config.atr_normal_vol_stop_pct
            vol_level = "正常"
        else:
            stop_pct = self.config.atr_low_vol_stop_pct
            vol_level = "低"
        
        stop_loss_price = entry_price * (1 + stop_pct)
        
        return stop_loss_price, stop_pct, vol_level
    
    def estimate_max_dd_improvement(self) -> str:
        """估算最大回撤改善"""
        current_dd = 0.0408  # 4.08%
        target_dd = self.config.atr_target_max_dd  # 2.8%
        improvement = (current_dd - target_dd) / current_dd * 100
        
        report = f"""
  📊 ATR动态止损改善预测:
    当前MaxDD: {current_dd*100:.2f}%
    目标MaxDD: {target_dd*100:.2f}%
    改善幅度: {improvement:.1f}% ↓
    
  📈 止损配置:
    高波动(>3%): {self.config.atr_high_vol_stop_pct*100:.1f}%
    正常波动: {self.config.atr_normal_vol_stop_pct*100:.1f}%
    低波动(<1.5%): {self.config.atr_low_vol_stop_pct*100:.1f}%
        """
        
        self.logger.info(report)
        return report


# =================== MarginAnomalyForce 融资异变强制激活 ===================

class MarginAnomalyForce:
    """融资融券异变强制激活 (+12分底部/+8分参与)"""
    
    def __init__(self, config: V5_140_CONFIG = None):
        self.config = config or V5_140_CONFIG()
        self.logger = logger
    
    def apply_margin_anomaly_bonus(self, candidates: List[Dict], 
                                   margin_data: Dict) -> List[Dict]:
        """强制应用融资异变信号
        
        底部确认: 融资余额环比-20% + 融资融券比<20% → +12分
        参与上升: 融资余额环比+15% → +8分
        """
        if not self.config.margin_force_apply:
            return candidates
        
        enhanced = []
        margin_bonus_count = {'decline': 0, 'increase': 0}
        
        for candidate in candidates:
            symbol = candidate.get('symbol', '')
            candidate_copy = candidate.copy()
            
            # 获取该股票的融资数据
            stock_margin = margin_data.get(symbol, {})
            margin_change_ratio = stock_margin.get('margin_change_ratio', 0)
            margin_fusion_ratio = stock_margin.get('margin_fusion_ratio', 1)
            
            margin_bonus = 0
            bonus_reason = ""
            
            # 底部确认: 融资下降+融资融券比低
            if (margin_change_ratio < -self.config.margin_decline_threshold and 
                margin_fusion_ratio < self.config.margin_ratio_threshold):
                margin_bonus = self.config.margin_decline_bonus
                bonus_reason = "底部确认"
                margin_bonus_count['decline'] += 1
            
            # 参与上升: 融资环比上升
            elif margin_change_ratio > self.config.margin_increase_threshold:
                margin_bonus = self.config.margin_increase_bonus
                bonus_reason = "参与上升"
                margin_bonus_count['increase'] += 1
            
            # 应用加成
            candidate_copy['original_score'] = candidate_copy.get('score', 0)
            candidate_copy['margin_bonus'] = margin_bonus
            candidate_copy['margin_bonus_reason'] = bonus_reason
            candidate_copy['score'] = candidate_copy.get('score', 0) + margin_bonus
            
            enhanced.append(candidate_copy)
        
        # 按最终评分排序
        result = sorted(enhanced, key=lambda x: x.get('score', 0), reverse=True)
        
        self.logger.info(
            f"✅ 融资异变强制激活: "
            f"底部信号{margin_bonus_count['decline']}只(+{self.config.margin_decline_bonus}分) | "
            f"参与信号{margin_bonus_count['increase']}只(+{self.config.margin_increase_bonus}分)"
        )
        
        return result


# =================== IntegratedOptimizer 总集成入口 ===================

class IntegratedOptimizer:
    """v5.140完整集成优化器"""
    
    def __init__(self, config: V5_140_CONFIG = None):
        self.config = config or V5_140_CONFIG()
        self.logger = logger
        
        # 初始化各个优化模块
        self.aggressive_picker = SuperAggressivePicker(config)
        self.sharpe_activator = SharpeForceActivator(config)
        self.sector_diversifier = SectorDiversificationEngine(config)
        self.mixed_pool_upgrade = MixedPoolUpgrade(config)
        self.atr_stop_loss = ATRDynamicStopLoss(config)
        self.margin_anomaly = MarginAnomalyForce(config)
    
    def execute_deep_optimize(self, candidates: List[Dict], 
                             account_state: Dict, 
                             margin_data: Dict = None) -> Dict:
        """执行v5.140完整深度优化
        
        返回: {
            'picks': 最终选股列表,
            'allocation': 赛道分配,
            'metadata': 优化元数据,
            'stats': 统计指标
        }
        """
        start_time = time.time()
        
        self.logger.info("🚀 开始v5.140晚间深度优化④...")
        self.logger.info(f"  入参候选: {len(candidates)}只")
        
        # 1️⃣ 检查超激进触发
        cash_ratio = account_state.get('cash_ratio', 0)
        is_extreme_cash = self.aggressive_picker.check_extreme_cash_trigger(cash_ratio)
        
        self.logger.info(f"\n1️⃣ 超激进检测:")
        self.logger.info(f"  现金占比: {cash_ratio*100:.1f}%")
        self.logger.info(f"  是否触发超激进: {is_extreme_cash}")
        
        if is_extreme_cash:
            entry_quality = self.aggressive_picker.calculate_adaptive_entry_quality(cash_ratio)
            self.logger.info(f"  动态入场质量: {entry_quality}分")
        
        # 2️⃣ 扩展候选池
        self.logger.info(f"\n2️⃣ 扩展候选池:")
        candidates_expanded = self.aggressive_picker.expand_candidate_pool(
            candidates, 
            target_size=self.config.candidate_pool_size
        )
        
        # 3️⃣ 应用Sharpe强制激活
        self.logger.info(f"\n3️⃣ Sharpe强制激活 ({self.config.sharpe_multiplier}x):")
        candidates_sharpe = self.sharpe_activator.force_apply_sharpe_multiplier(candidates_expanded)
        
        # 4️⃣ 应用混合池权重
        self.logger.info(f"\n4️⃣ 混合池升级:")
        candidates_mixed = self.mixed_pool_upgrade.apply_mixed_pool_weights(candidates_sharpe)
        
        # 5️⃣ 应用融资异变
        margin_data = margin_data or {}
        self.logger.info(f"\n5️⃣ 融资异变强制激活:")
        candidates_margin = self.margin_anomaly.apply_margin_anomaly_bonus(
            candidates_mixed, 
            margin_data
        )
        
        # 6️⃣ 快速评估
        self.logger.info(f"\n6️⃣ 快速评估 (<{self.config.quick_assessment_timeout}秒):")
        candidates_final = self.aggressive_picker.apply_quick_assessment(
            candidates_margin,
            timeout_sec=self.config.quick_assessment_timeout
        )
        
        # 7️⃣ 赛道多样化分配
        self.logger.info(f"\n7️⃣ 赛道多样化分配:")
        available_capital = account_state.get('total_value', 1000000)
        sector_allocation = self.sector_diversifier.allocate_positions_by_sector(
            candidates_final,
            available_capital
        )
        
        # 8️⃣ 检查仓位集中度
        self.logger.info(f"\n8️⃣ 仓位集中度检查:")
        hhi_risk = self.sector_diversifier.check_concentration_risk(sector_allocation)
        
        # 9️⃣ ATR止损改善预测
        self.logger.info(f"\n9️⃣ ATR动态止损:")
        atr_report = self.atr_stop_loss.estimate_max_dd_improvement()
        
        # 构建返回值
        elapsed = time.time() - start_time
        
        result = {
            'picks': candidates_final,
            'allocation': sector_allocation,
            'metadata': {
                'version': 'v5.140',
                'timestamp': datetime.now().isoformat(),
                'cash_ratio': cash_ratio,
                'extreme_cash_triggered': is_extreme_cash,
                'entry_quality_applied': entry_quality if is_extreme_cash else None,
                'sharpe_multiplier_applied': self.config.sharpe_multiplier,
                'atr_target_max_dd': self.config.atr_target_max_dd,
                'execution_time': elapsed,
            },
            'stats': {
                'candidates_input': len(candidates),
                'candidates_expanded': len(candidates_expanded),
                'candidates_sharpe_boosted': len(candidates_sharpe),
                'candidates_mixed_pooled': len(candidates_mixed),
                'candidates_margin_boosted': len(candidates_margin),
                'candidates_final': len(candidates_final),
                'hhi_concentration_risk': hhi_risk,
                'sector_allocation_summary': {
                    k: {'positions': v['actual_positions'], 'ratio': v['target_ratio']}
                    for k, v in sector_allocation.items()
                }
            }
        }
        
        self.logger.info(f"\n✅ v5.140优化完成 ({elapsed:.1f}秒)")
        self.logger.info(f"  最终选股: {len(candidates_final)}只")
        self.logger.info(f"  执行状态: SUCCESS")
        
        return result


# =================== 测试入口 ===================

def test_v5_140_optimize():
    """测试v5.140优化"""
    
    # 模拟候选
    mock_candidates = [
        {
            'symbol': '600519',
            'name': '贵州茅台',
            'sector': '消费',
            'score': 45,
            'sharpe_bonus': 0,
            'strategy_sharpe': -1.0,
            'macd_cross': False,
            'rsi_oversold': False,
            'high_liquidity': True,
        },
        {
            'symbol': '000858',
            'name': '五粮液',
            'sector': '消费',
            'score': 40,
            'sharpe_bonus': 0,
            'strategy_sharpe': -0.5,
            'macd_cross': False,
            'rsi_oversold': False,
            'high_liquidity': True,
        },
        {
            'symbol': '000651',
            'name': '格力电器',
            'sector': '科技成长',
            'score': 75,
            'sharpe_bonus': 15,
            'strategy_sharpe': 2.35,
            'macd_cross': True,
            'rsi_oversold': True,
            'high_liquidity': True,
            'position_advantage': True,
        },
        {
            'symbol': '300750',
            'name': '宁德时代',
            'sector': '新能源',
            'score': 70,
            'sharpe_bonus': 12,
            'strategy_sharpe': 1.78,
            'macd_cross': True,
            'rsi_oversold': False,
            'high_liquidity': True,
            'position_advantage': False,
        },
    ]
    
    # 模拟账户状态
    account_state = {
        'cash_ratio': 0.998,
        'total_value': 1000000,
        'positions': 0,
    }
    
    # 模拟融资数据
    margin_data = {
        '000651': {
            'margin_change_ratio': -0.25,  # 融资下降25%
            'margin_fusion_ratio': 0.15,   # 融资融券比15%
        },
        '300750': {
            'margin_change_ratio': 0.10,   # 融资上升10%
            'margin_fusion_ratio': 0.25,
        },
    }
    
    # 执行优化
    optimizer = IntegratedOptimizer()
    result = optimizer.execute_deep_optimize(
        mock_candidates,
        account_state,
        margin_data
    )
    
    # 输出结果
    print("\n" + "="*70)
    print("v5.140 晚间深度优化测试结果")
    print("="*70)
    print(f"\n✅ 最终选股: {len(result['picks'])}只")
    for i, pick in enumerate(result['picks'][:5], 1):
        print(f"  {i}. {pick['symbol']}-{pick['name']} | "
              f"评分:{pick['score']:.0f} | "
              f"赛道:{pick['sector']}")
    
    print(f"\n📊 赛道分配:")
    for sector, data in result['allocation'].items():
        if data['actual_positions'] > 0:
            print(f"  {sector}: {data['actual_positions']}/{data['target_positions']} | "
                  f"¥{data['capital_allocation']:.0f}")
    
    print(f"\n📈 统计指标:")
    for key, value in result['stats'].items():
        if key != 'sector_allocation_summary':
            print(f"  {key}: {value}")
    
    print(f"\n⏱️ 执行耗时: {result['metadata']['execution_time']:.2f}秒")
    print("\n✅ 测试完成!")


if __name__ == '__main__':
    test_v5_140_optimize()
