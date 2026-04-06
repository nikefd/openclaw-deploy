"""多策略选股引擎 — 综合技术面+资金面+消息面+新闻舆情+AI研判"""

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
from position_manager import SECTOR_STRATEGY_WEIGHTS, get_sector_score_multiplier, kelly_position_size, get_stop_loss_blacklist


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


def get_learned_signal_weights() -> dict:
    """从实际交易结果动态学习信号可靠性权重
    
    分析历史买入信号 vs 实际盈亏，自动调低失败信号的权重
    """
    try:
        import sqlite3
        conn = sqlite3.connect('/home/nikefd/finance-agent/data/trading.db')
        c = conn.cursor()
        # 获取最近30天的买入交易及其最近一次卖出结果
        c.execute("""
            SELECT b.reason, 
                   CASE WHEN s.reason LIKE '%止损%' THEN 'loss'
                        WHEN s.reason LIKE '%止盈%' THEN 'win'
                        ELSE 'unknown' END as outcome
            FROM trades b
            LEFT JOIN trades s ON b.symbol = s.symbol AND s.direction = 'SELL' 
                AND s.id = (SELECT MIN(s2.id) FROM trades s2 WHERE s2.symbol = b.symbol AND s2.direction = 'SELL' AND s2.id > b.id)
            WHERE b.direction = 'BUY' AND b.trade_date >= date('now', '-30 days')
        """)
        rows = c.fetchall()
        conn.close()
        
        if len(rows) < 5:
            return {}  # 样本太少不学习
        
        signal_stats = {}  # signal -> {wins, losses}
        for reason, outcome in rows:
            if not reason:
                continue
            # 解析买入理由中的信号
            for sig_name in SIGNAL_QUALITY_WEIGHTS:
                if sig_name in reason:
                    if sig_name not in signal_stats:
                        signal_stats[sig_name] = {'wins': 0, 'losses': 0}
                    if outcome == 'win':
                        signal_stats[sig_name]['wins'] += 1
                    elif outcome == 'loss':
                        signal_stats[sig_name]['losses'] += 1
        
        # 计算学习后的权重调节
        adjustments = {}
        for sig, stats in signal_stats.items():
            total = stats['wins'] + stats['losses']
            if total >= 3:  # 至少3次才有统计意义
                win_rate = stats['wins'] / total
                if win_rate < 0.25:
                    adjustments[sig] = 0.5   # 胜率<25%大幅降权
                elif win_rate < 0.4:
                    adjustments[sig] = 0.7   # 胜率<40%适度降权
                elif win_rate > 0.6:
                    adjustments[sig] = 1.3   # 胜率>60%提权
        return adjustments
    except:
        return {}


# 信号类别分组 — 用于共识门槛检查
SIGNAL_CATEGORIES = {
    '量价齐升': 'momentum',
    '创新高': 'momentum',
    '大笔买入': 'money_flow',
    '火箭发射': 'money_flow',
    '强势股': 'strong',
    '机构买入': 'institution',
    '机构增持': 'institution',
    '机构强烈推荐': 'institution',
    '新闻利好': 'news',
    '机构龙虎榜买入': 'lhb',
    '北向增持': 'northbound',
    '缩量企稳': 'technical',
    '均线收敛突破': 'technical',
}


def get_dynamic_score_threshold(regime: str = "", loss_streak: int = 0) -> int:
    """基于近期胜率动态调节最低买入分数门槛
    
    连亏越多、胜率越低 → 门槛越高，只买最强信号
    """
    base = 20  # 正常市场下的最低分数
    
    # 近期胜率调节
    try:
        from performance_tracker import get_performance_summary
        perf = get_performance_summary()
        hr = perf.get('hit_rate', 50)
        if hr < 20:
            base += 15  # 近期命中率极低,大幅提高门槛
        elif hr < 35:
            base += 8
    except:
        pass
    
    # 连亏调节
    if loss_streak >= 5:
        base += 12
    elif loss_streak >= 3:
        base += 6
    
    # 熊市调节
    if regime == 'bear':
        base += 5
    
    return base


def check_signal_consensus(signals: list) -> tuple:
    """检查信号共识: 至少2个不同类别的信号同意才通过
    
    Returns: (pass: bool, categories: set, category_count: int)
    """
    categories = set()
    for sig in signals:
        sig_base = sig.split('×')[0].split('+')[0].split(':')[0]
        cat = SIGNAL_CATEGORIES.get(sig_base, 'other')
        categories.add(cat)
    return len(categories) >= 2, categories, len(categories)


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


def get_sector_momentum() -> dict:
    """板块动量轮动 — 追踪近期板块资金流入方向，倾斜选股权重
    
    Returns: {sector_name: momentum_score} 正=资金流入，负=流出
    """
    try:
        from data_collector import get_sector_fund_flow
        sectors = get_sector_fund_flow()
        if sectors is None or sectors.empty:
            return {}
        
        result = {}
        for _, row in sectors.iterrows():
            name = str(row.get('板块名称', ''))
            change = float(row.get('涨跌幅', 0) or 0)
            net_flow = float(row.get('主力净流入', 0) or 0)
            # 正向动量: 涨幅+资金流入
            momentum = 0
            if change > 2:
                momentum += 2
            elif change > 0:
                momentum += 1
            elif change < -2:
                momentum -= 2
            if net_flow > 0:
                momentum += 1
            elif net_flow < -1e8:  # 超过1亿流出
                momentum -= 1
            result[name] = momentum
        return result
    except:
        return {}


def score_and_rank(all_candidates: list, regime: str = "") -> list:
    """综合打分+技术面验证+板块策略路由+市场状态调节+排名"""
    # 合并同一股票的信号（按信号质量加权 + 动态学习调整）
    learned_adj = get_learned_signal_weights()
    merged = {}
    for c in all_candidates:
        code = c['code']
        if not code or len(code) < 6:
            continue
        sig_base = c['signal'].split('×')[0].split('+')[0]
        quality_w = SIGNAL_QUALITY_WEIGHTS.get(sig_base, 1.0)
        # 应用学习调整: 实盘验证后的信号权重覆盖默认值
        if sig_base in learned_adj:
            quality_w *= learned_adj[sig_base]
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

    # === 熊市均值回归模式 ===
    # 熊市下追涨策略命中率低,切换为超跌反弹逻辑
    bear_mode = (regime == 'bear')

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
                elif rsi < 30 and bear_mode:  # 熊市超跌反弹加分
                    stock['score'] += 12  # 熊市下RSI<30是抄底机会
                elif rsi < 30:
                    stock['score'] += 5

                macd_sig = tech.get('macd_signal', '')
                macd_weight = weights.get('macd_rsi', 1.0)
                if macd_sig == 'golden_cross':
                    stock['score'] += int(12 * macd_weight)  # MACD金叉按板块加权
                elif macd_sig == 'bullish':
                    stock['score'] += int(5 * macd_weight)
                elif macd_sig == 'death_cross':
                    stock['score'] -= 12

                # === MACD零轴突破: DIF上穿零轴=趋势空翻多，比金叉更强 ===
                if tech.get('macd_zero_cross_up'):
                    stock['score'] += int(10 * macd_weight)  # 强趋势反转信号
                elif tech.get('macd_zero_cross_down'):
                    stock['score'] -= 8  # DIF跌穿零轴=趋势转空

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

                # === OBV能量潮确认 ===
                obv_trend = tech.get('obv_trend', 0)
                if obv_trend > 0.15:  # OBV明显上升，量价配合
                    stock['score'] += 6
                elif obv_trend < -0.15:  # OBV下降，上涨可能是假突破
                    stock['score'] -= 5
                if tech.get('obv_price_diverge'):  # 价涨量缩的OBV背离
                    stock['score'] -= 7

                # === Williams %R 信号 ===
                wr = tech.get('williams_r', -50)
                if tech.get('wr_reversal'):
                    stock['score'] += 8  # 从超卖回升=强买入信号
                elif wr > -20:  # 超买区
                    stock['score'] -= 6
                elif tech.get('wr_overbought_exit'):
                    stock['score'] -= 4  # 从超买回落=减弱信号

                # === 周线趋势过滤器 ===
                # 日线信号必须有周线趋势确认，否则打折
                weekly_trend = tech.get('weekly_trend', 'neutral')
                if weekly_trend == 'down':
                    stock['score'] = int(stock['score'] * 0.6)  # 周线下降趋势，信号大幅打折
                    stock['weekly_downtrend'] = True
                elif weekly_trend == 'up':
                    stock['score'] = int(stock['score'] * 1.15)  # 周线上升趋势，加分
                # neutral不调整

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

                # === ADX趋势强度调节 ===
                # ADX>25=强趋势: 趋势信号可信; ADX<20=弱趋势: 趋势信号打折
                adx = tech.get('adx', 0)
                trend_strength = tech.get('trend_strength', 'unknown')
                if trend_strength == 'strong':
                    # 强趋势下，多头排列/MACD金叉更可信，额外加分
                    if '多头' in trend or macd_sig in ('golden_cross', 'bullish'):
                        stock['score'] += 6
                elif trend_strength == 'weak':
                    # 无方向市场，趋势信号不可信，扣分避免假突破
                    if '多头' in trend or macd_sig in ('golden_cross', 'bullish'):
                        stock['score'] -= 4
                stock['adx'] = adx

                # === 布林带 %B 超卖/超买 ===
                pct_b = tech.get('boll_pct_b', 0.5)
                if pct_b < 0:  # 跌破下轨，极度超卖
                    stock['score'] += 10 if bear_mode else 6
                elif pct_b < 0.2:  # 接近下轨
                    stock['score'] += 5 if bear_mode else 3
                elif pct_b > 1.0:  # 突破上轨，超买
                    stock['score'] -= 6
                
                # 布林带收窄(squeeze) = 即将变盘，观望
                if tech.get('boll_squeeze'):
                    stock['score'] -= 3  # 方向不明，不急着进场
                
                # === 成交量高潮 ===
                if tech.get('sell_climax') and bear_mode:
                    stock['score'] += 10  # 恐慌抛售尾声，熊市抄底好机会
                elif tech.get('sell_climax'):
                    stock['score'] += 5
                if tech.get('buy_climax'):
                    stock['score'] -= 10  # 追高巨量，获利盘回吐风险极大

                # === 相对强度评级 (RS vs 大盘) ===
                # 比大盘弱的股票不买，只选强于大盘的
                stock_ret_10d = tech.get('stock_ret_10d', 0)
                stock_ret_20d = tech.get('stock_ret_20d', 0)
                rs_10d = stock_ret_10d  # 绝对收益当RS
                if rs_10d < -5:
                    stock['score'] -= 8  # 近10日大跌>5%，弱势
                elif rs_10d > 5:
                    stock['score'] += 5  # 近10日涨>5%，强势
                stock['rs_10d'] = rs_10d

                # === 缩量企稳(Volume Dry-up) ===
                if tech.get('volume_dryup'):
                    stock['score'] += 10 if bear_mode else 6  # 卖方耗尽=底部信号
                    stock['volume_dryup'] = True

                # === 均线密集收敛突破 ===
                if tech.get('ma_converge_breakout'):
                    stock['score'] += 12  # MA收敛后突破=强启动信号
                    stock['ma_breakout'] = True

                # === 价格结构: Higher Low 确认底部 ===
                if tech.get('higher_low'):
                    stock['score'] += 8 if bear_mode else 5  # 底部抬升=筑底成功
                if tech.get('lower_low'):
                    stock['score'] -= 8  # 下降通道，不抄底

                # === 抛物线拉升过滤 ===
                # 5日涨幅>15%的票大概率要回调，不追
                if df is not None and len(df) >= 5:
                    try:
                        close_5 = df['收盘'].astype(float)
                        ret_5d = (close_5.iloc[-1] - close_5.iloc[-5]) / close_5.iloc[-5] * 100
                        if ret_5d > 15:
                            stock['score'] -= 12  # 重扣: 抛物线拉升回调风险极大
                            stock['parabolic'] = True
                        elif ret_5d > 10:
                            stock['score'] -= 5   # 轻扣: 短期涨幅较大
                    except:
                        pass

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

                # === 板块动量轮动加分 ===
                try:
                    sector_mom = get_sector_momentum()
                    # 用板块名称关键词匹配: 科技→半导体/软件/芯片, 新能源→光伏/锂电/风电 等
                    SECTOR_KEYWORDS = {
                        '科技成长': ['半导体', '软件', '芯片', '计算机', '电子', '通信', '互联网', '人工智能', 'AI'],
                        '新能源': ['光伏', '锂电', '风电', '新能源', '储能', '太阳能', '电池'],
                        '消费白马': ['白酒', '食品', '家电', '医药', '消费', '零售'],
                    }
                    keywords = SECTOR_KEYWORDS.get(sector, [])
                    best_mom = 0
                    for sec_name, mom_score in sector_mom.items():
                        for kw in keywords:
                            if kw in sec_name:
                                if abs(mom_score) > abs(best_mom):
                                    best_mom = mom_score
                                break
                    if best_mom >= 2:
                        stock['score'] += 6  # 强势板块加分
                    elif best_mom <= -2:
                        stock['score'] -= 4  # 弱势板块扣分
                except:
                    pass

            time.sleep(0.3)
        except Exception as e:
            print(f"  ⚠️ {stock['code']}技术面验证失败: {e}")

    # 重新排序
    ranked = sorted(ranked, key=lambda x: -x['score'])
    
    # === 信号共识过滤 ===
    # 只保留至少2个独立信号类别支持的候选,减少假信号
    consensus_filtered = []
    for stock in ranked:
        passed, cats, cat_count = check_signal_consensus(stock['signals'])
        stock['signal_categories'] = list(cats)
        stock['consensus_count'] = cat_count
        if passed:
            # 多类别共识加分: 3类别+6, 4类别+10
            if cat_count >= 4:
                stock['score'] += 10
            elif cat_count >= 3:
                stock['score'] += 6
            consensus_filtered.append(stock)
        else:
            # 单类别但分数极高(>50)的也保留(可能是强机构推荐)
            if stock['score'] >= 50:
                stock['score'] = int(stock['score'] * 0.8)  # 打折但保留
                consensus_filtered.append(stock)
    
    # 如果共识过滤后太少,放宽到原列表(避免空选)
    if len(consensus_filtered) < 3:
        consensus_filtered = ranked
    
    return sorted(consensus_filtered, key=lambda x: -x['score'])


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


def multi_strategy_pick(regime: str = "", use_news: bool = True, loss_streak: int = 0) -> dict:
    """多策略综合选股主流程（含新闻/舆情数据源）"""
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

    # === 策略5: 新闻/舆情驱动 ===
    news_signals = None
    news_candidates = []
    if use_news:
        try:
            from news_collector import collect_and_analyze, get_news_score_for_stock
            print("  📰 策略5: 新闻/舆情信号...")
            news_result = collect_and_analyze()
            news_signals = news_result.get('signals', {})
            
            # 从新闻信号中提取个股候选
            for sig in news_signals.get('stock_signals', []):
                code = sig.get('code', '')
                if code and len(code) == 6 and sig.get('signal') == '利好':
                    news_candidates.append({
                        'code': code,
                        'name': sig.get('name', ''),
                        'signal': f"新闻利好:{sig.get('reason', '')[:20]}",
                        'score': 15,
                    })
            print(f"    → {len(news_signals.get('stock_signals', []))}条个股信号, "
                  f"{len(news_signals.get('sector_signals', []))}条板块信号")
        except Exception as e:
            print(f"  ⚠️ 新闻采集失败(不影响其他策略): {e}")

    # === 策略6: 资金面数据(北向+龙虎榜+融资融券+宏观) ===
    money_overview = None
    money_candidates = []
    try:
        from market_data_ext import get_money_flow_overview, get_stock_money_signals, save_money_flow_snapshot
        print("  💰 策略6: 资金面数据(北向/龙虎榜/融资融券/宏观)...")
        money_overview = get_money_flow_overview()
        save_money_flow_snapshot(money_overview)
        
        # 从龙虎榜机构买入中提取候选
        for stock in money_overview.get('lhb', {}).get('institution_buys', []):
            code = stock.get('code', '')
            if code and len(code) == 6:
                money_candidates.append({
                    'code': code,
                    'name': stock.get('name', ''),
                    'signal': f"机构龙虎榜买入",
                    'score': 15,
                })
        # 北向大额增持
        for stock in money_overview.get('northbound', {}).get('top_buys', [])[:5]:
            code = stock.get('code', '')
            if code and len(code) == 6 and stock.get('increase_value', 0) > 1:
                money_candidates.append({
                    'code': code,
                    'name': stock.get('name', ''),
                    'signal': f"北向增持{stock['increase_value']}亿",
                    'score': 12,
                })
        print(f"    → 资金面评分: {money_overview.get('money_flow_score', '?')}/100 "
              f"({money_overview.get('money_flow_label', '?')}), "
              f"{len(money_candidates)}只资金面候选")
    except Exception as e:
        print(f"  ⚠️ 资金面数据采集失败(不影响其他策略): {e}")

    # 合并所有候选
    all_candidates = momentum + money + strong + institution + news_candidates + money_candidates
    print(f"  📊 共{len(all_candidates)}条信号，开始综合打分...")

    # 打分排名（含市场状态调节）
    ranked = score_and_rank(all_candidates, regime=regime)

    # === 新闻信号叠加到候选股分数 ===
    if news_signals and use_news:
        try:
            from news_collector import get_news_score_for_stock
            print("  📰 叠加新闻信号到候选股...")
            for stock in ranked:
                news_score = get_news_score_for_stock(
                    stock['code'], stock.get('name', ''), news_signals)
                if news_score['has_news']:
                    stock['score'] += news_score['score_delta']
                    stock['news_reasons'] = news_score['reasons']
                    print(f"    {stock.get('name','')}({stock['code']}): "
                          f"新闻{'+' if news_score['score_delta']>=0 else ''}{news_score['score_delta']}分")
            # 重新排序
            ranked = sorted(ranked, key=lambda x: -x['score'])
        except Exception as e:
            print(f"  ⚠️ 新闻信号叠加失败: {e}")

    # === 资金面信号叠加到候选股分数 ===
    if money_overview:
        try:
            from market_data_ext import get_stock_money_signals
            print("  💰 叠加资金面信号到候选股...")
            for stock in ranked:
                money_sig = get_stock_money_signals(
                    stock['code'], stock.get('name', ''), money_overview)
                if money_sig['score_delta'] != 0:
                    stock['score'] += money_sig['score_delta']
                    stock['money_reasons'] = money_sig['reasons']
                    stock['northbound_hold'] = money_sig.get('northbound_hold', False)
                    stock['institution_buy'] = money_sig.get('institution_buy', False)
                    print(f"    {stock.get('name','')}({stock['code']}): "
                          f"资金面{'+' if money_sig['score_delta']>=0 else ''}{money_sig['score_delta']}分")
            ranked = sorted(ranked, key=lambda x: -x['score'])
        except Exception as e:
            print(f"  ⚠️ 资金面信号叠加失败: {e}")

    # === 动态分数门槛: 根据近期胜率+连亏情况自动提高门槛 ===
    score_threshold = get_dynamic_score_threshold(regime=regime, loss_streak=loss_streak)
    ranked = [s for s in ranked if s['score'] >= score_threshold]
    print(f"  🎯 动态分数门槛: {score_threshold}分, 通过{len(ranked)}只")

    # === 止损黑名单: 近期止损过的股票不再买回 ===
    blacklist = get_stop_loss_blacklist()
    if blacklist:
        before = len(ranked)
        ranked = [s for s in ranked if s['code'] not in blacklist]
        blocked = before - len(ranked)
        if blocked > 0:
            print(f"  🚫 止损黑名单过滤: 排除{blocked}只近期止损股")

    # === 市场宽度检查: 普跌行情进一步提高门槛 ===
    breadth_info = {}
    try:
        from market_regime import get_market_breadth
        breadth_info = get_market_breadth()
        breadth_sig = breadth_info.get('breadth_signal', 'neutral')
        print(f"  📊 市场宽度: 涨{breadth_info.get('advance',0)}跌{breadth_info.get('decline',0)} "
              f"({breadth_info.get('breadth_ratio',0.5):.1%}) → {breadth_sig}")
        if breadth_sig == 'very_weak':
            # 普跌行情，只保留最强的2只
            ranked = ranked[:2]
            print(f"  ⚠️ 市场普跌，候选缩减至{len(ranked)}只")
        elif breadth_sig == 'weak':
            ranked = ranked[:4]
    except Exception as e:
        print(f"  ⚠️ 市场宽度检查失败: {e}")

    # 过滤
    tradeable = filter_tradeable(ranked)

    return {
        'candidates': tradeable,
        'news_signals': news_signals,
        'money_overview': money_overview,
        'breadth': breadth_info,
        'stats': {
            'momentum_count': len(momentum),
            'money_flow_count': len(money),
            'strong_count': len(strong),
            'institution_count': len(institution),
            'news_count': len(news_candidates),
            'money_data_count': len(money_candidates),
            'total_signals': len(all_candidates),
            'final_count': len(tradeable),
            'money_flow_score': money_overview.get('money_flow_score', 0) if money_overview else 0,
            'money_flow_label': money_overview.get('money_flow_label', '') if money_overview else '',
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
