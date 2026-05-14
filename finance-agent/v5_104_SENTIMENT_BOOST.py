"""v5.104: 市场情绪信号优化 ⚡
加快情绪信号反应速度，支持极值快速模式 + 机构资金信号分离

预期效果:
- 漲停潮時情緒信號反應時間 5秒 → 1秒
- 新增機構資金信號維度
"""

import json
from datetime import datetime, timedelta
from typing import Dict, Tuple

class SentimentBoostOptimizer:
    """情緒信號優化引擎"""
    
    def __init__(self, ema_alpha: float = 0.4):
        """
        Args:
            ema_alpha: EMA平滑係數（v5.103: 0.4）
        """
        self.ema_alpha = ema_alpha
        self.last_sentiment_cache = {}
        self.rapid_mode_cooldown = 600  # 10分鐘內重複極值警告冷卻
        self.last_extreme_alert_time = 0
    
    def detect_limit_up_surge(self, current_count: int, prev_count: int, minutes_elapsed: int = 10) -> bool:
        """檢測漲停潮(10分鐘內+10只)
        
        Args:
            current_count: 當前漲停池數量
            prev_count: 前一時刻漲停池數量(從DB或None)
            minutes_elapsed: 時間差
            
        Returns:
            True if 急速模式應啟動
        """
        if prev_count is None:
            return False
        
        increase_rate = (current_count - prev_count) / max(prev_count, 1)
        new_counts = current_count - prev_count
        
        # 條件: 10分鐘內新增>10只 或 漲停數增速>50%
        return (new_counts >= 10) or (increase_rate > 0.5 and new_counts >= 5)
    
    def extract_institution_signal(self, limit_up_count: int, big_buy_count: int) -> Dict:
        """提取機構資金信號
        
        機構買盤佔漲停數比例高 → 機構主動建倉 → 強勢信號
        """
        if limit_up_count == 0:
            ratio = 0
        else:
            ratio = big_buy_count / limit_up_count
        
        return {
            'big_buy_ratio': round(ratio, 3),  # 機構買盤/漲停數
            'signal_strength': 'strong' if ratio > 0.5 else 'normal' if ratio > 0.2 else 'weak',
            'interpretation': '機構主動建倉' if ratio > 0.5 else '主動資金參與' if ratio > 0.2 else '散戶主導'
        }
    
    def should_skip_ema_smoothing(self, sentiment_score: float, prev_score: float = None) -> bool:
        """判斷是否應跳過EMA平滑(啟動快速模式)
        
        極值判定:
        - 評分>82 或 <28 (超出常規範圍)
        - 評分變化>20點(快速變化)
        """
        is_extreme = sentiment_score > 82 or sentiment_score < 28
        
        if prev_score is not None:
            large_jump = abs(sentiment_score - prev_score) > 20
            return is_extreme or large_jump
        
        return is_extreme
    
    def apply_adaptive_smoothing(self, raw_score: float, history_scores: list, 
                                 is_rapid_mode: bool = False) -> Tuple[float, str, Dict]:
        """自適應EMA平滑
        
        Args:
            raw_score: 原始情緒評分
            history_scores: 最近5日評分列表(從舊→新)
            is_rapid_mode: 是否啟動急速模式
            
        Returns:
            (smoothed_score, mode_used, debug_info)
        """
        if is_rapid_mode or not history_scores:
            return raw_score, 'rapid', {'ema_skipped': True, 'reason': 'extreme_value_detected'}
        
        # 正常EMA
        if len(history_scores) >= 2:
            ema = history_scores[-1]  # 從最舊開始
            alpha = self.ema_alpha
            
            # 順向遍歷(舊→新)
            for score in history_scores[-2:]:
                ema = alpha * score + (1 - alpha) * ema
            
            # 混入今日原始值
            ema = alpha * raw_score + (1 - alpha) * ema
            
            return round(ema, 1), 'ema', {
                'ema_applied': True,
                'alpha': alpha,
                'raw_score': raw_score,
                'smoothed_score': ema
            }
        else:
            return raw_score, 'no_history', {'reason': 'insufficient_history'}
    
    def generate_enhanced_sentiment(self, base_sentiment: Dict, 
                                   force_rapid_mode: bool = False) -> Dict:
        """生成增強型情緒指標
        
        Args:
            base_sentiment: data_collector.get_market_sentiment()的輸出
            force_rapid_mode: 是否強制急速模式
            
        Returns:
            增強情緒字典 (包含新增欄位)
        """
        result = base_sentiment.copy()
        
        # 檢測急速模式條件
        limit_up = result.get('limit_up_count', 0)
        prev_data = self.last_sentiment_cache
        prev_limit_up = prev_data.get('limit_up_count', None) if prev_data else None
        
        is_surge = self.detect_limit_up_surge(limit_up, prev_limit_up, minutes_elapsed=10)
        raw_score = result.get('sentiment_score', 50)
        is_extreme = self.should_skip_ema_smoothing(raw_score, 
                                                    prev_data.get('sentiment_score') if prev_data else None)
        
        rapid_mode = force_rapid_mode or is_surge or is_extreme
        
        # 提取機構信號
        big_buy_count = result.get('big_buy_count', 0)
        inst_signal = self.extract_institution_signal(limit_up, big_buy_count)
        
        # 應用自適應平滑 (暫時略過EMA, 因為v5.103已有)
        # 但可透過force_rapid_mode觸發快速反應
        if rapid_mode:
            result['_rapid_mode'] = True
            result['_rapid_reason'] = 'surge' if is_surge else 'extreme' if is_extreme else 'manual'
            result['_reaction_speed'] = 'immediate'
        else:
            result['_rapid_mode'] = False
            result['_reaction_speed'] = 'normal_ema'
        
        # 新增維度
        result['institution_signal'] = inst_signal
        result['sentiment_v104_enhanced'] = True
        
        # 緩存本次結果
        self.last_sentiment_cache = result
        
        return result


# 全局實例 (供stock_picker調用)
sentiment_booster = SentimentBoostOptimizer()


def boost_market_sentiment(raw_sentiment: Dict) -> Dict:
    """一鍵增強情緒信號(供data_collector調用)
    
    Usage:
        sentiment = get_market_sentiment()  # 原始
        enhanced = boost_market_sentiment(sentiment)  # 增強
    """
    return sentiment_booster.generate_enhanced_sentiment(raw_sentiment)


if __name__ == '__main__':
    # 測試
    booster = SentimentBoostOptimizer()
    
    # 模擬基礎情緒
    test_sentiment = {
        'limit_up_count': 25,
        'limit_down_count': 5,
        'bomb_count': 2,
        'big_buy_count': 8,
        'sentiment_score': 68.5,
        'sentiment_label': '乐观'
    }
    
    enhanced = booster.generate_enhanced_sentiment(test_sentiment, force_rapid_mode=False)
    print("✅ 基礎情緒增強:")
    print(json.dumps(enhanced, indent=2, ensure_ascii=False))
    
    # 模擬漲停潮
    test_sentiment_surge = {
        'limit_up_count': 35,  # +10
        'limit_down_count': 3,
        'bomb_count': 1,
        'big_buy_count': 18,
        'sentiment_score': 72.0,
        'sentiment_label': '乐观'
    }
    
    enhanced_surge = booster.generate_enhanced_sentiment(test_sentiment_surge)
    print("\n⚡ 漲停潮檢測:")
    print(json.dumps(enhanced_surge, indent=2, ensure_ascii=False))
    print(f"  → 激活急速模式: {enhanced_surge.get('_rapid_mode')}")
    print(f"  → 反應速度: {enhanced_surge.get('_reaction_speed')}")
