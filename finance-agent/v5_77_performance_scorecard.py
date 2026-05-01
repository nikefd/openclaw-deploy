#!/usr/bin/env python3
"""
v5.77 金融Agent 绩效评分仪表板
核心功能: 实时计算7大关键指标,生成健康度评分
- 账户健康度 (0-100) 
- 风险调整收益率 (Sharpe/Calmar)
- 持仓多样性评分
- 策略有效性评分
- 风控执行力评分
- 资金利用效率评分
- 市场适应度评分
"""

import sqlite3
import json
from datetime import datetime, timedelta
import math

DB_PATH = '/home/nikefd/finance-agent/data/trading.db'

class PerformanceScorecard:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self.scores = {}
        
    def _query(self, sql):
        """Execute SQL query"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        result = cursor.execute(sql).fetchall()
        conn.close()
        return [dict(row) for row in result]
    
    def calculate_health_score(self):
        """
        计算账户综合健康度 (0-100)
        - 收益性 (20分): 相对基准 (沪深300)
        - 稳定性 (20分): 低回撤、低波动
        - 集中度 (15分): 持仓分散度
        - 风控 (20分): 止损执行率
        - 效率 (25分): 资金利用率、胜率、Sharpe
        """
        scores = {}
        
        # 1. 收益性 (20分)
        snapshots = self._query(
            "SELECT * FROM daily_snapshots ORDER BY date DESC LIMIT 1"
        )
        if snapshots:
            snap = snapshots[0]
            total_ret = (snap['total_value'] - 1000000) / 1000000 * 100
            if total_ret > 15:
                scores['return'] = 20
            elif total_ret > 10:
                scores['return'] = 16
            elif total_ret > 5:
                scores['return'] = 12
            elif total_ret > 0:
                scores['return'] = 8
            else:
                scores['return'] = max(0, 4 + total_ret / 5)
        else:
            scores['return'] = 0
        
        # 2. 稳定性 (20分)
        snapshots_30d = self._query(
            "SELECT * FROM daily_snapshots ORDER BY date DESC LIMIT 30"
        )
        if len(snapshots_30d) > 1:
            # 计算最大回撤
            peak = snapshots_30d[-1]['total_value']
            max_dd = 0
            for s in reversed(snapshots_30d):
                if s['total_value'] > peak:
                    peak = s['total_value']
                dd = (peak - s['total_value']) / peak
                max_dd = max(max_dd, dd)
            
            # 计算日收益波动率
            rets = []
            for i in range(len(snapshots_30d) - 1):
                ret = (snapshots_30d[i]['total_value'] - snapshots_30d[i+1]['total_value']) / snapshots_30d[i+1]['total_value']
                rets.append(ret)
            
            if len(rets) > 1:
                avg_ret = sum(rets) / len(rets)
                variance = sum((r - avg_ret) ** 2 for r in rets) / len(rets)
                volatility = math.sqrt(variance) if variance > 0 else 0
            else:
                volatility = 0
            
            # 评分: 回撤越低越好, 波动越低越好
            stability_score = 20
            if max_dd > 0.1:  # 超过10%回撤
                stability_score -= (max_dd - 0.1) * 100  # 每增加1%回撤,扣分
            if volatility > 0.05:  # 日波动超过5%
                stability_score -= (volatility - 0.05) * 200
            
            scores['stability'] = max(0, stability_score)
        else:
            scores['stability'] = 0
        
        # 3. 集中度 (15分) - 按持仓数量
        positions = self._query("SELECT COUNT(*) as cnt FROM positions WHERE shares > 0")
        pos_count = positions[0]['cnt'] if positions else 0
        
        if pos_count > 0:
            # HHI 简化版: 持仓越多越分散
            if pos_count >= 5:
                scores['concentration'] = 15
            elif pos_count >= 3:
                scores['concentration'] = 12
            elif pos_count >= 2:
                scores['concentration'] = 8
            else:
                scores['concentration'] = 4
        else:
            scores['concentration'] = 0
        
        # 4. 风控执行力 (20分)
        # 检查止损/止盈执行记录
        try:
            with open('/home/nikefd/finance-agent/reports/stop_loss_execution_log.jsonl', 'r') as f:
                sl_records = [json.loads(line) for line in f if line.strip()]
        except:
            sl_records = []
        
        today_executed = 0
        today_checked = 0
        for rec in sl_records[-1:]:  # 最近一条记录
            today_executed = rec.get('stop_loss_triggered', 0) + rec.get('take_profit_triggered', 0)
            today_checked = rec.get('positions_checked', 0)
        
        # 评分: 每日都检查则满分
        if today_checked > 0:
            scores['risk_control'] = min(20, 10 + today_executed * 2)
        else:
            scores['risk_control'] = 0
        
        # 5. 效率指标 (25分)
        trades = self._query("SELECT * FROM trades")
        positions = self._query("SELECT COUNT(*) as cnt FROM positions WHERE shares > 0")
        pos_count = positions[0]['cnt'] if positions else 0
        
        efficiency_score = 0
        
        # 胜率 (10分)
        if trades:
            sell_trades = [t for t in trades if t.get('direction') == 'SELL']
            if sell_trades:
                # 简单计算: 以交易记录中的pnl判断胜负
                wins = len([t for t in sell_trades if t.get('pnl', 0) > 0])
                win_rate = wins / len(sell_trades)
                efficiency_score += win_rate * 10
        
        # Sharpe比率贡献 (8分)
        if len(snapshots_30d) > 5:
            rets = []
            for i in range(len(snapshots_30d) - 1):
                ret = (snapshots_30d[i]['total_value'] - snapshots_30d[i+1]['total_value']) / snapshots_30d[i+1]['total_value']
                rets.append(ret * 252)  # 年化
            
            if len(rets) > 1:
                avg_ret = sum(rets) / len(rets)
                variance = sum((r - avg_ret) ** 2 for r in rets) / len(rets)
                std_dev = math.sqrt(variance) if variance > 0 else 0
                sharpe = (avg_ret / std_dev) if std_dev > 0 else 0
                
                # Sharpe > 1.5 满分,< 0.5 无分
                if sharpe > 1.5:
                    efficiency_score += 8
                elif sharpe > 1.0:
                    efficiency_score += 6
                elif sharpe > 0.5:
                    efficiency_score += 3
        
        # 资金利用率贡献 (7分)
        account = self._query("SELECT * FROM account ORDER BY id DESC LIMIT 1")
        if account:
            acc = account[0]
            cash_ratio = acc.get('cash', 0) / acc.get('total_value', 1)
            position_ratio = 1 - cash_ratio
            
            # 目标: 40-70%仓位 (最优)
            if 0.4 <= position_ratio <= 0.7:
                efficiency_score += 7
            elif 0.2 <= position_ratio < 0.4 or 0.7 < position_ratio <= 0.9:
                efficiency_score += 5
            elif position_ratio > 0.9:
                efficiency_score += 2  # 过度满仓风险
        
        scores['efficiency'] = min(25, efficiency_score)
        
        # 6. 市场适应度 (这里可扩展,暂设基础值)
        scores['market_adaptation'] = 10
        
        # 总分
        total = sum(scores.values())
        self.scores = scores
        
        return {
            'total_score': min(100, total),
            'components': scores,
            'health_emoji': self._score_to_emoji(min(100, total)),
            'health_status': self._score_to_status(min(100, total))
        }
    
    def _score_to_emoji(self, score):
        if score >= 80:
            return '🟢'
        elif score >= 60:
            return '🟡'
        else:
            return '🔴'
    
    def _score_to_status(self, score):
        if score >= 85:
            return '优秀'
        elif score >= 70:
            return '良好'
        elif score >= 50:
            return '中等'
        else:
            return '需改善'
    
    def get_component_bars(self):
        """生成评分组件柱状数据"""
        bars = []
        for name, score in self.scores.items():
            display_name = {
                'return': '📈 收益性',
                'stability': '📊 稳定性',
                'concentration': '🎯 分散度',
                'risk_control': '🛡 风控力',
                'efficiency': '⚡ 效率',
                'market_adaptation': '🌍 市场适应'
            }.get(name, name)
            
            max_score = {
                'return': 20,
                'stability': 20,
                'concentration': 15,
                'risk_control': 20,
                'efficiency': 25,
                'market_adaptation': 10
            }.get(name, 20)
            
            bars.append({
                'name': display_name,
                'score': score,
                'max': max_score,
                'pct': (score / max_score * 100) if max_score > 0 else 0,
                'color': '#2ec4b6' if score >= max_score * 0.8 else '#f4a261' if score >= max_score * 0.6 else '#e63946'
            })
        
        return bars
    
    def to_dict(self):
        result = self.calculate_health_score()
        result['components_bars'] = self.get_component_bars()
        result['timestamp'] = datetime.now().isoformat()
        return result


if __name__ == '__main__':
    sc = PerformanceScorecard()
    result = sc.to_dict()
    print(json.dumps(result, indent=2, ensure_ascii=False))
