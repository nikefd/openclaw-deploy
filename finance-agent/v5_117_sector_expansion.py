"""
v5.117 赛道扩展 + 配置优化
从2个赛道 (科技+新能源) 扩展到5个赛道 (科技/新能源/消费/金融/地产)
"""

import json
from config import *

# ============================================================================
# 赛道定义 v5.117 (5个赛道)
# ============================================================================

SECTOR_DEFINITIONS_V117 = {
    'TECH_GROWTH': {
        'name': '科技成长',
        'description': '高增长科技公司',
        'keywords': ['芯片', '软件', '互联网', '电商', '信息技术', '科技'],
        'target_symbols': ['000651', '300124', '301236', '300750', '301283'],
        'weight': 0.20,
        'strategy': 'MACD+RSI',
        'expected_return': 0.171,
        'max_positions': 15,
        'risk_level': 'HIGH',
    },
    'NEW_ENERGY': {
        'name': '新能源',
        'description': '新能源及清洁能源相关',
        'keywords': ['光伏', '风电', '电池', '新能源', '充电', '电动车'],
        'target_symbols': ['000591', '603501', '688599', '301537', '301228'],
        'weight': 0.15,
        'strategy': 'MOMENTUM_SENTIMENT',
        'expected_return': 0.1466,
        'max_positions': 8,
        'risk_level': 'MEDIUM_HIGH',
    },
    'CONSUMER_WHITE_HORSE': {
        'name': '消费白马',
        'description': '品质消费公司(饮料/食品/日用品)',
        'keywords': ['消费', '食品', '饮料', '日化', '白酒', '快消'],
        'target_symbols': ['000858', '000651', '600887', '600298', '601919'],
        'weight': 0.25,
        'strategy': 'MA_REVERT_VOL',
        'expected_return': 0.10,
        'max_positions': 15,
        'risk_level': 'LOW',
    },
    'FINANCIAL_CYCLE': {
        'name': '金融周期',
        'description': '银行/保险等金融机构',
        'keywords': ['银行', '保险', '证券', '金融', '资产管理'],
        'target_symbols': ['600000', '600016', '601988', '601398', '601166'],
        'weight': 0.20,
        'strategy': 'IV_ARBITRAGE',
        'expected_return': 0.12,
        'max_positions': 10,
        'risk_level': 'MEDIUM',
    },
    'REAL_ESTATE_HEDGE': {
        'name': '地产及其他',
        'description': '房地产/建筑等对冲资产',
        'keywords': ['地产', '房地产', '建筑', '工程', '基建'],
        'target_symbols': ['000002', '000651', '601766', '601588', '601628'],
        'weight': 0.20,
        'strategy': 'MULTI_FACTOR',
        'expected_return': 0.08,
        'max_positions': 8,
        'risk_level': 'MEDIUM_LOW',
    },
}

# ============================================================================
# 赛道策略映射 v5.117
# ============================================================================

SECTOR_STRATEGY_ROUTING_V117 = {
    'TECH_GROWTH': {
        'primary': 'MACD+RSI',
        'secondary': 'MOMENTUM_SENTIMENT',
        'tertiary': 'MULTI_FACTOR',
        'weights': [0.6, 0.3, 0.1],
        'macd_fast': 10,
        'macd_slow': 26,
        'macd_signal': 9,
        'rsi_period': 14,
        'rsi_low': 25,
        'rsi_high': 75,
    },
    'NEW_ENERGY': {
        'primary': 'MOMENTUM_SENTIMENT',
        'secondary': 'MACD+RSI',
        'tertiary': 'MA_CROSS',
        'weights': [0.5, 0.35, 0.15],
        'momentum_period': 20,
        'rsi_low': 30,
        'rsi_high': 70,
    },
    'CONSUMER_WHITE_HORSE': {
        'primary': 'MA_REVERT_VOL',
        'secondary': 'MULTI_FACTOR',
        'tertiary': 'MA_CROSS',
        'weights': [0.5, 0.35, 0.15],
        'ma_period': 120,
        'deviation_pct': 2.5,
        'vol_period': 20,
    },
    'FINANCIAL_CYCLE': {
        'primary': 'IV_ARBITRAGE',
        'secondary': 'MULTI_FACTOR',
        'tertiary': 'MA_REVERT_VOL',
        'weights': [0.5, 0.3, 0.2],
        'iv_lookback': 252,
        'percentile_low': 30,
        'percentile_high': 70,
    },
    'REAL_ESTATE_HEDGE': {
        'primary': 'MULTI_FACTOR',
        'secondary': 'MA_CROSS',
        'tertiary': 'MOMENTUM_SENTIMENT',
        'weights': [0.5, 0.3, 0.2],
    },
}

# ============================================================================
# 赛道权重和持仓限制
# ============================================================================

PORTFOLIO_ALLOCATION_V117 = {
    'TECH_GROWTH': 0.20,
    'NEW_ENERGY': 0.15,
    'CONSUMER_WHITE_HORSE': 0.25,
    'FINANCIAL_CYCLE': 0.20,
    'REAL_ESTATE_HEDGE': 0.20,
}

SECTOR_POSITION_LIMITS_V117 = {
    'TECH_GROWTH': {
        'max_total_positions': 15,
        'max_single_position': 0.05,  # 5% per stock
        'min_sharpe': 1.5,
    },
    'NEW_ENERGY': {
        'max_total_positions': 8,
        'max_single_position': 0.06,  # 6% per stock
        'min_sharpe': 1.4,
    },
    'CONSUMER_WHITE_HORSE': {
        'max_total_positions': 15,
        'max_single_position': 0.04,  # 4% per stock (防御性更强)
        'min_sharpe': 1.3,
    },
    'FINANCIAL_CYCLE': {
        'max_total_positions': 10,
        'max_single_position': 0.05,  # 5% per stock
        'min_sharpe': 1.3,
    },
    'REAL_ESTATE_HEDGE': {
        'max_total_positions': 8,
        'max_single_position': 0.05,  # 5% per stock
        'min_sharpe': 1.2,
    },
}

# ============================================================================
# Kelly准则激进系数 (基于市场情绪)
# ============================================================================

KELLY_FRACTION_BY_SENTIMENT_V117 = {
    'extremely_greedy': {
        'sentiment_range': (85, 100),  # 极度贪婪
        'kelly_fraction': 0.3,  # 保守 (防止过度杠杆)
        'max_new_positions': -0.5,  # 暂停新建仓50%
        'stop_loss_tightness': 1.5,  # 止损更紧
    },
    'greedy': {
        'sentiment_range': (70, 85),  # 贪婪
        'kelly_fraction': 0.5,
        'max_new_positions': -0.3,  # 限制新建仓30%
        'stop_loss_tightness': 1.2,
    },
    'neutral': {
        'sentiment_range': (40, 70),  # 正常
        'kelly_fraction': 0.8,
        'max_new_positions': 0.0,  # 无限制
        'stop_loss_tightness': 1.0,
    },
    'fearful': {
        'sentiment_range': (20, 40),  # 恐惧
        'kelly_fraction': 1.0,  # 激进
        'max_new_positions': 0.2,  # 加速建仓20%
        'stop_loss_tightness': 0.8,  # 止损更松
    },
    'extremely_fearful': {
        'sentiment_range': (0, 20),  # 极度恐惧
        'kelly_fraction': 1.0,  # 最激进
        'max_new_positions': 0.3,  # 加速建仓30%
        'stop_loss_tightness': 0.7,  # 止损最松
    },
}

# ============================================================================
# 赛道风险调整
# ============================================================================

SECTOR_RISK_ADJUSTMENTS_V117 = {
    'TECH_GROWTH': {
        'base_volatility': 0.08,  # 8% (高波动)
        'max_sector_drawdown': 0.06,  # 6% 最大回撤
        'daily_volume_requirement': 1000000,  # 日均成交100万
        'momentum_strength_threshold': 0.02,  # 2% 动量最低
    },
    'NEW_ENERGY': {
        'base_volatility': 0.07,  # 7%
        'max_sector_drawdown': 0.07,  # 7% 最大回撤
        'daily_volume_requirement': 800000,
        'momentum_strength_threshold': 0.015,
    },
    'CONSUMER_WHITE_HORSE': {
        'base_volatility': 0.04,  # 4% (低波动)
        'max_sector_drawdown': 0.03,  # 3% 最大回撤 (防御)
        'daily_volume_requirement': 500000,
        'momentum_strength_threshold': 0.005,
    },
    'FINANCIAL_CYCLE': {
        'base_volatility': 0.05,  # 5%
        'max_sector_drawdown': 0.04,  # 4% 最大回撤
        'daily_volume_requirement': 2000000,  # 高流动性
        'momentum_strength_threshold': 0.01,
    },
    'REAL_ESTATE_HEDGE': {
        'base_volatility': 0.06,  # 6%
        'max_sector_drawdown': 0.05,  # 5% 最大回撤
        'daily_volume_requirement': 500000,
        'momentum_strength_threshold': 0.008,
    },
}

# ============================================================================
# 赛道多样性检查 (避免过度集中)
# ============================================================================

class SectorDiversityChecker:
    """检查投资组合的赛道多样性"""
    
    @staticmethod
    def check_portfolio_balance(holdings_by_sector):
        """
        检查组合中各赛道的权重是否平衡
        
        Args:
            holdings_by_sector: {'TECH_GROWTH': [stocks...], 'NEW_ENERGY': [...]}
        
        Returns:
            {
                'balanced': bool,
                'sector_weights': {...},
                'warnings': [...],
                'suggestions': [...]
            }
        """
        total_value = sum(
            sum(s.get('value', 0) for s in stocks)
            for stocks in holdings_by_sector.values()
        )
        
        sector_weights = {}
        warnings = []
        suggestions = []
        
        for sector, stocks in holdings_by_sector.items():
            sector_value = sum(s.get('value', 0) for s in stocks)
            weight = sector_value / total_value if total_value > 0 else 0
            sector_weights[sector] = weight
            
            # 检查是否超过目标权重
            target_weight = PORTFOLIO_ALLOCATION_V117.get(sector, 0.2)
            if weight > target_weight * 1.5:
                warnings.append(f"{sector}权重过高 ({weight:.1%} vs 目标 {target_weight:.1%})")
                suggestions.append(f"考虑减少{sector}持仓")
            elif weight < target_weight * 0.5:
                warnings.append(f"{sector}权重过低 ({weight:.1%} vs 目标 {target_weight:.1%})")
                suggestions.append(f"考虑增加{sector}持仓")
        
        # 计算多样性指数 (Herfindahl指数)
        herfindahl = sum(w ** 2 for w in sector_weights.values())
        diversified = herfindahl < 0.30  # <0.30表示良好多样性
        
        return {
            'balanced': diversified,
            'sector_weights': sector_weights,
            'herfindahl_index': herfindahl,
            'diversified': diversified,
            'warnings': warnings,
            'suggestions': suggestions,
        }


# ============================================================================
# 配置导出函数
# ============================================================================

def export_v117_config_to_main():
    """
    导出v5.117配置到config.py
    (通常由部署脚本调用)
    """
    config_updates = {
        'SECTOR_DEFINITIONS_V117': SECTOR_DEFINITIONS_V117,
        'SECTOR_STRATEGY_ROUTING_V117': SECTOR_STRATEGY_ROUTING_V117,
        'PORTFOLIO_ALLOCATION_V117': PORTFOLIO_ALLOCATION_V117,
        'SECTOR_POSITION_LIMITS_V117': SECTOR_POSITION_LIMITS_V117,
        'KELLY_FRACTION_BY_SENTIMENT_V117': KELLY_FRACTION_BY_SENTIMENT_V117,
        'SECTOR_RISK_ADJUSTMENTS_V117': SECTOR_RISK_ADJUSTMENTS_V117,
    }
    
    return config_updates


def generate_v117_optimization_summary():
    """生成v5.117优化摘要"""
    summary = {
        'version': 'v5.117',
        'optimization_date': '2026-05-20',
        'optimizations': [
            {
                'id': 'OPT1',
                'name': '新增3个策略',
                'description': 'MOMENTUM_SENTIMENT, MA_REVERT_VOL, IV_ARBITRAGE',
                'expected_improvement': '+5-10% Sharpe',
            },
            {
                'id': 'OPT2',
                'name': '赛道扩展',
                'description': '从2个赛道扩展到5个赛道',
                'expected_improvement': 'Diversification +150%, 回撤 -25-30%',
            },
            {
                'id': 'OPT3',
                'name': '现代投资组合优化',
                'description': '使用MPT和最大Sharpe投资组合',
                'expected_improvement': 'Sharpe +10-20%',
            },
            {
                'id': 'OPT4',
                'name': '智能止损系统',
                'description': '基于ATR和回撤的动态止损',
                'expected_improvement': '最大回撤 -30%, 风险调整回报 +15%',
            },
            {
                'id': 'OPT5',
                'name': '准确率追踪',
                'description': '历史推荐准确率分析和反馈循环',
                'expected_improvement': '识别低效策略, 持续优化',
            },
        ],
        'sector_allocation': PORTFOLIO_ALLOCATION_V117,
        'expected_results': {
            'annual_return': '18-20%',
            'sharpe_ratio': 2.6 - 2.8,
            'max_drawdown': '4-5%',
            'win_rate': '70%+',
        },
    }
    
    return summary


if __name__ == "__main__":
    print("v5.117 赛道扩展配置已加载")
    print(f"✅ 5个赛道定义")
    print(f"✅ 赛道策略路由")
    print(f"✅ 投资组合分配")
    print(f"✅ Kelly准则配置")
    print(f"✅ 风险调整")
    print()
    print("赛道配置:")
    for sector, config in SECTOR_DEFINITIONS_V117.items():
        print(f"  - {config['name']}: {config['weight']:.0%} | {config['max_positions']}头 | Sharpe目标 {config['expected_return']:.1%}")
