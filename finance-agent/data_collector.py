"""数据采集模块 v2 — 加重试、UA伪装、多数据源"""

import akshare as ak
import pandas as pd
import requests
import time
import json
from datetime import datetime, timedelta
from functools import wraps

# 伪装UA
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Referer': 'https://data.eastmoney.com/',
}

def retry(max_retries=3, delay=2):
    """重试装饰器"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for i in range(max_retries):
                try:
                    result = func(*args, **kwargs)
                    return result
                except Exception as e:
                    if i < max_retries - 1:
                        time.sleep(delay * (i + 1))
                    else:
                        print(f"[{func.__name__}] 重试{max_retries}次后失败: {e}")
                        return None
            return None
        return wrapper
    return decorator


@retry(max_retries=2, delay=1)
def get_stock_news(symbol: str = None) -> pd.DataFrame:
    """获取财联社/东方财富新闻"""
    df = ak.stock_news_em()
    if symbol:
        df = df[df['关键词'].str.contains(symbol, na=False)]
    return df.head(50)


@retry(max_retries=2, delay=1)
def get_market_sentiment() -> dict:
    """获取市场情绪指标"""
    today = datetime.now().strftime('%Y%m%d')
    result = {}

    # 涨停池
    try:
        df_up = ak.stock_zt_pool_em(date=today)
        result['limit_up_count'] = len(df_up)
        result['limit_up_stocks'] = df_up[['代码','名称','涨跌幅','成交额']].head(10).to_dict('records') if not df_up.empty else []
    except:
        result['limit_up_count'] = 0
        result['limit_up_stocks'] = []

    # 跌停池
    try:
        df_down = ak.stock_zt_pool_dtgc_em(date=today)
        result['limit_down_count'] = len(df_down)
    except:
        result['limit_down_count'] = 0

    # 炸板池
    try:
        df_bomb = ak.stock_zt_pool_zbgc_em(date=today)
        result['bomb_count'] = len(df_bomb)
    except:
        result['bomb_count'] = 0

    # 连板池
    try:
        df_strong = ak.stock_zt_pool_strong_em(date=today)
        result['strong_stocks'] = df_strong[['代码','名称','涨跌幅','连板数']].head(10).to_dict('records') if not df_strong.empty else []
    except:
        result['strong_stocks'] = []

    # 大单异动
    try:
        df_changes = ak.stock_changes_em(symbol='大笔买入')
        result['big_buy_count'] = len(df_changes)
        result['big_buys'] = df_changes[['代码','名称','板块']].head(10).to_dict('records') if not df_changes.empty else []
    except:
        result['big_buy_count'] = 0
        result['big_buys'] = []

    # 情绪评分
    up = result.get('limit_up_count', 0)
    down = result.get('limit_down_count', 0)
    bomb = result.get('bomb_count', 0)
    if up + down > 0:
        ratio = up / (up + down)
        bomb_rate = bomb / max(up + bomb, 1)
        score = ratio * 70 + (1 - bomb_rate) * 20 + min(up / 50, 1) * 10
        result['sentiment_score'] = round(min(score, 100), 1)
    else:
        result['sentiment_score'] = 50

    # 情绪标签
    s = result['sentiment_score']
    if s >= 80: result['sentiment_label'] = '贪婪'
    elif s >= 65: result['sentiment_label'] = '乐观'
    elif s >= 45: result['sentiment_label'] = '中性'
    elif s >= 30: result['sentiment_label'] = '谨慎'
    else: result['sentiment_label'] = '恐慌'

    return result


def get_stock_daily(symbol: str, days: int = 60) -> pd.DataFrame:
    """获取个股日K数据 — 腾讯财经源（稳定不限IP）"""
    try:
        prefix = 'sh' if symbol.startswith('6') or symbol.startswith('9') else 'sz'
        qq_symbol = f'{prefix}{symbol}'
        start = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        end = datetime.now().strftime('%Y-%m-%d')
        url = f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={qq_symbol},day,{start},{end},{days},qfq'
        r = requests.get(url, timeout=15)
        data = r.json()
        stock_data = data.get('data', {}).get(qq_symbol, {})
        klines = stock_data.get('qfqday', stock_data.get('day', []))
        if not klines:
            return pd.DataFrame()
        cols = ['日期', '开盘', '收盘', '最高', '最低', '成交量']
        df = pd.DataFrame(klines, columns=cols[:len(klines[0])])
        for col in ['开盘', '收盘', '最高', '最低', '成交量']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        return df
    except Exception as e:
        print(f"获取{symbol}日K失败: {e}")
        return pd.DataFrame()


def get_realtime_quotes(symbols: list) -> dict:
    """批量获取实时行情 — 腾讯财经源"""
    try:
        qq_list = []
        for s in symbols:
            prefix = 'sh' if s.startswith('6') or s.startswith('9') else 'sz'
            qq_list.append(f'{prefix}{s}')
        url = f'https://qt.gtimg.cn/q={",".join(qq_list)}'
        r = requests.get(url, timeout=10)
        result = {}
        for line in r.text.strip().split(';'):
            line = line.strip()
            if not line or '=' not in line:
                continue
            parts = line.split('=')
            if len(parts) < 2:
                continue
            data = parts[1].strip('"').split('~')
            if len(data) < 5:
                continue
            result[data[2]] = {
                'name': data[1],
                'price': float(data[3]) if data[3] else 0,
                'change_pct': float(data[32]) if len(data) > 32 and data[32] else 0,
            }
        return result
    except Exception as e:
        print(f"获取实时行情失败: {e}")
        return {}


def get_hot_stocks() -> pd.DataFrame:
    """获取热门股票 — 直接调东方财富API"""
    try:
        url = 'https://emappdata.eastmoney.com/stockrank/getAllCurrentList'
        data = {
            'appId': 'appId01',
            'globalId': '786e4c21-70dc-435a-93bb-38',
            'marketType': '',
            'pageNo': 1,
            'pageSize': 30
        }
        r = requests.post(url, json=data, headers=HEADERS, timeout=10)
        items = r.json().get('data', [])
        if not items:
            return pd.DataFrame()

        # 获取股票名称和价格
        codes = [item['sc'] for item in items]
        records = []
        for item in items:
            records.append({
                '排名': item['rk'],
                '代码': item['sc'],
                '排名变化': item['rc'],
            })
        return pd.DataFrame(records)
    except Exception as e:
        print(f"获取热门股票失败: {e}")
        return pd.DataFrame()


def get_sector_fund_flow() -> pd.DataFrame:
    """获取板块资金流向 — 直接调东方财富API"""
    try:
        url = "https://push2.eastmoney.com/api/qt/clist/get"
        params = {
            'fid': 'f62',
            'po': 1,
            'pz': 20,
            'pn': 1,
            'np': 1,
            'fltt': 2,
            'invt': 2,
            'fs': 'm:90+t:2',
            'fields': 'f12,f14,f2,f3,f62,f184,f66,f69,f72,f75,f78,f81,f84,f87',
        }
        r = requests.get(url, params=params, headers=HEADERS, timeout=10)
        data = r.json()
        items = data.get('data', {}).get('diff', [])
        if not items:
            return pd.DataFrame()

        records = []
        for item in items:
            records.append({
                '板块代码': item.get('f12', ''),
                '板块名称': item.get('f14', ''),
                '涨跌幅': item.get('f3', 0),
                '主力净流入': item.get('f62', 0),
                '主力净流入占比': item.get('f184', 0),
                '超大单净流入': item.get('f66', 0),
                '大单净流入': item.get('f72', 0),
            })
        return pd.DataFrame(records)
    except Exception as e:
        print(f"获取板块资金流向失败: {e}")
        return pd.DataFrame()


def get_stock_research_reports(symbol: str = None) -> pd.DataFrame:
    """获取研报 — 东方财富研报中心"""
    try:
        if symbol:
            # 个股研报
            url = f"https://reportapi.eastmoney.com/report/list"
            params = {
                'industryCode': '*',
                'pageSize': 15,
                'industry': '*',
                'rating': '*',
                'ratingChange': '*',
                'beginTime': (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'),
                'endTime': datetime.now().strftime('%Y-%m-%d'),
                'pageNo': 1,
                'fields': '',
                'qType': 0,
                'orgCode': '',
                'code': symbol,
                '_': int(time.time() * 1000)
            }
        else:
            # 最新研报
            url = "https://reportapi.eastmoney.com/report/list"
            params = {
                'industryCode': '*',
                'pageSize': 30,
                'industry': '*',
                'rating': '*',
                'ratingChange': '*',
                'beginTime': (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'),
                'endTime': datetime.now().strftime('%Y-%m-%d'),
                'pageNo': 1,
                'fields': '',
                'qType': 0,
                'orgCode': '',
                'code': '*',
                '_': int(time.time() * 1000)
            }

        r = requests.get(url, params=params, headers=HEADERS, timeout=10)
        data = r.json()
        items = data.get('data', [])
        if not items:
            return pd.DataFrame()

        records = []
        for item in items:
            records.append({
                '标题': item.get('title', ''),
                '股票代码': item.get('stockCode', ''),
                '股票名称': item.get('stockName', ''),
                '机构': item.get('orgSName', ''),
                '作者': item.get('researcher', ''),
                '评级': item.get('emRatingName', ''),
                '日期': item.get('publishDate', '')[:10] if item.get('publishDate') else '',
            })
        return pd.DataFrame(records)
    except Exception as e:
        print(f"获取研报失败: {e}")
        return pd.DataFrame()


def get_market_indices() -> dict:
    """获取大盘指数 — 腾讯财经源"""
    try:
        url = 'https://qt.gtimg.cn/q=sh000001,sz399001,sz399006'
        r = requests.get(url, timeout=10)
        result = {}
        for line in r.text.strip().split(';'):
            line = line.strip()
            if not line or '=' not in line:
                continue
            data = line.split('=')[1].strip('"').split('~')
            if len(data) < 33:
                continue
            result[data[1]] = {
                'price': float(data[3]) if data[3] else 0,
                'change_pct': float(data[32]) if data[32] else 0,
                'change': float(data[31]) if len(data) > 31 and data[31] else 0,
            }
        return result
    except Exception as e:
        print(f"获取指数失败: {e}")
        return {}


def calculate_technical_indicators(df: pd.DataFrame) -> dict:
    """计算技术指标"""
    if df is None or df.empty or len(df) < 20:
        return {}

    close = df['收盘'].astype(float)
    volume = df['成交量'].astype(float) if '成交量' in df.columns else None

    indicators = {}

    # MA均线
    indicators['ma5'] = round(close.tail(5).mean(), 2)
    indicators['ma10'] = round(close.tail(10).mean(), 2)
    indicators['ma20'] = round(close.tail(20).mean(), 2)
    if len(close) >= 60:
        indicators['ma60'] = round(close.tail(60).mean(), 2)

    # RSI (14日)
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss.replace(0, float('nan'))
    rsi = 100 - (100 / (1 + rs))
    indicators['rsi14'] = round(rsi.iloc[-1], 1) if not rsi.empty else 50

    # MACD
    ema12 = close.ewm(span=12).mean()
    ema26 = close.ewm(span=26).mean()
    dif = ema12 - ema26
    dea = dif.ewm(span=9).mean()
    macd = 2 * (dif - dea)
    indicators['macd'] = round(macd.iloc[-1], 4)
    indicators['macd_dif'] = round(dif.iloc[-1], 4)
    indicators['macd_dea'] = round(dea.iloc[-1], 4)
    indicators['macd_signal'] = 'golden_cross' if dif.iloc[-1] > dea.iloc[-1] and dif.iloc[-2] <= dea.iloc[-2] else \
                                 'death_cross' if dif.iloc[-1] < dea.iloc[-1] and dif.iloc[-2] >= dea.iloc[-2] else \
                                 'bullish' if dif.iloc[-1] > dea.iloc[-1] else 'bearish'

    # 布林带 (20日)
    sma20 = close.rolling(20).mean()
    std20 = close.rolling(20).std()
    indicators['boll_upper'] = round((sma20 + 2 * std20).iloc[-1], 2)
    indicators['boll_middle'] = round(sma20.iloc[-1], 2)
    indicators['boll_lower'] = round((sma20 - 2 * std20).iloc[-1], 2)

    current = close.iloc[-1]
    indicators['current_price'] = round(current, 2)

    # 趋势判断
    if current > indicators['ma5'] > indicators['ma10'] > indicators['ma20']:
        indicators['trend'] = '多头排列(强势)'
    elif current < indicators['ma5'] < indicators['ma10'] < indicators['ma20']:
        indicators['trend'] = '空头排列(弱势)'
    else:
        indicators['trend'] = '震荡整理'

    # 量价关系
    if volume is not None and len(volume) >= 5:
        vol_ma5 = volume.tail(5).mean()
        vol_today = volume.iloc[-1]
        indicators['volume_ratio'] = round(vol_today / vol_ma5, 2) if vol_ma5 > 0 else 1.0

    return indicators


if __name__ == "__main__":
    print("=== 数据采集v2测试 ===")

    print("\n--- 市场情绪 ---")
    sentiment = get_market_sentiment()
    print(json.dumps(sentiment, ensure_ascii=False, indent=2, default=str))

    print("\n--- 大盘指数 ---")
    indices = get_market_indices()
    print(json.dumps(indices, ensure_ascii=False, indent=2))

    print("\n--- 热门股票 ---")
    hot = get_hot_stocks()
    print(hot.head(10) if hot is not None and not hot.empty else "无数据")

    print("\n--- 板块资金流向 ---")
    sectors = get_sector_fund_flow()
    print(sectors.head(10) if sectors is not None and not sectors.empty else "无数据")

    print("\n--- 最新研报 ---")
    reports = get_stock_research_reports()
    print(reports.head(5) if reports is not None and not reports.empty else "无数据")

    print("\n--- 技术指标测试 (伊利股份) ---")
    daily = get_stock_daily('600887', 60)
    if daily is not None and not daily.empty:
        tech = calculate_technical_indicators(daily)
        print(json.dumps(tech, ensure_ascii=False, indent=2))
