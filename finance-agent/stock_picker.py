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
from performance_tracker import classify_sector, record_recommendation
from position_manager import SECTOR_STRATEGY_WEIGHTS, get_sector_score_multiplier, kelly_position_size


# 各信号源对应的策略key（用于市场状态调节权重）
SIGNAL_STRATEGY_MAP = {
    '量价齐升': 'momentum',
    '创新高': 'momentum',
    '大笔买入': 'money_flow',
    '火箭发射': 'money_flow',
    '强势股': 'strong',
    '机构买入': 'institution',
    '机构增持': 'institution',
    '机构强烈推荐': 'institution',
}

# 信号历史胜率权重(基于回测和实盘经验)
SIGNAL_QUALITY_WEIGHTS = {
    '量价齐升': 1.2,     # 量价配合信号可靠
    '创新高': 0.9,       # 追高有风险
    '大笔买入': 1.1,     # 资金流入有效
    '火箭发射': 0.7,     # 短线信号容易反转
    '强势股': 0.8,       # 可能已到顶
    '机构买入': 1.3,     # 机构买入最可靠
    '机构增持': 1.2,
    '机构强烈推荐': 1.4,
}


def get_recent_strategy_performance() -> dict:
    """读取近期推荐绩效，动态调节策略可信度
    
    如果某策略近期命中率低于30%，降低其权重
    如果某板块近期表现好，提升其权重
    """
    try:
        from performance_tracker import get_performance_summary
        perf = get_performance_summary()
        
        strategy_mult = {}
        for s in perf.get('by_strategy', []):
            if s['total'] >= 3:  # 至少3次推荐才有统计意义
                hr = s['hit_rate']
                if hr >= 50:
                    strategy_mult[s['strategy']] = 1.2
                elif hr >= 30:
                    strategy_mult[s['strategy']] = 1.0
                else:
                    strategy_mult[s['strategy']] = 0.7  # 近期表现差，降权
        
        sector_mult = {}
        for s in perf.get('by_sector', []):
            if s['total'] >= 3:
                hr = s['hit_rate']
                if hr >= 50:
                    sector_mult[s['sector']] = 1.15
                elif hr < 25:
                    sector_mult[s['sector']] = 0.8
        
        return {'strategy': strategy_mult, 'sector': sector_mult}
    except:
        return {'strategy': {}, 'sector': {}}


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


def score_and_rank(all_candidates: list, regime: str = "") -> list:
    """综合打分+技术面验证+板块策略路由+市场状态调节+排名"""
    # 合并同一股票的信号（按信号质量加权）
    merged = {}
    for c in all_candidates:
        code = c['code']
        if not code or len(code) < 6:
            continue
        sig_base = c['signal'].split('×')[0].split('+')[0]
        quality_w = SIGNAL_QUALITY_WEIGHTS.get(sig_base, 1.0)
        weighted_score = int(c['score'] * quality_w)
        if code in merged:
            merged[code]['signals'].append(c['signal'])
            merged[code]['score'] += weighted_score
        else:
            merged[code] = {
                'code': code,
                'name': c.get('name', ''),
                'signals': [c['signal']],
                'score': weighted_score,
            }

    # 排序取top
    ranked = sorted(merged.values(), key=lambda x: -x['score'])[:15]

    # 市场状态调节信号源权重
    if regime:
        from market_regime import get_regime_strategy_multiplier
        for stock in ranked:
            adjusted_score = 0
            for sig in stock['signals']:
                sig_base = sig.split('×')[0].split('+')[0]  # 取信号基础名
                strategy_key = SIGNAL_STRATEGY_MAP.get(sig_base, 'multi_factor')
                multiplier = get_regime_strategy_multiplier(regime, strategy_key)
                adjusted_score += stock['score'] / max(len(stock['signals']), 1) * multiplier
            stock['score'] = int(adjusted_score)

    # 加技术面验证 + 板块策略路由
    print(f"  📊 验证{len(ranked)}只候选股技术面...")
    for i, stock in enumerate(ranked):
        try:
            # 板块分类
            sector = classify_sector(stock['code'], stock.get('name', ''))
            stock['sector'] = sector
            weights = SECTOR_STRATEGY_WEIGHTS.get(sector, {})

            df = get_stock_daily(stock['code'], 60)
            if df is not None and not df.empty:
                tech = calculate_technical_indicators(df)
                stock['technical'] = tech

                # 技术面加减分 — 按板块策略权重调节
                trend = tech.get('trend', '')
                if '多头' in trend or '强势' in trend:
                    stock['score'] += int(10 * weights.get('trend_follow', 1.0))
                elif '空头' in trend or '弱势' in trend:
                    stock['score'] -= 10

                rsi = tech.get('rsi14', 50)
                if 40 < rsi < 70:  # RSI适中，安全区
                    stock['score'] += 5
                elif rsi > 80:  # 超买风险
                    stock['score'] -= 8

                macd_sig = tech.get('macd_signal', '')
                macd_weight = weights.get('macd_rsi', 1.0)
                if macd_sig == 'golden_cross':
                    stock['score'] += int(12 * macd_weight)  # MACD金叉按板块加权
                elif macd_sig == 'bullish':
                    stock['score'] += int(5 * macd_weight)
                elif macd_sig == 'death_cross':
                    stock['score'] -= 12

                vol_ratio = tech.get('volume_ratio', 1)
                if vol_ratio > 1.5:  # 放量
                    stock['score'] += 5
                elif vol_ratio < 0.5:  # 缩量
                    stock['score'] -= 3

                # KDJ信号加减分
                kdj_sig = tech.get('kdj_signal', '')
                if kdj_sig == 'golden_cross':
                    stock['score'] += 8
                elif kdj_sig == 'oversold':
                    stock['score'] += 5
                elif kdj_sig == 'death_cross':
                    stock['score'] -= 8
                elif kdj_sig == 'overbought':
                    stock['score'] -= 5

                # RSI背离信号 — 强反转信号
                rsi_div = tech.get('rsi_divergence', 'none')
                if rsi_div == 'bullish':
                    stock['score'] += 10  # 底背离是强买入信号
                elif rsi_div == 'bearish':
                    stock['score'] -= 10  # 顶背离是强卖出信号

                # === 动量衰减检测 — 避免追高 ===
                if tech.get('momentum_decay'):
                    stock['score'] -= 8  # MACD柱线递减，动力不足
                if tech.get('volume_price_diverge'):
                    stock['score'] -= 6  # 量价背离，上涨不可持续

                # === VWAP入场时机 ===
                price_vs_vwap = tech.get('price_vs_vwap', 0)
                if price_vs_vwap < -3:  # 低于VWAP 3%+，折价买入好时机
                    stock['score'] += 8
                elif price_vs_vwap < -1:
                    stock['score'] += 4
                elif price_vs_vwap > 5:  # 远超VWAP，溢价追高风险大
                    stock['score'] -= 5

                # === 跳空缺口信号 ===
                if tech.get('gap_up'):
                    stock['score'] += 6  # 向上跳空缺口=强势突破
                if tech.get('gap_down'):
                    stock['score'] -= 8  # 向下跳空缺口=破位风险

                # === 换手率过滤 ===
                # 用volume_ratio近似判断异常换手: 量比>3说明换手极高,可能是游资炒作
                if vol_ratio > 3.0:
                    stock['score'] -= 6  # 异常高换手,游资出货风险
                    stock['high_turnover'] = True

                # === ATR波动率过滤 ===
                atr_pct = tech.get('atr_pct', 0)
                if atr_pct > 6:  # 日均波动>6%，风险太大
                    stock['score'] -= 8
                elif atr_pct > 4:  # 较高波动
                    stock['score'] -= 3
                stock['atr_pct'] = atr_pct

                # 板块整体乘数（回测验证好的板块加成）
                stock['score'] = int(stock['score'] * get_sector_score_multiplier(sector))

                # === 近期绩效自适应 ===
                # 根据近期实际推荐表现动态调节分数
                try:
                    perf_mult = get_recent_strategy_performance()
                    sector_adj = perf_mult.get('sector', {}).get(sector, 1.0)
                    stock['score'] = int(stock['score'] * sector_adj)
                except:
                    pass

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


def multi_strategy_pick(regime: str = "") -> dict:
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

    # 打分排名（含市场状态调节）
    ranked = score_and_rank(all_candidates, regime=regime)

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
