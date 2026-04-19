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

# =================== v5.49 深度优化: 回测驱动参数 ===================
# MACD+RSI策略参数 (基于回测: 17.1% 收益, 2.35 Sharpe, 60% 胜率)
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

# MACD+RSI 信号权重提升
MACD_RSI_SIGNAL_BOOST = 1.3  # 相比其他信号提升30%

# 科技成长赛道权重优化
TECH_GROWTH_SECTORS = [
    '软件服务',
    '芯片',
    '新能源',
    '电子产品',
    '通信设备',
    '互联网',
    '计算机'
]
TECH_GROWTH_WEIGHT_BOOST = 0.20  # +20%权重

# 信号持续性要求
MIN_SIGNAL_PERSISTENCE_DAYS = 3  # 至少连续3天才算持续性信号(从2天升级)

# 低胜率信号黑名单
LOW_WIN_RATE_THRESHOLD = 0.40  # 胜率<40%
SIGNAL_BLACKLIST_DAYS = 30     # 黑名单保留30天

# Kelly准则参数
KELLY_MAX_POSITION = 0.30      # Kelly最大仓位30%
KELLY_WIN_RATE_BOOST = 0.05    # 胜率每高5%，仓位+1%(max 30%)

# 高Sharpe持仓保留
HIGH_SHARPE_THRESHOLD = 1.5    # Sharpe>1.5的持仓加强保留
HIGH_SHARPE_STOP_LOSS_RELAX = 0.02  # 止损容错放宽+2%
