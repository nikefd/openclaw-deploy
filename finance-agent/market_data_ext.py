"""扩展数据源模块 — 北向资金、龙虎榜、融资融券、宏观经济

补充 data_collector.py 和 news_collector.py，提供机构级数据维度
"""

import akshare as ak
import pandas as pd
import requests
import json
import sqlite3
import time
from datetime import datetime, timedelta
from functools import wraps

DB_PATH = "/home/nikefd/finance-agent/data/trading.db"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
}


def retry(max_retries=2, delay=1):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for i in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if i < max_retries - 1:
                        time.sleep(delay * (i + 1))
                    else:
                        print(f"[{func.__name__}] 失败: {e}")
                        return None
            return None
        return wrapper
    return decorator


# ============================================================
# 1. 北向资金 (沪深港通)
# ============================================================
@retry()
def get_northbound_flow() -> dict:
    """北向资金净流入 — 最重要的外资指标
    
    Returns:
        {
            'net_flow_today': float,      # 今日净流入(亿)
            'net_flow_5d': float,         # 5日累计净流入(亿)
            'trend': str,                 # 流入/流出/震荡
            'top_buys': [...],            # 今日增持TOP个股
            'top_sells': [...],           # 今日减持TOP个股
        }
    """
    result = {}
    
    # 北向资金历史净流入 (通过东方财富API)
    try:
        url = "https://push2his.eastmoney.com/api/qt/kamt.kline/get"
        params = {
            'fields1': 'f1,f3,f5',
            'fields2': 'f51,f52,f53,f54,f55,f56',
            'klt': 101,
            'lmt': 10,
            'ut': 'b2884a393a59ad64002292a3e90d46a5',
        }
        r = requests.get(url, params=params, headers=HEADERS, timeout=10)
        data = r.json()
        
        # 解析北向资金数据
        klines_sh = data.get('data', {}).get('s2n', [])  # 沪股通
        klines_sz = data.get('data', {}).get('n2s', [])  # 深股通（字段名可能不同）
        
        if klines_sh:
            # 格式: 日期,净买入,累计净买入,...
            latest = klines_sh[-1].split(',')
            if len(latest) >= 4:
                # f52=沪股通净买入, f53=深股通净买入, f54=北向合计
                result['date'] = latest[0]
                try:
                    result['net_flow_today'] = round(float(latest[1]) / 1e8, 2)  # 转亿
                except:
                    result['net_flow_today'] = 0
            
            # 5日累计
            total_5d = 0
            for k in klines_sh[-5:]:
                parts = k.split(',')
                try:
                    total_5d += float(parts[1])
                except:
                    pass
            result['net_flow_5d'] = round(total_5d / 1e8, 2)
    except Exception as e:
        print(f"北向资金流向获取失败: {e}")
        result['net_flow_today'] = 0
        result['net_flow_5d'] = 0
    
    # 北向资金个股持仓变化 (akshare)
    try:
        df = ak.stock_hsgt_hold_stock_em(market='北向', indicator='今日排行')
        if df is not None and not df.empty:
            # 增持TOP
            df_sorted = df.sort_values('今日增持估计-市值', ascending=False)
            result['top_buys'] = []
            for _, row in df_sorted.head(10).iterrows():
                val = row.get('今日增持估计-市值', 0)
                if pd.notna(val) and float(val) > 0:
                    result['top_buys'].append({
                        'code': str(row.get('代码', '')),
                        'name': str(row.get('名称', '')),
                        'increase_value': round(float(val) / 1e8, 2),  # 亿
                        'hold_pct': float(row.get('今日持股-占流通股比', 0) or 0),
                    })
            
            # 减持TOP
            df_sorted2 = df.sort_values('今日增持估计-市值', ascending=True)
            result['top_sells'] = []
            for _, row in df_sorted2.head(10).iterrows():
                val = row.get('今日增持估计-市值', 0)
                if pd.notna(val) and float(val) < 0:
                    result['top_sells'].append({
                        'code': str(row.get('代码', '')),
                        'name': str(row.get('名称', '')),
                        'decrease_value': round(float(val) / 1e8, 2),  # 亿(负数)
                        'hold_pct': float(row.get('今日持股-占流通股比', 0) or 0),
                    })
    except Exception as e:
        print(f"北向个股持仓获取失败: {e}")
        result['top_buys'] = []
        result['top_sells'] = []
    
    # 趋势判断
    today = result.get('net_flow_today', 0)
    five_day = result.get('net_flow_5d', 0)
    if today > 30 and five_day > 50:
        result['trend'] = '大幅流入'
    elif today > 0 and five_day > 0:
        result['trend'] = '持续流入'
    elif today < -30 and five_day < -50:
        result['trend'] = '大幅流出'
    elif today < 0 and five_day < 0:
        result['trend'] = '持续流出'
    else:
        result['trend'] = '震荡'
    
    return result


# ============================================================
# 2. 龙虎榜 — 游资和机构的真实交易
# ============================================================
@retry()
def get_lhb_data(days: int = 3) -> dict:
    """龙虎榜数据 — 机构和游资的真金白银
    
    Returns:
        {
            'institution_buys': [...],    # 机构买入的股票
            'institution_sells': [...],   # 机构卖出的股票
            'hot_money_buys': [...],      # 游资买入
            'net_buy_top': [...],         # 净买入TOP
        }
    """
    result = {}
    end_date = datetime.now().strftime('%Y%m%d')
    start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')
    
    # 机构买卖统计
    try:
        df = ak.stock_lhb_jgmmtj_em(start_date=start_date, end_date=end_date)
        if df is not None and not df.empty:
            # 机构净买入 > 0
            df['机构买入净额_num'] = pd.to_numeric(df['机构买入净额'], errors='coerce')
            
            buys = df[df['机构买入净额_num'] > 0].sort_values('机构买入净额_num', ascending=False)
            result['institution_buys'] = []
            for _, row in buys.head(15).iterrows():
                result['institution_buys'].append({
                    'code': str(row.get('代码', '')),
                    'name': str(row.get('名称', '')),
                    'net_buy': float(row.get('机构买入净额_num', 0)),
                    'buy_count': int(row.get('买方机构数', 0) or 0),
                    'sell_count': int(row.get('卖方机构数', 0) or 0),
                    'reason': str(row.get('上榜原因', '')),
                    'date': str(row.get('上榜日期', '')),
                })
            
            # 机构净卖出
            sells = df[df['机构买入净额_num'] < 0].sort_values('机构买入净额_num', ascending=True)
            result['institution_sells'] = []
            for _, row in sells.head(10).iterrows():
                result['institution_sells'].append({
                    'code': str(row.get('代码', '')),
                    'name': str(row.get('名称', '')),
                    'net_buy': float(row.get('机构买入净额_num', 0)),
                    'sell_count': int(row.get('卖方机构数', 0) or 0),
                })
    except Exception as e:
        print(f"龙虎榜机构数据获取失败: {e}")
        result['institution_buys'] = []
        result['institution_sells'] = []
    
    # 龙虎榜净买入TOP
    try:
        df2 = ak.stock_lhb_detail_em(start_date=start_date, end_date=end_date)
        if df2 is not None and not df2.empty:
            df2['龙虎榜净买额_num'] = pd.to_numeric(df2['龙虎榜净买额'], errors='coerce')
            top_net = df2.sort_values('龙虎榜净买额_num', ascending=False).head(15)
            result['net_buy_top'] = []
            for _, row in top_net.iterrows():
                result['net_buy_top'].append({
                    'code': str(row.get('代码', '')),
                    'name': str(row.get('名称', '')),
                    'net_buy': round(float(row.get('龙虎榜净买额_num', 0)) / 1e8, 2),  # 亿
                    'change_pct': float(row.get('涨跌幅', 0) or 0),
                    'turnover': float(row.get('换手率', 0) or 0),
                    'reason': str(row.get('上榜原因', '')),
                })
    except Exception as e:
        print(f"龙虎榜详情获取失败: {e}")
        result['net_buy_top'] = []
    
    return result


# ============================================================
# 3. 融资融券 — 杠杆资金动向
# ============================================================
@retry()
def get_margin_data() -> dict:
    """融资融券数据 — 杠杆资金情绪
    
    Returns:
        {
            'total_margin_balance': float,  # 融资余额(亿)
            'margin_change': float,         # 融资余额变化(亿)
            'top_margin_buys': [...],       # 融资买入TOP
            'margin_trend': str,            # 趋势判断
        }
    """
    result = {}
    
    # 融资融券汇总
    try:
        # 先尝试最近的交易日
        for days_back in range(0, 5):
            try:
                date = (datetime.now() - timedelta(days=days_back)).strftime('%Y%m%d')
                df = ak.stock_margin_detail_sse(date=date)
                if df is not None and not df.empty:
                    result['date'] = date
                    # 计算总融资余额
                    df['融资余额_num'] = pd.to_numeric(df['融资余额'], errors='coerce')
                    df['融资买入额_num'] = pd.to_numeric(df['融资买入额'], errors='coerce')
                    total_balance = df['融资余额_num'].sum()
                    total_buy = df['融资买入额_num'].sum()
                    result['total_margin_balance'] = round(total_balance / 1e8, 2)  # 亿
                    result['total_margin_buy'] = round(total_buy / 1e8, 2)
                    break
            except:
                continue
    except Exception as e:
        print(f"融资融券汇总获取失败: {e}")
    
    # 融资余额变化趋势 (通过akshare)
    try:
        df_hist = ak.stock_margin_sse(start_date=(datetime.now() - timedelta(days=30)).strftime('%Y%m%d'),
                                       end_date=datetime.now().strftime('%Y%m%d'))
        if df_hist is not None and not df_hist.empty:
            df_hist['融资余额_num'] = pd.to_numeric(df_hist.get('融资余额(元)', df_hist.iloc[:, 1]), errors='coerce')
            if len(df_hist) >= 5:
                recent = df_hist['融资余额_num'].tail(1).iloc[0]
                prev = df_hist['融资余额_num'].tail(5).iloc[0]
                change = recent - prev
                result['margin_change_5d'] = round(change / 1e8, 2)  # 亿
                
                if change > 50e8:
                    result['margin_trend'] = '杠杆加仓'
                elif change > 0:
                    result['margin_trend'] = '温和加仓'
                elif change < -50e8:
                    result['margin_trend'] = '杠杆去化'
                else:
                    result['margin_trend'] = '小幅减仓'
    except Exception as e:
        print(f"融资余额历史获取失败: {e}")
        result['margin_trend'] = '未知'
    
    # 个股融资买入TOP (高融资买入 = 多头信心)
    try:
        for days_back in range(0, 5):
            try:
                date = (datetime.now() - timedelta(days=days_back)).strftime('%Y%m%d')
                df_detail = ak.stock_margin_detail_sse(date=date)
                if df_detail is not None and not df_detail.empty:
                    df_detail['融资买入额_num'] = pd.to_numeric(df_detail['融资买入额'], errors='coerce')
                    top = df_detail.sort_values('融资买入额_num', ascending=False).head(15)
                    result['top_margin_buys'] = []
                    for _, row in top.iterrows():
                        code = str(row.get('标的证券代码', ''))
                        if len(code) == 6:
                            result['top_margin_buys'].append({
                                'code': code,
                                'name': str(row.get('标的证券简称', '')),
                                'margin_buy': round(float(row.get('融资买入额_num', 0)) / 1e8, 2),  # 亿
                                'margin_balance': round(float(pd.to_numeric(row.get('融资余额', 0), errors='coerce') or 0) / 1e8, 2),
                            })
                    break
            except:
                continue
    except Exception as e:
        print(f"个股融资详情获取失败: {e}")
        result['top_margin_buys'] = []
    
    return result


# ============================================================
# 4. 宏观经济指标
# ============================================================
@retry()
def get_macro_indicators() -> dict:
    """宏观经济关键指标
    
    Returns:
        {
            'cpi': {...},           # 最新CPI
            'pmi': {...},           # 制造业PMI
            'social_finance': {...},# 社融数据
            'money_supply': {...},  # M2/M1
        }
    """
    result = {}
    
    # CPI
    try:
        df = ak.macro_china_cpi_monthly()
        if df is not None and not df.empty:
            latest = df.iloc[-1]
            result['cpi'] = {
                'date': str(latest.get('日期', '')),
                'value': float(latest.get('今值', 0) or 0),
            }
    except Exception as e:
        print(f"CPI获取失败: {e}")
    
    # PMI
    try:
        df = ak.macro_china_pmi()
        if df is not None and not df.empty:
            latest = df.iloc[0]  # 最新在第一行
            result['pmi'] = {
                'date': str(latest.get('月份', '')),
                'manufacturing': float(latest.get('制造业-指数', 0) or 0),
                'non_manufacturing': float(latest.get('非制造业-指数', 0) or 0),
            }
    except Exception as e:
        print(f"PMI获取失败: {e}")
    
    # M2货币供应
    try:
        df = ak.macro_china_money_supply()
        if df is not None and not df.empty:
            # 数据按时间倒序，第一行是最新的
            latest = df.iloc[0]
            result['money_supply'] = {
                'date': str(latest.get('月份', '')),
                'm2_yoy': float(latest.get('货币和准货币(M2)-同比增长', 0) or 0),
                'm1_yoy': float(latest.get('货币(M1)-同比增长', 0) or 0),
            }
            m1 = result['money_supply']['m1_yoy']
            m2 = result['money_supply']['m2_yoy']
            result['money_supply']['scissor'] = round(m1 - m2, 2)
            if m1 - m2 > 0:
                result['money_supply']['signal'] = '资金活化(利好)'
            elif m1 - m2 > -5:
                result['money_supply']['signal'] = '温和沉淀'
            else:
                result['money_supply']['signal'] = '资金沉淀(偏空)'
    except Exception as e:
        print(f"M2获取失败: {e}")
    
    # 社融
    try:
        df = ak.macro_china_shrzgm()
        if df is not None and not df.empty:
            latest = df.iloc[-1]
            result['social_finance'] = {
                'date': str(latest.get('月份', '')),
                'value': float(latest.get('社会融资规模增量', 0) or 0),  # 亿
            }
    except Exception as e:
        print(f"社融获取失败: {e}")
    
    return result


# ============================================================
# 5. 综合资金面分析
# ============================================================
def get_money_flow_overview() -> dict:
    """综合资金面分析 — 北向+龙虎榜+融资融券
    
    Returns 完整的资金面画像
    """
    print("  💰 采集资金面数据...")
    
    print("    → 北向资金...")
    northbound = get_northbound_flow()
    print(f"      今日净流入: {northbound.get('net_flow_today', '?')}亿, 趋势: {northbound.get('trend', '?')}")
    
    time.sleep(0.5)
    print("    → 龙虎榜...")
    lhb = get_lhb_data()
    print(f"      机构买入: {len(lhb.get('institution_buys', []))}只, 净买TOP: {len(lhb.get('net_buy_top', []))}只")
    
    time.sleep(0.5)
    print("    → 融资融券...")
    margin = get_margin_data()
    print(f"      融资余额: {margin.get('total_margin_balance', '?')}亿, 趋势: {margin.get('margin_trend', '?')}")
    
    time.sleep(0.5)
    print("    → 宏观指标...")
    macro = get_macro_indicators()
    print(f"      PMI: {macro.get('pmi', {}).get('manufacturing', '?')}, "
          f"M1-M2剪刀差: {macro.get('money_supply', {}).get('scissor', '?')}")
    
    # 资金面综合评分 (0-100, >60偏多, <40偏空)
    score = 50  # 基准
    
    # 北向资金
    nf = northbound.get('net_flow_today', 0) or 0
    if nf > 50:
        score += 15
    elif nf > 0:
        score += 5
    elif nf < -50:
        score -= 15
    elif nf < 0:
        score -= 5
    
    nf5 = northbound.get('net_flow_5d', 0) or 0
    if nf5 > 100:
        score += 10
    elif nf5 < -100:
        score -= 10
    
    # 融资融券趋势
    mt = margin.get('margin_trend', '')
    if mt == '杠杆加仓':
        score += 10
    elif mt == '温和加仓':
        score += 5
    elif mt == '杠杆去化':
        score -= 10
    elif mt == '小幅减仓':
        score -= 5
    
    # 龙虎榜机构买入
    inst_buys = len(lhb.get('institution_buys', []))
    inst_sells = len(lhb.get('institution_sells', []))
    if inst_buys > inst_sells * 2:
        score += 8
    elif inst_sells > inst_buys * 2:
        score -= 8
    
    # PMI
    pmi = macro.get('pmi', {}).get('manufacturing', 50) or 50
    if pmi > 52:
        score += 5
    elif pmi < 48:
        score -= 5
    
    score = max(0, min(100, score))
    
    # 标签
    if score >= 70:
        label = '资金积极做多'
    elif score >= 55:
        label = '资金偏多'
    elif score >= 45:
        label = '资金中性'
    elif score >= 30:
        label = '资金偏空'
    else:
        label = '资金撤退'
    
    return {
        'northbound': northbound,
        'lhb': lhb,
        'margin': margin,
        'macro': macro,
        'money_flow_score': score,
        'money_flow_label': label,
        'collected_at': datetime.now().isoformat(),
    }


# ============================================================
# 6. 个股级别资金面查询
# ============================================================
def get_stock_money_signals(stock_code: str, stock_name: str, overview: dict) -> dict:
    """查询个股在资金面数据中的信号
    
    Returns:
        {
            'score_delta': int,
            'reasons': [str],
            'northbound_hold': bool,    # 北向是否持有
            'institution_buy': bool,    # 机构龙虎榜买入
            'margin_hot': bool,         # 融资热门
        }
    """
    score = 0
    reasons = []
    flags = {'northbound_hold': False, 'institution_buy': False, 'margin_hot': False}
    
    # 北向资金
    nb = overview.get('northbound', {})
    for stock in nb.get('top_buys', []):
        if stock['code'] == stock_code:
            score += 12
            reasons.append(f"🌏北向增持{stock['increase_value']}亿, 持仓占比{stock['hold_pct']}%")
            flags['northbound_hold'] = True
            break
    for stock in nb.get('top_sells', []):
        if stock['code'] == stock_code:
            score -= 15  # 外资减持是强烈卖出信号
            reasons.append(f"⚠️北向减持{stock['decrease_value']}亿")
            break
    
    # 龙虎榜
    lhb = overview.get('lhb', {})
    for stock in lhb.get('institution_buys', []):
        if stock['code'] == stock_code:
            score += 15
            reasons.append(f"🏛机构龙虎榜买入, {stock['buy_count']}家买/{stock['sell_count']}家卖")
            flags['institution_buy'] = True
            break
    for stock in lhb.get('institution_sells', []):
        if stock['code'] == stock_code:
            score -= 12
            reasons.append(f"⚠️机构龙虎榜净卖出")
            break
    for stock in lhb.get('net_buy_top', []):
        if stock['code'] == stock_code and stock.get('net_buy', 0) > 0:
            score += 8
            reasons.append(f"📊龙虎榜净买入{stock['net_buy']}亿")
            break
    
    # 融资
    margin = overview.get('margin', {})
    for stock in margin.get('top_margin_buys', []):
        if stock['code'] == stock_code:
            score += 5
            reasons.append(f"💳融资买入{stock['margin_buy']}亿")
            flags['margin_hot'] = True
            break
    
    # 资金面总体环境加成
    flow_score = overview.get('money_flow_score', 50)
    if flow_score >= 65:
        score += 3  # 整体资金做多环境，适度加分
    elif flow_score <= 35:
        score -= 3  # 整体资金撤退，适度减分
    
    return {
        'score_delta': score,
        'reasons': reasons,
        **flags,
    }


# ============================================================
# 存储资金面快照
# ============================================================
def save_money_flow_snapshot(overview: dict):
    """保存资金面快照到数据库"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS money_flow_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            data TEXT,
            score INTEGER,
            label TEXT,
            created_at TEXT
        )''')
        
        today = datetime.now().strftime('%Y-%m-%d')
        c.execute(
            'INSERT INTO money_flow_snapshots (date, data, score, label, created_at) VALUES (?, ?, ?, ?, ?)',
            (today, json.dumps(overview, ensure_ascii=False, default=str),
             overview.get('money_flow_score', 50),
             overview.get('money_flow_label', ''),
             datetime.now().isoformat())
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"保存资金面快照失败: {e}")


if __name__ == "__main__":
    print("=== 扩展数据源测试 ===\n")
    
    overview = get_money_flow_overview()
    
    print(f"\n{'='*50}")
    print(f"📊 资金面综合评分: {overview['money_flow_score']}/100 ({overview['money_flow_label']})")
    
    nb = overview['northbound']
    print(f"\n🌏 北向资金:")
    print(f"  今日净流入: {nb.get('net_flow_today', '?')}亿")
    print(f"  5日累计: {nb.get('net_flow_5d', '?')}亿")
    print(f"  趋势: {nb.get('trend', '?')}")
    print(f"  增持TOP3:")
    for s in nb.get('top_buys', [])[:3]:
        print(f"    {s['name']}({s['code']}) +{s['increase_value']}亿")
    
    lhb = overview['lhb']
    print(f"\n🏛 龙虎榜:")
    print(f"  机构买入: {len(lhb.get('institution_buys', []))}只")
    for s in lhb.get('institution_buys', [])[:3]:
        print(f"    {s['name']}({s['code']}) 净买{s['net_buy']/1e8:.2f}亿")
    
    margin = overview['margin']
    print(f"\n💳 融资融券:")
    print(f"  融资余额: {margin.get('total_margin_balance', '?')}亿")
    print(f"  趋势: {margin.get('margin_trend', '?')}")
    
    macro = overview['macro']
    print(f"\n📈 宏观:")
    print(f"  PMI: {macro.get('pmi', {}).get('manufacturing', '?')}")
    print(f"  M1-M2剪刀差: {macro.get('money_supply', {}).get('scissor', '?')} ({macro.get('money_supply', {}).get('signal', '?')})")
    
    save_money_flow_snapshot(overview)
    print("\n✅ 快照已保存")
