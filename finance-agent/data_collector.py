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

# 数据源健康监控
try:
    from datasource_monitor import monitored
except ImportError:
    def monitored(name):
        def decorator(func): return func
        return decorator


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
@monitored("东方财富个股新闻")
def get_stock_news(symbol: str = None) -> pd.DataFrame:
    """获取财联社/东方财富新闻"""
    df = ak.stock_news_em()
    if symbol:
        df = df[df['关键词'].str.contains(symbol, na=False)]
    return df.head(50)


@retry(max_retries=2, delay=1)
@monitored("市场情绪")
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

    # 情绪EMA平滑 — 用最近5日快照做指数移动平均，避免单日极端值
    try:
        import sqlite3
        conn = sqlite3.connect('/home/nikefd/finance-agent/data/trading.db')
        c = conn.cursor()
        c.execute("SELECT sentiment_score FROM daily_snapshots ORDER BY date DESC LIMIT 5")
        history = [row[0] for row in c.fetchall() if row[0] and row[0] > 0]
        conn.close()
        if history:
            # EMA: 当日权重0.4, 历史权重0.6
            ema = result['sentiment_score']
            alpha = 0.4
            for h in history:
                ema = alpha * ema + (1 - alpha) * h
            result['sentiment_raw'] = result['sentiment_score']
            result['sentiment_score'] = round(ema, 1)
            # 重新判断标签
            s = result['sentiment_score']
            if s >= 80: result['sentiment_label'] = '贪婪'
            elif s >= 65: result['sentiment_label'] = '乐观'
            elif s >= 45: result['sentiment_label'] = '中性'
            elif s >= 30: result['sentiment_label'] = '谨慎'
            else: result['sentiment_label'] = '恐慌'
    except:
        pass  # 数据库不存在或无历史，用原始值

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
        df = pd.DataFrame(klines)
        # 只取前6列，忽略多余的
        df = df.iloc[:, :min(len(df.columns), 6)]
        df.columns = cols[:len(df.columns)]
        for col in ['开盘', '收盘', '最高', '最低', '成交量']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        return df
    except Exception as e:
        print(f"获取{symbol}日K失败: {e}")
        return pd.DataFrame()


def get_realtime_quotes(symbols: list) -> dict:
    """批量获取实时行情 — 腾讯财经源（支持A股+港股）"""
    try:
        qq_list = []
        for s in symbols:
            if s.startswith('0') and len(s) == 5:
                # 港股: 5位代码，如01810
                qq_list.append(f'hk{s}')
            elif s.startswith('6') or s.startswith('9'):
                qq_list.append(f'sh{s}')
            else:
                qq_list.append(f'sz{s}')
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
            code = data[2]  # 股票代码
            result[code] = {
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

    # KDJ指标 (9,3,3)
    if len(close) >= 9:
        low_list = df['最低'].astype(float).rolling(9).min()
        high_list = df['最高'].astype(float).rolling(9).max()
        rsv = (close - low_list) / (high_list - low_list) * 100
        rsv = rsv.fillna(50)
        k = rsv.ewm(com=2, adjust=False).mean()
        d = k.ewm(com=2, adjust=False).mean()
        j = 3 * k - 2 * d
        indicators['kdj_k'] = round(k.iloc[-1], 1)
        indicators['kdj_d'] = round(d.iloc[-1], 1)
        indicators['kdj_j'] = round(j.iloc[-1], 1)
        # KDJ金叉/死叉
        if len(k) >= 2:
            if k.iloc[-1] > d.iloc[-1] and k.iloc[-2] <= d.iloc[-2]:
                indicators['kdj_signal'] = 'golden_cross'
            elif k.iloc[-1] < d.iloc[-1] and k.iloc[-2] >= d.iloc[-2]:
                indicators['kdj_signal'] = 'death_cross'
            elif j.iloc[-1] > 80:
                indicators['kdj_signal'] = 'overbought'
            elif j.iloc[-1] < 20:
                indicators['kdj_signal'] = 'oversold'
            else:
                indicators['kdj_signal'] = 'neutral'

    # 量价关系
    if volume is not None and len(volume) >= 5:
        vol_ma5 = volume.tail(5).mean()
        vol_today = volume.iloc[-1]
        indicators['volume_ratio'] = round(vol_today / vol_ma5, 2) if vol_ma5 > 0 else 1.0

    # RSI背离检测 (看近10根K线)
    # 价格创新低但RSI不创新低 → 看涨背离(底背离)
    # 价格创新高但RSI不创新高 → 看跌背离(顶背离)
    if len(close) >= 20 and not rsi.empty and len(rsi) >= 20:
        try:
            recent_close = close.iloc[-10:]
            prev_close = close.iloc[-20:-10]
            recent_rsi = rsi.iloc[-10:]
            prev_rsi = rsi.iloc[-20:-10]

            recent_low = recent_close.min()
            prev_low = prev_close.min()
            recent_rsi_low = recent_rsi.min()
            prev_rsi_low = prev_rsi.min()

            recent_high = recent_close.max()
            prev_high = prev_close.max()
            recent_rsi_high = recent_rsi.max()
            prev_rsi_high = prev_rsi.max()

            if recent_low < prev_low and recent_rsi_low > prev_rsi_low:
                indicators['rsi_divergence'] = 'bullish'  # 底背离，看涨
            elif recent_high > prev_high and recent_rsi_high < prev_rsi_high:
                indicators['rsi_divergence'] = 'bearish'  # 顶背离，看跌
            else:
                indicators['rsi_divergence'] = 'none'
        except:
            indicators['rsi_divergence'] = 'none'

    # === ATR (Average True Range) — 波动率指标，用于自适应止损 ===
    if len(close) >= 14:
        try:
            high = df['最高'].astype(float)
            low = df['最低'].astype(float)
            prev_close = close.shift(1)
            tr1 = high - low
            tr2 = (high - prev_close).abs()
            tr3 = (low - prev_close).abs()
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr14 = tr.rolling(14).mean().iloc[-1]
            indicators['atr14'] = round(atr14, 4)
            # ATR占价格的百分比 — 衡量相对波动率
            indicators['atr_pct'] = round(atr14 / current * 100, 2) if current > 0 else 0
        except:
            indicators['atr14'] = 0
            indicators['atr_pct'] = 0

    # === VWAP (Volume Weighted Average Price) ===
    # 近20日VWAP，用于判断入场时机: 低于VWAP买入更安全
    if volume is not None and len(close) >= 20:
        try:
            typical_price = (df['最高'].astype(float) + df['最低'].astype(float) + close) / 3
            vwap_20 = (typical_price.tail(20) * volume.tail(20)).sum() / volume.tail(20).sum()
            indicators['vwap_20'] = round(vwap_20, 2)
            indicators['price_vs_vwap'] = round((current - vwap_20) / vwap_20 * 100, 2)  # 正=溢价, 负=折价
        except:
            indicators['vwap_20'] = 0
            indicators['price_vs_vwap'] = 0

    # === 跳空缺口检测 (Gap Detection) ===
    # 近5日内的跳空缺口是重要的趋势信号
    if len(close) >= 5:
        try:
            high_col = df['最高'].astype(float)
            low_col = df['最低'].astype(float)
            gap_up = False
            gap_down = False
            for i in range(-1, -4, -1):  # 检查最近3天
                if len(low_col) + i >= 1:
                    prev_high = high_col.iloc[i - 1]
                    curr_low = low_col.iloc[i]
                    prev_low = low_col.iloc[i - 1]
                    curr_high = high_col.iloc[i]
                    if curr_low > prev_high:  # 向上跳空
                        gap_up = True
                    if curr_high < prev_low:  # 向下跳空
                        gap_down = True
            indicators['gap_up'] = gap_up
            indicators['gap_down'] = gap_down
        except:
            indicators['gap_up'] = False
            indicators['gap_down'] = False

    # === OBV (On-Balance Volume) 能量潮 ===
    # 经典量价确认指标: OBV上升确认上涨趋势，OBV下降警示假突破
    if volume is not None and len(close) >= 20:
        try:
            obv = pd.Series(0.0, index=close.index)
            for idx in range(1, len(close)):
                if close.iloc[idx] > close.iloc[idx-1]:
                    obv.iloc[idx] = obv.iloc[idx-1] + volume.iloc[idx]
                elif close.iloc[idx] < close.iloc[idx-1]:
                    obv.iloc[idx] = obv.iloc[idx-1] - volume.iloc[idx]
                else:
                    obv.iloc[idx] = obv.iloc[idx-1]
            # OBV趋势: 比较近5日OBV均值 vs 前5日OBV均值
            obv_recent = obv.iloc[-5:].mean()
            obv_prev = obv.iloc[-10:-5].mean()
            if obv_prev != 0:
                obv_trend = (obv_recent - obv_prev) / abs(obv_prev)
            else:
                obv_trend = 0
            indicators['obv_trend'] = round(obv_trend, 4)
            # 量价背离: 价格上涨但OBV下降
            price_up_5d = close.iloc[-1] > close.iloc[-5]
            obv_down = obv_trend < -0.1
            indicators['obv_price_diverge'] = price_up_5d and obv_down
        except:
            indicators['obv_trend'] = 0
            indicators['obv_price_diverge'] = False

    # === 动量衰减检测 ===
    # 检测MACD柱线递减 + 量能递减，识别上涨动力不足
    if len(close) >= 10:
        try:
            macd_hist = macd.tail(5).tolist()
            # MACD柱线连续3天递减 = 动量衰减
            if len(macd_hist) >= 3:
                if (macd_hist[-1] < macd_hist[-2] < macd_hist[-3] and 
                    macd_hist[-1] > 0):  # 还在零上但在递减
                    indicators['momentum_decay'] = True
                else:
                    indicators['momentum_decay'] = False
            
            # 量能衰减: 价格上涨但成交量递减
            if volume is not None and len(volume) >= 5:
                price_up = close.iloc[-1] > close.iloc[-3]
                vol_down = volume.iloc[-1] < volume.iloc[-3] * 0.7
                indicators['volume_price_diverge'] = price_up and vol_down
            else:
                indicators['volume_price_diverge'] = False
        except:
            indicators['momentum_decay'] = False
            indicators['volume_price_diverge'] = False

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
