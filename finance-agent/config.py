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

# v5.54 盘前优化①: 现金高占比动态入场门槛激活
# 问题: 现金98%+但入场质量要求仍为65分 -> 候选数不足(5-8只)
# 解决: 现金占比逐级激活更宽松的入场门槛
ENTRY_QUALITY_DYNAMIC_THRESHOLDS = {
    'normal': 65,      # 正常: >=65分
    'high_cash': 55,   # 现金75-95%: >=55分 (-10分宽松)
    'extreme_cash': 45 # 现金>95%: >=45分 (-20分激进)
}
# 预期: 候选数 +40%, 资金利用率从4%->8~12%

# v5.53: 支撑位强化参数
VP_SUPPORT_STRENGTH_THRESHOLD = 1.5  # Volume Profile支撑强度系数
Z_SCORE_EXTREME_THRESHOLD = -2.0     # 统计极度超卖门槛
Z_SCORE_EXTREME_BONUS_BEAR = 12      # 熊市Z<-2加12分
Z_SCORE_EXTREME_BONUS_NORMAL = 8     # 普通市Z<-2加8分
FIB_618_SUPPORT_BONUS = 7            # FIB 0.618支撑+7分

# =================== v5.56 深度优化④: 赛道级策略路由 + 风险平衡 + 机构稳定性评分 ===================

# v5.56: 赛道级最优策略路由表 (基于回测数据,突破单一MACD+RSI依赖)
SECTOR_STRATEGY_ROUTING = {
    '科技成长': {
        'primary': ('MACD_RSI', 0.65),      # MACD+RSI 权重65% [17.1% Sharpe 2.35]
        'secondary': ('MULTI_FACTOR', 0.20),  # 多因子 权重20% [风险管理]
        'hedge': ('MA_CROSS', 0.15)        # 均线反向 权重15% [高波动对冲]
    },
    '新能源': {
        'primary': ('MACD_RSI', 0.60),      # MACD+RSI 权重60% [14.66% Sharpe 1.78]
        'secondary': ('MULTI_FACTOR', 0.25),  # 多因子 权重25% [稳定性]
        'hedge': ('TREND_FOLLOW', 0.15)    # 趋势 权重15% [势能捕捉]
    },
    '白马消费': {
        'primary': ('MULTI_FACTOR', 0.50),    # 多因子 50% [低回撤]
        'secondary': ('TREND_FOLLOW', 0.30),  # 趋势 30%
        'hedge': ('MA_CROSS', 0.20)        # 均线 20%
    }
}

# v5.56: Sharpe 风险分级 (动态调权)
SHARPE_RISK_THRESHOLDS = {
    'high_quality': 1.5,    # Sharpe >= 1.5: 100%权重(推荐)
    'medium_quality': 1.0,  # Sharpe 1.0-1.5: 50%权重(谨慎)
    'low_quality': 0.5,     # Sharpe 0.5-1.0: 25%权重(保守)
    # Sharpe < 0.5: 黑名单(除非特殊)
}

# v5.56: 机构持仓稳定性阈值 (入场质量新维度)
INSTITUTION_HOLDING_THRESHOLDS = {
    'high_hold_pct': 0.20,              # 机构持股>20%算优质 +15分
    'institution_increase_bonus': 8,    # 机构环比增加 +8分
    'margin_balance_pct': 0.02,         # 融资余额<2% +5分
    'northbound_stable_range': 0.05,    # 北向持股±5%算稳定 +5分
}

# v5.56: 新的入场质量评分权重 (5维×20分模型)
# 从 (趋势25+位置25+量价25+动量25) → (趋势20+位置20+量价20+动量20+机构20)
ENTRY_QUALITY_SCORE_WEIGHTS = {
    'trend': 20,           # 趋势对齐 (从25降到20)
    'position': 20,        # 位置优势 (从25降到20)
    'volume': 20,          # 量价确认 (从25降到20)
    'momentum': 20,        # 动量确认 (从25降到20)
    'institution': 20,     # 机构稳定性 (新增)
}

# =================== v5.57 盘前优化①: 现金高占比下的策略权重自适应激活 ===================
# 问题: 现金占比98%+,但策略权重仍为正常模式,导致选股不够激进
# 解决: 现金占比触发策略激进系数调权

# 现金占比对应的策略权重激进系数
CASH_RATIO_STRATEGY_BOOST = {
    'high': {          # 现金>95%: 激进模式 (快速消耗现金)
        'MACD_RSI': 1.8,       # MACD+RSI激进度1.8x
        'MULTI_FACTOR': 1.2,   # 多因子1.2x
        'TREND_FOLLOW': 1.3,   # 趋势跟随1.3x
        'MA_CROSS': 1.1,
    },
    'medium': {        # 现金75-95%: 中等模式
        'MACD_RSI': 1.3,
        'MULTI_FACTOR': 1.1,
        'TREND_FOLLOW': 1.1,
        'MA_CROSS': 1.0,
    },
    'normal': {        # 现金<75%: 正常保守模式
        'MACD_RSI': 1.0,
        'MULTI_FACTOR': 1.0,
        'TREND_FOLLOW': 1.0,
        'MA_CROSS': 1.0,
    }
}

# Sharpe实时权重应用阈值 (v5.57: 新增确保权重被应用)
APPLY_SHARPE_WEIGHTS_IN_RANKING = True  # 在stock_picker score_and_rank()中强制应用
SHARPE_WEIGHT_MULTIPLIER = 1.5  # Sharpe权重乘数(相对其他指标权重)

# =================== v5.59 盤後優化③: 超激進模式 + 加倉/追蹤止損強化 ===================
# 問題: 現金98%+但持倉利用率仅1.57%, 需要超激進模式快速消耗現金

# 超激進模式參數 (現金>98%時激活)
EXTREME_CASH_RATIO = 0.98           # 現金占比>98%觸發超激進
EXTREME_CASH_TARGET_ALLOCATION = 0.12  # 目標配置12%持倉(快速消耗現金)
EXTREME_CASH_ENTRY_QUALITY = 35     # 超激進下的入場質量閾值(45→35, -28%)
EXTREME_CASH_SIGNAL_BOOST = {
    'MACD_RSI': 2.2,        # MACD+RSI權重 1.8x → 2.2x (+22%)
    'MULTI_FACTOR': 1.4,    # 多因子 1.2x → 1.4x (+17%)
    'TREND_FOLLOW': 1.5,    # 趨勢跟隨 1.3x → 1.5x (+15%)
    'MA_CROSS': 1.2,
}

# 加倉參數 (position_manager.py新增)
POSITION_ADDING_CONDITIONS = {
    'min_hold_days': 3,         # 持倉至少3天才加倉
    'min_profit_pct': 0.02,     # 浮盈>2%時開始考慮加倉
    'max_add_pct': 0.30,        # 最多加倉到原頭寸的130%
    'kelly_add_ratio': 0.5,     # Kelly建議仓位×50%用於加倉
}

# 追蹤止損參數 (position_manager.py新增)
TRAILING_STOP_LOSS = {
    'peak_retracement_pct': 0.05,  # 從峰值回撤>5%觸發
    'lock_ratio': 0.95,             # 鎖定95%峰值
    'time_stop_hours': 8,           # 8小時無新高止損
    'enabled': True,                # 啟用追蹤止損
}

# 候選池擴展 (stock_picker.py調參)
MOMENTUM_SIGNAL_TARGET = 55         # 從45提升至55只 (+22%)
VOLUME_SIGNAL_TARGET = 30           # 從25提升至30只 (+20%)
