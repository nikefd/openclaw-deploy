"""v5.166 清仓后保守入场策略 - 提高入场品质 + 降低追高风险"""

from typing import List, Dict, Tuple
import math


class ConservativeEntryV166:
    """清仓后保守入场模块
    
    背景: 5月29日全部清仓(触发止损), 当前100%现金
    目标: 
    - 重建入场机制(质量优先)
    - 减少追高风险(Z-score过滤)
    - 小仓位试探(3-5% vs之前5-8%)
    """
    
    def __init__(self):
        self.min_quality_score = 65  # 提升到65分
        self.min_consecutive_up_days = 3  # 连续上升3天
        self.z_score_threshold = 2.5  # Z-score超过2.5自动降50%
        self.min_position_ratio = 0.03  # 3%
        self.max_position_ratio = 0.05  # 5%
        self.margin_anomaly_required = True  # 强制融资异变验证
    
    def should_enter(self, stock_data: Dict) -> Tuple[bool, str, float]:
        """判断是否应该入场
        
        Args:
            stock_data: {
                'code': str,
                'name': str,
                'entry_quality': int,  # 0-100分
                'price_z_score': float,  # 统计Z-score
                'consecutive_up': int,  # 连续上升天数
                'margin_anomaly_score': int,  # 融资异变得分 0/8/15
                'current_price': float,
                'profit_margin': float,  # 持仓盈利率
                'current_sentiment': str,  # 'bullish'/'neutral'/'bearish'
            }
        
        Returns:
            (should_enter: bool, reason: str, position_ratio: float)
        """
        
        # 条件1: 入场品质必须>65分 (从60提升)
        if stock_data.get('entry_quality', 0) < self.min_quality_score:
            return False, f"质量不足: {stock_data.get('entry_quality', 0)}/65分", 0.0
        
        # 条件2: 融资异变强制验证
        if self.margin_anomaly_required:
            margin_score = stock_data.get('margin_anomaly_score', 0)
            if margin_score == 0:
                return False, "未通过融资异变验证(必需)", 0.0
        
        # 条件3: Z-score过高自动降仓 (防追高)
        z_score = abs(stock_data.get('price_z_score', 0))
        position_ratio = self.max_position_ratio
        
        if z_score > 2.5:
            position_ratio *= 0.5  # 降到2.5%
            reason_note = f"[Z-score高风险{z_score:.2f}, 仓位减半]"
        else:
            reason_note = ""
        
        # 条件4: 连续上升天数 (至少3天)
        if stock_data.get('consecutive_up', 0) < self.min_consecutive_up_days:
            return False, f"上升动力不足: 仅{stock_data.get('consecutive_up', 0)}天", 0.0
        
        # 条件5: 情绪不能太悲观
        if stock_data.get('current_sentiment') == 'bearish':
            return False, "市场情绪过悲观", 0.0
        
        # 全部通过
        reason = (
            f"✅入场确认 | 品质{stock_data.get('entry_quality')}分 | "
            f"融资+{stock_data.get('margin_anomaly_score')}分 | "
            f"Z-score{z_score:.2f} {reason_note}"
        )
        
        return True, reason, position_ratio
    
    def calculate_initial_position_size(
        self,
        total_cash: float,
        position_ratio: float,
        current_price: float,
        expected_holding_days: int = 15
    ) -> Tuple[int, float, str]:
        """计算初始仓位规模 (小仓位策略)
        
        Args:
            total_cash: 总现金
            position_ratio: 仓位比例 (0.03-0.05)
            current_price: 股价
            expected_holding_days: 预期持仓天数(用于风险计算)
        
        Returns:
            (shares: int, amount: float, reason: str)
        """
        
        # 基础仓位
        position_amount = total_cash * position_ratio
        shares = int(position_amount / current_price)
        
        # 100股对齐
        shares = (shares // 100) * 100
        
        actual_amount = shares * current_price
        
        reason = (
            f"初始仓位 | 比例{position_ratio*100:.1f}% | "
            f"金额¥{actual_amount:,.2f} | {shares}股 | "
            f"预期持仓{expected_holding_days}天"
        )
        
        return shares, actual_amount, reason
    
    def get_add_position_signal(
        self,
        current_profit_margin: float,
        entry_quality_improvement: int = 0,
        **kwargs
    ) -> Tuple[bool, float, str]:
        """加仓信号判断 (逐步建仓)
        
        加仓条件:
        1. 当前持仓盈利>3%
        2. entry_quality继续维持或改进
        3. 加仓幅度: 初始仓位的30-50%
        
        Args:
            current_profit_margin: 当前持仓盈利率
            entry_quality_improvement: 品质改进幅度 (>0为加分)
        
        Returns:
            (should_add: bool, add_ratio: float, reason: str)
        """
        
        if current_profit_margin < 0.03:  # 盈利<3%
            return False, 0.0, "盈利不足3%, 暂不加仓"
        
        if entry_quality_improvement < 0:
            return False, 0.0, "品质恶化, 暂不加仓"
        
        # 加仓幅度
        add_ratio = 0.4 if entry_quality_improvement > 0 else 0.3
        
        reason = (
            f"加仓信号确认 | 盈利{current_profit_margin*100:.1f}% | "
            f"品质{entry_quality_improvement:+d}分 | "
            f"加仓{add_ratio*100:.0f}%"
        )
        
        return True, add_ratio, reason
    
    def format_entry_report(self, stocks: List[Dict]) -> str:
        """格式化入场报告"""
        
        good_entries = [
            s for s in stocks 
            if self.should_enter(s)[0]
        ]
        
        report = f"""
╔════════════════════════════════════════════════════════════════╗
║          v5.166 清仓后保守入场策略 - 入场筛选报告          ║
╚════════════════════════════════════════════════════════════════╝

📊 筛选结果:
   • 总候选: {len(stocks)} 只
   • 符合条件: {len(good_entries)} 只
   • 通过率: {len(good_entries)/max(1,len(stocks))*100:.1f}%

【筛选标准】
   ✓ 入场品质 >= 65分 (提升5分)
   ✓ 融资异变必须通过 (底部确认)
   ✓ Z-score > 2.5 时自动减半仓位
   ✓ 连续上升 >= 3天 (动力确认)
   ✓ 市场情绪 != 过悲观

【符合条件的品种】
"""
        
        for stock in good_entries:
            should_enter, reason, pos_ratio = self.should_enter(stock)
            shares, amount, pos_reason = self.calculate_initial_position_size(
                1000000, pos_ratio, stock.get('current_price', 10)
            )
            report += f"""   {stock.get('code')} {stock.get('name', 'N/A')}
      品质: {stock.get('entry_quality', 0)}/100 | 融资: +{stock.get('margin_anomaly_score', 0)}分
      仓位: {shares}股 (¥{amount:,.0f}, {pos_ratio*100:.1f}%)
      理由: {reason}

"""
        
        report += f"""
【下一步建议】
   1. 如有符合品种: 以初始仓位3-5%试探性建仓
   2. 监控: 盈利>3% 时评估是否加仓 (+30-50%)
   3. 止损: 低于-5% 或 Z-score异常 时提前止损
   4. 建仓速度: 一周内建仓控制在2-3只品种

【风险提示】
   ⚠️  当前100%现金, 需逐步建仓, 勿一次性全投
   ⚠️  融资数据滞后, 需核对实时融资变化
   ⚠️  Z-score仅参考, 不作硬止条件
"""
        
        return report


if __name__ == '__main__':
    # 测试用例
    entry = ConservativeEntryV166()
    
    test_stocks = [
        {
            'code': '000536',
            'name': '华映科技',
            'entry_quality': 68,
            'price_z_score': 1.8,
            'consecutive_up': 5,
            'margin_anomaly_score': 15,
            'current_price': 4.2,
            'profit_margin': 0.0,
            'current_sentiment': 'bullish',
        },
        {
            'code': '300833',
            'name': '浩洋股份',
            'entry_quality': 62,  # 不足65分
            'price_z_score': 2.8,
            'consecutive_up': 4,
            'margin_anomaly_score': 8,
            'current_price': 38.5,
            'profit_margin': 0.0,
            'current_sentiment': 'neutral',
        },
    ]
    
    print(entry.format_entry_report(test_stocks))
