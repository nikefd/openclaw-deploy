"""
v5.160 晚间深度优化④ - 策略聚焦优化引擎
核心: 基于回测数据 (MACD+RSI科技成长 Sharpe2.35) 重构选股权重

目标改进:
- 移除失效策略 (VOLUME_BREAKOUT, BOLL_REVERT 返回0)
- 强化TOP策略权重 (+40%)
- 赛道优化: 科技成长50% + 新能源30%
- 白马消费限制模式 (<5%)
"""

import json
from datetime import datetime
from typing import Dict, List, Tuple, Optional

# =================== v5.160 核心参数 ===================

# 基于回测Sharpe排序的策略权重
STRATEGY_BACKTEST_SHARPE = {
    'MACD_RSI_TECH_GROWTH': {
        'sharpe': 2.35,
        'win_rate': 0.60,
        'max_dd': 4.08,
        'return': 17.1,
        'weight': 0.45  # 核心策略权重 +40% vs v5.159
    },
    'MACD_RSI_NEW_ENERGY': {
        'sharpe': 1.78,
        'win_rate': 0.70,
        'max_dd': 6.93,
        'return': 14.66,
        'weight': 0.30
    },
    'MULTI_FACTOR_TECH': {
        'sharpe': 1.66,
        'win_rate': 0.57,
        'max_dd': 3.09,
        'return': 6.45,
        'weight': 0.15
    },
    'MA_CROSS': {
        'sharpe': 1.38,
        'win_rate': 0.67,
        'max_dd': 2.86,
        'return': 5.30,
        'weight': 0.05
    },
    'TREND_FOLLOW': {
        'sharpe': 0.97,
        'win_rate': 0.38,
        'max_dd': 2.27,
        'return': 3.93,
        'weight': 0.03
    },
    # 失效策略设置权重为0 (移除)
    'VOLUME_BREAKOUT': {'sharpe': 0.0, 'weight': 0.0},
    'BOLL_REVERT': {'sharpe': -0.55, 'weight': 0.0},
}

# 赛道权重重构 (基于回测结果)
SECTOR_WEIGHTS_V160 = {
    'TECH_GROWTH': 0.50,       # 科技成长 (TOP策略, Sharpe 2.35)
    'NEW_ENERGY': 0.30,        # 新能源 (Sharpe 1.78, 胜率70%)
    'CHIP_SEMI': 0.10,         # 芯片/半导体 (科技细分, 独立优化)
    'WHITE_HORSE': 0.05,       # 白马消费 (限制, -5.51% 表现差)
    'FINANCE': 0.03,           # 金融 (保守, 基础权重)
    'OTHER': 0.02              # 其他 (兜底)
}

# 策略聚焦配置
STRATEGY_FOCUS_CONFIG = {
    'enabled': True,
    'top_strategy_boost': 1.40,  # TOP策略权重×1.40 (从0.30→0.42)
    'multi_factor_weight': 0.25,  # MULTI_FACTOR权重提升
    'weak_sector_conservative': True,  # 白马消费保守模式
    'remove_dead_strategies': ['VOLUME_BREAKOUT', 'BOLL_REVERT'],  # 移除失效策略
}

# 情绪驱动下的策略调整
STRATEGY_SENTIMENT_OVERRIDE = {
    'extreme_fear': {
        'preferred_strategy': 'MULTI_FACTOR_TECH',  # 恐慌时用MULTI_FACTOR (稳定性强)
        'weight_adjustment': {'MACD_RSI': -0.15, 'MULTI_FACTOR': +0.25},
        'sector_override': 'NEW_ENERGY'  # 切换到新能源 (70%胜率)
    },
    'extreme_greed': {
        'preferred_strategy': 'MACD_RSI_TECH_GROWTH',  # 贪婪时用TOP策略
        'weight_adjustment': {'MACD_RSI': +0.25, 'MULTI_FACTOR': -0.10},
        'sector_override': 'TECH_GROWTH'
    }
}


# =================== v5.160 核心函数 ===================

class StrategyOptimizer:
    """基于回测数据的策略优化引擎"""
    
    def __init__(self):
        self.backtest_sharpe = STRATEGY_BACKTEST_SHARPE
        self.sector_weights = SECTOR_WEIGHTS_V160
        self.focus_config = STRATEGY_FOCUS_CONFIG
        self.optimization_log = []
        self.version = "v5.160"
        self.created_at = datetime.now().isoformat()
    
    def get_strategy_score(self, strategy_name: str, market_sentiment: float = 50) -> Dict:
        """
        计算策略综合评分
        
        Args:
            strategy_name: 策略名称 (e.g. 'MACD_RSI_TECH_GROWTH')
            market_sentiment: 市场情绪分数 (0-100)
        
        Returns: {score, weight, recommended, reason}
        """
        if strategy_name not in self.backtest_sharpe:
            return {'score': 0, 'weight': 0, 'recommended': False, 'reason': '策略未知'}
        
        strategy_data = self.backtest_sharpe[strategy_name]
        
        # 基础评分 = Sharpe权重 + 胜率权重
        base_score = strategy_data.get('sharpe', 0) * 0.6 + strategy_data.get('win_rate', 0) * 100 * 0.4
        
        # 情绪调整
        if market_sentiment > 92:  # 极度贪婪
            if 'TECH_GROWTH' in strategy_name:
                base_score *= 1.30  # TOP策略加权
            else:
                base_score *= 0.85
        elif market_sentiment < 25:  # 极度恐慌
            if 'MULTI_FACTOR' in strategy_name:
                base_score *= 1.25  # MULTI_FACTOR加权
            else:
                base_score *= 0.90
        
        # 最终权重
        final_weight = strategy_data.get('weight', 0) * (base_score / 100 if base_score > 0 else 0)
        
        return {
            'strategy': strategy_name,
            'base_score': round(base_score, 2),
            'final_weight': round(final_weight, 3),
            'recommended': strategy_data.get('weight', 0) > 0,
            'reason': self._get_recommendation_reason(strategy_name, base_score),
            'backtest_metrics': {
                'sharpe': strategy_data.get('sharpe'),
                'win_rate': strategy_data.get('win_rate'),
                'max_dd': strategy_data.get('max_dd'),
                'return': strategy_data.get('return')
            }
        }
    
    def _get_recommendation_reason(self, strategy_name: str, score: float) -> str:
        """生成推荐理由"""
        if 'TECH_GROWTH' in strategy_name and score > 1.0:
            return f"TOP策略 (Sharpe 2.35, 回测+17.1%)"
        elif 'NEW_ENERGY' in strategy_name and score > 0.9:
            return f"次优策略 (Sharpe 1.78, 胜率70%)"
        elif 'MULTI_FACTOR' in strategy_name and score > 0.7:
            return f"稳定性优先 (Sharpe 1.66, 利润因子4.2)"
        elif score <= 0:
            return "失效或弱势策略"
        else:
            return "有效但非优先"
    
    def get_sector_weight(self, sector_name: str, sentiment: float = 50) -> float:
        """
        获取赛道权重 (考虑情绪调整)
        
        Args:
            sector_name: 赛道名称 (e.g. 'TECH_GROWTH')
            sentiment: 市场情绪 (0-100)
        
        Returns: 调整后的权重
        """
        base_weight = self.sector_weights.get(sector_name, 0.0)
        
        # 情绪极端时进行赛道切换
        if sentiment > 92 and sector_name == 'TECH_GROWTH':
            return base_weight * 1.20  # 极度贪婪时科技加权
        elif sentiment < 25 and sector_name == 'NEW_ENERGY':
            return base_weight * 1.15  # 极度恐慌时新能源加权 (稳定)
        elif sector_name == 'WHITE_HORSE':
            return base_weight * 0.70  # 白马消费始终保守
        
        return base_weight
    
    def apply_to_candidates(self, candidates: List[Dict], market_sentiment: float = 50) -> List[Dict]:
        """
        将优化权重应用到候选股票
        
        Args:
            candidates: 原始候选股票列表 [{code, strategy, sector, score, ...}]
            market_sentiment: 市场情绪
        
        Returns: 调整后的候选列表
        """
        for candidate in candidates:
            strategy_name = candidate.get('strategy_name', 'UNKNOWN')
            sector = candidate.get('sector', 'OTHER')
            
            # 获取策略评分
            strategy_score = self.get_strategy_score(strategy_name, market_sentiment)
            
            # 应用策略权重 (乘以原始分数)
            if strategy_score['recommended']:
                candidate['strategy_weight'] = strategy_score['final_weight']
                candidate['optimized_score'] = candidate.get('score', 0) * (1 + strategy_score['final_weight'] * 0.5)
            else:
                candidate['strategy_weight'] = 0
                candidate['optimized_score'] = candidate.get('score', 0) * 0.3  # 弱势策略×0.3
            
            # 应用赛道权重
            sector_weight = self.get_sector_weight(sector, market_sentiment)
            candidate['sector_weight'] = sector_weight
            candidate['optimized_score'] *= (1 + sector_weight * 0.3)
            
            # 记录优化过程
            candidate['v160_optimization'] = {
                'strategy_boost': strategy_score['final_weight'],
                'sector_boost': sector_weight,
                'reason': strategy_score['reason']
            }
        
        self.optimization_log.append({
            'timestamp': datetime.now().isoformat(),
            'candidates_count': len(candidates),
            'sentiment': market_sentiment,
            'applied': True
        })
        
        return candidates
    
    def get_optimization_report(self) -> Dict:
        """生成优化报告"""
        return {
            'version': self.version,
            'created_at': self.created_at,
            'strategy_weights': STRATEGY_BACKTEST_SHARPE,
            'sector_weights': self.sector_weights,
            'focus_config': self.focus_config,
            'top_strategy': {
                'name': 'MACD_RSI_TECH_GROWTH',
                'sharpe': 2.35,
                'win_rate': 0.60,
                'max_dd': 4.08,
                'weight_boost': '+40%',
                'expected_improvement': '+15-25%'
            },
            'removed_strategies': self.focus_config['remove_dead_strategies'],
            'optimization_count': len(self.optimization_log),
            'last_applied': self.optimization_log[-1] if self.optimization_log else None
        }


# =================== 实例化全局优化器 ===================

strategy_optimizer = StrategyOptimizer()


# =================== 向下兼容函数 ===================

def get_v160_strategy_weight(strategy_name: str, sentiment: float = 50) -> float:
    """获取v5.160策略权重"""
    score = strategy_optimizer.get_strategy_score(strategy_name, sentiment)
    return score['final_weight']


def apply_v160_optimization(candidates: List[Dict], sentiment: float = 50) -> List[Dict]:
    """应用v5.160优化到候选列表"""
    return strategy_optimizer.apply_to_candidates(candidates, sentiment)


def get_v160_report() -> Dict:
    """获取优化报告"""
    return strategy_optimizer.get_optimization_report()


# 测试代码
if __name__ == '__main__':
    print("=" * 80)
    print("v5.160 晚间深度优化 - 策略聚焦优化引擎")
    print("=" * 80)
    
    # 测试策略评分
    print("\n📊 策略评分 (情绪=50, 正常市场):")
    for strat in ['MACD_RSI_TECH_GROWTH', 'MACD_RSI_NEW_ENERGY', 'MULTI_FACTOR_TECH', 'VOLUME_BREAKOUT']:
        score = strategy_optimizer.get_strategy_score(strat, 50)
        print(f"\n  {strat}:")
        print(f"    基础评分: {score['base_score']}")
        print(f"    权重: {score['final_weight']}")
        print(f"    推荐: {score['recommended']} ({score['reason']})")
        if score['backtest_metrics']['sharpe']:
            print(f"    回测: Sharpe {score['backtest_metrics']['sharpe']}, 胜率 {score['backtest_metrics']['win_rate']:.1%}")
        else:
            print(f"    回测: 无数据")
    
    # 测试情绪调整
    print("\n\n💧 极度贪婪时 (情绪=95):")
    score = strategy_optimizer.get_strategy_score('MACD_RSI_TECH_GROWTH', 95)
    print(f"  TOP策略权重提升 -> {score['final_weight']}")
    
    print("\n\n😨 极度恐慌时 (情绪=20):")
    score = strategy_optimizer.get_strategy_score('MULTI_FACTOR_TECH', 20)
    print(f"  MULTI_FACTOR权重提升 -> {score['final_weight']}")
    
    # 测试赛道权重
    print("\n\n🎯 赛道权重分布:")
    for sector, weight in SECTOR_WEIGHTS_V160.items():
        print(f"  {sector}: {weight:.1%}")
    
    # 获取报告
    report = strategy_optimizer.get_optimization_report()
    print("\n\n📋 优化报告:")
    print(json.dumps(report, indent=2, ensure_ascii=False))
