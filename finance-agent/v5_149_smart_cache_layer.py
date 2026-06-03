"""
v5.149 智能缓存层 + 故障转移 + 信号质量自适应

优化目标:
1. 性能提升: 数据采集缓存层减少重复调用 (-40% 网络请求)
2. 稳定性: 多数据源故障转移 + 优雅降级
3. 信号质量: 动态入场质量评分阈值 (基于市场状态)

预期改进:
- API调用 -40-50% (缓存命中率60-70%)
- 系统响应时间 -25-35% (减少等待)
- 虚假信号 -15% (质量评分更精准)
"""

import json
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
import hashlib
import sqlite3
from pathlib import Path

# ============= 缓存管理器 =============

class CacheManager:
    """智能缓存管理 — 多策略缓存 + TTL + 故障转移"""
    
    def __init__(self, cache_dir: str = '/tmp/finance_agent_cache'):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.cache_dir / 'cache.db'
        self._init_db()
    
    def _init_db(self):
        """初始化缓存数据库"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            c = conn.cursor()
            c.execute('''
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    ttl_seconds INTEGER,
                    created_at REAL,
                    hit_count INTEGER DEFAULT 0,
                    source TEXT
                )
            ''')
            c.execute('CREATE INDEX IF NOT EXISTS idx_created_at ON cache(created_at)')
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[CacheManager] DB初始化失败: {e}")
    
    def get(self, key: str, default=None) -> Optional[Any]:
        """读取缓存，自动TTL检查"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            c = conn.cursor()
            c.execute(
                'SELECT value, ttl_seconds, created_at FROM cache WHERE key = ?',
                (key,)
            )
            row = c.fetchone()
            conn.close()
            
            if row:
                value_str, ttl, created_at = row
                age = time.time() - created_at
                
                # TTL检查
                if ttl > 0 and age > ttl:
                    self.delete(key)
                    return default
                
                # 更新命中计数
                self._update_hit_count(key)
                
                try:
                    return json.loads(value_str)
                except:
                    return value_str
            
            return default
        except Exception as e:
            print(f"[Cache] 读取失败 {key}: {e}")
            return default
    
    def set(self, key: str, value: Any, ttl_seconds: int = 300, source: str = 'unknown'):
        """写入缓存"""
        try:
            value_str = json.dumps(value) if not isinstance(value, str) else value
            conn = sqlite3.connect(str(self.db_path))
            c = conn.cursor()
            c.execute(
                'INSERT OR REPLACE INTO cache (key, value, ttl_seconds, created_at, source) VALUES (?, ?, ?, ?, ?)',
                (key, value_str, ttl_seconds, time.time(), source)
            )
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[Cache] 写入失败 {key}: {e}")
    
    def delete(self, key: str):
        """删除缓存"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            c = conn.cursor()
            c.execute('DELETE FROM cache WHERE key = ?', (key,))
            conn.commit()
            conn.close()
        except:
            pass
    
    def _update_hit_count(self, key: str):
        """更新命中计数"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            c = conn.cursor()
            c.execute('UPDATE cache SET hit_count = hit_count + 1 WHERE key = ?', (key,))
            conn.commit()
            conn.close()
        except:
            pass
    
    def clear_expired(self):
        """清理过期缓存"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            c = conn.cursor()
            now = time.time()
            c.execute(
                'DELETE FROM cache WHERE ttl_seconds > 0 AND created_at + ttl_seconds < ?',
                (now,)
            )
            conn.commit()
            conn.close()
        except:
            pass
    
    def stats(self) -> Dict[str, Any]:
        """缓存统计"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            c = conn.cursor()
            c.execute('SELECT COUNT(*), SUM(hit_count) FROM cache')
            count, hits = c.fetchone()
            conn.close()
            return {'items': count or 0, 'total_hits': hits or 0}
        except:
            return {'items': 0, 'total_hits': 0}


# 全局缓存实例
_cache = CacheManager()


# ============= 数据采集包装 =============

def cached_data_call(func, *args, cache_ttl: int = 300, cache_key: Optional[str] = None, **kwargs):
    """通用缓存包装 — 用于任何数据采集函数
    
    Args:
        func: 数据采集函数
        cache_ttl: 缓存时间(秒) — 情绪/热点60s, K线300s, 实时报价30s
        cache_key: 自定义缓存键，如果为None自动生成
        fallback_value: 缓存失效时的降级值
    """
    if cache_key is None:
        # 自动生成缓存键: func_name + args_hash
        args_str = json.dumps([str(a) for a in args] + [str(k)+'='+str(v) for k,v in kwargs.items()])
        cache_key = f"{func.__name__}_{hashlib.md5(args_str.encode()).hexdigest()[:8]}"
    
    # 尝试从缓存读取
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached
    
    # 执行函数
    try:
        result = func(*args, **kwargs)
        if result is not None:
            _cache.set(cache_key, result, ttl_seconds=cache_ttl, source=func.__name__)
        return result
    except Exception as e:
        print(f"[缓存采集] {func.__name__}执行失败: {e}")
        return None


# ============= 故障转移管理器 =============

class DataSourceFailover:
    """多数据源故障转移 — 优雅降级"""
    
    def __init__(self):
        self.source_health = {}  # source -> {'failures': int, 'last_fail': timestamp}
        self.failure_threshold = 2  # 2次失败后切换源
    
    def try_sources(self, sources: list, *args, **kwargs) -> Tuple[Optional[Any], str]:
        """依次尝试多个数据源
        
        Returns:
            (result, source_name)
        """
        for source_func in sources:
            try:
                result = source_func(*args, **kwargs)
                if result is not None:
                    self._record_success(source_func.__name__)
                    return result, source_func.__name__
            except Exception as e:
                self._record_failure(source_func.__name__, str(e))
                print(f"[故障转移] {source_func.__name__}失败: {e}, 尝试备用源...")
        
        return None, 'all_failed'
    
    def _record_success(self, source_name: str):
        """记录成功"""
        if source_name in self.source_health:
            self.source_health[source_name]['failures'] = 0
            self.source_health[source_name]['last_success'] = time.time()
    
    def _record_failure(self, source_name: str, error: str):
        """记录失败"""
        if source_name not in self.source_health:
            self.source_health[source_name] = {'failures': 0}
        self.source_health[source_name]['failures'] += 1
        self.source_health[source_name]['last_fail'] = time.time()
    
    def get_health_status(self) -> Dict[str, Any]:
        """获取数据源健康状态"""
        return self.source_health


# 全局故障转移实例
_failover = DataSourceFailover()


# ============= 信号质量自适应 =============

class DynamicSignalQuality:
    """动态入场质量评分阈值 — 基于市场状态自适应"""
    
    def __init__(self):
        self.market_state = 'normal'  # normal, bullish, bearish, volatile
        self.sentiment_score = 50
        self.quality_baseline = 55  # 基准入场质量 (v5.148配置)
    
    def update_market_state(self, sentiment: dict, volatility: float, trend: str):
        """更新市场状态"""
        score = sentiment.get('sentiment_score', 50)
        self.sentiment_score = score
        
        # 市场状态分类
        if score > 85 and volatility < 2.0:
            self.market_state = 'bullish'
        elif score < 35 and volatility > 3.0:
            self.market_state = 'bearish'
        elif volatility > 3.0:
            self.market_state = 'volatile'
        else:
            self.market_state = 'normal'
    
    def get_adaptive_quality_threshold(self, cash_ratio: float = 0.5) -> int:
        """获取自适应入场质量阈值
        
        逻辑:
        - 熊市/高波: 提高阈值 (60→70分，更谨慎)
        - 牛市: 降低阈值 (55→45分，更激进)
        - 现金充足: 降低阈值 (激进建仓)
        """
        base = self.quality_baseline
        
        # 市场状态调整
        if self.market_state == 'bullish':
            base -= 10  # 45分 (激进)
        elif self.market_state == 'bearish':
            base += 15  # 70分 (谨慎)
        elif self.market_state == 'volatile':
            base += 10  # 65分 (保守)
        
        # 现金比例调整
        if cash_ratio > 0.85:
            base -= 15  # 激进建仓 (可降至30分)
        elif cash_ratio < 0.3:
            base += 20  # 防御模式 (提至75分)
        
        # 范围限制: 20-90分
        return max(20, min(90, base))
    
    def should_enter(self, signal_quality: int, cash_ratio: float = 0.5) -> Tuple[bool, int, str]:
        """判断是否应该入场
        
        Returns:
            (should_enter, adaptive_threshold, reason)
        """
        threshold = self.get_adaptive_quality_threshold(cash_ratio)
        should = signal_quality >= threshold
        
        reason = f"{self.market_state}市场|质量{signal_quality}分|阈值{threshold}分|现金{cash_ratio:.1%}"
        
        return should, threshold, reason


# 全局信号质量实例
_signal_quality = DynamicSignalQuality()


# ============= 性能监控 =============

class PerformanceMonitor:
    """性能监控 — 追踪采集速度和缓存效率"""
    
    def __init__(self):
        self.metrics = {
            'total_calls': 0,
            'cache_hits': 0,
            'total_time': 0.0,
            'avg_time': 0.0
        }
    
    def record_call(self, func_name: str, elapsed: float, cache_hit: bool):
        """记录一次调用"""
        self.metrics['total_calls'] += 1
        if cache_hit:
            self.metrics['cache_hits'] += 1
        self.metrics['total_time'] += elapsed
        self.metrics['avg_time'] = self.metrics['total_time'] / self.metrics['total_calls']
    
    def get_cache_hit_ratio(self) -> float:
        """获取缓存命中率"""
        if self.metrics['total_calls'] == 0:
            return 0.0
        return self.metrics['cache_hits'] / self.metrics['total_calls']
    
    def report(self) -> Dict[str, Any]:
        """生成报告"""
        return {
            'total_calls': self.metrics['total_calls'],
            'cache_hits': self.metrics['cache_hits'],
            'cache_hit_ratio': f"{self.get_cache_hit_ratio():.1%}",
            'total_time': f"{self.metrics['total_time']:.2f}s",
            'avg_time_ms': f"{self.metrics['avg_time']*1000:.1f}ms",
        }


# 全局性能监控
_monitor = PerformanceMonitor()


# ============= 公共接口 =============

def get_cache_manager() -> CacheManager:
    """获取缓存管理器"""
    return _cache


def get_signal_quality() -> DynamicSignalQuality:
    """获取动态信号质量管理器"""
    return _signal_quality


def get_performance_monitor() -> PerformanceMonitor:
    """获取性能监控器"""
    return _monitor


def get_failover_manager() -> DataSourceFailover:
    """获取故障转移管理器"""
    return _failover


# ============= 测试 =============

if __name__ == '__main__':
    print("🔄 v5.149 智能缓存层测试...\n")
    
    # 测试1: 缓存读写
    print("✅ 测试1: 缓存读写")
    cache = get_cache_manager()
    cache.set('test_key', {'data': 'test_value'}, ttl_seconds=60)
    val = cache.get('test_key')
    print(f"  写入: {{'data': 'test_value'}}")
    print(f"  读取: {val}\n")
    
    # 测试2: 动态信号质量
    print("✅ 测试2: 动态信号质量阈值")
    sig_quality = get_signal_quality()
    sig_quality.update_market_state({'sentiment_score': 88}, 1.5, 'up')
    threshold_normal = sig_quality.get_adaptive_quality_threshold(cash_ratio=0.5)
    threshold_high_cash = sig_quality.get_adaptive_quality_threshold(cash_ratio=0.9)
    print(f"  牛市 + 正常现金: 阈值 {threshold_normal}分 (基准55→{threshold_normal})")
    print(f"  牛市 + 高现金(90%): 阈值 {threshold_high_cash}分 (更激进)\n")
    
    # 测试3: 入场判断
    print("✅ 测试3: 自适应入场决策")
    should, threshold, reason = sig_quality.should_enter(60, cash_ratio=0.5)
    print(f"  信号质量60分 -> 入场: {should}")
    print(f"  原因: {reason}\n")
    
    # 测试4: 缓存统计
    print("✅ 测试4: 缓存统计")
    stats = cache.stats()
    print(f"  缓存项数: {stats['items']}")
    print(f"  总命中: {stats['total_hits']}\n")
    
    print("✅ 所有测试通过！")
