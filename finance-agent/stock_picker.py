"""多策略选股引擎 — 综合技术面+资金面+消息面+AI研判"""

import akshare as ak
import pandas as pd
import json
import time
from datetime import datetime
from data_collector import (
    get_stock_daily, get_realtime_quotes, get_market_sentiment,
    get_hot_stocks, get_stock_research_reports, get_stock_news,
    get_market_indices, get_sector_fund_flow, calculate_technical_indicators
)


def get_momentum_candidates() -> list:
    """策略1: 动量策略 — 量价齐升+创新高"""
    candidates = []

    # 量价齐升
    try:
        df = ak.stock_rank_ljqs_ths()
        for _, row in df.head(30).iterrows():
            code = str(row.get('股票代码', ''))
            candidates.append({
                'code': code,
                'name': row.get('股票简称', ''),
                'signal': '量价齐升',
                'days': int(row.get('量价齐升天数', 0)),
                'score': min(int(row.get('量价齐升天数', 0)) * 3, 15),
            })
    except Exception as e:
        print(f"量价齐升获取失败: {e}")

    # 创新高
    try:
        time.sleep(0.5)
        df = ak.stock_rank_cxg_ths()
        for _, row in df.head(20).iterrows():
            code = str(row.get('股票代码', ''))
            existing = next((c for c in candidates if c['code'] == code), None)
            if existing:
                existing['signal'] += '+创新高'
                existing['score'] += 10
            else:
                candidates.append({
                    'code': code,
                    'name': row.get('股票简称', ''),
                    'signal': '创新高',
                    'score': 10,
                })
    except Exception as e:
        print(f"创新高获取失败: {e}")

    return candidates


def get_money_flow_candidates() -> list:
    """策略2: 资金流入 — 大笔买入+火箭发射"""
    candidates = []
    buy_counts = {}

    # 大笔买入统计（同一只股票出现多次=资金持续流入）
    try:
        df = ak.stock_changes_em(symbol='大笔买入')
        for _, row in df.iterrows():
            code = str(row.get('代码', ''))
            name = str(row.get('名称', ''))
            if code not in buy_counts:
                buy_counts[code] = {'name': name, 'count': 0}
            buy_counts[code]['count'] += 1

        # 多次大笔买入的股票
        for code, info in sorted(buy_counts.items(), key=lambda x: -x[1]['count']):
            if info['count'] >= 3:  # 至少3次大笔买入
                candidates.append({
                    'code': code,
                    'name': info['name'],
                    'signal': f'大笔买入×{info["count"]}',
                    'score': min(info['count'] * 3, 15),
                })
            if len(candidates) >= 20:
                break
    except Exception as e:
        print(f"大笔买入获取失败: {e}")

    # 火箭发射（快速拉升信号）
    try:
        time.sleep(0.5)
        df = ak.stock_changes_em(symbol='火箭发射')
        rocket_counts = {}
        for _, row in df.iterrows():
            code = str(row.get('代码', ''))
            if code not in rocket_counts:
                rocket_counts[code] = {'name': str(row.get('名称', '')), 'count': 0}
            rocket_counts[code]['count'] += 1

        for code, info in sorted(rocket_counts.items(), key=lambda x: -x[1]['count']):
            existing = next((c for c in candidates if c['code'] == code), None)
            if existing:
                existing['signal'] += f'+火箭×{info["count"]}'
                existing['score'] += min(info['count'] * 4, 12)
            elif info['count'] >= 2:
                candidates.append({
                    'code': code,
                    'name': info['name'],
                    'signal': f'火箭发射×{info["count"]}',
                    'score': min(info['count'] * 4, 12),
                })
            if len(candidates) >= 30:
                break
    except Exception as e:
        print(f"火箭发射获取失败: {e}")

    return candidates


def get_strong_candidates() -> list:
    """策略3: 强势股 — 涨停板+强势连板"""
    candidates = []
    today = datetime.now().strftime('%Y%m%d')

    # 强势股池
    try:
        df = ak.stock_zt_pool_strong_em(date=today)
        for _, row in df.head(20).iterrows():
            code = str(row.get('代码', ''))
            candidates.append({
                'code': code,
                'name': row.get('名称', ''),
                'signal': '强势股',
                'change': row.get('涨跌幅', 0),
                'score': 8,
            })
    except Exception as e:
        print(f"强势股获取失败: {e}")

    return candidates


def get_institution_candidates() -> list:
    """策略4: 机构推荐 — 研报买入/增持评级"""
    candidates = []
    reports = get_stock_research_reports()
    if reports is not None and not reports.empty:
        for _, row in reports.iterrows():
            rating = str(row.get('评级', ''))
            if rating in ['买入', '增持', '强烈推荐']:
                code = str(row.get('股票代码', ''))
                if code:
                    candidates.append({
                        'code': code,
                        'name': row.get('股票名称', ''),
                        'signal': f'机构{rating}',
                        'institution': row.get('机构', ''),
                        'score': 12 if rating == '买入' else 8,
                    })
    return candidates[:20]


def score_and_rank(all_candidates: list) -> list:
    """综合打分+技术面验证+排名"""
    # 合并同一股票的信号
    merged = {}
    for c in all_candidates:
        code = c['code']
        if not code or len(code) < 6:
            continue
        if code in merged:
            merged[code]['signals'].append(c['signal'])
            merged[code]['score'] += c['score']
        else:
            merged[code] = {
                'code': code,
                'name': c.get('name', ''),
                'signals': [c['signal']],
                'score': c['score'],
            }

    # 排序取top
    ranked = sorted(merged.values(), key=lambda x: -x['score'])[:15]

    # 加技术面验证
    print(f"  📊 验证{len(ranked)}只候选股技术面...")
    for i, stock in enumerate(ranked):
        try:
            df = get_stock_daily(stock['code'], 60)
            if df is not None and not df.empty:
                tech = calculate_technical_indicators(df)
                stock['technical'] = tech

                # 技术面加减分
                trend = tech.get('trend', '')
                if '多头' in trend or '强势' in trend:
                    stock['score'] += 10
                elif '空头' in trend or '弱势' in trend:
                    stock['score'] -= 10

                rsi = tech.get('rsi14', 50)
                if 40 < rsi < 70:  # RSI适中，安全区
                    stock['score'] += 5
                elif rsi > 80:  # 超买风险
                    stock['score'] -= 8

                macd_sig = tech.get('macd_signal', '')
                if macd_sig == 'golden_cross':
                    stock['score'] += 12  # MACD金叉重大加分
                elif macd_sig == 'bullish':
                    stock['score'] += 5
                elif macd_sig == 'death_cross':
                    stock['score'] -= 12

                vol_ratio = tech.get('volume_ratio', 1)
                if vol_ratio > 1.5:  # 放量
                    stock['score'] += 5
                elif vol_ratio < 0.5:  # 缩量
                    stock['score'] -= 3

            time.sleep(0.3)
        except Exception as e:
            print(f"  ⚠️ {stock['code']}技术面验证失败: {e}")

    # 重新排序
    ranked = sorted(ranked, key=lambda x: -x['score'])
    return ranked


def filter_tradeable(candidates: list) -> list:
    """过滤：排除ST、停牌、涨跌停（无法买入）"""
    filtered = []
    codes = [c['code'] for c in candidates[:10]]
    quotes = get_realtime_quotes(codes)

    for c in candidates[:10]:
        name = c.get('name', '')
        if 'ST' in name or '*ST' in name:
            continue
        code = c['code']
        if code in quotes:
            price = quotes[code]['price']
            change = quotes[code].get('change_pct', 0)
            if price <= 0:  # 停牌
                continue
            if abs(change) >= 9.8:  # 涨跌停，大概率买不进
                c['at_limit'] = True
            c['realtime_price'] = price
            c['change_pct'] = change
        filtered.append(c)

    return filtered


def multi_strategy_pick() -> dict:
    """多策略综合选股主流程"""
    print("  🔍 策略1: 动量选股(量价齐升+创新高)...")
    momentum = get_momentum_candidates()
    print(f"    → {len(momentum)}只候选")

    print("  💰 策略2: 资金流入(大笔买入+火箭发射)...")
    money = get_money_flow_candidates()
    print(f"    → {len(money)}只候选")

    print("  🔥 策略3: 强势股池...")
    strong = get_strong_candidates()
    print(f"    → {len(strong)}只候选")

    print("  📋 策略4: 机构推荐...")
    institution = get_institution_candidates()
    print(f"    → {len(institution)}只候选")

    # 合并所有候选
    all_candidates = momentum + money + strong + institution
    print(f"  📊 共{len(all_candidates)}条信号，开始综合打分...")

    # 打分排名
    ranked = score_and_rank(all_candidates)

    # 过滤
    tradeable = filter_tradeable(ranked)

    return {
        'candidates': tradeable,
        'stats': {
            'momentum_count': len(momentum),
            'money_flow_count': len(money),
            'strong_count': len(strong),
            'institution_count': len(institution),
            'total_signals': len(all_candidates),
            'final_count': len(tradeable),
        }
    }


if __name__ == "__main__":
    print("=== 多策略选股测试 ===")
    result = multi_strategy_pick()
    print(f"\n📊 统计: {json.dumps(result['stats'], ensure_ascii=False)}")
    print(f"\n🎯 Top候选股:")
    for i, c in enumerate(result['candidates'][:8]):
        print(f"  {i+1}. {c['name']}({c['code']}) 分数:{c['score']} 信号:{'+'.join(c['signals'])} "
              f"价格:{c.get('realtime_price','?')} 涨跌:{c.get('change_pct','?')}%")
        tech = c.get('technical', {})
        if tech:
            print(f"     趋势:{tech.get('trend','')} RSI:{tech.get('rsi14','')} MACD:{tech.get('macd_signal','')}")
