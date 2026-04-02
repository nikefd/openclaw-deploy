"""新闻/舆情数据采集模块 — 多源聚合+LLM解读

数据源:
1. 东方财富快讯 (7x24h滚动)
2. 财联社电报
3. 新浪财经要闻
4. 雪球热帖/个股讨论
5. 政策公告 (央行/证监会)
6. 个股公告 (巨潮资讯)

输出: 结构化的新闻信号，可直接用于选股打分
"""

import requests
import json
import time
import re
import sqlite3
from datetime import datetime, timedelta
from functools import wraps

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
}

DB_PATH = "/home/nikefd/finance-agent/data/trading.db"

# 数据源健康监控
try:
    from datasource_monitor import monitored
except ImportError:
    def monitored(name):
        def decorator(func): return func
        return decorator


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
                        return []
            return []
        return wrapper
    return decorator


# ============================================================
# 1. 东方财富 7x24 快讯
# ============================================================
@retry()
@monitored("东方财富资讯")
def get_eastmoney_express() -> list:
    """东方财富资讯中心 — A股综合新闻"""
    url = "https://newsapi.eastmoney.com/kuaixun/v1/getlist_102_ajaxResult_50_1_.html"
    r = requests.get(url, headers=HEADERS, timeout=10)
    text = r.text.strip()
    # 去掉 var ajaxResult= 前缀
    if text.startswith('var '):
        text = text.split('=', 1)[1].strip()
    if text.endswith(';'):
        text = text[:-1]
    data = json.loads(text)
    
    news_list = []
    for item in data.get('LivesList', []):
        title = item.get('title', '')
        content = item.get('digest', '')
        pub_time = item.get('showtime', '')
        
        title = re.sub(r'<[^>]+>', '', title)
        content = re.sub(r'<[^>]+>', '', content)
        
        if title:
            news_list.append({
                'source': '东方财富资讯',
                'title': title.strip(),
                'content': content.strip()[:200],
                'time': pub_time,
                'url': item.get('url_unique', ''),
            })
    return news_list


# ============================================================
# 2. 财联社电报 (通过东方财富API获取财联社新闻)
# ============================================================
@retry()
@monitored("财联社电报")
def get_cls_telegraph() -> list:
    """财联社电报 — A股最重要的实时消息源"""
    url = "https://np-anotice-stock.eastmoney.com/api/security/ann"
    params = {
        'sr': -1,
        'page_size': 30,
        'page_index': 1,
        'ann_type': 'A',
        'client_source': 'web',
        'f_node': 0,
        's_node': 0,
    }
    
    # 备用: 直接走cls的web API
    try:
        cls_url = "https://www.cls.cn/nodeapi/updateTelegraphList"
        cls_params = {
            'app': 'CailianpressWeb',
            'os': 'web',
            'sv': '8.4.6',
            'rn': 30,
        }
        r = requests.get(cls_url, params=cls_params, headers={
            **HEADERS,
            'Referer': 'https://www.cls.cn/telegraph',
        }, timeout=10)
        data = r.json()
        
        news_list = []
        for item in data.get('data', {}).get('roll_data', []):
            title = item.get('title', '') or item.get('brief', '')
            content = item.get('content', '') or item.get('brief', '')
            # 清理HTML
            content = re.sub(r'<[^>]+>', '', content)
            
            ctime = item.get('ctime', 0)
            pub_time = datetime.fromtimestamp(ctime).strftime('%Y-%m-%d %H:%M') if ctime else ''
            
            if content:
                news_list.append({
                    'source': '财联社电报',
                    'title': title.strip()[:100] if title else content[:50],
                    'content': content.strip()[:300],
                    'time': pub_time,
                    'importance': item.get('level', 0),  # 重要性级别
                })
        return news_list
    except Exception as e:
        print(f"财联社电报获取失败: {e}")
        return []


# ============================================================
# 3. 新浪财经要闻
# ============================================================
@retry()
@monitored("akshare个股新闻")
def get_sina_finance_news() -> list:
    """新浪财经要闻 — 通过akshare获取"""
    import akshare as ak
    try:
        # 用akshare的stock_zh_a_alerts_cls接口
        df = ak.stock_news_em(symbol='000001')  # 用平安银行触发一般财经新闻
        news_list = []
        if df is not None and not df.empty:
            for _, row in df.head(20).iterrows():
                news_list.append({
                    'source': '东方财富个股新闻',
                    'title': str(row.get('新闻标题', '')),
                    'content': str(row.get('新闻内容', ''))[:200],
                    'time': str(row.get('发布时间', '')),
                    'media': str(row.get('文章来源', '')),
                })
        return news_list
    except Exception as e:
        print(f"新浪/akshare新闻获取失败: {e}")
        return []


# ============================================================
# 4. 雪球热帖
# ============================================================
@retry()
@monitored("雪球热帖")
def get_xueqiu_hot(stock_code: str = None) -> list:
    """雪球热帖 — 散户情绪风向标"""
    session = requests.Session()
    # 先获取cookie
    session.get('https://xueqiu.com/', headers=HEADERS, timeout=5)
    
    if stock_code:
        # 个股讨论
        prefix = 'SH' if stock_code.startswith('6') else 'SZ'
        symbol = f'{prefix}{stock_code}'
        url = f"https://xueqiu.com/query/v1/symbol/search/status.json"
        params = {
            'u': '',
            'SID': '',
            'source': 'all',
            'sort': '',
            'symbol': symbol,
            'count': 20,
            'page': 1,
            'q': '',
            'type': 11,
        }
    else:
        # 热门帖子
        url = "https://xueqiu.com/statuses/hot/listV2.json"
        params = {
            'since_id': -1,
            'max_id': -1,
            'size': 20,
        }
    
    r = session.get(url, params=params, headers={
        **HEADERS,
        'Referer': 'https://xueqiu.com/',
    }, timeout=10)
    data = r.json()
    
    news_list = []
    items = data.get('list', data.get('statuses', []))
    for item in items:
        if isinstance(item, dict) and 'original_status' in item:
            item = item['original_status']
        
        title = item.get('title', '') or item.get('description', '')
        text = item.get('text', '') or item.get('description', '')
        # 清理HTML
        text = re.sub(r'<[^>]+>', '', text)
        
        reply_count = item.get('reply_count', 0)
        retweet_count = item.get('retweet_count', 0)
        like_count = item.get('like_count', 0)
        
        if title or text:
            news_list.append({
                'source': '雪球',
                'title': (title or text[:50]).strip(),
                'content': text.strip()[:200],
                'time': datetime.fromtimestamp(item.get('created_at', 0) / 1000).strftime('%Y-%m-%d %H:%M') if item.get('created_at') else '',
                'engagement': reply_count + retweet_count + like_count,
                'replies': reply_count,
            })
    
    # 按互动量排序
    news_list.sort(key=lambda x: -x.get('engagement', 0))
    return news_list


# ============================================================
# 5. 政策公告 (国务院/央行/证监会)
# ============================================================
@retry()
@monitored("政策公告")
def get_policy_news() -> list:
    """政策公告 — 从东方财富资讯中筛选政策相关"""
    news_list = []
    
    policy_keywords = ['央行', '国务院', '证监会', '发改委', '财政部',
                      '降准', '降息', 'MLF', 'LPR', '利率',
                      '印花税', 'IPO', '注册制', '融资融券',
                      '减持', '回购', '分红', '关税', '贸易',
                      '工信部', '商务部', '政策', '监管']
    
    # 扫描多个频道
    for channel in ['102', '103', '104']:
        try:
            url = f"https://newsapi.eastmoney.com/kuaixun/v1/getlist_{channel}_ajaxResult_50_1_.html"
            r = requests.get(url, headers=HEADERS, timeout=10)
            text = r.text.strip()
            if text.startswith('var '):
                text = text.split('=', 1)[1].strip()
            if text.endswith(';'):
                text = text[:-1]
            data = json.loads(text)
            
            for item in data.get('LivesList', []):
                title = re.sub(r'<[^>]+>', '', item.get('title', ''))
                if any(kw in title for kw in policy_keywords):
                    # 去重
                    if not any(n['title'] == title.strip() for n in news_list):
                        news_list.append({
                            'source': '政策公告',
                            'title': title.strip(),
                            'content': re.sub(r'<[^>]+>', '', item.get('digest', '')).strip()[:200],
                            'time': item.get('showtime', ''),
                            'importance': 'high',
                        })
        except:
            pass
    
    return news_list


# ============================================================
# 6. 个股公告 (巨潮资讯)
# ============================================================
@retry()
@monitored("巨潮公告")
def get_stock_announcements(stock_code: str = None) -> list:
    """个股公告 — 巨潮资讯网"""
    url = "http://www.cninfo.com.cn/new/hisAnnouncement/query"
    today = datetime.now().strftime('%Y-%m-%d')
    week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    
    data = {
        'pageNum': 1,
        'pageSize': 30,
        'column': 'szse',  # 深交所
        'tabName': 'fulltext',
        'plate': '',
        'stock': stock_code or '',
        'searchkey': '',
        'secid': '',
        'category': '',
        'trade': '',
        'seDate': f'{week_ago}~{today}',
        'sortName': '',
        'sortType': '',
        'isHLtitle': True,
    }
    
    r = requests.post(url, data=data, headers={
        **HEADERS,
        'Referer': 'http://www.cninfo.com.cn/new/commonUrl?url=disclosure/list/notice',
        'Content-Type': 'application/x-www-form-urlencoded',
    }, timeout=10)
    result = r.json()
    
    news_list = []
    for item in result.get('announcements', []):
        title = item.get('announcementTitle', '')
        sec_name = item.get('secName', '')
        sec_code = item.get('secCode', '')
        ann_time = datetime.fromtimestamp(item.get('announcementTime', 0) / 1000).strftime('%Y-%m-%d') if item.get('announcementTime') else ''
        
        # 关键公告类型
        important = any(kw in title for kw in [
            '业绩预告', '业绩快报', '年度报告', '半年度报告', '季度报告',
            '重大合同', '中标', '收购', '增持', '减持', '回购',
            '分红', '送股', '转增', '定增', '融资',
            '停牌', '复牌', '风险提示', '立案', '处罚',
        ])
        
        if title:
            news_list.append({
                'source': '巨潮公告',
                'title': f"[{sec_name}]{title}".strip(),
                'stock_code': sec_code,
                'stock_name': sec_name,
                'time': ann_time,
                'important': important,
            })
    
    return news_list


# ============================================================
# 7. 东方财富股吧热度
# ============================================================
@retry()
@monitored("股吧热度")
def get_guba_hot() -> list:
    """股吧热度 — 通过akshare获取人气榜"""
    import akshare as ak
    try:
        df = ak.stock_hot_rank_em()
        result = []
        if df is not None and not df.empty:
            for _, row in df.head(20).iterrows():
                code = str(row.get('代码', ''))
                # 去掉SH/SZ前缀
                if code.startswith('SH') or code.startswith('SZ'):
                    code = code[2:]
                result.append({
                    'source': '股吧热度',
                    'stock_code': code,
                    'stock_name': str(row.get('股票名称', '')),
                    'rank': int(row.get('当前排名', 0)),
                    'hot_score': 0,
                    'change_rank': 0,
                })
        return result
    except Exception as e:
        print(f"股吧热度获取失败: {e}")
        return []


# ============================================================
# 聚合: 获取所有新闻数据
# ============================================================
def collect_all_news(stock_code: str = None) -> dict:
    """聚合所有新闻源
    
    Returns:
        {
            'express': [...],      # 快讯
            'telegraph': [...],    # 财联社电报
            'sina': [...],         # 新浪要闻
            'xueqiu': [...],      # 雪球热帖
            'policy': [...],       # 政策公告
            'announcements': [...],# 个股公告
            'guba_hot': [...],     # 股吧热度
            'collected_at': '...',
        }
    """
    print("  📰 采集新闻数据...")
    
    result = {'collected_at': datetime.now().isoformat()}
    
    print("    → 东方财富快讯...")
    result['express'] = get_eastmoney_express()
    print(f"      {len(result['express'])}条")
    
    time.sleep(0.3)
    print("    → 财联社电报...")
    result['telegraph'] = get_cls_telegraph()
    print(f"      {len(result['telegraph'])}条")
    
    time.sleep(0.3)
    print("    → 新浪财经要闻...")
    result['sina'] = get_sina_finance_news()
    print(f"      {len(result['sina'])}条")
    
    time.sleep(0.3)
    print("    → 雪球热帖...")
    result['xueqiu'] = get_xueqiu_hot(stock_code)
    print(f"      {len(result['xueqiu'])}条")
    
    time.sleep(0.3)
    print("    → 政策公告...")
    result['policy'] = get_policy_news()
    print(f"      {len(result['policy'])}条")
    
    time.sleep(0.3)
    print("    → 股吧热度...")
    result['guba_hot'] = get_guba_hot()
    print(f"      {len(result['guba_hot'])}条")
    
    if stock_code:
        time.sleep(0.3)
        print(f"    → {stock_code}个股公告...")
        result['announcements'] = get_stock_announcements(stock_code)
        print(f"      {len(result['announcements'])}条")
    else:
        result['announcements'] = []
    
    total = sum(len(v) for k, v in result.items() if isinstance(v, list))
    print(f"  📰 新闻采集完成: 共{total}条")
    
    return result


# ============================================================
# LLM新闻解读: 非结构化 → 结构化交易信号
# ============================================================
def analyze_news_with_llm(news_data: dict) -> dict:
    """用LLM解读新闻，提取交易信号
    
    Returns:
        {
            'market_signals': [...],    # 市场级别信号
            'sector_signals': [...],    # 板块信号
            'stock_signals': [...],     # 个股信号
            'risk_alerts': [...],       # 风险预警
            'sentiment_summary': str,   # 情绪总结
        }
    """
    from ai_analyst import call_llm
    
    # 整理新闻文本（控制token量）
    news_text = ""
    
    # 政策公告（最重要）
    policy = news_data.get('policy', [])
    if policy:
        news_text += "【重要政策公告】\n"
        for n in policy[:10]:
            news_text += f"- {n['title']}\n"
        news_text += "\n"
    
    # 财联社电报
    telegraph = news_data.get('telegraph', [])
    if telegraph:
        news_text += "【财联社电报】\n"
        for n in telegraph[:15]:
            imp = "🔴" if str(n.get('importance', '0')) not in ('0', 'C', '') else ""
            news_text += f"- {imp}{n['title']} | {n.get('content', '')[:80]}\n"
        news_text += "\n"
    
    # 东方财富快讯
    express = news_data.get('express', [])
    if express:
        news_text += "【东方财富快讯】\n"
        for n in express[:15]:
            news_text += f"- {n['title']}\n"
        news_text += "\n"
    
    # 新浪财经
    sina = news_data.get('sina', [])
    if sina:
        news_text += "【新浪财经要闻】\n"
        for n in sina[:10]:
            news_text += f"- {n['title']}\n"
        news_text += "\n"
    
    # 雪球热帖
    xueqiu = news_data.get('xueqiu', [])
    if xueqiu:
        news_text += "【雪球热帖(散户情绪)】\n"
        for n in xueqiu[:10]:
            news_text += f"- {n['title']} (互动:{n.get('engagement',0)})\n"
        news_text += "\n"
    
    # 股吧热度
    guba = news_data.get('guba_hot', [])
    if guba:
        news_text += "【股吧热度TOP10】\n"
        for n in guba[:10]:
            news_text += f"- {n['stock_name']}({n['stock_code']}) 热度排名:{n.get('rank','')} 排名变化:{n.get('change_rank','')}\n"
        news_text += "\n"
    
    if not news_text.strip():
        return {
            'market_signals': [],
            'sector_signals': [],
            'stock_signals': [],
            'risk_alerts': [],
            'sentiment_summary': '暂无新闻数据',
        }
    
    prompt = f"""你是A股交易信号分析师。请从以下新闻中提取可操作的交易信号。

今天是{datetime.now().strftime('%Y年%m月%d日')}。

{news_text}

请严格按以下JSON格式输出:
```json
{{
  "market_signals": [
    {{
      "signal": "利好/利空/中性",
      "description": "一句话描述",
      "impact_level": "high/medium/low",
      "affected_sectors": ["板块1", "板块2"]
    }}
  ],
  "sector_signals": [
    {{
      "sector": "板块名",
      "signal": "利好/利空",
      "reason": "原因",
      "related_stocks": ["代码1", "代码2"]
    }}
  ],
  "stock_signals": [
    {{
      "code": "股票代码",
      "name": "股票名称",
      "signal": "利好/利空/关注",
      "reason": "原因",
      "source": "消息来源"
    }}
  ],
  "risk_alerts": [
    {{
      "type": "政策风险/市场风险/个股风险",
      "description": "描述",
      "severity": "high/medium/low"
    }}
  ],
  "sentiment_summary": "一段话总结今日市场情绪和新闻面"
}}
```

要求:
1. 只提取有明确交易含义的信号，不要凑数
2. 个股信号要给出具体代码（6位数字）
3. 政策类信号优先级最高
4. 区分短期影响和长期影响
5. 雪球/股吧数据反映散户情绪，注意反向指标的可能性

只输出JSON，不要其他内容。"""

    result_text = call_llm(prompt, system="你是专业的A股交易信号分析师。严格输出JSON格式。")
    
    try:
        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0]
        elif "```" in result_text:
            result_text = result_text.split("```")[1].split("```")[0]
        signals = json.loads(result_text.strip())
    except:
        signals = {
            'market_signals': [],
            'sector_signals': [],
            'stock_signals': [],
            'risk_alerts': [],
            'sentiment_summary': result_text[:500],
            'parse_error': True,
        }
    
    return signals


# ============================================================
# 新闻信号 → 选股加分
# ============================================================
def get_news_score_for_stock(stock_code: str, stock_name: str, signals: dict) -> dict:
    """根据新闻信号给个股加分
    
    Returns:
        {
            'score_delta': int,      # 加减分
            'reasons': [str],        # 原因列表
            'has_news': bool,        # 是否有相关新闻
        }
    """
    score = 0
    reasons = []
    
    # 个股直接信号
    for sig in signals.get('stock_signals', []):
        if sig.get('code') == stock_code or sig.get('name') == stock_name:
            if sig['signal'] == '利好':
                score += 15
                reasons.append(f"📰利好: {sig['reason']}")
            elif sig['signal'] == '利空':
                score -= 20  # 利空扣分更重，风控优先
                reasons.append(f"⚠️利空: {sig['reason']}")
            elif sig['signal'] == '关注':
                score += 5
                reasons.append(f"👀关注: {sig['reason']}")
    
    # 板块信号（间接影响）
    from performance_tracker import classify_sector
    sector = classify_sector(stock_code, stock_name)
    
    SECTOR_KEYWORDS = {
        '科技成长': ['科技', '半导体', '芯片', '软件', 'AI', '人工智能', '计算机', '电子', '通信', '数据'],
        '新能源': ['新能源', '光伏', '锂电', '风电', '储能', '电池', '太阳能', '碳中和'],
        '消费白马': ['消费', '白酒', '食品', '家电', '医药', '零售', '旅游', '餐饮'],
        '金融地产': ['金融', '银行', '保险', '证券', '地产', '房地产'],
        '周期资源': ['周期', '钢铁', '煤炭', '有色', '化工', '石油', '资源'],
    }
    
    keywords = SECTOR_KEYWORDS.get(sector, [])
    
    for sig in signals.get('sector_signals', []):
        sector_name = sig.get('sector', '')
        if any(kw in sector_name for kw in keywords):
            if sig['signal'] == '利好':
                score += 8
                reasons.append(f"📊板块利好: {sig['reason']}")
            elif sig['signal'] == '利空':
                score -= 10
                reasons.append(f"📊板块利空: {sig['reason']}")
    
    # 风险警报
    for alert in signals.get('risk_alerts', []):
        if alert.get('severity') == 'high':
            # 高风险市场环境，所有股票都要打折
            score -= 3
    
    # 股吧热度（反向指标警告）
    # 如果一只股票在股吧热度前5且股价已涨很多，小心散户接盘
    
    return {
        'score_delta': score,
        'reasons': reasons,
        'has_news': len(reasons) > 0,
    }


# ============================================================
# 存储新闻快照到数据库
# ============================================================
def save_news_snapshot(news_data: dict, signals: dict):
    """保存新闻快照到数据库，用于回溯分析"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        c.execute('''CREATE TABLE IF NOT EXISTS news_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            news_data TEXT,
            signals TEXT,
            created_at TEXT
        )''')
        
        today = datetime.now().strftime('%Y-%m-%d')
        c.execute(
            'INSERT INTO news_snapshots (date, news_data, signals, created_at) VALUES (?, ?, ?, ?)',
            (today, json.dumps(news_data, ensure_ascii=False, default=str),
             json.dumps(signals, ensure_ascii=False, default=str),
             datetime.now().isoformat())
        )
        
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"保存新闻快照失败: {e}")


# ============================================================
# 主入口: 新闻采集+分析一条龙
# ============================================================
def collect_and_analyze(stock_code: str = None) -> dict:
    """新闻采集+LLM分析，返回结构化信号"""
    news_data = collect_all_news(stock_code)
    
    print("  🤖 LLM解读新闻信号...")
    signals = analyze_news_with_llm(news_data)
    
    # 保存快照
    save_news_snapshot(news_data, signals)
    
    # 统计
    total_signals = (
        len(signals.get('market_signals', [])) +
        len(signals.get('sector_signals', [])) +
        len(signals.get('stock_signals', []))
    )
    print(f"  🤖 提取{total_signals}条交易信号, {len(signals.get('risk_alerts', []))}条风险预警")
    
    return {
        'news': news_data,
        'signals': signals,
    }


if __name__ == "__main__":
    print("=== 新闻/舆情数据采集测试 ===\n")
    result = collect_and_analyze()
    
    signals = result['signals']
    print(f"\n📊 市场信号: {len(signals.get('market_signals', []))}条")
    for s in signals.get('market_signals', []):
        print(f"  [{s.get('impact_level','')}] {s['signal']}: {s['description']}")
    
    print(f"\n🏭 板块信号: {len(signals.get('sector_signals', []))}条")
    for s in signals.get('sector_signals', []):
        print(f"  {s['sector']}: {s['signal']} - {s['reason']}")
    
    print(f"\n📌 个股信号: {len(signals.get('stock_signals', []))}条")
    for s in signals.get('stock_signals', []):
        print(f"  {s.get('name','')}({s.get('code','')}): {s['signal']} - {s['reason']}")
    
    print(f"\n⚠️ 风险预警: {len(signals.get('risk_alerts', []))}条")
    for s in signals.get('risk_alerts', []):
        print(f"  [{s.get('severity','')}] {s['type']}: {s['description']}")
    
    print(f"\n💬 情绪总结: {signals.get('sentiment_summary', 'N/A')}")
