"""
v5.141 晚间深度优化V - 策略融合+动态Kelly+多维评分+现金精细化
Created: 2026-06-03 14:01 UTC | Target: 混合池 5.06%→8-10%, Sharpe 0.86→1.2-1.5

核心改进:
1. P1: 策略融合 (TOP回测结果→实盘加权)
2. P2: Kelly动态调整 (按赛道胜率实时调整 1.75→2.0+)
3. P3: 8维评分系统 (新增维度7: 历史胜率, 维度8: 融资异变)
4. P4: 现金激活精细化 (现金>80%激活激进模式)
"""

import json
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import sqlite3

# =================== v5.141 配置常量 ===================

V5_141_ACTIVE = True
V5_141_VERSION = 'v5.141-Deep-Evening-Optimize-V'

# TOP回测策略缓存 (从backtest.db提取)
BACKTEST_TOP_STRATEGIES = {
    'MACD+RSI_科技成长': {
        'total_return': 0.171,
        'sharpe_ratio': 2.35,
        'win_rate': 0.60,
        'max_drawdown': 0.0408,
        'sector': '科技成长',
        'signal_boost': 2.0,
    },
    'MACD+RSI_新能源': {
        'total_return': 0.1466,
        'sharpe_ratio': 1.78,
        'win_rate': 0.70,
        'max_drawdown': 0.0693,
        'sector': '新能源',
        'signal_boost': 1.8,
    },
    'MACD+RSI_混合池': {
        'total_return': 0.0506,
        'sharpe_ratio': 0.86,
        'win_rate': 0.391,
        'max_drawdown': 0.0532,
        'sector': '混合池',
        'signal_boost': 1.0,  # 基准
    }
}

# 赛道权重 (基于回测表现)
BACKTEST_SECTOR_WEIGHTS_V141 = {
    '科技成长': 0.45,      # TOP1: 17.1% 收益
    '新能源': 0.40,        # TOP2: 14.66% 收益
    '医药': 0.08,          # 中等表现
    '金融': 0.05,          # 基础配置
    '消费': 0.02,          # 最小化 (避免 -5.51% 负收益)
}

# Kelly系数 (按赛道胜率调整)
KELLY_ADJUSTMENT_BY_SECTOR = {
    '科技成长': 1.95,      # 胜率60% → Kelly 1.75 × 1.11 ≈ 1.95
    '新能源': 2.05,        # 胜率70% → Kelly 1.75 × 1.17 ≈ 2.05 (最激进)
    '医药': 1.65,          # 中等胜率 → Kelly 1.75 × 0.94 ≈ 1.65
    '金融': 1.55,          # 一般胜率 → Kelly 1.75 × 0.89 ≈ 1.55
    '消费': 0.85,          # 低胜率 (-5.51%) → Kelly 1.75 × 0.49 ≈ 0.85 (保守)
}

# 现金激活阈值 (v5.141新增精细化)
CASH_ACTIVATION_TIERS = {
    'ultra_aggressive': {
        'cash_threshold': 0.95,      # 现金>95%
        'entry_quality': 15,         # 最激进
        'max_positions': 20,         # 最多持仓
        'multiplier': 1.0
    },
    'aggressive': {
        'cash_threshold': 0.80,      # 现金>80%
        'entry_quality': 20,         # 激进
        'max_positions': 15,         # 标准持仓
        'multiplier': 0.85
    },
    'normal': {
        'cash_threshold': 0.50,      # 现金>50%
        'entry_quality': 25,         # 正常
        'max_positions': 12,         # 较少持仓
        'multiplier': 0.70
    },
    'conservative': {
        'cash_threshold': 0.00,      # 现金<50%
        'entry_quality': 35,         # 保守
        'max_positions': 8,          # 最少持仓
        'multiplier': 0.50
    }
}

# Sharpe倍数升级 (按赛道和现金占比)
SHARPE_MULTIPLIER_BY_SECTOR_AND_CASH = {
    '科技成长': {
        'high_cash': 5.0,            # 现金>80%: 3.5 → 5.0
        'normal_cash': 4.0,          # 现金50-80%: 3.5 → 4.0
        'low_cash': 3.0              # 现金<50%: 3.0
    },
    '新能源': {
        'high_cash': 4.8,            # 新能源胜率70% 稍低于科技
        'normal_cash': 3.8,
        'low_cash': 2.8
    },
    '医药': {
        'high_cash': 3.5,
        'normal_cash': 3.0,
        'low_cash': 2.0
    },
    '金融': {
        'high_cash': 3.0,
        'normal_cash': 2.5,
        'low_cash': 1.5
    },
    '消费': {
        'high_cash': 1.5,            # 最小化 (要避免)
        'normal_cash': 1.0,
        'low_cash': 0.5
    }
}

# 8维评分系统 (新增维度7和8)
ENHANCED_SCORING_DIMENSIONS = [
    'technical_signal',          # D1: 技术面信号 (已有)
    'capital_flow',              # D2: 资金面 (已有)
    'market_sentiment',          # D3: 市场情绪 (已有)
    'sector_strength',           # D4: 赛道强度 (已有)
    'news_sentiment',            # D5: 新闻舆情 (已有)
    'entry_quality',             # D6: 入场质量 (已有)
    'historical_winrate',        # D7: 历史胜率 (NEW: v5.141)
    'margin_anomaly_score'       # D8: 融资异变 (NEW: 已在v5.140中)
]

# 维度权重 (8维)
DIMENSION_WEIGHTS_V8 = {
    'technical_signal': 0.25,          # D1: 25%
    'capital_flow': 0.20,              # D2: 20%
    'market_sentiment': 0.15,          # D3: 15%
    'sector_strength': 0.15,           # D4: 15%
    'news_sentiment': 0.10,            # D5: 10%
    'entry_quality': 0.05,             # D6: 5%
    'historical_winrate': 0.05,        # D7: 5% (NEW)
    'margin_anomaly_score': 0.05,      # D8: 5% (NEW)
}


# =================== v5.141 类实现 ===================

class BacktestStraegyFusion:
    """P1: 回测策略融合 - 将TOP回测结果加权到实盘选股"""
    
    def __init__(self):
        self.backtest_data = BACKTEST_TOP_STRATEGIES
        self.sector_weights = BACKTEST_SECTOR_WEIGHTS_V141
        
    def get_sector_signal_boost(self, sector: str) -> float:
        """根据回测表现获取赛道信号倍数"""
        for strategy_key, strategy_data in self.backtest_data.items():
            if strategy_data['sector'] == sector:
                return strategy_data['signal_boost']
        return 1.0  # 默认不增强
    
    def apply_backtest_fusion(self, candidates: List[Dict], sector_distribution: Dict) -> List[Dict]:
        """应用回测数据融合
        
        Args:
            candidates: 候选股票列表
            sector_distribution: 赛道分布字典 {sector: [stocks]}
            
        Returns: 融合后的候选列表
        """
        result = []
        
        for candidate in candidates:
            sector = candidate.get('sector', '未分类')
            signal_boost = self.get_sector_signal_boost(sector)
            
            # 应用赛道倍数 (基于回测表现)
            enhanced_score = candidate.get('score', 50) * signal_boost
            
            # 应用赛道权重加成
            sector_weight = self.sector_weights.get(sector, 0.02)
            weight_bonus = sector_weight * 10  # 权重转化为分数加成
            
            candidate['backtest_fusion_score'] = enhanced_score + weight_bonus
            candidate['signal_boost'] = signal_boost
            candidate['sector_weight'] = sector_weight
            
            result.append(candidate)
        
        return result


class DynamicKellyAdjustment:
    """P2: Kelly系数动态调整 - 按实盘选股准确率调整 (1.75→2.0+)"""
    
    def __init__(self):
        self.kelly_base = 1.75
        self.kelly_adjustments = KELLY_ADJUSTMENT_BY_SECTOR
        self.historical_winrates = {}
        
    def load_historical_winrates(self, db_path: str = None) -> Dict[str, float]:
        """从数据库加载过去3月的选股准确率 (按赛道)"""
        try:
            import sqlite3
            if not db_path:
                db_path = "/home/nikefd/finance-agent/data/trading.db"
            
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # 查询过去3月的选股记录
            since_date = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
            cursor.execute("""
                SELECT sector, AVG(is_profitable) as winrate, COUNT(*) as count
                FROM recommendations
                WHERE date >= ?
                GROUP BY sector
                HAVING count >= 5
            """, (since_date,))
            
            results = cursor.fetchall()
            self.historical_winrates = {
                row[0]: row[1] for row in results
            }
            conn.close()
            
        except Exception as e:
            print(f"⚠️  无法加载历史胜率: {e}, 使用回测数据替代")
            # 降级到回测数据
            self.historical_winrates = {
                '科技成长': 0.60,
                '新能源': 0.70,
                '医药': 0.50,
                '金融': 0.45,
                '消费': 0.25  # 低胜率要回避
            }
        
        return self.historical_winrates
    
    def calculate_kelly_coefficient(self, sector: str, market_sentiment: float = 50.0) -> float:
        """计算赛道级Kelly系数
        
        Args:
            sector: 赛道名称
            market_sentiment: 市场情绪分数 (0-100)
            
        Returns: 调整后的Kelly系数
        """
        # 基础Kelly (按赛道回测表现)
        kelly = self.kelly_adjustments.get(sector, self.kelly_base)
        
        # 根据历史胜率进一步调整
        if sector in self.historical_winrates:
            historical_wr = self.historical_winrates[sector]
            
            # 胜率高于60%: Kelly增加20%
            if historical_wr > 0.60:
                kelly *= 1.20
            # 胜率在40-60%: 保持不变
            elif historical_wr < 0.40:
                kelly *= 0.70  # 胜率低: Kelly大幅降低
        
        # 根据市场情绪调整 (极度贪婪时收紧)
        if market_sentiment > 90:
            kelly *= 0.85
        elif market_sentiment < 30:
            kelly *= 0.90
        
        # Kelly上下限
        kelly = max(0.5, min(2.2, kelly))
        
        return kelly


class EnhancedScoringSystem8D:
    """P3: 8维评分系统 - 新增维度7 (历史胜率) 和维度8 (融资异变)"""
    
    def __init__(self):
        self.weights = DIMENSION_WEIGHTS_V8
        self.historical_winrates = {}
        
    def calculate_dimension7_historical_winrate(self, stock_code: str) -> float:
        """D7: 历史胜率维度 (过去选股准确率)"""
        try:
            import sqlite3
            db_path = "/home/nikefd/finance-agent/data/trading.db"
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # 查询该股过去3月选股准确率
            since_date = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
            cursor.execute("""
                SELECT COUNT(*) as total,
                       SUM(CASE WHEN is_profitable = 1 THEN 1 ELSE 0 END) as wins
                FROM recommendations
                WHERE stock_code = ? AND date >= ?
            """, (stock_code, since_date))
            
            result = cursor.fetchone()
            conn.close()
            
            if result and result[0] >= 3:  # 至少3次推荐
                winrate = result[1] / result[0] if result[1] else 0
                # 转化为0-100分
                return winrate * 100
            else:
                return 50  # 无历史数据时默认50分
                
        except Exception as e:
            print(f"⚠️  计算D7失败: {e}")
            return 50
    
    def calculate_dimension8_margin_anomaly(self, stock_code: str) -> float:
        """D8: 融资异变维度 (融资异常信号评分)"""
        try:
            import akshare as ak
            
            # 获取融资融券数据
            margin_data = ak.margin_day(symbol=stock_code)
            
            if margin_data.empty:
                return 50
            
            latest = margin_data.iloc[-1]
            prev = margin_data.iloc[-2] if len(margin_data) > 1 else None
            
            # 融资异变指标
            finance_change = (latest['余额'] - prev['余额']) / prev['余额'] if prev is not None else 0
            
            # 评分逻辑
            if finance_change > 0.20:  # 融资增加>20%
                return 75  # 资金关注,积极信号
            elif finance_change < -0.25:  # 融资减少>25%
                return 25  # 资金撤出,消极信号
            else:
                return 50  # 正常
                
        except Exception as e:
            print(f"⚠️  计算D8失败: {e}")
            return 50
    
    def compute_enhanced_score_8d(self, candidate: Dict) -> Dict:
        """计算8维综合评分"""
        
        # 提取现有6维
        score_6d = {
            'technical_signal': candidate.get('technical_score', 50),
            'capital_flow': candidate.get('capital_score', 50),
            'market_sentiment': candidate.get('sentiment_score', 50),
            'sector_strength': candidate.get('sector_score', 50),
            'news_sentiment': candidate.get('news_score', 50),
            'entry_quality': candidate.get('entry_quality_score', 50),
        }
        
        # 计算新增维度
        stock_code = candidate.get('code', '')
        score_6d['historical_winrate'] = self.calculate_dimension7_historical_winrate(stock_code)
        score_6d['margin_anomaly_score'] = self.calculate_dimension8_margin_anomaly(stock_code)
        
        # 加权求和
        final_score = sum(
            score * self.weights[dim]
            for dim, score in score_6d.items()
        )
        
        candidate['enhanced_score_8d'] = final_score
        candidate['dimension_scores'] = score_6d
        
        return candidate


class CashActivationTiered:
    """P4: 现金激活机制精细化 - 4层现金阈值自动激活"""
    
    def __init__(self):
        self.tiers = CASH_ACTIVATION_TIERS
        
    def get_activation_tier(self, cash_ratio: float) -> Dict:
        """根据现金占比获取激活层级"""
        
        for tier_name, tier_config in sorted(
            self.tiers.items(),
            key=lambda x: x[1]['cash_threshold'],
            reverse=True
        ):
            if cash_ratio >= tier_config['cash_threshold']:
                return {
                    'tier_name': tier_name,
                    'config': tier_config,
                    'cash_ratio': cash_ratio
                }
        
        # 默认保守模式
        return {
            'tier_name': 'conservative',
            'config': self.tiers['conservative'],
            'cash_ratio': cash_ratio
        }
    
    def apply_cash_tier_adjustment(self, picks: List[Dict], cash_ratio: float) -> List[Dict]:
        """应用现金层级调整"""
        
        tier_info = self.get_activation_tier(cash_ratio)
        tier_config = tier_info['config']
        
        # 调整每个候选的权重
        for pick in picks:
            current_score = pick.get('score', 50)
            
            # 根据Sharpe倍数调整
            adjusted_score = current_score * tier_config['multiplier']
            pick['cash_tier_adjusted_score'] = adjusted_score
            pick['cash_tier'] = tier_info['tier_name']
            pick['entry_quality_threshold'] = tier_config['entry_quality']
        
        return picks


class IntegratedOptimizer141:
    """v5.141 完整集成器 - 将P1-P4优化统一应用"""
    
    def __init__(self):
        self.fusion = BacktestStraegyFusion()
        self.kelly_adj = DynamicKellyAdjustment()
        self.scoring_8d = EnhancedScoringSystem8D()
        self.cash_tier = CashActivationTiered()
        
    def optimize(self, candidates: List[Dict], account_state: Dict, market_sentiment: float = 50) -> Dict:
        """执行完整优化流程
        
        Args:
            candidates: 候选股票列表
            account_state: 账户状态 {'cash_ratio': 0.95, 'total_value': 1000000}
            market_sentiment: 市场情绪分数 (0-100)
            
        Returns: 优化结果
        """
        
        if not candidates:
            return {'status': 'no_candidates', 'picks': []}
        
        result_candidates = []
        cash_ratio = account_state.get('cash_ratio', 0.5)
        
        # P1: 回测策略融合
        candidates = self.fusion.apply_backtest_fusion(candidates, {})
        
        # P3: 8维评分系统
        candidates = [self.scoring_8d.compute_enhanced_score_8d(c) for c in candidates]
        
        # P4: 现金激活层级
        candidates = self.cash_tier.apply_cash_tier_adjustment(candidates, cash_ratio)
        
        # 按综合分数排序
        candidates.sort(key=lambda x: x.get('cash_tier_adjusted_score', 0), reverse=True)
        
        # P2: 应用Kelly调整 (仓位层面)
        kelly_multipliers = {}
        for sector in set(c.get('sector', '未分类') for c in candidates):
            kelly_multipliers[sector] = self.kelly_adj.calculate_kelly_coefficient(
                sector, market_sentiment
            )
        
        return {
            'status': 'success',
            'picks': candidates[:15],  # 前15只
            'backtest_fusion': self.fusion.sector_weights,
            'kelly_multipliers': kelly_multipliers,
            'cash_tier': self.cash_tier.get_activation_tier(cash_ratio),
            'metrics': {
                'total_candidates': len(candidates),
                'selected': min(15, len(candidates)),
                'cash_ratio': cash_ratio,
                'market_sentiment': market_sentiment
            }
        }


def apply_v5_141_optimization_if_enabled(
    picks: List[Dict],
    account_state: Dict,
    market_sentiment: float = 50
) -> Optional[Dict]:
    """条件化应用v5.141优化"""
    
    if not V5_141_ACTIVE:
        return None
    
    try:
        optimizer = IntegratedOptimizer141()
        return optimizer.optimize(picks, account_state, market_sentiment)
    except Exception as e:
        print(f"❌ v5.141优化失败: {e}")
        return None


# =================== 单元测试 ===================

def test_v5_141():
    """v5.141 功能测试"""
    
    print("\n" + "="*60)
    print("🧪 v5.141 晚间深度优化V - 功能测试")
    print("="*60)
    
    # 测试数据
    test_candidates = [
        {
            'code': '000001',
            'name': '平安银行',
            'sector': '金融',
            'score': 50,
            'technical_score': 60,
            'capital_score': 50,
            'sentiment_score': 45,
            'sector_score': 40,
            'news_score': 50,
            'entry_quality_score': 35,
        },
        {
            'code': '000858',
            'name': '五粮液',
            'sector': '消费',
            'score': 45,
            'technical_score': 55,
            'capital_score': 45,
            'sentiment_score': 48,
            'sector_score': 30,
            'news_score': 50,
            'entry_quality_score': 40,
        },
        {
            'code': '000591',
            'name': '太阳能',
            'sector': '新能源',
            'score': 70,
            'technical_score': 75,
            'capital_score': 70,
            'sentiment_score': 65,
            'sector_score': 80,
            'news_score': 70,
            'entry_quality_score': 60,
        },
        {
            'code': '000333',
            'name': '美的集团',
            'sector': '科技成长',
            'score': 72,
            'technical_score': 80,
            'capital_score': 75,
            'sentiment_score': 70,
            'sector_score': 85,
            'news_score': 70,
            'entry_quality_score': 65,
        },
    ]
    
    account_state = {
        'cash_ratio': 0.85,  # 85% 现金 → 激进模式
        'total_value': 1000000
    }
    
    # 执行优化
    result = apply_v5_141_optimization_if_enabled(test_candidates, account_state, market_sentiment=60)
    
    if result and result['status'] == 'success':
        print("\n✅ 优化成功!")
        print(f"   - 候选数: {result['metrics']['total_candidates']}")
        print(f"   - 选中数: {result['metrics']['selected']}")
        print(f"   - 现金占比: {result['metrics']['cash_ratio']*100:.1f}%")
        print(f"   - 激活层级: {result['cash_tier']['tier_name']}")
        print(f"\n   TOP3 选股结果:")
        for i, pick in enumerate(result['picks'][:3]):
            print(f"   {i+1}. {pick.get('name', 'N/A'):10} " +
                  f"(赛道:{pick.get('sector', 'N/A'):8} " +
                  f"8维分:{pick.get('enhanced_score_8d', 0):.1f}) " +
                  f"→ Kelly {result['kelly_multipliers'].get(pick.get('sector', 'N/A'), 1.75):.2f}x")
        print(f"\n   赛道权重 (基于回测):")
        for sector, weight in result['backtest_fusion'].items():
            print(f"   - {sector:10}: {weight*100:5.1f}%")
    else:
        print("❌ 优化失败")
    
    print("\n" + "="*60)


if __name__ == '__main__':
    test_v5_141()
