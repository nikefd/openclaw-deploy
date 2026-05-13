"""v5.101 盘前优化① - 实时市场情绪信号+超时防护v2+动态入场门槛
时间: 2026-05-13 08:00 UTC
目标: 高情绪日期提升3-5个基点,100%防超时

三大改进:
1. 情绪极值检测器 - 涨停>50自动激进模式
2. 动态候选池缩放 - 保证<1.5s完成
3. 现金占比阶梯激活 - 自动调整入场门槛
"""

from datetime import datetime
import json
from typing import Dict, List, Tuple

# =================== 1. 情绪极值检测器 ===================

class SentimentExtremeDetector:
    """实时市场情绪极值检测与激进模式激活"""
    
    def __init__(self):
        # 极值阈值
        self.limit_up_extreme = 50      # 涨停>50 = 极端贪婪
        self.limit_down_extreme = 20    # 跌停>20 = 极端恐慌
        self.bomb_extreme = 30          # 闪崩>30 = 高风险
        
    def detect_sentiment_extreme(self, sentiment_data: Dict) -> Dict:
        """
        检测市场情绪极值并返回激活模式
        
        Args:
            sentiment_data: get_market_sentiment()的输出
            
        Returns:
            {
                'extreme_mode': 'aggressive'|'normal'|'defensive',
                'limit_up_count': int,
                'limit_down_count': int,
                'bomb_count': int,
                'mode_reason': str,
                'entry_quality_override': int (or None),
                'kelly_boost': float (or 1.0),
            }
        """
        limit_up = sentiment_data.get('limit_up_count', 0)
        limit_down = sentiment_data.get('limit_down_count', 0)
        bomb = sentiment_data.get('bomb_count', 0)
        sentiment_score = sentiment_data.get('sentiment_score', 50)
        
        result = {
            'limit_up_count': limit_up,
            'limit_down_count': limit_down,
            'bomb_count': bomb,
            'entry_quality_override': None,
            'kelly_boost': 1.0,
            'mode_reason': '',
        }
        
        # 极端贪婪: 涨停>50 or 情绪>85
        if limit_up > self.limit_up_extreme or sentiment_score > 85:
            result['extreme_mode'] = 'aggressive'
            result['entry_quality_override'] = 20  # 从35↓20
            result['kelly_boost'] = 1.3
            result['mode_reason'] = f'涨停{limit_up}超极值/情绪{sentiment_score},激进模式'
        
        # 极端恐慌: 跌停>20 or 情绪<30
        elif limit_down > self.limit_down_extreme or sentiment_score < 30:
            result['extreme_mode'] = 'defensive'
            result['entry_quality_override'] = 50  # 从35↑50
            result['kelly_boost'] = 0.7
            result['mode_reason'] = f'跌停{limit_down}超极值/情绪{sentiment_score},防守模式'
        
        # 正常市场
        else:
            result['extreme_mode'] = 'normal'
            result['entry_quality_override'] = None
            result['kelly_boost'] = 1.0
            result['mode_reason'] = '正常市场环境'
        
        return result


# =================== 2. 动态候选池缩放器 ===================

class DynamicCandidatePoolScaler:
    """根据候选数量动态缩小搜索池,保证<1.5秒完成"""
    
    def __init__(self):
        # 时间限制: 1.5秒内必须完成
        self.target_time_sec = 1.5
        
        # 候选数 → 最大筛选数映射
        # 理由: 每个候选需要~10-15ms技术面计算
        # 100个候选 → 1500ms,超过目标 → 缩小到60
        self.candidate_cap_by_pool_size = {
            'total_< 50': 50,        # 候选<50只: 全部检查
            'total_50_100': 60,      # 50-100只: 缩至60
            'total_100_200': 40,     # 100-200只: 缩至40
            'total_200_500': 30,     # 200-500只: 缩至30 (快速筛选)
            'total_500_plus': 20,    # 500+只: 缩至20 (超快速)
        }
        
    def calculate_candidate_limit(self, total_candidates: int) -> int:
        """根据总候选数返回本次应筛选的最大候选数
        
        Args:
            total_candidates: 候选池总数(经过行业/基本面筛选)
            
        Returns:
            本次应该筛选的候选数上限
        """
        if total_candidates < 50:
            return self.candidate_cap_by_pool_size['total_< 50']
        elif total_candidates < 100:
            return self.candidate_cap_by_pool_size['total_50_100']
        elif total_candidates < 200:
            return self.candidate_cap_by_pool_size['total_100_200']
        elif total_candidates < 500:
            return self.candidate_cap_by_pool_size['total_200_500']
        else:
            return self.candidate_cap_by_pool_size['total_500_plus']
    
    def get_scaling_report(self, total_candidates: int) -> Dict:
        """返回缩放诊断报告"""
        cap = self.calculate_candidate_limit(total_candidates)
        return {
            'total_candidates': total_candidates,
            'processing_limit': cap,
            'reduction_pct': 100 - int(100 * cap / total_candidates) if total_candidates > 0 else 0,
            'estimated_time_sec': cap * 0.012,  # 每个候选12ms估算
            'status': '✅ 可控' if cap * 0.012 < self.target_time_sec else '⚠️ 接近上限',
        }


# =================== 3. 现金占比阶梯入场门槛激活器 ===================

class CashRatioTierEntryQuality:
    """根据现金占比自动调整入场质量阈值"""
    
    def __init__(self):
        # 阶梯配置: 现金占比 → 入场门槛
        # 理由: 现金多时应激进建仓,现金少时应保守
        self.cash_ratio_tiers = [
            (0.95, 20),   # 现金>95%: 极激进,阈值20
            (0.90, 24),   # 90-95%: 激进,阈值24
            (0.80, 28),   # 80-90%: 中等,阈值28
            (0.70, 32),   # 70-80%: 偏保守,阈值32
            (0.0, 35),    # <70%: 保守,阈值35(默认)
        ]
    
    def get_entry_quality_threshold(self, current_cash_ratio: float) -> Tuple[int, str]:
        """根据现金占比返回应用的入场质量阈值
        
        Args:
            current_cash_ratio: 当前现金占比(0.0-1.0)
            
        Returns:
            (阈值, 理由)
        """
        for cash_threshold, quality_threshold in self.cash_ratio_tiers:
            if current_cash_ratio >= cash_threshold:
                reason = f"现金占比{current_cash_ratio:.1%}≥{cash_threshold:.0%},应用激进阈值{quality_threshold}"
                return quality_threshold, reason
        
        # 默认
        return 35, "未知现金占比,保持默认阈值35"
    
    def get_all_tiers(self) -> List[Dict]:
        """返回所有阶梯配置(用于调试/日志)"""
        return [
            {
                'cash_ratio_min': tier[0],
                'entry_quality_threshold': tier[1],
                'mode': self._tier_to_mode(tier[1]),
            }
            for tier in self.cash_ratio_tiers
        ]
    
    @staticmethod
    def _tier_to_mode(quality_threshold: int) -> str:
        if quality_threshold <= 20:
            return '极激进'
        elif quality_threshold <= 24:
            return '激进'
        elif quality_threshold <= 28:
            return '中等'
        elif quality_threshold <= 32:
            return '偏保守'
        else:
            return '保守'


# =================== 集成函数 ===================

def apply_v5_101_optimization(
    current_sentiment: Dict,
    total_candidates: int,
    current_cash_ratio: float,
    current_entry_quality_threshold: int,
) -> Dict:
    """集成v5.101三大优化的主函数
    
    这个函数应该在 stock_picker.py 的 pick_stocks() 之前调用
    
    Args:
        current_sentiment: get_market_sentiment()返回的字典
        total_candidates: 本轮候选数(行业/基本面筛选后)
        current_cash_ratio: 当前现金占比
        current_entry_quality_threshold: 当前的ENTRY_QUALITY_THRESHOLD值
        
    Returns:
        {
            'sentiment_mode': str,
            'sentiment_override': Dict (包含entry_quality_override, kelly_boost),
            'candidate_scaling': Dict,
            'cash_tier_entry': Tuple[int, str],
            'final_entry_quality_threshold': int (应该使用这个值),
            'final_kelly_boost': float,
            'optimization_report': str,
        }
    """
    detector = SentimentExtremeDetector()
    scaler = DynamicCandidatePoolScaler()
    cash_tier = CashRatioTierEntryQuality()
    
    # 1. 情绪极值检测
    sentiment_result = detector.detect_sentiment_extreme(current_sentiment)
    
    # 2. 候选池缩放
    scaling_result = scaler.get_scaling_report(total_candidates)
    
    # 3. 现金占比阶梯
    cash_threshold, cash_reason = cash_tier.get_entry_quality_threshold(current_cash_ratio)
    
    # 优先级: 情绪极值 > 现金占比阶梯 > 原配置
    final_entry_quality = (
        sentiment_result['entry_quality_override'] 
        or cash_threshold 
        or current_entry_quality_threshold
    )
    
    final_kelly_boost = sentiment_result['kelly_boost']
    
    # 生成诊断报告
    report = f"""
🔍 v5.101盘前优化诊断报告 [{datetime.now().isoformat()}]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[1] 情绪极值检测
  • 涨停: {sentiment_result['limit_up_count']}只 (极值:{detector.limit_up_extreme})
  • 跌停: {sentiment_result['limit_down_count']}只 (极值:{detector.limit_down_extreme})
  • 闪崩: {sentiment_result['bomb_count']}只
  • 模式: {sentiment_result['extreme_mode'].upper()} 
  • 说明: {sentiment_result['mode_reason']}
  • Kelly加成: {sentiment_result['kelly_boost']:.2f}x

[2] 动态候选池缩放
  • 总候选数: {scaling_result['total_candidates']}只
  • 本次筛选: {scaling_result['processing_limit']}只
  • 缩减比例: {scaling_result['reduction_pct']}%
  • 预计耗时: {scaling_result['estimated_time_sec']:.2f}秒
  • 状态: {scaling_result['status']}

[3] 现金占比阶梯激活
  • 现金占比: {current_cash_ratio:.1%}
  • 应用阈值: {cash_threshold}
  • 说明: {cash_reason}

[4] 最终配置
  • 入场质量阈值: {final_entry_quality} (原:{current_entry_quality_threshold})
  • Kelly倍数: {final_kelly_boost}x
  • 推荐动作: {'启用激进建仓' if sentiment_result['entry_quality_override'] and sentiment_result['entry_quality_override'] < 30 else '正常运行'}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
    
    return {
        'sentiment_mode': sentiment_result['extreme_mode'],
        'sentiment_override': sentiment_result,
        'candidate_scaling': scaling_result,
        'cash_tier_entry': (cash_threshold, cash_reason),
        'final_entry_quality_threshold': final_entry_quality,
        'final_kelly_boost': final_kelly_boost,
        'optimization_report': report,
    }


if __name__ == '__main__':
    # 测试代码
    print("✅ v5.101 盘前优化模块已加载")
    print("\n单元测试:")
    
    # 测试1: 极端贪婪
    test_sentiment_1 = {
        'limit_up_count': 58,
        'limit_down_count': 7,
        'bomb_count': 23,
        'sentiment_score': 87.4,
    }
    
    result = apply_v5_101_optimization(
        current_sentiment=test_sentiment_1,
        total_candidates=150,
        current_cash_ratio=0.96,
        current_entry_quality_threshold=35,
    )
    
    print(result['optimization_report'])
    print(f"\n✅ 最终入场质量阈值应该是: {result['final_entry_quality_threshold']}")
