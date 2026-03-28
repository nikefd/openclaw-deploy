"""绩效追踪器 — 跟踪推荐准确率、持仓表现、策略有效性"""

import sqlite3
import json
from datetime import datetime, date, timedelta
from config import DB_PATH


def init_tracker_tables():
    """初始化追踪表"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # 推荐记录表 — 每次AI推荐都记录，后续回查准确率
    c.execute('''CREATE TABLE IF NOT EXISTS recommendations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT,
        name TEXT,
        rec_date TEXT,
        rec_price REAL,
        confidence INTEGER,
        signals TEXT,
        strategy TEXT,
        sector TEXT,
        -- 后续填入
        price_1d REAL,
        price_3d REAL,
        price_5d REAL,
        price_10d REAL,
        max_gain REAL,
        max_loss REAL,
        outcome TEXT,
        created_at TEXT
    )''')

    # 策略绩效汇总
    c.execute('''CREATE TABLE IF NOT EXISTS strategy_performance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        strategy TEXT,
        sector TEXT,
        period TEXT,
        total_recs INTEGER,
        win_count INTEGER,
        avg_return REAL,
        hit_rate REAL,
        avg_confidence REAL,
        updated_at TEXT
    )''')

    conn.commit()
    conn.close()


def record_recommendation(symbol: str, name: str, price: float,
                          confidence: int, signals: list,
                          strategy: str = "", sector: str = ""):
    """记录一条推荐"""
    init_tracker_tables()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""INSERT INTO recommendations 
        (symbol, name, rec_date, rec_price, confidence, signals, strategy, sector, created_at)
        VALUES (?,?,?,?,?,?,?,?,?)""",
        (symbol, name, date.today().isoformat(), price, confidence,
         json.dumps(signals, ensure_ascii=False), strategy, sector,
         datetime.now().isoformat()))
    conn.commit()
    conn.close()


def update_recommendation_outcomes():
    """更新历史推荐的实际表现（用日K数据回查）"""
    from data_collector import get_stock_daily
    import time

    init_tracker_tables()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # 找出还没更新outcome的记录（推荐日期至少1天前）
    cutoff = (date.today() - timedelta(days=1)).isoformat()
    c.execute("""SELECT id, symbol, rec_date, rec_price FROM recommendations 
                 WHERE outcome IS NULL AND rec_date <= ?""", (cutoff,))
    pending = c.fetchall()

    updated = 0
    for rec_id, symbol, rec_date, rec_price in pending:
        try:
            df = get_stock_daily(symbol, days=30)
            if df is None or df.empty or rec_price <= 0:
                continue

            # 找推荐日之后的价格
            future = df[df['日期'] > rec_date]
            if future.empty:
                continue

            closes = future['收盘'].astype(float).tolist()
            highs = future['最高'].astype(float).tolist()
            lows = future['最低'].astype(float).tolist()

            price_1d = closes[0] if len(closes) >= 1 else None
            price_3d = closes[2] if len(closes) >= 3 else None
            price_5d = closes[4] if len(closes) >= 5 else None
            price_10d = closes[9] if len(closes) >= 10 else None

            max_high = max(highs) if highs else rec_price
            min_low = min(lows) if lows else rec_price
            max_gain = (max_high - rec_price) / rec_price * 100
            max_loss = (min_low - rec_price) / rec_price * 100

            # 判断outcome: 5日内涨超3%为win, 跌超5%为loss, 其余neutral
            ref_price = price_5d or price_3d or price_1d
            if ref_price:
                ret = (ref_price - rec_price) / rec_price * 100
                if ret >= 3:
                    outcome = 'win'
                elif ret <= -5:
                    outcome = 'loss'
                else:
                    outcome = 'neutral'
            else:
                outcome = 'pending'

            c.execute("""UPDATE recommendations SET 
                price_1d=?, price_3d=?, price_5d=?, price_10d=?,
                max_gain=?, max_loss=?, outcome=?
                WHERE id=?""",
                (price_1d, price_3d, price_5d, price_10d,
                 round(max_gain, 2), round(max_loss, 2), outcome, rec_id))
            updated += 1
            time.sleep(0.3)
        except Exception as e:
            print(f"  ⚠️ 更新{symbol}推荐表现失败: {e}")

    conn.commit()
    conn.close()
    return updated


def get_performance_summary() -> dict:
    """获取推荐绩效汇总"""
    init_tracker_tables()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # 总体统计
    c.execute("SELECT COUNT(*), SUM(CASE WHEN outcome='win' THEN 1 ELSE 0 END), "
              "SUM(CASE WHEN outcome='loss' THEN 1 ELSE 0 END), "
              "AVG(max_gain), AVG(max_loss), AVG(confidence) "
              "FROM recommendations WHERE outcome IS NOT NULL AND outcome != 'pending'")
    row = c.fetchone()
    total = row[0] or 0
    wins = row[1] or 0
    losses = row[2] or 0

    # 按策略分组
    c.execute("""SELECT strategy, COUNT(*), 
              SUM(CASE WHEN outcome='win' THEN 1 ELSE 0 END),
              AVG(CASE WHEN price_5d IS NOT NULL THEN (price_5d - rec_price)/rec_price*100 END),
              AVG(confidence)
              FROM recommendations 
              WHERE outcome IS NOT NULL AND outcome != 'pending'
              GROUP BY strategy""")
    by_strategy = []
    for srow in c.fetchall():
        by_strategy.append({
            'strategy': srow[0] or '未分类',
            'total': srow[1],
            'wins': srow[2],
            'hit_rate': round(srow[2] / max(srow[1], 1) * 100, 1),
            'avg_return': round(srow[3] or 0, 2),
            'avg_confidence': round(srow[4] or 0, 1),
        })

    # 按板块分组
    c.execute("""SELECT sector, COUNT(*), 
              SUM(CASE WHEN outcome='win' THEN 1 ELSE 0 END),
              AVG(CASE WHEN price_5d IS NOT NULL THEN (price_5d - rec_price)/rec_price*100 END)
              FROM recommendations 
              WHERE outcome IS NOT NULL AND outcome != 'pending' AND sector != ''
              GROUP BY sector""")
    by_sector = []
    for srow in c.fetchall():
        by_sector.append({
            'sector': srow[0],
            'total': srow[1],
            'wins': srow[2],
            'hit_rate': round(srow[2] / max(srow[1], 1) * 100, 1),
            'avg_return': round(srow[3] or 0, 2),
        })

    # 最近推荐表现
    c.execute("""SELECT symbol, name, rec_date, rec_price, confidence, signals, 
              price_5d, max_gain, max_loss, outcome
              FROM recommendations ORDER BY rec_date DESC LIMIT 20""")
    recent = []
    for r in c.fetchall():
        recent.append({
            'symbol': r[0], 'name': r[1], 'date': r[2], 'price': r[3],
            'confidence': r[4], 'signals': r[5],
            'price_5d': r[6], 'max_gain': r[7], 'max_loss': r[8], 'outcome': r[9]
        })

    conn.close()
    return {
        'total_recommendations': total,
        'wins': wins,
        'losses': losses,
        'neutrals': total - wins - losses,
        'hit_rate': round(wins / max(total, 1) * 100, 1),
        'avg_max_gain': round(row[3] or 0, 2),
        'avg_max_loss': round(row[4] or 0, 2),
        'avg_confidence': round(row[5] or 0, 1),
        'by_strategy': by_strategy,
        'by_sector': by_sector,
        'recent': recent,
    }


def classify_sector(code: str, name: str = "") -> str:
    """简单板块分类（基于代码和名称关键字）"""
    # 科创板
    if code.startswith('688'):
        return '科技成长'
    # 创业板
    if code.startswith('300') or code.startswith('301'):
        return '科技成长'
    # 名称关键字分类
    name = name.lower()
    tech_kw = ['科技', '电子', '芯片', '半导体', '软件', '信息', '智能', '数据', '通信', '光', '算']
    energy_kw = ['能源', '电力', '风电', '光伏', '锂', '电池', '新能', '储能', '氢', '节能']
    consumer_kw = ['食品', '饮料', '白酒', '乳', '消费', '医药', '药业', '生物', '农', '牧']

    for kw in tech_kw:
        if kw in name:
            return '科技成长'
    for kw in energy_kw:
        if kw in name:
            return '新能源'
    for kw in consumer_kw:
        if kw in name:
            return '消费白马'

    # 主板默认
    if code.startswith('60'):
        return '主板'
    if code.startswith('00'):
        return '主板'
    return '其他'


if __name__ == "__main__":
    print("=== 绩效追踪器测试 ===")
    init_tracker_tables()
    # 更新历史推荐
    n = update_recommendation_outcomes()
    print(f"更新了{n}条推荐记录")
    # 汇总
    summary = get_performance_summary()
    print(json.dumps(summary, ensure_ascii=False, indent=2))
