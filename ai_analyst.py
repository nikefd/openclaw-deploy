"""AI分析师 v2 — 多维度分析，更精准的选股"""

import json
import urllib.request
from datetime import datetime
from data_collector import (
    get_stock_news, get_market_sentiment, get_stock_daily,
    get_stock_research_reports, get_hot_stocks, get_sector_fund_flow,
    get_market_indices, calculate_technical_indicators
)

GATEWAY_TOKEN = "17043bad6b19491dfa222d681d43584fbc3e8dd3781edfbc"

def call_llm(prompt: str, system: str = "你是一个专业的A股分析师，擅长技术分析和基本面分析。") -> str:
    """调用LLM"""
    url = "http://127.0.0.1:18789/v1/chat/completions"
    payload = json.dumps({
        "model": "openclaw/reader",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 4000,
        "temperature": 0.3
    })
    req = urllib.request.Request(url, data=payload.encode(),
                                 headers={
                                     "Content-Type": "application/json",
                                     "Authorization": f"Bearer {GATEWAY_TOKEN}"
                                 })
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
            return data["choices"][0]["message"]["content"]
    except Exception as e:
        return f"LLM调用失败: {e}"


def analyze_market() -> dict:
    """市场全局分析"""
    sentiment = get_market_sentiment()
    indices = get_market_indices()
    sectors = get_sector_fund_flow()
    hot = get_hot_stocks()
    news = get_stock_news()
    reports = get_stock_research_reports()

    sector_text = sectors.head(15).to_string(index=False) if sectors is not None and not sectors.empty else "暂无数据"
    hot_text = hot.head(15).to_string(index=False) if hot is not None and not hot.empty else "暂无数据"

    news_text = ""
    if news is not None and not news.empty:
        cols = [c for c in ['新闻标题', '新闻内容', '关键词'] if c in news.columns]
        if cols:
            news_text = news[cols].head(20).to_string(index=False)

    report_text = ""
    if reports is not None and not reports.empty:
        report_text = reports.head(15).to_string(index=False)

    indices_text = json.dumps(indices, ensure_ascii=False) if indices else "暂无数据"

    prompt = f"""今天是{datetime.now().strftime('%Y年%m月%d日')}。请综合分析以下A股市场数据。

## 大盘指数
{indices_text}

## 市场情绪指标
- 涨停家数: {sentiment.get('limit_up_count', 'N/A')}
- 跌停家数: {sentiment.get('limit_down_count', 'N/A')}
- 炸板家数: {sentiment.get('bomb_count', 'N/A')}
- 大笔买入异动: {sentiment.get('big_buy_count', 'N/A')}笔
- 情绪得分: {sentiment.get('sentiment_score', 'N/A')}/100 ({sentiment.get('sentiment_label', '?')})

## 涨停龙虎榜
{json.dumps(sentiment.get('limit_up_stocks', []), ensure_ascii=False)[:500]}

## 板块资金流向
{sector_text}

## 热门股票
{hot_text}

## 最新研报 (机构推荐)
{report_text}

## 最新财经新闻
{news_text if news_text else '暂无数据'}

请输出:
1. **市场总结** (简明扼要概括今日市场)
2. **情绪判断** (贪婪/乐观/中性/谨慎/恐慌) + 理由
3. **板块机会** (最值得关注的2-3个板块及原因)
4. **风险提示**
5. **仓位建议** (几成仓位，攻守策略)
"""

    analysis = call_llm(prompt)
    return {
        "sentiment": sentiment,
        "indices": indices,
        "analysis": analysis,
        "timestamp": datetime.now().isoformat()
    }


def analyze_stock(symbol: str, name: str = "") -> dict:
    """个股深度分析"""
    daily = get_stock_daily(symbol, days=60)
    tech = {}
    price_text = ""
    if daily is not None and not daily.empty:
        price_text = daily.tail(10).to_string(index=False)
        tech = calculate_technical_indicators(daily)

    reports = get_stock_research_reports(symbol)
    report_text = reports.head(5).to_string(index=False) if reports is not None and not reports.empty else "暂无"

    news = get_stock_news(symbol)
    news_text = ""
    if news is not None and not news.empty:
        cols = [c for c in ['新闻标题', '新闻内容'] if c in news.columns]
        if cols:
            news_text = news[cols].head(10).to_string(index=False)

    prompt = f"""请深度分析 {symbol} {name}:

## 近10日行情
{price_text if price_text else '暂无'}

## 技术指标
{json.dumps(tech, ensure_ascii=False, indent=2) if tech else '暂无'}

## 最新研报
{report_text}

## 相关新闻
{news_text if news_text else '暂无'}

请输出:
1. **技术面** (趋势、支撑/压力、MACD/RSI/布林带信号)
2. **消息面** (利好/利空)
3. **机构观点**
4. **综合评分** (1-10)
5. **操作建议** (买入/持有/观望/卖出，具体价位和仓位)
"""

    analysis = call_llm(prompt)
    return {"symbol": symbol, "name": name, "analysis": analysis, "technical": tech, "timestamp": datetime.now().isoformat()}


def pick_stocks() -> dict:
    """AI选股"""
    market = analyze_market()

    # 收集候选股
    hot = get_hot_stocks()
    reports = get_stock_research_reports()

    candidates = []
    if hot is not None and not hot.empty:
        for _, row in hot.head(15).iterrows():
            code = str(row.get('代码', ''))
            if code.startswith('SH') or code.startswith('SZ'):
                code = code[2:]
            if code:
                candidates.append({"code": code, "source": "热门"})

    if reports is not None and not reports.empty:
        for _, row in reports.head(15).iterrows():
            code = str(row.get('股票代码', ''))
            name = str(row.get('股票名称', ''))
            rating = str(row.get('评级', ''))
            if code and rating in ['买入', '增持', '强烈推荐']:
                candidates.append({"code": code, "name": name, "rating": rating, "source": "研报"})

    # 去重
    seen = set()
    unique = []
    for c in candidates:
        if c['code'] not in seen:
            seen.add(c['code'])
            unique.append(c)

    # 对top候选加技术指标
    for i, c in enumerate(unique[:10]):
        try:
            df = get_stock_daily(c['code'], 60)
            if df is not None and not df.empty:
                tech = calculate_technical_indicators(df)
                unique[i]['technical'] = tech
                unique[i]['name'] = unique[i].get('name', '') or (df.iloc[-1].get('股票名称', '') if '股票名称' in df.columns else '')
        except:
            pass

    prompt = f"""基于市场分析和候选股票，选出3-5只最值得买入的股票。

## 市场分析
{market['analysis'][:1500]}

## 候选池 (含技术指标)
{json.dumps(unique[:15], ensure_ascii=False, default=str)[:3000]}

要求：
- 优先选：研报推荐+技术面好+有资金关注的
- 考虑风险收益比
- 给出具体价位

JSON格式输出:
```json
{{
  "picks": [
    {{
      "symbol": "600xxx",
      "name": "xxx",
      "reason": "...",
      "buy_price": 0.0,
      "target_price": 0.0,
      "stop_loss": 0.0,
      "position_pct": 0.1,
      "confidence": 8
    }}
  ],
  "market_view": "一句话总结"
}}
```
只输出JSON。"""

    result = call_llm(prompt, system="你是顶级A股量化分析师。严格按JSON格式输出。")
    try:
        if "```json" in result:
            result = result.split("```json")[1].split("```")[0]
        elif "```" in result:
            result = result.split("```")[1].split("```")[0]
        picks = json.loads(result.strip())
    except:
        picks = {"raw": result, "picks": []}

    return {"market": market, "picks": picks, "timestamp": datetime.now().isoformat()}


if __name__ == "__main__":
    print("=== AI分析师v2测试 ===")
    result = pick_stocks()
    print(json.dumps(result.get("picks", {}), ensure_ascii=False, indent=2))
