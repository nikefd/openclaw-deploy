"""金融Agent配置"""

# 模拟盘初始资金
INITIAL_CAPITAL = 1_000_000  # 100万

# 交易规则 (A股)
COMMISSION_RATE = 0.0003     # 万三佣金
STAMP_TAX_RATE = 0.001       # 千一印花税(仅卖出)
MIN_COMMISSION = 5.0         # 最低佣金5元
SLIPPAGE = 0.002             # 滑点0.2%

# 持仓限制
MAX_POSITIONS = 10           # 最多同时持有10只
MAX_SINGLE_POSITION = 0.15   # 单只最多15%仓位
STOP_LOSS = -0.08            # 止损线 -8%
TAKE_PROFIT = 0.20           # 止盈线 +20%

# 数据库
DB_PATH = "/home/nikefd/finance-agent/data/trading.db"

# 报告输出
REPORT_DIR = "/home/nikefd/finance-agent/reports"

# =================== v5.53 深度优化IV: 回测驱动参数强化 ===================
# MACD+RSI策略参数 (基于回测TOP1: 17.1% 收益, 2.35 Sharpe, 60% 胜率, 4.08%回撤)
MACD_PARAMS = {
    'fast': 12,
    'slow': 26,
    'signal': 9
}

# RSI参数
RSI_PARAMS = {
    'period': 14,
    'oversold_threshold': 30,  # 超卖门槛
    'overbought_threshold': 70  # 超买门槛
}

# v5.53: MACD+RSI 信号权重激进提升 (1.3x → 1.5x)
# 理由: 回测数据显示MACD+RSI最优(17.1%+2.35Sharpe),直接加权确保权重覆盖
MACD_RSI_SIGNAL_BOOST = 1.5  # 从1.3提升到1.5 (+15%额外权重)

# 科技成长赛道权重激进优化 (0.20 → 0.30)
TECH_GROWTH_SECTORS = [
    '软件服务',
    '芯片',
    '新能源',
    '电子产品',
    '通信设备',
    '互联网',
    '计算机',
    '人工智能',
    '半导体'
]
TECH_GROWTH_WEIGHT_BOOST = 0.30  # 从0.20提升到0.30 (+50%权重加成)

# 信号持续性要求
MIN_SIGNAL_PERSISTENCE_DAYS = 3  # 至少连续3天才算持续性信号

# 低胜率信号黑名单
LOW_WIN_RATE_THRESHOLD = 0.40  # 胜率<40%
SIGNAL_BLACKLIST_DAYS = 30     # 黑名单保留30天

# Kelly准则参数
KELLY_MAX_POSITION = 0.30      # Kelly最大仓位30%
KELLY_WIN_RATE_BOOST = 0.05    # 胜率每高5%，仓位+1%(max 30%)

# 高Sharpe持仓保留
HIGH_SHARPE_THRESHOLD = 1.5    # Sharpe>1.5的持仓加强保留
HIGH_SHARPE_STOP_LOSS_RELAX = 0.02  # 止损容错放宽+2%

# =================== v5.53: 入场质量评分系统 ===================
# 4维×25分模型: 趋势对齐 + 位置优势 + 量价确认 + 动量确认
ENTRY_QUALITY_THRESHOLD = 65  # 入场质量通过门槛 (0-100分)

# v5.53: 过滤器动态松绑参数
HIGH_CASH_RATIO_THRESHOLD = 0.95  # 现金>95%触发激进模式
LOSS_STREAK_THRESHOLD = 7          # 连亏≥7次触发微仓试单
MICRO_POSITION_SIZE = 0.025        # 连亏微仓: 固定2.5%

# v5.53: 支撑位强化参数
VP_SUPPORT_STRENGTH_THRESHOLD = 1.5  # Volume Profile支撑强度系数
Z_SCORE_EXTREME_THRESHOLD = -2.0     # 统计极度超卖门槛
Z_SCORE_EXTREME_BONUS_BEAR = 12      # 熊市Z<-2加12分
Z_SCORE_EXTREME_BONUS_NORMAL = 8     # 普通市Z<-2加8分
FIB_618_SUPPORT_BONUS = 7            # FIB 0.618支撑+7分
