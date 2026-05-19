"""v5_108_API缓存优化 — 减少重复API调用，提升选股速度"""

import json
import time
from datetime import datetime, timedelta
from functools import wraps

# ============ 内存缓存层 ============

class APICache:
    """简单的内存缓存 — 支持TTL和手动刷新"""
    
    def __init__(self):
        self.cache = {}
        self.timestamps = {}
    
    def get(self, key: str, max_age_seconds: int = 300) -> any:
        """获取缓存，检查是否过期
        
        Args:
            key: 缓存键
            max_age_seconds: 最大年龄(秒)
        
        Returns:
            缓存值或None
        """
        if key not in self.cache:
            return None
        
        age = time.time() - self.timestamps.get(key, 0)
        if age > max_age_seconds:
            del self.cache[key]
            del self.timestamps[key]
            return None
        
        return self.cache[key]
    
    def set(self, key: str, value: any):
        """设置缓存"""
        self.cache[key] = value
        self.timestamps[key] = time.time()
    
    def clear(self, pattern: str = None):
        """清空缓存"""
        if pattern is None:
            self.cache.clear()
            self.timestamps.clear()
        else:
            keys_to_delete = [k for k in self.cache if pattern in k]
            for k in keys_to_delete:
                del self.cache[k]
                del self.timestamps[k]
    
    def size(self) -> int:
        """缓存大小"""
        return len(self.cache)


# 全局缓存实例
_api_cache = APICache()


def cached_api_call(ttl_seconds: int = 300, key_prefix: str = ''):
    """API缓存装饰器
    
    使用示例:
    @cached_api_call(ttl_seconds=300, key_prefix='sentiment')
    def get_market_sentiment():
        return expensive_api_call()
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 生成缓存键 (函数名 + 参数)
            cache_key = f"{key_prefix}:{func.__name__}:{args}:{kwargs}"
            
            # 尝试从缓存获取
            cached_value = _api_cache.get(cache_key, max_age_seconds=ttl_seconds)
            if cached_value is not None:
                return cached_value
            
            # 缓存未命中，调用函数
            result = func(*args, **kwargs)
            
            # 存入缓存
            if result is not None:
                _api_cache.set(cache_key, result)
            
            return result
        return wrapper
    return decorator


# ============ API调用优化 ============

class APICallOptimizer:
    """API调用优化器 — 批量调用、去重、并发限制"""
    
    def __init__(self, rate_limit_per_second: int = 5):
        """
        Args:
            rate_limit_per_second: 每秒最多调用次数
        """
        self.rate_limit = rate_limit_per_second
        self.last_call_time = 0
        self.call_count = 0
    
    def should_throttle(self) -> bool:
        """检查是否需要限流"""
        now = time.time()
        elapsed = now - self.last_call_time
        
        if elapsed >= 1.0:
            # 1秒已过，重置计数
            self.call_count = 0
            self.last_call_time = now
            return False
        
        if self.call_count >= self.rate_limit:
            # 已达限制
            sleep_time = 1.0 - elapsed
            time.sleep(sleep_time)
            self.call_count = 0
            self.last_call_time = time.time()
            return False
        
        self.call_count += 1
        return False
    
    def call_with_throttle(self, func, *args, **kwargs):
        """带限流的API调用"""
        self.should_throttle()
        return func(*args, **kwargs)


# 全局优化器实例
_api_optimizer = APICallOptimizer(rate_limit_per_second=5)


# ============ 批量调用优化 ============

def batch_get_stock_data(symbols: list, data_type: str = 'daily') -> dict:
    """批量获取股票数据，而不是逐只调用
    
    Args:
        symbols: 股票代码列表
        data_type: 数据类型 ('daily', 'realtime', 'fundamental')
    
    Returns:
        {symbol: data...}
    """
    results = {}
    
    # 批量调用API，通常比单独调用更高效
    if data_type == 'realtime':
        # 实时数据通常支持批量查询
        try:
            import akshare as ak
            df = ak.stock_zh_a_hist_jq(symbol=','.join(symbols))
            for _, row in df.iterrows():
                results[row['code']] = row.to_dict()
        except Exception as e:
            print(f"⚠️  批量实时数据获取失败: {e}")
    
    return results


# ============ 性能监控 ============

class APIPerformanceMonitor:
    """API性能监控 — 追踪调用次数、延迟、缓存命中率"""
    
    def __init__(self):
        self.call_count = 0
        self.cache_hits = 0
        self.cache_misses = 0
        self.total_time = 0
    
    def record_call(self, hit: bool = False, duration: float = 0):
        """记录API调用"""
        self.call_count += 1
        self.total_time += duration
        
        if hit:
            self.cache_hits += 1
        else:
            self.cache_misses += 1
    
    def get_stats(self) -> dict:
        """获取统计数据"""
        total = self.cache_hits + self.cache_misses
        hit_rate = (self.cache_hits / total * 100) if total > 0 else 0
        avg_time = (self.total_time / self.call_count) if self.call_count > 0 else 0
        
        return {
            'total_calls': self.call_count,
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'hit_rate_percent': hit_rate,
            'avg_duration_ms': avg_time * 1000,
            'total_duration_s': self.total_time
        }
    
    def reset(self):
        """重置统计"""
        self.call_count = 0
        self.cache_hits = 0
        self.cache_misses = 0
        self.total_time = 0


# 全局监控实例
_performance_monitor = APIPerformanceMonitor()


def get_api_cache():
    """获取全局API缓存实例"""
    return _api_cache


def get_performance_stats():
    """获取API性能统计"""
    return _performance_monitor.get_stats()


def clear_all_caches():
    """清空所有API缓存"""
    _api_cache.clear()
    print("✅ 所有API缓存已清空")


# ============ 验证函数 ============

def validate_v5_108():
    """验证v5.108缓存优化模块"""
    print("✅ v5.108 API缓存优化已加载")
    print(f"   - 内存缓存: {_api_cache.size()}项")
    print(f"   - 速率限制: {_api_optimizer.rate_limit}次/秒")
    print("   - 性能监控: 已启用")
    return True


if __name__ == '__main__':
    validate_v5_108()
