"""v5.104: 智能超時防護層 ⏱️
3層候選池動態縮放 + 時間預算分配 + 異常自動降級

目標: 保證選股完成時間<10秒, 消除超時風險
"""

import time
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime

@dataclass
class TimeBudget:
    """時間預算分配"""
    total_seconds: float = 10.0
    sentiment_collection: float = 2.0      # 情緒採集
    tech_indicator_calc: float = 4.0       # 技術指標計算
    score_and_rank: float = 3.0            # 評分排序
    buffer_time: float = 1.0               # 緩衝/安全邊際
    
    def get_deadline(self, phase: str) -> float:
        """計算各階段的絕對截止時間(相對於開始時刻)"""
        if phase == 'sentiment':
            return self.sentiment_collection
        elif phase == 'tech':
            return self.sentiment_collection + self.tech_indicator_calc
        elif phase == 'rank':
            return self.sentiment_collection + self.tech_indicator_calc + self.score_and_rank
        elif phase == 'total':
            return self.total_seconds
        return self.total_seconds


class StockPickingTimeoutShield:
    """選股超時防護盾"""
    
    # 3層候選池規模
    POOL_SIZES = {
        'stage1': 100,   # 0-5秒: 全量
        'stage2': 50,    # 5-10秒: 縮減50%
        'stage3': 10,    # >10秒: 緊急降級TOP10
    }
    
    # 各階段時間窗口
    STAGE_WINDOWS = {
        'stage1': (0, 5),      # 0-5秒
        'stage2': (5, 10),     # 5-10秒
        'stage3': (10, float('inf')),  # >10秒
    }
    
    def __init__(self, time_budget: Optional[TimeBudget] = None):
        """初始化
        
        Args:
            time_budget: 自訂時間預算, 默認使用標準10秒配置
        """
        self.time_budget = time_budget or TimeBudget()
        self.start_time = None
        self.phase_times = {}
        self.fallback_cache = None
    
    def start_timing(self):
        """開始計時"""
        self.start_time = time.time()
        self.phase_times = {}
    
    def elapsed_seconds(self) -> float:
        """已耗時(秒)"""
        if not self.start_time:
            return 0
        return time.time() - self.start_time
    
    def check_phase_timeout(self, phase: str) -> Tuple[bool, float]:
        """檢查某階段是否超時
        
        Args:
            phase: 階段名稱 ('sentiment', 'tech', 'rank', 'total')
            
        Returns:
            (is_timeout: bool, remaining_time_seconds: float)
        """
        elapsed = self.elapsed_seconds()
        deadline = self.time_budget.get_deadline(phase)
        is_timeout = elapsed > deadline
        remaining = max(0, deadline - elapsed)
        
        return is_timeout, remaining
    
    def get_current_stage(self) -> str:
        """根據耗時決定當前階段
        
        Returns:
            'stage1', 'stage2', 或 'stage3'
        """
        elapsed = self.elapsed_seconds()
        
        if elapsed < 5:
            return 'stage1'
        elif elapsed < 10:
            return 'stage2'
        else:
            return 'stage3'
    
    def get_pool_size_for_current_stage(self) -> int:
        """獲取當前階段的候選池大小"""
        stage = self.get_current_stage()
        return self.POOL_SIZES[stage]
    
    def adaptive_pool_reduction(self, candidates: List[Dict], 
                                scores: List[float]) -> List[Dict]:
        """自適應候選池縮減
        
        Args:
            candidates: 候選股票列表
            scores: 對應的評分列表
            
        Returns:
            縮減後的候選列表
        """
        stage = self.get_current_stage()
        max_size = self.POOL_SIZES[stage]
        
        if len(candidates) <= max_size:
            return candidates
        
        # 按評分排序取TOP max_size
        indexed = list(zip(range(len(candidates)), scores, candidates))
        indexed.sort(key=lambda x: x[1], reverse=True)
        
        reduced = [item[2] for item in indexed[:max_size]]
        
        return reduced
    
    def record_phase_completion(self, phase: str, success: bool = True):
        """記錄階段完成時間"""
        elapsed = self.elapsed_seconds()
        self.phase_times[phase] = {
            'elapsed_seconds': round(elapsed, 2),
            'success': success,
            'timestamp': datetime.now().isoformat()
        }
    
    def get_performance_report(self) -> Dict:
        """獲取性能報告"""
        total_time = self.elapsed_seconds()
        
        return {
            'total_time_seconds': round(total_time, 2),
            'phases': self.phase_times,
            'final_stage': self.get_current_stage(),
            'status': 'ok' if total_time <= 10 else 'warning' if total_time <= 12 else 'critical',
            'timestamp': datetime.now().isoformat()
        }
    
    def should_trigger_emergency_mode(self) -> bool:
        """判斷是否應觸發緊急模式(降級到TOP5)
        
        規則: 若已耗時>9秒且未完成評分階段
        """
        elapsed = self.elapsed_seconds()
        phase_times = self.phase_times
        
        # 若超過9秒且'rank'階段未完成 → 觸發緊急
        if elapsed > 9 and 'rank' not in phase_times:
            return True
        
        return False
    
    def fallback_to_cache(self, last_picks: List[Dict]) -> List[Dict]:
        """降級到上次結果(用作備用)
        
        當選股邏輯完全超時時,返回上次的TOP候選
        """
        return last_picks[:min(5, len(last_picks))] if last_picks else []


class TimeoutShieldSingleton:
    """單例實例(供全局調用)"""
    _instance = None
    
    @classmethod
    def get_instance(cls) -> StockPickingTimeoutShield:
        if cls._instance is None:
            cls._instance = StockPickingTimeoutShield()
        return cls._instance


def get_timeout_shield() -> StockPickingTimeoutShield:
    """獲取全局超時防護實例"""
    return TimeoutShieldSingleton.get_instance()


def monitor_stock_picking_execution(func):
    """裝飾器: 監控函數執行時間
    
    Usage:
        @monitor_stock_picking_execution
        def pick_stocks(...):
            ...
    """
    def wrapper(*args, **kwargs):
        shield = get_timeout_shield()
        shield.start_timing()
        
        try:
            # 執行選股邏輯
            result = func(*args, **kwargs)
            shield.record_phase_completion('execution', success=True)
            
            report = shield.get_performance_report()
            if report['status'] != 'ok':
                print(f"⚠️  選股耗時{report['total_time_seconds']}秒 (狀態: {report['status']})")
            
            return result
        except Exception as e:
            shield.record_phase_completion('execution', success=False)
            print(f"❌ 選股異常: {e}")
            raise
    
    return wrapper


if __name__ == '__main__':
    print("=" * 60)
    print("v5.104 智能超時防護演示")
    print("=" * 60)
    
    # 模擬選股流程
    shield = StockPickingTimeoutShield()
    shield.start_timing()
    
    print("\n🕐 模擬各階段執行:")
    
    # 階段1: 情緒採集(2秒)
    time.sleep(0.5)
    shield.record_phase_completion('sentiment', True)
    print(f"✅ 情緒採集完成: {shield.elapsed_seconds():.1f}秒")
    print(f"   當前階段: {shield.get_current_stage()}")
    print(f"   候選池規模: {shield.get_pool_size_for_current_stage()}只")
    
    # 階段2: 技術指標(4秒)
    time.sleep(0.8)
    shield.record_phase_completion('tech', True)
    print(f"✅ 技術指標計算: {shield.elapsed_seconds():.1f}秒")
    print(f"   當前階段: {shield.get_current_stage()}")
    print(f"   候選池規模: {shield.get_pool_size_for_current_stage()}只")
    
    # 階段3: 評分排序(3秒)
    time.sleep(0.8)
    shield.record_phase_completion('rank', True)
    print(f"✅ 評分排序完成: {shield.elapsed_seconds():.1f}秒")
    print(f"   當前階段: {shield.get_current_stage()}")
    
    # 最終報告
    report = shield.get_performance_report()
    print(f"\n📊 最終報告:")
    print(f"   總耗時: {report['total_time_seconds']}秒")
    print(f"   狀態: {report['status']}")
    print(f"   詳情: {report['phases']}")
    
    print("\n" + "=" * 60)
    print("池大小自適應演示")
    print("=" * 60)
    
    # 模擬不同階段的池大小
    test_candidates = [{'symbol': f'00{i:04d}', 'score': 100-i} for i in range(150)]
    test_scores = [100-i for i in range(150)]
    
    for stage in ['stage1', 'stage2', 'stage3']:
        max_size = StockPickingTimeoutShield.POOL_SIZES[stage]
        print(f"\n{stage}階段: 候選池最大{max_size}只")
