"""数据源健康监控 — 追踪每个数据源的可用性、延迟、数据量

每次数据源调用时记录状态，提供健康度仪表盘数据
"""

import sqlite3
import json
import time
from datetime import datetime, timedelta
from functools import wraps

DB_PATH = "/home/nikefd/finance-agent/data/trading.db"


def _init_db():
    """初始化监控表"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS datasource_health (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_name TEXT NOT NULL,
        status TEXT NOT NULL,         -- ok / error / empty / slow
        latency_ms INTEGER,           -- 耗时(毫秒)
        record_count INTEGER,         -- 返回数据条数
        error_msg TEXT,
        checked_at TEXT NOT NULL
    )''')
    c.execute('''CREATE INDEX IF NOT EXISTS idx_ds_source_time 
                 ON datasource_health(source_name, checked_at)''')
    conn.commit()
    conn.close()

_init_db()


def record_check(source_name: str, status: str, latency_ms: int = 0,
                 record_count: int = 0, error_msg: str = ""):
    """记录一次数据源检查结果"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(
            '''INSERT INTO datasource_health 
               (source_name, status, latency_ms, record_count, error_msg, checked_at)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (source_name, status, latency_ms, record_count, error_msg,
             datetime.now().isoformat())
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[datasource_monitor] 记录失败: {e}")


def monitored(source_name: str):
    """装饰器: 自动监控数据源函数的健康状态
    
    用法:
        @monitored('东方财富快讯')
        def get_eastmoney_express():
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = func(*args, **kwargs)
                latency = int((time.time() - start) * 1000)
                
                # 判断返回数据量
                if result is None:
                    record_check(source_name, 'error', latency, 0, 'returned None')
                elif isinstance(result, list):
                    count = len(result)
                    status = 'ok' if count > 0 else 'empty'
                    if latency > 10000:
                        status = 'slow'
                    record_check(source_name, status, latency, count)
                elif isinstance(result, dict):
                    count = sum(len(v) for v in result.values() if isinstance(v, list))
                    status = 'ok' if count > 0 or result else 'empty'
                    if latency > 10000:
                        status = 'slow'
                    record_check(source_name, status, latency, count)
                else:
                    record_check(source_name, 'ok', latency, 1)
                
                return result
            except Exception as e:
                latency = int((time.time() - start) * 1000)
                record_check(source_name, 'error', latency, 0, str(e)[:200])
                raise
        return wrapper
    return decorator


def get_health_summary(hours: int = 24) -> list:
    """获取所有数据源的健康汇总
    
    Returns:
        [
            {
                'name': '东方财富快讯',
                'status': 'healthy',        # healthy / degraded / down
                'last_check': '2026-04-02T10:00:00',
                'last_status': 'ok',
                'avg_latency_ms': 500,
                'success_rate': 95.0,       # 最近N次成功率
                'avg_records': 50,
                'total_checks': 10,
                'last_error': '',
            },
            ...
        ]
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    since = (datetime.now() - timedelta(hours=hours)).isoformat()
    
    # 获取所有数据源
    c.execute('''SELECT DISTINCT source_name FROM datasource_health 
                 WHERE checked_at > ? ORDER BY source_name''', (since,))
    sources = [row['source_name'] for row in c.fetchall()]
    
    results = []
    for name in sources:
        # 最近N次检查
        c.execute('''SELECT status, latency_ms, record_count, error_msg, checked_at
                     FROM datasource_health 
                     WHERE source_name = ? AND checked_at > ?
                     ORDER BY checked_at DESC LIMIT 20''', (name, since))
        checks = [dict(row) for row in c.fetchall()]
        
        if not checks:
            continue
        
        total = len(checks)
        ok_count = sum(1 for ch in checks if ch['status'] in ('ok', 'slow'))
        success_rate = round(ok_count / total * 100, 1) if total > 0 else 0
        avg_latency = round(sum(ch['latency_ms'] or 0 for ch in checks) / total)
        avg_records = round(sum(ch['record_count'] or 0 for ch in checks) / total, 1)
        
        last = checks[0]
        last_error = ''
        for ch in checks:
            if ch['error_msg']:
                last_error = ch['error_msg']
                break
        
        # 健康度判断
        if success_rate >= 80 and last['status'] == 'ok':
            health = 'healthy'
        elif success_rate >= 50:
            health = 'degraded'
        else:
            health = 'down'
        
        results.append({
            'name': name,
            'status': health,
            'last_check': last['checked_at'],
            'last_status': last['status'],
            'avg_latency_ms': avg_latency,
            'success_rate': success_rate,
            'avg_records': avg_records,
            'total_checks': total,
            'last_error': last_error[:100],
        })
    
    conn.close()
    
    # 补充未被监控的数据源（手动维护的列表）
    ALL_SOURCES = [
        '东方财富资讯', '财联社电报', 'akshare个股新闻', '雪球热帖',
        '政策公告', '股吧热度', '巨潮公告',
        '北向资金', '北向个股持仓', '龙虎榜机构', '龙虎榜详情',
        '融资融券汇总', '融资融券个股',
        '宏观CPI', '宏观PMI', '宏观M2', '宏观社融',
        '市场情绪', '板块资金流向', '热门股票', '研报',
        '腾讯日K', '腾讯实时行情', '大盘指数',
    ]
    monitored_names = {r['name'] for r in results}
    for name in ALL_SOURCES:
        if name not in monitored_names:
            results.append({
                'name': name,
                'status': 'unknown',
                'last_check': None,
                'last_status': 'never',
                'avg_latency_ms': 0,
                'success_rate': 0,
                'avg_records': 0,
                'total_checks': 0,
                'last_error': '尚未监控',
            })
    
    return results


def run_health_check() -> dict:
    """主动探测所有数据源，返回实时健康状态"""
    print("🔍 数据源健康检查开始...")
    
    results = {}
    
    # --- 新闻/舆情类 ---
    from news_collector import (
        get_eastmoney_express, get_cls_telegraph, get_sina_finance_news,
        get_policy_news, get_guba_hot, get_xueqiu_hot,
    )
    
    checks = [
        ('东方财富资讯', get_eastmoney_express),
        ('财联社电报', get_cls_telegraph),
        ('akshare个股新闻', get_sina_finance_news),
        ('政策公告', get_policy_news),
        ('股吧热度', get_guba_hot),
        ('雪球热帖', get_xueqiu_hot),
    ]
    
    for name, func in checks:
        start = time.time()
        try:
            data = func()
            latency = int((time.time() - start) * 1000)
            count = len(data) if isinstance(data, list) else 0
            status = 'ok' if count > 0 else 'empty'
            record_check(name, status, latency, count)
            results[name] = {'status': status, 'latency': latency, 'count': count}
            print(f"  ✅ {name}: {count}条, {latency}ms")
        except Exception as e:
            latency = int((time.time() - start) * 1000)
            record_check(name, 'error', latency, 0, str(e)[:200])
            results[name] = {'status': 'error', 'latency': latency, 'error': str(e)[:100]}
            print(f"  ❌ {name}: {e}")
        time.sleep(0.3)
    
    # --- 资金面类 ---
    from data_collector import (
        get_market_sentiment, get_sector_fund_flow, get_hot_stocks,
        get_stock_research_reports, get_market_indices, get_stock_daily,
    )
    
    checks2 = [
        ('市场情绪', get_market_sentiment),
        ('板块资金流向', get_sector_fund_flow),
        ('热门股票', get_hot_stocks),
        ('研报', get_stock_research_reports),
        ('大盘指数', get_market_indices),
    ]
    
    for name, func in checks2:
        start = time.time()
        try:
            data = func()
            latency = int((time.time() - start) * 1000)
            if isinstance(data, dict):
                count = len(data)
            elif hasattr(data, '__len__'):
                count = len(data)
            else:
                count = 1 if data else 0
            status = 'ok' if count > 0 else 'empty'
            record_check(name, status, latency, count)
            results[name] = {'status': status, 'latency': latency, 'count': count}
            print(f"  ✅ {name}: {count}条, {latency}ms")
        except Exception as e:
            latency = int((time.time() - start) * 1000)
            record_check(name, 'error', latency, 0, str(e)[:200])
            results[name] = {'status': 'error', 'latency': latency, 'error': str(e)[:100]}
            print(f"  ❌ {name}: {e}")
        time.sleep(0.3)
    
    # 腾讯日K
    start = time.time()
    try:
        df = get_stock_daily('600519', 10)
        latency = int((time.time() - start) * 1000)
        count = len(df) if df is not None and not df.empty else 0
        status = 'ok' if count > 0 else 'empty'
        record_check('腾讯日K', status, latency, count)
        results['腾讯日K'] = {'status': status, 'latency': latency, 'count': count}
        print(f"  ✅ 腾讯日K: {count}条, {latency}ms")
    except Exception as e:
        latency = int((time.time() - start) * 1000)
        record_check('腾讯日K', 'error', latency, 0, str(e)[:200])
        results['腾讯日K'] = {'status': 'error', 'latency': latency, 'error': str(e)[:100]}
        print(f"  ❌ 腾讯日K: {e}")
    
    # --- 扩展数据源 ---
    try:
        from market_data_ext import get_northbound_flow, get_lhb_data, get_margin_data, get_macro_indicators
        
        ext_checks = [
            ('北向资金', get_northbound_flow),
            ('龙虎榜', get_lhb_data),
            ('融资融券', get_margin_data),
            ('宏观指标', get_macro_indicators),
        ]
        
        for name, func in ext_checks:
            start = time.time()
            try:
                data = func()
                latency = int((time.time() - start) * 1000)
                count = len(data) if isinstance(data, dict) else 0
                status = 'ok' if data and count > 0 else 'empty'
                record_check(name, status, latency, count)
                results[name] = {'status': status, 'latency': latency, 'count': count}
                print(f"  ✅ {name}: {latency}ms")
            except Exception as e:
                latency = int((time.time() - start) * 1000)
                record_check(name, 'error', latency, 0, str(e)[:200])
                results[name] = {'status': 'error', 'latency': latency, 'error': str(e)[:100]}
                print(f"  ❌ {name}: {e}")
            time.sleep(0.5)
    except ImportError:
        pass
    
    # 统计
    total = len(results)
    ok = sum(1 for v in results.values() if v['status'] == 'ok')
    print(f"\n📊 健康检查完成: {ok}/{total} 正常")
    
    return {
        'results': results,
        'summary': {
            'total': total,
            'ok': ok,
            'error': sum(1 for v in results.values() if v['status'] == 'error'),
            'empty': sum(1 for v in results.values() if v['status'] == 'empty'),
            'checked_at': datetime.now().isoformat(),
        }
    }


if __name__ == "__main__":
    result = run_health_check()
    print(f"\n总计: {result['summary']}")
