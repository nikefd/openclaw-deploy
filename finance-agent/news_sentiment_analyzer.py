#!/usr/bin/env python3
"""
新闻情感分析集成 - 盤中实时新闻舆情
- 关键词提取 + 情感打分
- 风险等级判定
- 新闻热度排序
"""

import json
import re
from datetime import datetime, timedelta
from pathlib import Path

def analyze_news_sentiment(news_title, news_content):
    """
    对新闻进行情感分析
    返回: {'sentiment': 'positive|neutral|negative', 'score': 0-100, 'keywords': [...]}
    """
    # 正向关键词表
    positive_keywords = [
        '涨停', '涨', '上升', '突破', '创新高', '利好', '强势', '爆量',
        '机构买入', '产业链', '受益', '增长', '加速', '复苏', '回暖',
        '布局', '联合', '战略', '合作', '并购', '融资', '轮融'
    ]
    
    # 负向关键词表
    negative_keywords = [
        '跌停', '下跌', '暴跌', '闪崩', '利空', '风险', '警示', '亏损',
        '违规', '处罚', '减持', '高位', '套牢', '爆雷', '退市',
        '停牌', '延期', '重组', '清仓', '破产', '债务'
    ]
    
    # 中性关键词表
    neutral_keywords = [
        '公告', '持仓', '调研', '报告', '会议', '论坛', '发布',
        '宣布', '推出', '发起', '启动', '计划', '预期', '目标'
    ]
    
    text = (news_title + ' ' + news_content).lower()
    
    # 计数
    pos_count = sum(text.count(kw) for kw in positive_keywords)
    neg_count = sum(text.count(kw) for kw in negative_keywords)
    neu_count = sum(text.count(kw) for kw in neutral_keywords)
    
    # 判定
    if pos_count > neg_count * 1.5:
        sentiment = 'positive'
        score = min(100, 50 + pos_count * 5)
    elif neg_count > pos_count * 1.5:
        sentiment = 'negative'
        score = max(0, 50 - neg_count * 5)
    else:
        sentiment = 'neutral'
        score = 50 + (pos_count - neg_count) * 2
    
    # 关键词提取
    keywords = []
    for kw in positive_keywords:
        if kw in text and len(keywords) < 3:
            keywords.append(f"+{kw}")
    for kw in negative_keywords:
        if kw in text and len(keywords) < 6:
            keywords.append(f"-{kw}")
    
    return {
        'sentiment': sentiment,
        'score': max(0, min(100, score)),
        'keywords': keywords[:5],
        'analyzed_at': datetime.now().isoformat()
    }

def process_news_batch(news_list):
    """
    批量处理新闻列表
    返回: {'hot_news': [...], 'sentiment_distribution': {...}, 'risk_level': 'green|yellow|red'}
    """
    if not news_list:
        return {
            'hot_news': [],
            'sentiment_distribution': {'positive': 0, 'neutral': 0, 'negative': 0},
            'risk_level': 'green',
            'avg_sentiment_score': 50
        }
    
    analyzed_news = []
    sentiment_scores = []
    
    for i, news in enumerate(news_list[:20]):  # 处理前20条
        analysis = analyze_news_sentiment(
            news.get('title', ''),
            news.get('content', '')[:200]  # 只取前200字
        )
        
        news_item = {
            'title': news.get('title', ''),
            'time': news.get('time', ''),
            'rank': i + 1,
            **analysis
        }
        analyzed_news.append(news_item)
        sentiment_scores.append(analysis['score'])
    
    # 统计分布
    positive_cnt = sum(1 for n in analyzed_news if n['sentiment'] == 'positive')
    negative_cnt = sum(1 for n in analyzed_news if n['sentiment'] == 'negative')
    neutral_cnt = len(analyzed_news) - positive_cnt - negative_cnt
    
    # 计算平均情感
    avg_sentiment = sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else 50
    
    # 风险等级
    if avg_sentiment >= 70:
        risk_level = 'green'  # 乐观
    elif avg_sentiment >= 40:
        risk_level = 'yellow'  # 谨慎
    else:
        risk_level = 'red'  # 警报
    
    return {
        'hot_news': sorted(analyzed_news, key=lambda x: abs(x['score'] - 50), reverse=True)[:10],
        'sentiment_distribution': {
            'positive': positive_cnt,
            'neutral': neutral_cnt,
            'negative': negative_cnt
        },
        'risk_level': risk_level,
        'avg_sentiment_score': round(avg_sentiment, 1),
        'total_analyzed': len(analyzed_news)
    }

def generate_news_insight(analysis_result):
    """
    根据新闻分析结果生成洞察文字
    """
    avg_score = analysis_result['avg_sentiment_score']
    risk = analysis_result['risk_level']
    dist = analysis_result['sentiment_distribution']
    
    if avg_score >= 70:
        insight = f"📈 市场舆情向好 | 正面新闻{dist['positive']}条占主导，市场情绪乐观"
    elif avg_score >= 50:
        insight = f"➡️ 舆情平稳 | 正面{dist['positive']}条，负面{dist['negative']}条，市场信号混合"
    else:
        insight = f"📉 市场舆情偏弱 | 负面新闻{dist['negative']}条占比较高，需要谨慎"
    
    return insight

if __name__ == '__main__':
    # 测试用例
    test_news = [
        {
            'title': '某科技股涨停，机构买入持续增加',
            'content': '今日受产业链利好刺激，该股涨停，成交量创新高，机构持续加仓',
            'time': '2026-05-05 10:30'
        },
        {
            'title': '某新能源企业爆雷，下跌',
            'content': '公司财务出现问题，引发投资者担忧，股价闪崩',
            'time': '2026-05-05 09:15'
        }
    ]
    
    result = process_news_batch(test_news)
    print("=== 新闻情感分析 ===")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    insight = generate_news_insight(result)
    print(f"\n洞察: {insight}")
