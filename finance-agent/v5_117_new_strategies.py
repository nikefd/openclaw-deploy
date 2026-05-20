"""
v5.117 晚间深度优化 - 新策略引擎 (无scipy依赖版本)
包含: 动量+情绪策略, 均线反转策略, 智能止损系统, 现代投资组合优化(简化版)
"""

import json
import math
from datetime import datetime, timedelta
from collections import defaultdict

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

from config import *

# ============================================================================
# 新增策略1: 动量+情绪组合 (MOMENTUM_SENTIMENT)
# ============================================================================

class MomentumSentimentStrategy:
    """
    结合价格动量和市场情绪的策略
    - 动量: 20天价格变化率
    - 情绪: RSI指标 (30=超卖/70=超买)
    - 权重: 动量70% + 情绪30%
    """
    
    def __init__(self, momentum_period=20, rsi_low=30, rsi_high=70):
        self.momentum_period = momentum_period
        self.rsi_low = rsi_low
        self.rsi_high = rsi_high
        self.name = "MOMENTUM_SENTIMENT"
    
    def calculate_momentum(self, closes):
        """计算动量 (最近20天的价格变化率)"""
        if len(closes) < self.momentum_period:
            return 0.0
        current = closes[-1]
        past = closes[-self.momentum_period]
        if past == 0:
            return 0.0
        return (current - past) / past * 100
    
    def calculate_rsi(self, closes, period=14):
        """计算RSI (相对强弱指标)"""
        if len(closes) < period + 1:
            return 50.0
        
        deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
        seed = deltas[:period]
        up = sum([x for x in seed if x > 0]) / period
        down = -sum([x for x in seed if x < 0]) / period
        
        rs = up / down if down != 0 else 1
        rsi = 100 - (100 / (1 + rs))
        
        for d in deltas[period:]:
            up = (up * (period - 1) + (d if d > 0 else 0)) / period
            down = (down * (period - 1) + (-d if d < 0 else 0)) / period
            rs = up / down if down != 0 else 1
            rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def score(self, closes, current_price=None):
        """
        计算综合得分 (0-100)
        - 动量强: 加分
        - RSI超卖 (<30): 加分 (反转机会)
        - RSI超买 (>70): 减分 (警告)
        """
        if not closes or len(closes) < self.momentum_period:
            return 50.0
        
        momentum = self.calculate_momentum(closes)
        rsi = self.calculate_rsi(closes)
        
        # 动量贡献 (-20%~+20% → 40~60分)
        momentum_score = 50 + (momentum / 5) * 5  # 归一化
        momentum_score = max(30, min(70, momentum_score))  # 限制在30-70
        
        # 情绪贡献 (RSI < 30 → 70分, RSI > 70 → 30分)
        if rsi < self.rsi_low:
            emotion_score = 70 + (self.rsi_low - rsi)  # <30时超到70-100
        elif rsi > self.rsi_high:
            emotion_score = 30 - (rsi - self.rsi_high)  # >70时降到0-30
        else:
            emotion_score = 50  # 正常区间
        emotion_score = max(20, min(80, emotion_score))
        
        # 加权平均: 动量70% + 情绪30%
        score = momentum_score * 0.7 + emotion_score * 0.3
        return score


# ============================================================================
# 新增策略2: 均线反转+波动率加权 (MA_REVERT_VOL)
# ============================================================================

class MARevertVolStrategy:
    """
    均线反转策略 + 波动率加权
    - 当价格偏离中期均线 (-2.5%~+2.5%) 时进场
    - 低波动率时增加权重 (相对安全)
    - 适合白马消费/金融赛道 (低波动, 稳定现金流)
    """
    
    def __init__(self, ma_period=120, deviation_pct=2.5, vol_period=20):
        self.ma_period = ma_period
        self.deviation_pct = deviation_pct
        self.vol_period = vol_period
        self.name = "MA_REVERT_VOL"
    
    def calculate_sma(self, closes, period):
        """计算简单移动平均线"""
        if len(closes) < period:
            return closes[-1] if closes else 0
        return sum(closes[-period:]) / period
    
    def calculate_volatility(self, closes, period):
        """计算波动率 (收益率标准差)"""
        if len(closes) < period + 1:
            return 0.01
        
        returns = [(closes[i] / closes[i-1] - 1) for i in range(len(closes) - period, len(closes))]
        mean_return = sum(returns) / len(returns)
        variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
        return math.sqrt(variance)
    
    def score(self, closes, current_price=None):
        """
        计算均线反转得分
        - 价格在MA ±2.5% 范围内: 高得分 (反转机会)
        - 偏离过大: 低得分 (有风险)
        - 低波动率加权
        """
        if not closes or len(closes) < self.ma_period:
            return 50.0
        
        current = closes[-1]
        ma = self.calculate_sma(closes, self.ma_period)
        
        if ma == 0:
            return 50.0
        
        # 价格偏离度
        deviation = abs(current - ma) / ma * 100
        
        # 基础得分 (偏离度越小越好)
        if deviation < self.deviation_pct:
            base_score = 70 + (self.deviation_pct - deviation) / self.deviation_pct * 20
        elif deviation < self.deviation_pct * 2:
            base_score = 50 - (deviation - self.deviation_pct) / self.deviation_pct * 20
        else:
            base_score = 30  # 严重偏离, 风险大
        
        base_score = max(20, min(80, base_score))
        
        # 波动率加权 (低波动率时提升, 高波动率时降低)
        volatility = self.calculate_volatility(closes, self.vol_period)
        vol_factor = 1 - min(volatility, 0.05) / 0.05 * 0.2  # 最多调整±20%
        
        final_score = base_score * vol_factor
        return max(20, min(80, final_score))


# ============================================================================
# 新增策略3: 隐含波动率套利 (IV_ARBITRAGE)  
# ============================================================================

class IVArbitrageStrategy:
    """
    隐含波动率套利策略
    - 买入被低估的IV (IV百分位 <30%)
    - 卖出被高估的IV (IV百分位 >70%)
    - 使用风险平价头寸大小
    - 适合高流动性蓝筹
    """
    
    def __init__(self, iv_lookback=252, percentile_low=30, percentile_high=70):
        self.iv_lookback = iv_lookback
        self.percentile_low = percentile_low
        self.percentile_high = percentile_high
        self.name = "IV_ARBITRAGE"
    
    def calculate_parkinson_vol(self, highs, lows, closes, period=20):
        """
        Parkinson波动率估计 (基于日内高低价)
        相比历史波动率, 对波动率突变更敏感
        """
        if len(highs) < period:
            return 0.01
        
        rs_sum = 0
        for i in range(len(highs) - period, len(highs)):
            h = highs[i]
            l = lows[i]
            if h > 0 and l > 0:
                r = math.log(h / l)
                rs_sum += r * r
        
        vol = math.sqrt(rs_sum / (4 * period * math.log(2)))
        return vol
    
    def calculate_iv_percentile(self, vols, current_vol):
        """计算当前波动率的百分位"""
        if not vols or current_vol is None:
            return 50.0
        
        sorted_vols = sorted(vols)
        position = sum(1 for v in sorted_vols if v <= current_vol)
        percentile = position / len(sorted_vols) * 100
        return percentile
    
    def score(self, highs, lows, closes, current_price=None):
        """
        计算IV套利得分
        - IV低估 (百分位<30): 高得分 (买入信号)
        - IV正常: 中等得分
        - IV高估 (百分位>70): 低得分 (卖出信号)
        """
        if not closes or len(closes) < self.iv_lookback:
            return 50.0
        
        # 计算历史波动率
        hist_vols = []
        for i in range(len(closes) - self.iv_lookback, len(closes) - 20):
            vol = self.calculate_parkinson_vol(
                highs[i:i+20], lows[i:i+20], closes[i:i+20], period=20
            )
            hist_vols.append(vol)
        
        current_vol = self.calculate_parkinson_vol(
            highs[-20:], lows[-20:], closes[-20:], period=20
        )
        
        if not hist_vols:
            return 50.0
        
        iv_percentile = self.calculate_iv_percentile(hist_vols, current_vol)
        
        # 根据百分位生成得分
        if iv_percentile < self.percentile_low:
            # IV被低估 - 买入信号
            score = 70 + (self.percentile_low - iv_percentile) / self.percentile_low * 20
        elif iv_percentile > self.percentile_high:
            # IV被高估 - 卖出信号
            score = 30 - (iv_percentile - self.percentile_high) / (100 - self.percentile_high) * 20
        else:
            # 正常区间
            score = 50
        
        return max(20, min(80, score))


# ============================================================================
# 智能组合优化模块 (Modern Portfolio Optimizer - 简化版)
# ============================================================================

class ModernPortfolioOptimizer:
    """
    使用现代投资组合理论 (MPT) 优化投资组合 (简化版, 无scipy)
    - 计算相关系数矩阵
    - 按Sharpe比贪心分配
    - 实现风险平价分配
    """
    
    def __init__(self, returns_series, risk_free_rate=0.03):
        """
        初始化优化器
        returns_series: dict {symbol: [returns...]}
        """
        self.returns = returns_series
        self.risk_free_rate = risk_free_rate
        self.n_assets = len(returns_series)
    
    def calculate_cov_matrix(self):
        """计算协方差矩阵 (简化版)"""
        symbols = list(self.returns.keys())
        
        if not HAS_NUMPY:
            # 不依赖numpy的简单实现
            cov_matrix = []
            for i, sym1 in enumerate(symbols):
                row = []
                for j, sym2 in enumerate(symbols):
                    if i == j:
                        # 方差
                        returns = self.returns[sym1]
                        mean = sum(returns) / len(returns)
                        var = sum((r - mean) ** 2 for r in returns) / len(returns)
                        row.append(var)
                    else:
                        # 协方差
                        r1 = self.returns[sym1]
                        r2 = self.returns[sym2]
                        mean1 = sum(r1) / len(r1)
                        mean2 = sum(r2) / len(r2)
                        covar = sum((r1[k] - mean1) * (r2[k] - mean2) for k in range(min(len(r1), len(r2)))) / min(len(r1), len(r2))
                        row.append(covar)
                cov_matrix.append(row)
            return cov_matrix, symbols
        else:
            returns_array = np.array([self.returns[s] for s in symbols]).T
            cov_matrix = np.cov(returns_array.T).tolist()
            return cov_matrix, symbols
    
    def calculate_expected_returns(self):
        """计算期望收益"""
        expected = {}
        for symbol, returns in self.returns.items():
            expected[symbol] = sum(returns) / len(returns) if returns else 0
        return expected
    
    def max_sharpe_portfolio(self):
        """求解最大Sharpe比投资组合 (贪心算法)"""
        expected = self.calculate_expected_returns()
        symbols = list(expected.keys())
        
        try:
            cov_matrix, _ = self.calculate_cov_matrix()
            stds = []
            for i in range(len(symbols)):
                var = cov_matrix[i][i]
                std = math.sqrt(max(var, 0))
                stds.append(std)
        except:
            stds = [0.01] * len(symbols)
        
        # 按Sharpe贡献加权
        sharpe_scores = []
        for i, sym in enumerate(symbols):
            ret = expected[sym]
            risk = stds[i] if stds[i] > 0 else 0.01
            sharpe = (ret - self.risk_free_rate) / risk if risk > 0 else 1
            sharpe_scores.append(max(0, sharpe))  # 只保留正的Sharpe
        
        # 归一化为权重
        total_sharpe = sum(sharpe_scores)
        if total_sharpe > 0:
            weights = [s / total_sharpe for s in sharpe_scores]
        else:
            weights = [1 / len(symbols)] * len(symbols)
        
        return {symbols[i]: weights[i] for i in range(len(symbols))}
    
    def risk_parity_portfolio(self):
        """风险平价分配 (按反波动率加权)"""
        try:
            cov_matrix, symbols = self.calculate_cov_matrix()
            stds = []
            for i in range(len(symbols)):
                var = cov_matrix[i][i]
                std = math.sqrt(max(var, 1e-8))
                stds.append(std)
        except:
            symbols = list(self.returns.keys())
            stds = [0.01] * len(symbols)
        
        # 按反波动率加权
        inv_stds = [1 / (s + 1e-8) for s in stds]
        total = sum(inv_stds)
        if total > 0:
            weights = [w / total for w in inv_stds]
        else:
            weights = [1 / len(symbols)] * len(symbols)
        
        return {symbols[i]: weights[i] for i in range(len(symbols))}


# ============================================================================
# 智能止损系统 (Smart Stop Loss)
# ============================================================================

class SmartStopLossSystem:
    """
    动态智能止损系统
    - 基于ATR的动态止损
    - 基于回撤的分级保护
    - 基于Sharpe的质量判断
    """
    
    def __init__(self, atr_multiplier=2.5, max_portfolio_drawdown=0.05):
        self.atr_multiplier = atr_multiplier  # 止损距离 = 入场价 - 2.5*ATR
        self.max_portfolio_drawdown = max_portfolio_drawdown  # 全局止损5%
    
    def calculate_atr(self, highs, lows, closes, period=14):
        """计算ATR (Average True Range)"""
        if len(highs) < period:
            return 0
        
        tr_values = []
        for i in range(len(highs)):
            h = highs[i]
            l = lows[i]
            c = closes[i-1] if i > 0 else closes[i]
            tr = max(h - l, abs(h - c), abs(l - c))
            tr_values.append(tr)
        
        atr = sum(tr_values[-period:]) / period
        return atr
    
    def calculate_stop_loss(self, entry_price, atr_value):
        """计算动态止损位"""
        stop_loss = entry_price - self.atr_multiplier * atr_value
        return max(stop_loss, entry_price * 0.85)  # 不低于入场价-15%
    
    def portfolio_drawdown_protection(self, current_portfolio_value, peak_value):
        """
        全局回撤保护
        返回: (当前回撤%, 保护级别, 建议操作)
        """
        drawdown = (peak_value - current_portfolio_value) / peak_value
        
        if drawdown < 0.02:
            return drawdown, "NORMAL", "continue_trading"
        elif drawdown < 0.03:
            return drawdown, "CAUTION", "pause_new_positions"
        elif drawdown < 0.05:
            return drawdown, "WARNING", "reduce_positions_20pct"
        else:
            return drawdown, "CRITICAL", "emergency_liquidate"


# ============================================================================
# 历史准确率追踪系统 (Accuracy Tracker)
# ============================================================================

class AccuracyTracker:
    """
    追踪股票推荐的准确率
    - 记录推荐时的预测收益/Sharpe
    - 更新实际收益
    - 生成准确率报告
    """
    
    def __init__(self, db_path='data/accuracy_v117.db'):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """初始化数据库"""
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('''CREATE TABLE IF NOT EXISTS recommendations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recommendation_date TEXT,
            symbol TEXT,
            name TEXT,
            strategy TEXT,
            sector TEXT,
            predicted_return REAL,
            predicted_sharpe REAL,
            entry_price REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS performance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recommendation_id INTEGER,
            symbol TEXT,
            actual_return_5d REAL,
            actual_return_10d REAL,
            actual_return_20d REAL,
            accurate BOOLEAN,
            updated_at TIMESTAMP,
            FOREIGN KEY(recommendation_id) REFERENCES recommendations(id)
        )''')
        
        conn.commit()
        conn.close()
    
    def record_recommendation(self, symbol, name, strategy, sector, 
                            predicted_return, predicted_sharpe, entry_price):
        """记录一条推荐"""
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        today = datetime.now().strftime('%Y-%m-%d')
        c.execute('''INSERT INTO recommendations 
                    (recommendation_date, symbol, name, strategy, sector, 
                     predicted_return, predicted_sharpe, entry_price)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                (today, symbol, name, strategy, sector, 
                 predicted_return, predicted_sharpe, entry_price))
        
        conn.commit()
        recommendation_id = c.lastrowid
        conn.close()
        
        return recommendation_id
    
    def update_performance(self, recommendation_id, symbol, 
                          actual_return_5d, actual_return_10d, actual_return_20d):
        """更新推荐的实际表现"""
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # 判断是否准确 (预测>0且实际>0)
        accurate = actual_return_5d > 0  # 简化: 5天后是否盈利
        
        c.execute('''INSERT INTO performance
                    (recommendation_id, symbol, actual_return_5d, actual_return_10d,
                     actual_return_20d, accurate, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, datetime('now'))''',
                (recommendation_id, symbol, actual_return_5d, actual_return_10d,
                 actual_return_20d, accurate))
        
        conn.commit()
        conn.close()
    
    def accuracy_report(self):
        """生成准确率报告"""
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # 按策略统计
        c.execute('''
            SELECT r.strategy, COUNT(*) as total, 
                   SUM(CASE WHEN p.accurate THEN 1 ELSE 0 END) as accurate_count,
                   AVG(p.actual_return_5d) as avg_5d_return,
                   AVG(p.actual_return_20d) as avg_20d_return
            FROM recommendations r
            LEFT JOIN performance p ON r.id = p.recommendation_id
            GROUP BY r.strategy
        ''')
        
        report = {}
        for row in c.fetchall():
            strategy, total, accurate_count, avg_5d, avg_20d = row
            accuracy_rate = (accurate_count / total * 100) if total > 0 else 0
            report[strategy] = {
                'total': total,
                'accurate': accurate_count or 0,
                'accuracy_rate': accuracy_rate,
                'avg_5d_return': avg_5d or 0,
                'avg_20d_return': avg_20d or 0
            }
        
        conn.close()
        return report
    
    def low_accuracy_strategies(self, threshold=0.45):
        """返回准确率低于阈值的策略"""
        report = self.accuracy_report()
        low_acc = {}
        for strategy, metrics in report.items():
            if metrics['accuracy_rate'] < threshold * 100:
                low_acc[strategy] = metrics
        return low_acc


if __name__ == "__main__":
    print("v5.117 新策略模块已加载 (无scipy依赖版本)")
    print("✅ MOMENTUM_SENTIMENT 策略")
    print("✅ MA_REVERT_VOL 策略")
    print("✅ IV_ARBITRAGE 策略")
    print("✅ ModernPortfolioOptimizer (简化版)")
    print("✅ SmartStopLossSystem")
    print("✅ AccuracyTracker")
