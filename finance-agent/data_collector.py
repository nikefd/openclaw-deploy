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
    # MACD零轴突破: DIF从负转正，比普通金叉更强(趋势从空翻多)
    indicators['macd_zero_cross_up'] = bool(dif.iloc[-1] > 0 and dif.iloc[-2] <= 0)
    indicators['macd_zero_cross_down'] = bool(dif.iloc[-1] < 0 and dif.iloc[-2] >= 0)

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

    # === ADX (Average Directional Index) — 趋势强度指标 ===
    # ADX>25=强趋势(信任趋势信号), ADX<20=无方向(避免趋势策略), 25附近=弱趋势
    if len(close) >= 30:
        try:
            high = df['最高'].astype(float)
            low = df['最低'].astype(float)
            prev_high = high.shift(1)
            prev_low = low.shift(1)
            prev_close = close.shift(1)
            # +DM / -DM
            plus_dm = high - prev_high
            minus_dm = prev_low - low
            plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
            minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)
            # True Range
            tr1 = high - low
            tr2 = (high - prev_close).abs()
            tr3 = (low - prev_close).abs()
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            # Smoothed (Wilder's 14-period)
            atr_s = tr.ewm(alpha=1/14, adjust=False).mean()
            plus_di = 100 * (plus_dm.ewm(alpha=1/14, adjust=False).mean() / atr_s)
            minus_di = 100 * (minus_dm.ewm(alpha=1/14, adjust=False).mean() / atr_s)
            dx = 100 * ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, float('nan')))
            adx = dx.ewm(alpha=1/14, adjust=False).mean()
            indicators['adx'] = round(adx.iloc[-1], 1)
            indicators['plus_di'] = round(plus_di.iloc[-1], 1)
            indicators['minus_di'] = round(minus_di.iloc[-1], 1)
            # 趋势强度标签
            adx_val = indicators['adx']
            if adx_val >= 25:
                indicators['trend_strength'] = 'strong'
            elif adx_val >= 20:
                indicators['trend_strength'] = 'moderate'
            else:
                indicators['trend_strength'] = 'weak'  # 无方向，区间震荡
        except:
            indicators['adx'] = 0
            indicators['trend_strength'] = 'unknown'

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

    # === Williams %R (14日) ===
    # 类似RSI但更灵敏，-80以下超卖，-20以上超买
    if len(close) >= 14:
        try:
            high14 = df['最高'].astype(float).rolling(14).max()
            low14 = df['最低'].astype(float).rolling(14).min()
            wr = (high14 - close) / (high14 - low14) * -100
            indicators['williams_r'] = round(wr.iloc[-1], 1)
            # Williams %R 趋势: 从超卖区回升是买入信号
            if len(wr) >= 3:
                wr_rising = wr.iloc[-1] > wr.iloc[-2] > wr.iloc[-3]
                indicators['wr_reversal'] = wr.iloc[-1] > -80 and wr.iloc[-2] < -80  # 从超卖回升
                indicators['wr_overbought_exit'] = wr.iloc[-1] < -20 and wr.iloc[-2] > -20  # 从超买回落
            else:
                indicators['wr_reversal'] = False
                indicators['wr_overbought_exit'] = False
        except:
            indicators['williams_r'] = -50
            indicators['wr_reversal'] = False
            indicators['wr_overbought_exit'] = False

    # === 周线趋势确认 ===
    # 用日K模拟周线: 取最近25个交易日(约5周)判断周级别趋势
    if len(close) >= 25:
        try:
            # 周级别均线: 5周≈25日, 10周≈50日
            ma25 = close.tail(25).mean()
            ma50 = close.tail(50).mean() if len(close) >= 50 else ma25
            weekly_close_5w = close.iloc[-25::5]  # 每5天取一个收盘价模拟周K
            if len(weekly_close_5w) >= 3:
                weekly_trend_up = weekly_close_5w.iloc[-1] > weekly_close_5w.iloc[-2] > weekly_close_5w.iloc[-3]
                weekly_trend_down = weekly_close_5w.iloc[-1] < weekly_close_5w.iloc[-2] < weekly_close_5w.iloc[-3]
            else:
                weekly_trend_up = False
                weekly_trend_down = False
            
            indicators['weekly_ma25'] = round(ma25, 2)
            indicators['weekly_trend'] = 'up' if (current > ma25 and weekly_trend_up) else \
                                         'down' if (current < ma25 and weekly_trend_down) else 'neutral'
            indicators['price_above_weekly_ma'] = current > ma25
        except:
            indicators['weekly_trend'] = 'neutral'
            indicators['price_above_weekly_ma'] = True

    # === 布林带 %B (Bollinger %B) ===
    # %B = (Price - Lower) / (Upper - Lower), 0=下轨, 1=上轨, <0=极度超卖
    if len(close) >= 20:
        try:
            bb_upper = sma20 + 2 * std20
            bb_lower = sma20 - 2 * std20
            bb_width = bb_upper - bb_lower
            pct_b = (close - bb_lower) / bb_width.replace(0, float('nan'))
            indicators['boll_pct_b'] = round(pct_b.iloc[-1], 3) if not pct_b.empty else 0.5
            # 带宽收窄(squeeze) = 即将变盘
            if len(bb_width) >= 20:
                bw_pct = bb_width / sma20 * 100
                indicators['boll_squeeze'] = bw_pct.iloc[-1] < bw_pct.tail(20).quantile(0.2)
            else:
                indicators['boll_squeeze'] = False
        except:
            indicators['boll_pct_b'] = 0.5
            indicators['boll_squeeze'] = False

    # === 成交量高潮检测 (Volume Climax) ===
    # 放巨量+大跌 = 恐慌抛售尾声, 可能是反弹机会
    if volume is not None and len(volume) >= 20 and len(close) >= 5:
        try:
            vol_ma20 = volume.tail(20).mean()
            vol_std20 = volume.tail(20).std()
            price_chg = (close.iloc[-1] - close.iloc[-2]) / close.iloc[-2] * 100 if close.iloc[-2] > 0 else 0
            # 卖出高潮: 量>均值+2倍标准差 且 跌幅>3%
            sell_climax = (volume.iloc[-1] > vol_ma20 + 2 * vol_std20) and price_chg < -3
            # 买入高潮(追高危险): 量>均值+2倍标准差 且 涨幅>5%
            buy_climax = (volume.iloc[-1] > vol_ma20 + 2 * vol_std20) and price_chg > 5
            indicators['sell_climax'] = bool(sell_climax)
            indicators['buy_climax'] = bool(buy_climax)
        except:
            indicators['sell_climax'] = False
            indicators['buy_climax'] = False

    # === 价格结构: Higher Low 检测 ===
    # 近期低点是否在抬升 — 确认底部形成，过滤下降通道中的假反弹
    if len(close) >= 20:
        try:
            # 找近20日的两个局部低点
            lows = df['最低'].astype(float).tail(20)
            # 简化: 比较前10日最低 vs 后10日最低
            first_half_low = lows.iloc[:10].min()
            second_half_low = lows.iloc[10:].min()
            indicators['higher_low'] = second_half_low > first_half_low * 1.005  # 后半段低点更高
            indicators['lower_low'] = second_half_low < first_half_low * 0.995   # 后半段低点更低(下降通道)
        except:
            indicators['higher_low'] = False
            indicators['lower_low'] = False

    # === 相对强度评级 (RS Rating vs 大盘) ===
    # 只买比大盘强的股票，弱于大盘的不碰
    if len(close) >= 20:
        try:
            stock_ret_10d = (close.iloc[-1] - close.iloc[-10]) / close.iloc[-10] * 100
            stock_ret_20d = (close.iloc[-1] - close.iloc[-20]) / close.iloc[-20] * 100
            indicators['stock_ret_10d'] = round(stock_ret_10d, 2)
            indicators['stock_ret_20d'] = round(stock_ret_20d, 2)
            # RS rating will be computed in stock_picker with index data
            indicators['_needs_rs'] = True
        except:
            indicators['stock_ret_10d'] = 0
            indicators['stock_ret_20d'] = 0

    # === 缩量企稳 (Volume Dry-up Bottom) ===
    # 下跌后成交量萎缩到极低水平 = 卖方耗尽，底部信号
    if volume is not None and len(volume) >= 20 and len(close) >= 20:
        try:
            vol_ma20 = volume.tail(20).mean()
            vol_recent3 = volume.tail(3).mean()
            price_down_10d = close.iloc[-1] < close.iloc[-10]  # 近10日下跌
            vol_ratio_dry = vol_recent3 / vol_ma20 if vol_ma20 > 0 else 1
            # 缩量企稳: 近3日量<均量50% + 价格跌幅收窄(近3日振幅<2%)
            price_range_3d = (close.tail(3).max() - close.tail(3).min()) / close.tail(3).mean() * 100
            indicators['volume_dryup'] = bool(
                price_down_10d and vol_ratio_dry < 0.5 and price_range_3d < 2.0
            )
            indicators['vol_dryup_ratio'] = round(vol_ratio_dry, 2)
        except:
            indicators['volume_dryup'] = False
            indicators['vol_dryup_ratio'] = 1.0

    # === 均线密集收敛突破 (MA Convergence Breakout) ===
    # MA5/MA10/MA20三线收敛后价格突破 = 强启动信号
    if len(close) >= 20:
        try:
            ma5 = indicators.get('ma5', 0)
            ma10 = indicators.get('ma10', 0)
            ma20 = indicators.get('ma20', 0)
            if ma20 > 0:
                # 三线之间的最大偏差百分比
                ma_spread = (max(ma5, ma10, ma20) - min(ma5, ma10, ma20)) / ma20 * 100
                indicators['ma_spread'] = round(ma_spread, 2)
                # 收敛: 偏差<2% + 今日收盘突破三线 + 放量确认(量比>1.2)
                vol_confirm = indicators.get('volume_ratio', 1.0) >= 1.2
                indicators['ma_converge_breakout'] = bool(
                    ma_spread < 2.0 and current > max(ma5, ma10, ma20) and vol_confirm
                )
            else:
                indicators['ma_spread'] = 99
                indicators['ma_converge_breakout'] = False
        except:
            indicators['ma_spread'] = 99
            indicators['ma_converge_breakout'] = False

    # === 支撑阻力位检测 (Support/Resistance) ===
    # 识别近期关键价位，买在支撑位附近成功率更高
    if len(close) >= 30:
        try:
            high_col = df['最高'].astype(float)
            low_col = df['最低'].astype(float)
            # 找近30日的局部极值作为支撑/阻力
            supports = []
            resistances = []
            for i in range(2, min(len(close)-2, 28)):
                # 局部低点 = 支撑
                if low_col.iloc[i] <= low_col.iloc[i-1] and low_col.iloc[i] <= low_col.iloc[i-2] and \
                   low_col.iloc[i] <= low_col.iloc[i+1] and low_col.iloc[i] <= low_col.iloc[i+2]:
                    supports.append(float(low_col.iloc[i]))
                # 局部高点 = 阻力
                if high_col.iloc[i] >= high_col.iloc[i-1] and high_col.iloc[i] >= high_col.iloc[i-2] and \
                   high_col.iloc[i] >= high_col.iloc[i+1] and high_col.iloc[i] >= high_col.iloc[i+2]:
                    resistances.append(float(high_col.iloc[i]))
            
            # 最近的支撑位和阻力位
            current_p = float(close.iloc[-1])
            nearby_supports = sorted([s for s in supports if s < current_p], reverse=True)
            nearby_resistances = sorted([r for r in resistances if r > current_p])
            
            if nearby_supports:
                nearest_support = nearby_supports[0]
                support_distance = (current_p - nearest_support) / current_p * 100
                indicators['nearest_support'] = round(nearest_support, 2)
                indicators['support_distance_pct'] = round(support_distance, 2)
                # 接近支撑位(距离<2%) = 好的买入位置
                indicators['near_support'] = support_distance < 2.0
            else:
                indicators['near_support'] = False
                indicators['support_distance_pct'] = 99
            
            if nearby_resistances:
                nearest_resistance = nearby_resistances[0]
                resistance_distance = (nearest_resistance - current_p) / current_p * 100
                indicators['nearest_resistance'] = round(nearest_resistance, 2)
                indicators['resistance_distance_pct'] = round(resistance_distance, 2)
                # 接近阻力位(距离<1.5%) = 不好的买入位置
                indicators['near_resistance'] = resistance_distance < 1.5
            else:
                indicators['near_resistance'] = False
                indicators['resistance_distance_pct'] = 99
            
            # 支撑/阻力密度: 同一价位附近多次出现的支撑更强
            if nearby_supports:
                strong_support = False
                for s in nearby_supports[:3]:
                    count = sum(1 for ss in supports if abs(ss - s) / s < 0.01)  # 1%内算同一支撑
                    if count >= 2:
                        strong_support = True
                        break
                indicators['strong_support'] = strong_support
            else:
                indicators['strong_support'] = False
        except:
            indicators['near_support'] = False
            indicators['near_resistance'] = False
            indicators['strong_support'] = False
            indicators['support_distance_pct'] = 99
            indicators['resistance_distance_pct'] = 99

    # === 价格Z-Score (均值回归检测) ===
    # 比RSI更精确: Z-Score < -2 = 统计意义上的极度超卖
    if len(close) >= 20:
        try:
            mean_20 = close.tail(20).mean()
            std_20 = close.tail(20).std()
            if std_20 > 0:
                z_score = (float(close.iloc[-1]) - mean_20) / std_20
                indicators['price_z_score'] = round(z_score, 2)
            else:
                indicators['price_z_score'] = 0
        except:
            indicators['price_z_score'] = 0

    # === K线形态识别 (Candlestick Patterns) ===
    # 经典反转形态: 锤子线/吞没形态/十字星，提高入场时机精准度
    if len(close) >= 5:
        try:
            open_col = df['开盘'].astype(float)
            high_col_k = df['最高'].astype(float)
            low_col_k = df['最低'].astype(float)
            
            # 取最近3根K线
            o1, c1, h1, l1 = open_col.iloc[-1], close.iloc[-1], high_col_k.iloc[-1], low_col_k.iloc[-1]
            o2, c2, h2, l2 = open_col.iloc[-2], close.iloc[-2], high_col_k.iloc[-2], low_col_k.iloc[-2]
            o3, c3, h3, l3 = open_col.iloc[-3], close.iloc[-3], high_col_k.iloc[-3], low_col_k.iloc[-3]
            
            body1 = abs(c1 - o1)
            body2 = abs(c2 - o2)
            range1 = h1 - l1 if h1 > l1 else 0.001
            range2 = h2 - l2 if h2 > l2 else 0.001
            upper_shadow1 = h1 - max(o1, c1)
            lower_shadow1 = min(o1, c1) - l1
            
            # 锤子线 (Hammer): 下影线>实体2倍 + 上影线很小 + 出现在下跌后
            hammer = (lower_shadow1 > body1 * 2 and 
                      upper_shadow1 < body1 * 0.3 and
                      c2 < o2 and c3 < o3)  # 前两根是阴线(下跌中)
            
            # 看涨吞没 (Bullish Engulfing): 阳线实体完全吞没前一根阴线
            bullish_engulf = (c2 < o2 and c1 > o1 and  # 前阴后阳
                              c1 > o2 and o1 < c2 and  # 阳线实体包含阴线
                              body1 > body2 * 1.3)     # 阳线明显更大
            
            # 看跌吞没 (Bearish Engulfing): 阴线实体完全吞没前一根阳线
            bearish_engulf = (c2 > o2 and c1 < o1 and  # 前阳后阴
                              o1 > c2 and c1 < o2 and  # 阴线实体包含阳线
                              body1 > body2 * 1.3)
            
            # 十字星 (Doji): 实体极小 + 上下影线长
            doji = (body1 < range1 * 0.1 and  # 实体<振幅10%
                    upper_shadow1 > body1 * 2 and 
                    lower_shadow1 > body1 * 2)
            
            # 早晨之星 (Morning Star): 阴线→十字星→阳线 (三根K线的底部反转)
            body3 = abs(c3 - o3)
            range3 = h3 - l3 if h3 > l3 else 0.001
            doji_middle = abs(c2 - o2) < range2 * 0.15  # 中间是十字星
            morning_star = (c3 < o3 and body3 > range3 * 0.5 and  # 第1根大阴线
                           doji_middle and  # 第2根十字星
                           c1 > o1 and body1 > range1 * 0.5 and  # 第3根大阳线
                           c1 > (o3 + c3) / 2)  # 阳线收盘超过阴线中点
            
            indicators['hammer'] = bool(hammer)
            indicators['bullish_engulf'] = bool(bullish_engulf)
            indicators['bearish_engulf'] = bool(bearish_engulf)
            indicators['doji'] = bool(doji)
            indicators['morning_star'] = bool(morning_star)
            # 综合看涨形态标记
            indicators['bullish_candle'] = bool(hammer or bullish_engulf or morning_star)
            indicators['bearish_candle'] = bool(bearish_engulf)
        except:
            indicators['hammer'] = False
            indicators['bullish_engulf'] = False
            indicators['bearish_engulf'] = False
            indicators['doji'] = False
            indicators['morning_star'] = False
            indicators['bullish_candle'] = False
            indicators['bearish_candle'] = False

    # === 连续阳线/阴线检测 (Consecutive Candles) ===
    # 连续3+阳线在超卖区=强反转信号; 连续3+阴线=趋势衰弱
    if len(close) >= 5:
        try:
            open_col_cc = df['开盘'].astype(float)
            consec_bull = 0
            consec_bear = 0
            for idx in range(-1, -6, -1):
                if close.iloc[idx] > open_col_cc.iloc[idx]:
                    if consec_bear > 0:
                        break
                    consec_bull += 1
                elif close.iloc[idx] < open_col_cc.iloc[idx]:
                    if consec_bull > 0:
                        break
                    consec_bear += 1
                else:
                    break
            indicators['consec_bull_candles'] = consec_bull
            indicators['consec_bear_candles'] = consec_bear
        except:
            indicators['consec_bull_candles'] = 0
            indicators['consec_bear_candles'] = 0

    # === 支撑位跟踪(含近期跌破的支撑) ===
    # 记录略高于当前价的支撑位(可能是刚跌破的)，供止损使用
    if len(close) >= 30:
        try:
            high_col_sr = df['最高'].astype(float)
            low_col_sr = df['最低'].astype(float)
            all_supports = []
            for i in range(2, min(len(close)-2, 28)):
                if (low_col_sr.iloc[i] <= low_col_sr.iloc[i-1] and low_col_sr.iloc[i] <= low_col_sr.iloc[i-2] and
                    low_col_sr.iloc[i] <= low_col_sr.iloc[i+1] and low_col_sr.iloc[i] <= low_col_sr.iloc[i+2]):
                    all_supports.append(float(low_col_sr.iloc[i]))
            # 刚跌破的支撑: 在当前价上方3%以内的支撑位
            current_p = float(close.iloc[-1])
            broken_supports = sorted([s for s in all_supports if current_p < s <= current_p * 1.03], reverse=False)
            if broken_supports:
                indicators['broken_support'] = round(broken_supports[0], 2)
                indicators['broken_support_pct'] = round((broken_supports[0] - current_p) / current_p * 100, 2)
            else:
                indicators['broken_support'] = 0
                indicators['broken_support_pct'] = 0
        except:
            indicators['broken_support'] = 0
            indicators['broken_support_pct'] = 0

    # === Fibonacci 回撤位 (Fibonacci Retracement) ===
    # 比局部极值更可靠的支撑阻力: 用近60日高低点计算0.236/0.382/0.5/0.618回撤位
    if len(close) >= 30:
        try:
            lookback = min(len(close), 60)
            high_val = float(df['最高'].astype(float).tail(lookback).max())
            low_val = float(df['最低'].astype(float).tail(lookback).min())
            diff = high_val - low_val
            if diff > 0:
                fib_levels = {
                    'fib_236': round(high_val - diff * 0.236, 2),
                    'fib_382': round(high_val - diff * 0.382, 2),
                    'fib_500': round(high_val - diff * 0.500, 2),
                    'fib_618': round(high_val - diff * 0.618, 2),
                }
                indicators.update(fib_levels)
                indicators['fib_high'] = round(high_val, 2)
                indicators['fib_low'] = round(low_val, 2)
                # 找当前价最近的Fib支撑和阻力
                curr = float(close.iloc[-1])
                fib_values = sorted(fib_levels.values())
                fib_supports = [f for f in fib_values if f < curr]
                fib_resistances = [f for f in fib_values if f > curr]
                if fib_supports:
                    nearest_fib_sup = fib_supports[-1]
                    indicators['fib_support'] = nearest_fib_sup
                    indicators['fib_support_dist_pct'] = round((curr - nearest_fib_sup) / curr * 100, 2)
                    indicators['near_fib_support'] = (curr - nearest_fib_sup) / curr * 100 < 2.0
                else:
                    indicators['near_fib_support'] = False
                    indicators['fib_support_dist_pct'] = 99
                if fib_resistances:
                    nearest_fib_res = fib_resistances[0]
                    indicators['fib_resistance'] = nearest_fib_res
                    indicators['fib_resistance_dist_pct'] = round((nearest_fib_res - curr) / curr * 100, 2)
                else:
                    indicators['fib_resistance_dist_pct'] = 99
            else:
                indicators['near_fib_support'] = False
                indicators['fib_support_dist_pct'] = 99
                indicators['fib_resistance_dist_pct'] = 99
        except:
            indicators['near_fib_support'] = False
            indicators['fib_support_dist_pct'] = 99
            indicators['fib_resistance_dist_pct'] = 99

    # === CMF (Chaikin Money Flow) 20日资金流向 ===
    # 比OBV更精确: 考虑收盘价在高低区间的位置，衡量真实资金流入/流出强度
    # CMF>0.1=资金强流入(确认上涨), CMF<-0.1=资金流出(警示下跌)
    if volume is not None and len(close) >= 20:
        try:
            high_cmf = df['最高'].astype(float)
            low_cmf = df['最低'].astype(float)
            hl_range = high_cmf - low_cmf
            # Money Flow Multiplier = ((Close - Low) - (High - Close)) / (High - Low)
            mfm = ((close - low_cmf) - (high_cmf - close)) / hl_range.replace(0, float('nan'))
            mfm = mfm.fillna(0)
            # Money Flow Volume = MFM × Volume
            mfv = mfm * volume
            # CMF = sum(MFV, 20) / sum(Volume, 20)
            cmf_20 = mfv.rolling(20).sum() / volume.rolling(20).sum().replace(0, float('nan'))
            indicators['cmf_20'] = round(float(cmf_20.iloc[-1]), 4) if not cmf_20.empty else 0
            # CMF趋势: 近5日CMF vs 前5日CMF
            if len(cmf_20.dropna()) >= 10:
                cmf_recent = cmf_20.iloc[-5:].mean()
                cmf_prev = cmf_20.iloc[-10:-5].mean()
                indicators['cmf_rising'] = bool(cmf_recent > cmf_prev + 0.02)
                indicators['cmf_falling'] = bool(cmf_recent < cmf_prev - 0.02)
            else:
                indicators['cmf_rising'] = False
                indicators['cmf_falling'] = False
        except:
            indicators['cmf_20'] = 0
            indicators['cmf_rising'] = False
            indicators['cmf_falling'] = False

    # === 动量衰减检测 ===
    # 检测MACD柱线递减 + 量能递减，识别上涨动力不足
    # 同时计算当日涨跌幅(用于持仓管理中的单日暴涨减仓)
    if len(close) >= 2:
        indicators['daily_change_pct'] = round((close.iloc[-1] - close.iloc[-2]) / close.iloc[-2] * 100, 2) if close.iloc[-2] > 0 else 0
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

    # === 成交密集区 (Volume Profile) ===
    # 用成交量加权的价格分布找到真正的支撑/阻力位
    # 比局部极值法更可靠，因为成交密集区代表真实的资金博弈位置
    try:
        if volume is not None and len(close) >= 20:
            high = df['最高'].astype(float)
            low = df['最低'].astype(float)
            price_range = high.max() - low.min()
            if price_range > 0:
                n_bins = 20
                bin_size = price_range / n_bins
                bins = {}
                for i in range(len(close)):
                    # 每根K线的成交量均匀分配到其价格区间
                    k_low = float(low.iloc[i])
                    k_high = float(high.iloc[i])
                    k_vol = float(volume.iloc[i])
                    for b in range(n_bins):
                        bin_low = float(low.min()) + b * bin_size
                        bin_high = bin_low + bin_size
                        if k_low <= bin_high and k_high >= bin_low:
                            overlap = min(k_high, bin_high) - max(k_low, bin_low)
                            k_range = k_high - k_low if k_high > k_low else bin_size
                            ratio = overlap / k_range
                            bin_mid = bin_low + bin_size / 2
                            bins[round(bin_mid, 2)] = bins.get(round(bin_mid, 2), 0) + k_vol * ratio
                
                if bins:
                    # 找成交量最大的价格区间 = POC (Point of Control)
                    poc_price = max(bins, key=bins.get)
                    total_vol = sum(bins.values())
                    
                    # 找当前价下方最近的成交密集区(支撑) 和 上方的(阻力)
                    avg_vol = total_vol / n_bins
                    dense_prices = [p for p, v in bins.items() if v > avg_vol * 1.5]  # 量>均值1.5倍=密集区
                    
                    vp_support = None
                    vp_resistance = None
                    cur = float(current)
                    for dp in sorted(dense_prices):
                        if dp < cur * 0.98:  # 低于当前价2%以上
                            vp_support = dp
                        elif dp > cur * 1.01 and vp_resistance is None:
                            vp_resistance = dp
                    
                    indicators['volume_profile_poc'] = poc_price
                    indicators['vp_support'] = vp_support
                    indicators['vp_resistance'] = vp_resistance
                    
                    if vp_support:
                        vp_sup_dist = (cur - vp_support) / cur * 100
                        indicators['vp_support_dist_pct'] = round(vp_sup_dist, 2)
                        indicators['near_vp_support'] = vp_sup_dist < 3  # 3%以内=接近成交密集支撑
                    else:
                        indicators['vp_support_dist_pct'] = 99
                        indicators['near_vp_support'] = False
                    
                    # 当前价在POC下方=潜在回归价值
                    indicators['below_poc'] = cur < poc_price
    except:
        pass

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
