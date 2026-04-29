"""
v5.75: 实盘准确率分析 + 回撤控制强化

【目标】
1. 实盘准确率分析: 对比历史推荐vs实际收益，找出打败算法的选股模式
   - 统计维度: 入场质量分数 vs 实际收益关联度
   - 找出高准确率模式 (胜率>60%, Sharpe>1.0)
   - 拉黑低准确率模式 (胜率<40%)

2. 回撤控制强化: 科技赛道虽然好但回撤4.08%，加强ATR止损精度
   - ATR周期: 14天 (已有,保持)
   - 高波动处理: ATR*1.2放宽止损
   - 低波动处理: ATR*0.8收紧止损
   - 目标MaxDD: 3.2% (从4.08% → -22%)
"""

import json
import os
from datetime import datetime, timedelta
from collections import defaultdict
import statistics


# =================== 实盘准确率分析 ===================

class BacktestAccuracyAnalyzer:
    """对比回测vs实盘，找出高准确率选股模式"""
    
    def __init__(self, backtest_log_path: str = None, trade_log_path: str = None):
        """
        Args:
            backtest_log_path: 回测历史日志 (JSON)
            trade_log_path: 实盘交易日志 (JSONL)
        """
        self.backtest_log_path = backtest_log_path or "/home/nikefd/finance-agent/reports/backtest_history.json"
        self.trade_log_path = trade_log_path or "/home/nikefd/finance-agent/reports/trades.jsonl"
        
        self.backtest_records = []
        self.trade_records = []
        self.accuracy_stats = defaultdict(list)
        self.pattern_analysis = {}
    
    def load_backtest_records(self) -> int:
        """加载回测历史记录"""
        
        if not os.path.exists(self.backtest_log_path):
            print(f"  ⚠️  回测日志不存在: {self.backtest_log_path}")
            return 0
        
        try:
            with open(self.backtest_log_path, 'r') as f:
                data = json.load(f)
                self.backtest_records = data if isinstance(data, list) else [data]
            print(f"  ✅ 加载回测记录: {len(self.backtest_records)}条")
            return len(self.backtest_records)
        except Exception as e:
            print(f"  ❌ 加载回测记录失败: {e}")
            return 0
    
    def load_trade_records(self) -> int:
        """加载实盘交易记录 (JSONL格式)"""
        
        if not os.path.exists(self.trade_log_path):
            print(f"  ⚠️  交易日志不存在: {self.trade_log_path}")
            return 0
        
        try:
            with open(self.trade_log_path, 'r') as f:
                for line in f:
                    if line.strip():
                        self.trade_records.append(json.loads(line))
            print(f"  ✅ 加载交易记录: {len(self.trade_records)}条")
            return len(self.trade_records)
        except Exception as e:
            print(f"  ❌ 加载交易记录失败: {e}")
            return 0
    
    def analyze_entry_quality_vs_profit(self, window_days=30) -> dict:
        """分析入场质量评分与实际收益的关联度
        
        Args:
            window_days: 统计窗口 (最近N天)
        
        Returns: {quality_score_ranges: [...], accuracy_stats: {...}}
        """
        
        # 按入场质量分组统计
        quality_buckets = {
            'excellent': {'range': (80, 100), 'trades': [], 'win_count': 0, 'profit_total': 0},
            'good': {'range': (60, 80), 'trades': [], 'win_count': 0, 'profit_total': 0},
            'moderate': {'range': (40, 60), 'trades': [], 'win_count': 0, 'profit_total': 0},
            'poor': {'range': (20, 40), 'trades': [], 'win_count': 0, 'profit_total': 0},
            'very_poor': {'range': (0, 20), 'trades': [], 'win_count': 0, 'profit_total': 0},
        }
        
        for trade in self.trade_records:
            entry_date = datetime.fromisoformat(trade.get('entry_date', ''))
            if (datetime.now() - entry_date).days > window_days:
                continue
            
            entry_quality = trade.get('entry_quality_score', 50)
            profit_pct = trade.get('profit_pct', 0)
            status = trade.get('status', 'closed')
            
            # 分类到对应的质量等级
            for bucket_name, bucket in quality_buckets.items():
                min_val, max_val = bucket['range']
                if min_val <= entry_quality < max_val:
                    bucket['trades'].append(trade)
                    if profit_pct > 0 or status == 'win':
                        bucket['win_count'] += 1
                    bucket['profit_total'] += profit_pct
                    break
        
        # 计算每个等级的准确率
        stats = {}
        for bucket_name, bucket in quality_buckets.items():
            trade_count = len(bucket['trades'])
            if trade_count > 0:
                win_rate = bucket['win_count'] / trade_count
                avg_profit = bucket['profit_total'] / trade_count
                stats[bucket_name] = {
                    'quality_range': f"{bucket['range'][0]}-{bucket['range'][1]}",
                    'trade_count': trade_count,
                    'win_count': bucket['win_count'],
                    'win_rate': win_rate,
                    'avg_profit_pct': avg_profit,
                    'total_profit_pct': bucket['profit_total'],
                    'sharpe_approx': win_rate * avg_profit / (0.01 + abs(avg_profit))  # 粗略Sharpe
                }
        
        return stats
    
    def identify_high_accuracy_patterns(self, min_win_rate=0.60, min_sharpe=1.0) -> list:
        """识别高准确率模式
        
        返回: [(pattern_name, win_rate, sharpe, trade_count), ...]
        """
        
        patterns = []
        
        quality_stats = self.analyze_entry_quality_vs_profit()
        
        for pattern_name, stats in quality_stats.items():
            win_rate = stats.get('win_rate', 0)
            sharpe = stats.get('sharpe_approx', 0)
            trade_count = stats.get('trade_count', 0)
            
            if win_rate >= min_win_rate and sharpe >= min_sharpe and trade_count >= 5:
                patterns.append({
                    'pattern': pattern_name,
                    'quality_range': stats['quality_range'],
                    'win_rate': win_rate,
                    'sharpe': sharpe,
                    'trade_count': trade_count,
                    'avg_profit': stats['avg_profit_pct'],
                    'description': f"{pattern_name}模式: {win_rate:.1%}胜率, {sharpe:.2f}Sharpe, {trade_count}笔"
                })
        
        return sorted(patterns, key=lambda x: -x['sharpe'])
    
    def identify_low_accuracy_patterns(self, max_win_rate=0.40) -> list:
        """识别低准确率模式 (待拉黑)
        
        返回: [(pattern_name, win_rate, trade_count), ...]
        """
        
        patterns = []
        
        quality_stats = self.analyze_entry_quality_vs_profit()
        
        for pattern_name, stats in quality_stats.items():
            win_rate = stats.get('win_rate', 0)
            trade_count = stats.get('trade_count', 0)
            
            if win_rate <= max_win_rate and trade_count >= 3:
                patterns.append({
                    'pattern': pattern_name,
                    'quality_range': stats['quality_range'],
                    'win_rate': win_rate,
                    'trade_count': trade_count,
                    'description': f"{pattern_name}模式: {win_rate:.1%}胜率, {trade_count}笔 [需拉黑]"
                })
        
        return patterns
    
    def generate_report(self) -> str:
        """生成实盘准确率分析报告"""
        
        report_lines = [
            "=" * 70,
            "📊 实盘准确率分析报告 (v5.75)",
            "=" * 70,
            f"分析时间: {datetime.now().isoformat()}",
            f"回测记录: {len(self.backtest_records)}条",
            f"交易记录: {len(self.trade_records)}条",
            "",
        ]
        
        # 1. 按质量评分统计
        quality_stats = self.analyze_entry_quality_vs_profit()
        report_lines.append("【1】按入场质量评分统计:")
        report_lines.append("")
        
        for quality_level, stats in sorted(quality_stats.items()):
            report_lines.append(f"  {quality_level}:")
            report_lines.append(f"    质量范围: {stats['quality_range']}")
            report_lines.append(f"    交易笔数: {stats['trade_count']}")
            report_lines.append(f"    胜率: {stats['win_rate']:.1%}")
            report_lines.append(f"    平均收益: {stats['avg_profit_pct']:+.2%}")
            report_lines.append(f"    Sharpe(粗略): {stats['sharpe_approx']:.2f}")
            report_lines.append("")
        
        # 2. 高准确率模式
        high_acc_patterns = self.identify_high_accuracy_patterns()
        report_lines.append("【2】高准确率模式 (胜率≥60%, Sharpe≥1.0):")
        report_lines.append("")
        
        if high_acc_patterns:
            for pattern in high_acc_patterns:
                report_lines.append(f"  ✅ {pattern['pattern']}:")
                report_lines.append(f"     {pattern['description']}")
                report_lines.append(f"     质量范围: {pattern['quality_range']}")
                report_lines.append("")
        else:
            report_lines.append("  (暂无高准确率模式,需积累更多样本)")
            report_lines.append("")
        
        # 3. 低准确率模式(待拉黑)
        low_acc_patterns = self.identify_low_accuracy_patterns()
        report_lines.append("【3】低准确率模式 (胜率≤40%, 建议拉黑):")
        report_lines.append("")
        
        if low_acc_patterns:
            for pattern in low_acc_patterns:
                report_lines.append(f"  ❌ {pattern['pattern']}:")
                report_lines.append(f"     {pattern['description']}")
                report_lines.append("")
        else:
            report_lines.append("  (暂无低准确率模式)")
            report_lines.append("")
        
        # 4. 建议
        report_lines.append("【4】建议:")
        report_lines.append("")
        report_lines.append("  • 优先使用高准确率模式选股")
        report_lines.append("  • 拉黑低准确率模式")
        report_lines.append("  • 继续积累样本数据,完善模型")
        
        return "\n".join(report_lines)


# =================== 回撤控制强化 (ATR动态止损) ===================

class ATRDrawdownControl:
    """基于ATR的动态止损和回撤控制"""
    
    def __init__(self, target_max_dd=0.032):
        """
        Args:
            target_max_dd: 目标最大回撤 (3.2%)
        """
        self.target_max_dd = target_max_dd
        self.atr_period = 14
        self.positions = {}  # {code: {atr_value, entry_price, peak_price, stop_loss_line}}
    
    def calculate_atr(self, high_prices: list, low_prices: list, close_prices: list) -> float:
        """计算ATR (Average True Range)"""
        
        if len(close_prices) < self.atr_period:
            return 0
        
        tr_values = []
        for i in range(len(close_prices)):
            high = high_prices[i]
            low = low_prices[i]
            close_prev = close_prices[i-1] if i > 0 else low
            
            tr = max(
                high - low,
                abs(high - close_prev),
                abs(low - close_prev)
            )
            tr_values.append(tr)
        
        # SMA-based ATR
        atr = sum(tr_values[-self.atr_period:]) / self.atr_period
        return atr
    
    def get_stop_loss_line(self, entry_price: float, atr: float, volatility_ratio=1.0) -> float:
        """根据ATR和波动率计算止损线
        
        Args:
            entry_price: 入场价格
            atr: ATR值
            volatility_ratio: 波动率倍数
                - 高波动 (>3%): 1.2x (容忍更大回撤)
                - 正常 (1.5%-3%): 1.0x
                - 低波动 (<1.5%): 0.8x (快速止损)
        
        Returns: 止损价格
        """
        
        atr_adjusted = atr * volatility_ratio
        stop_loss = entry_price - atr_adjusted
        
        return stop_loss
    
    def estimate_volatility(self, close_prices: list, window=20) -> float:
        """估计股票波动率"""
        
        if len(close_prices) < window:
            return 0.02
        
        returns = []
        for i in range(1, len(close_prices)):
            ret = (close_prices[i] - close_prices[i-1]) / close_prices[i-1]
            returns.append(ret)
        
        # 取最近window天的标准差
        recent_returns = returns[-window:]
        volatility = statistics.stdev(recent_returns) if len(recent_returns) > 1 else 0
        
        return abs(volatility)
    
    def get_volatility_multiplier(self, volatility: float) -> float:
        """根据波动率获取ATR倍数"""
        
        if volatility > 0.03:  # >3% 高波动
            return 1.2
        elif volatility < 0.015:  # <1.5% 低波动
            return 0.8
        else:  # 1.5%-3% 正常
            return 1.0
    
    def update_position_stop_loss(self, code: str, current_price: float, atr: float, 
                                  volatility: float) -> dict:
        """更新持仓的止损线 (追踪止损)
        
        Returns: {code, current_stop_loss, trigger_stop_loss, recommendation}
        """
        
        if code not in self.positions:
            return {'status': 'not_tracked'}
        
        pos = self.positions[code]
        entry_price = pos['entry_price']
        peak_price = max(pos.get('peak_price', entry_price), current_price)
        
        # 更新峰值
        pos['peak_price'] = peak_price
        
        # 计算波动率倍数
        vol_multiplier = self.get_volatility_multiplier(volatility)
        
        # 计算新的止损线
        new_stop_loss = self.get_stop_loss_line(current_price, atr, vol_multiplier)
        
        # 追踪止损: 如果新止损线高于当前止损线,则提升止损线
        old_stop_loss = pos.get('stop_loss_line', entry_price - atr)
        final_stop_loss = max(new_stop_loss, old_stop_loss)
        
        pos['stop_loss_line'] = final_stop_loss
        pos['atr'] = atr
        
        # 判断是否触发止损
        trigger_stop_loss = current_price < final_stop_loss
        
        return {
            'code': code,
            'current_price': current_price,
            'current_stop_loss': final_stop_loss,
            'trigger_stop_loss': trigger_stop_loss,
            'atr': atr,
            'volatility': volatility,
            'vol_multiplier': vol_multiplier,
            'peak_price': peak_price,
            'drawdown_from_peak': (peak_price - current_price) / peak_price if peak_price > 0 else 0,
            'recommendation': 'STOP_LOSS' if trigger_stop_loss else 'HOLD'
        }
    
    def get_portfolio_max_dd_estimate(self, positions: dict, current_prices: dict) -> dict:
        """估计组合当前的最大回撤"""
        
        total_entry_value = 0
        total_peak_value = 0
        
        for code, pos in positions.items():
            current_price = current_prices.get(code, pos['entry_price'])
            entry_value = pos['entry_price'] * pos['shares']
            peak_price = pos.get('peak_price', pos['entry_price'])
            peak_value = peak_price * pos['shares']
            
            total_entry_value += entry_value
            total_peak_value += peak_value
        
        current_total_value = sum(current_prices.get(c, p['entry_price']) * p['shares'] 
                                  for c, p in positions.items())
        
        max_dd = (total_peak_value - current_total_value) / total_peak_value if total_peak_value > 0 else 0
        
        return {
            'current_total_value': current_total_value,
            'peak_total_value': total_peak_value,
            'entry_total_value': total_entry_value,
            'max_dd': max_dd,
            'max_dd_pct': f"{max_dd:.2%}",
            'target_max_dd': f"{self.target_max_dd:.2%}",
            'status': 'OK' if max_dd <= self.target_max_dd else 'EXCEED'
        }


if __name__ == '__main__':
    # 测试实盘准确率分析
    print("v5.75 实盘准确率分析\n")
    
    analyzer = BacktestAccuracyAnalyzer()
    analyzer.load_backtest_records()
    analyzer.load_trade_records()
    
    # 如果没有实际数据，打印模拟报告
    if len(analyzer.trade_records) == 0:
        print("  ⚠️  暂无交易记录,生成演示报告\n")
    
    report = analyzer.generate_report()
    print(report)
    
    # 测试ATR控制
    print("\n" + "="*70)
    print("v5.75 ATR动态止损测试\n")
    
    atr_control = ATRDrawdownControl(target_max_dd=0.032)
    
    # 模拟数据
    high_prices = [100.5, 101.2, 102.0, 101.5, 102.5, 103.0]
    low_prices = [99.5, 100.2, 101.0, 100.5, 101.5, 102.0]
    close_prices = [100.0, 100.8, 101.5, 101.0, 102.0, 102.5]
    
    atr = atr_control.calculate_atr(high_prices, low_prices, close_prices)
    volatility = atr_control.estimate_volatility(close_prices)
    vol_mult = atr_control.get_volatility_multiplier(volatility)
    
    print(f"  ATR(14): {atr:.4f}")
    print(f"  波动率: {volatility:.2%}")
    print(f"  波动率倍数: {vol_mult}x")
    print(f"  建议止损线 (入场100): {atr_control.get_stop_loss_line(100, atr, vol_mult):.2f}")
    print(f"  ✅ 目标MaxDD: {atr_control.target_max_dd:.2%}")
