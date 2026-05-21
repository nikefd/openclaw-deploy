"""
v5.121 集成模块 - Sharpe分级管理 + 赛道智能路由 + 动态入场
"""

import config

class V5_121_SectorRouter:
    """赛道智能路由"""
    
    @staticmethod
    def get_quality_threshold(sector):
        """获取赛道入场质量阈值"""
        return config.SECTOR_QUALITY_THRESHOLDS.get(sector, 20)
    
    @staticmethod
    def get_kelly_multiplier(sector):
        """获取赛道Kelly倍数"""
        return config.SECTOR_KELLY_MULTIPLIERS.get(sector, 0.80)


class V5_121_SharpeGradedRisk:
    """Sharpe分级风险管理"""
    
    @staticmethod
    def get_risk_config(sharpe_ratio):
        """根据Sharpe值获取风险配置"""
        if sharpe_ratio >= 2.0:
            return config.SHARPE_GRADED_RISK['high']
        elif sharpe_ratio >= 1.5:
            return config.SHARPE_GRADED_RISK['medium']
        elif sharpe_ratio >= 1.0:
            return config.SHARPE_GRADED_RISK['normal']
        else:
            return config.SHARPE_GRADED_RISK['low']
    
    @staticmethod
    def adjust_stop_loss(base_stop_loss, sharpe_ratio):
        """根据Sharpe调整止损"""
        config = V5_121_SharpeGradedRisk.get_risk_config(sharpe_ratio)
        return config['stop_loss']
    
    @staticmethod
    def adjust_position_size(base_size, sharpe_ratio):
        """根据Sharpe调整仓位"""
        config = V5_121_SharpeGradedRisk.get_risk_config(sharpe_ratio)
        return base_size * config['position_multiplier']


class V5_121_DynamicEntryQuality:
    """动态入场质量系统"""
    
    @staticmethod
    def get_threshold(market_emotion, cash_ratio, sector='其他'):
        """获取动态入场质量阈值"""
        # 基础阈值 (赛道特定)
        base = V5_121_SectorRouter.get_quality_threshold(sector)
        
        # 情绪调整
        if market_emotion > 90:
            emotion_adj = +8
        elif market_emotion > 85:
            emotion_adj = +5
        elif market_emotion > 70:
            emotion_adj = +2
        elif market_emotion < 30:
            emotion_adj = -3
        else:
            emotion_adj = 0
        
        # 现金调整
        if cash_ratio > 0.95:
            cash_adj = -5
        elif cash_ratio > 0.85:
            cash_adj = -3
        elif cash_ratio > 0.70:
            cash_adj = -1
        else:
            cash_adj = 0
        
        threshold = max(12, base + emotion_adj + cash_adj)
        return threshold


class V5_121_KellyOptimizer:
    """Kelly系数优化器"""
    
    @staticmethod
    def get_optimized_kelly(sector='其他'):
        """获取赛道优化的Kelly系数"""
        base_kelly = config.KELLY_COEFFICIENT  # 1.52
        sector_multiplier = V5_121_SectorRouter.get_kelly_multiplier(sector)
        return base_kelly * sector_multiplier
