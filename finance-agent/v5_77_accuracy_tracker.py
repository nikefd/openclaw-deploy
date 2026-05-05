"""
v5.77 历史推荐准确率追踪器
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【核心价值】
追踪每日推荐的实际表现，计算：
  • 命中率 (推荐后涨幅>3% 的占比)
  • 平均超额收益 (vs 沪深300)
  • 30/60/90天滚动统计
  • 按赛道/策略分解

【数据源】
  • daily_runner.py 的推荐记录 (performance_tracker)
  • 实时行情数据 (data_collector)
  • 沪深300基准 (akshare)

【计算方法】
1. 读取performance_tracker的推荐记录
2. 对每条推荐，查询当前价格和历史价格
3. 计算 (当前价-推荐价) / 推荐价 = 超额收益%
4. 统计30/60/90天内的命中率、平均收益、Sharpe比
"""

import json
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import akshare as ak

from config import DB_PATH


# =================== v5.77 准确率追踪常量 ===================

# 命中标准
ACCURACY_HIT_THRESHOLD = 0.03  # 涨幅>3% 算命中
ACCURACY_WIN_THRESHOLD = 0.01  # 涨幅>1% 算赢
ACCURACY_LOSS_THRESHOLD = -0.05  # 跌幅<-5% 算亏损

# 统计周期
ACCURACY_TRACKING_PERIODS = [30, 60, 90]  # 天数
ACCURACY_MIN_SAMPLE_SIZE = 5  # 最少样本数


# =================== 核心类 ===================

class AccuracyTracker:
    """推荐准确率追踪"""
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
    
    def get_recommendations(
        self,
        days_back: int = 90,
        min_entry_quality: int = 0
    ) -> List[Dict]:
        """
        读取历史推荐记录
        
        从performance_tracker表读取，返回:
        [
            {
                'id': 推荐ID,
                'code': 股票代码,
                'name': 股票名称,
                'date': 推荐日期 (YYYY-MM-DD),
                'recommended_price': 推荐时价格,
                'sector': 赛道,
                'strategy': 策略,
                'entry_quality': 入场质量评分,
                'reason': 推荐理由,
                'status': 推荐状态 (open/closed/sold),
            }
        ]
        """
        try:
            cutoff_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
            
            query = """
            SELECT 
                id, code, name, 
                COALESCE(date, DATE('now')) as date,
                COALESCE(entry_price, 0) as recommended_price,
                sector, 
                COALESCE(strategy, 'multi_strategy') as strategy,
                COALESCE(entry_quality, 0) as entry_quality,
                reason, status
            FROM recommendations
            WHERE date >= ? AND entry_quality >= ?
            ORDER BY date DESC
            """
            
            self.cursor.execute(query, (cutoff_date, min_entry_quality))
            rows = self.cursor.fetchall()
            
            results = []
            for row in rows:
                results.append({
                    'id': row[0],
                    'code': row[1],
                    'name': row[2],
                    'date': row[3],
                    'recommended_price': float(row[4]),
                    'sector': row[5],
                    'strategy': row[6],
                    'entry_quality': int(row[7]),
                    'reason': row[8],
                    'status': row[9],
                })
            
            return results
        except Exception as e:
            print(f"  ⚠️ 读取推荐记录失败: {e}")
            return []
    
    def calculate_recommendation_outcome(
        self,
        recommendation: Dict,
        current_date: Optional[str] = None
    ) -> Dict:
        """
        计算单条推荐的实际表现
        
        Args:
            recommendation: 推荐记录 (来自get_recommendations)
            current_date: 计算截止日期，None=今天
        
        Returns:
            {
                'code': 代码,
                'name': 名称,
                'rec_date': 推荐日期,
                'rec_price': 推荐价,
                'current_price': 当前价,
                'return_pct': 收益率,
                'days_held': 持仓天数,
                'hit': 是否命中 (>3%),
                'win': 是否盈利 (>1%),
                'loss': 是否亏损 (<-5%),
                'status': '命中'/'盈利'/'小亏'/'大亏',
            }
        """
        
        try:
            code = recommendation['code']
            name = recommendation['name']
            rec_date = recommendation['date']
            rec_price = recommendation['recommended_price']
            
            if rec_price <= 0:
                return {'code': code, 'status': 'invalid_price'}
            
            # 获取当前价格
            current_date = current_date or datetime.now().strftime('%Y-%m-%d')
            try:
                # 尝试从实时行情获取
                from data_collector import get_realtime_quotes
                quotes = get_realtime_quotes([code])
                current_price = quotes.get(code, {}).get('current_price', 0) if quotes else 0
                
                # fallback: 从历史K线获取最新价
                if current_price <= 0:
                    from data_collector import get_stock_daily
                    df = get_stock_daily(code, 10)
                    if df is not None and not df.empty:
                        current_price = float(df.iloc[-1]['close'])
                
                if current_price <= 0:
                    return {'code': code, 'status': 'price_unavailable'}
            
            except Exception as e:
                print(f"  ⚠️ 获取{code}当前价失败: {e}")
                return {'code': code, 'status': 'price_fetch_error'}
            
            # 计算收益率和持仓天数
            return_pct = (current_price - rec_price) / rec_price
            
            try:
                from trading_engine import _trading_days_since
                days_held = _trading_days_since(rec_date)
            except:
                days_held = (datetime.strptime(current_date, '%Y-%m-%d') -
                           datetime.strptime(rec_date, '%Y-%m-%d')).days
            
            # 判定状态
            hit = return_pct > ACCURACY_HIT_THRESHOLD  # >3%
            win = return_pct > ACCURACY_WIN_THRESHOLD  # >1%
            loss = return_pct < ACCURACY_LOSS_THRESHOLD  # <-5%
            
            if hit:
                status = '✅ 命中'
            elif win:
                status = '✓ 盈利'
            elif loss:
                status = '❌ 大亏'
            else:
                status = '- 小亏'
            
            return {
                'code': code,
                'name': name,
                'sector': recommendation.get('sector', ''),
                'strategy': recommendation.get('strategy', ''),
                'entry_quality': recommendation.get('entry_quality', 0),
                'rec_date': rec_date,
                'rec_price': rec_price,
                'current_price': current_price,
                'return_pct': return_pct,
                'days_held': days_held,
                'hit': hit,
                'win': win,
                'loss': loss,
                'status': status,
            }
        
        except Exception as e:
            print(f"  ⚠️ 计算推荐表现失败 {recommendation.get('code', '')}: {e}")
            return {'code': recommendation.get('code'), 'status': 'calculation_error'}
    
    def analyze_accuracy_period(
        self,
        days_back: int = 30
    ) -> Dict:
        """
        分析指定周期的准确率
        
        Args:
            days_back: 回溯天数 (30/60/90)
        
        Returns:
            {
                'period_days': 30,
                'sample_size': 推荐数量,
                'hit_count': 命中数,
                'win_count': 盈利数,
                'loss_count': 大亏数,
                'hit_rate_pct': 命中率%,
                'win_rate_pct': 盈利率%,
                'loss_rate_pct': 大亏率%,
                'avg_return_pct': 平均收益%,
                'median_return_pct': 中位数收益%,
                'sharpe_ratio': Sharpe比率,
                'max_return_pct': 最高收益%,
                'min_return_pct': 最低收益%,
                'sector_breakdown': {赛道: 命中数/总数},
                'strategy_breakdown': {策略: 命中数/总数},
                'status': '数据充分'/'样本不足',
            }
        """
        
        recs = self.get_recommendations(days_back=days_back)
        if not recs:
            return {'period_days': days_back, 'status': '无推荐数据'}
        
        outcomes = []
        for rec in recs:
            outcome = self.calculate_recommendation_outcome(rec)
            if 'return_pct' in outcome:  # 有效结果
                outcomes.append(outcome)
        
        if len(outcomes) < ACCURACY_MIN_SAMPLE_SIZE:
            return {
                'period_days': days_back,
                'sample_size': len(outcomes),
                'status': f'样本不足 (需要{ACCURACY_MIN_SAMPLE_SIZE}+)'
            }
        
        # 计算统计指标
        returns = [o['return_pct'] for o in outcomes]
        hits = [o for o in outcomes if o['hit']]
        wins = [o for o in outcomes if o['win']]
        losses = [o for o in outcomes if o['loss']]
        
        import numpy as np
        
        avg_return = np.mean(returns)
        median_return = np.median(returns)
        std_return = np.std(returns)
        sharpe_ratio = avg_return / std_return if std_return > 0 else 0
        
        # 赛道分解
        sector_breakdown = {}
        for o in outcomes:
            sector = o.get('sector', '其他')
            if sector not in sector_breakdown:
                sector_breakdown[sector] = {'hit': 0, 'total': 0}
            sector_breakdown[sector]['total'] += 1
            if o['hit']:
                sector_breakdown[sector]['hit'] += 1
        
        sector_breakdown = {
            k: f"{v['hit']}/{v['total']} ({v['hit']/v['total']*100:.1f}%)"
            for k, v in sector_breakdown.items()
        }
        
        # 策略分解
        strategy_breakdown = {}
        for o in outcomes:
            strategy = o.get('strategy', '其他')
            if strategy not in strategy_breakdown:
                strategy_breakdown[strategy] = {'hit': 0, 'total': 0}
            strategy_breakdown[strategy]['total'] += 1
            if o['hit']:
                strategy_breakdown[strategy]['hit'] += 1
        
        strategy_breakdown = {
            k: f"{v['hit']}/{v['total']} ({v['hit']/v['total']*100:.1f}%)"
            for k, v in strategy_breakdown.items()
        }
        
        return {
            'period_days': days_back,
            'sample_size': len(outcomes),
            'hit_count': len(hits),
            'win_count': len(wins),
            'loss_count': len(losses),
            'hit_rate_pct': len(hits) / len(outcomes) * 100,
            'win_rate_pct': len(wins) / len(outcomes) * 100,
            'loss_rate_pct': len(losses) / len(outcomes) * 100,
            'avg_return_pct': avg_return * 100,
            'median_return_pct': median_return * 100,
            'sharpe_ratio': sharpe_ratio,
            'max_return_pct': max(returns) * 100,
            'min_return_pct': min(returns) * 100,
            'sector_breakdown': sector_breakdown,
            'strategy_breakdown': strategy_breakdown,
            'status': '数据充分',
        }
    
    def generate_accuracy_report(self) -> Dict:
        """
        生成完整的准确率报告
        
        包含30/60/90天的分析
        """
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'periods': {},
            'summary': '',
        }
        
        for period in ACCURACY_TRACKING_PERIODS:
            report['periods'][period] = self.analyze_accuracy_period(days_back=period)
        
        # 生成文字总结
        latest = report['periods'].get(30, {})
        if latest.get('status') == '数据充分':
            summary = (
                f"最近30天: {latest.get('sample_size', 0)}条推荐 | "
                f"命中率{latest.get('hit_rate_pct', 0):.1f}% | "
                f"平均收益{latest.get('avg_return_pct', 0):.1f}% | "
                f"Sharpe {latest.get('sharpe_ratio', 0):.2f}"
            )
            report['summary'] = summary
        
        return report
    
    def close(self):
        """关闭数据库连接"""
        try:
            self.conn.close()
        except:
            pass


# =================== 辅助函数 ===================

def get_benchmark_return(
    start_date: str,
    end_date: str = None
) -> float:
    """
    获取沪深300基准收益率
    
    Args:
        start_date: 开始日期 (YYYY-MM-DD)
        end_date: 结束日期，None=今天
    
    Returns: 收益率 (e.g., 0.05 = 5%)
    """
    try:
        end_date = end_date or datetime.now().strftime('%Y-%m-%d')
        
        # 使用hs300作为基准
        data = ak.index_daily(symbol='sh000300', start_date=start_date, end_date=end_date)
        
        if data is None or data.empty:
            return 0
        
        start_price = float(data.iloc[0]['open'])
        end_price = float(data.iloc[-1]['close'])
        
        return (end_price - start_price) / start_price
    
    except Exception as e:
        print(f"  ⚠️ 获取基准收益率失败: {e}")
        return 0


def export_accuracy_report_json(
    report: Dict,
    output_path: str = '/home/nikefd/finance-agent/data/accuracy_report.json'
) -> str:
    """导出准确率报告为JSON"""
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2, default=str)
        return output_path
    except Exception as e:
        print(f"  ⚠️ 导出报告失败: {e}")
        return ""


# =================== 测试 ===================

if __name__ == '__main__':
    print("=" * 80)
    print("【v5.77 准确率追踪器测试】")
    print("=" * 80)
    
    tracker = AccuracyTracker()
    
    print("\n✅ 读取最近30天推荐...")
    recs = tracker.get_recommendations(days_back=30, min_entry_quality=40)
    print(f"  找到 {len(recs)} 条推荐")
    
    if recs:
        print("\n✅ 计算推荐表现...")
        outcomes = []
        for rec in recs[:3]:  # 只处理前3个示例
            outcome = tracker.calculate_recommendation_outcome(rec)
            outcomes.append(outcome)
            print(f"  {outcome.get('name', '')} ({outcome.get('code', '')}): {outcome.get('status', '')}")
    
    print("\n✅ 分析30天准确率...")
    analysis_30 = tracker.analyze_accuracy_period(days_back=30)
    print(f"  样本数: {analysis_30.get('sample_size', 0)}")
    print(f"  命中率: {analysis_30.get('hit_rate_pct', 0):.1f}%")
    print(f"  平均收益: {analysis_30.get('avg_return_pct', 0):.1f}%")
    print(f"  Sharpe: {analysis_30.get('sharpe_ratio', 0):.2f}")
    
    print("\n✅ 生成完整报告...")
    report = tracker.generate_accuracy_report()
    print(f"  报告时间: {report['timestamp']}")
    print(f"  总结: {report['summary']}")
    
    print("\n✅ 导出为JSON...")
    export_accuracy_report_json(report)
    print(f"  已导出到 /home/nikefd/finance-agent/data/accuracy_report.json")
    
    tracker.close()
    
    print("\n" + "=" * 80)
    print("✅ 准确率追踪器测试完成")
    print("=" * 80)
