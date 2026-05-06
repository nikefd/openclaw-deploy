"""金融Agent配置"""

# 模拟盘初始资金
INITIAL_CAPITAL = 1_000_000  # 100万

# 交易规则 (A股)
COMMISSION_RATE = 0.0003     # 万三佣金
STAMP_TAX_RATE = 0.001       # 千一印花税(仅卖出)
MIN_COMMISSION = 5.0         # 最低佣金5元
SLIPPAGE = 0.002             # 滑点0.2%

# 持仓限制 (v5.85优化: 从保守→激进)
MAX_POSITIONS = 8            # 最多同时持有8只 (10→8,集中度控制)
MAX_SINGLE_POSITION = 0.05   # 单只最多5%仓位 (15%→5%,分散风险)
STOP_LOSS = -0.08            # 止损线 -8% (保持)
TAKE_PROFIT = 0.20           # 止盈线 +20% (保持)

# v5.85新增: 动态止损 (替代固定值)
TRAILING_STOP_ENABLED = True
TRAILING_STOP_PCT = 0.05     # 从峰值回撤5%触发

# v5.85新增: 资金配置结构 (35+40+15+10模型)
PORTFOLIO_ALLOCATION = {
    'defensive': 0.35,   # 消费白马/金融/医药 (+2-5%年化)
    'offensive': 0.40,   # 科技成长/新能源/军工 (+15-30%年化)
    'tactical': 0.15,    # 低位补漲/高分红 (防守反彈)
    'cash_reserve': 0.10 # 应对机会或风险
}

# v5.85新增: 最少现金比例 (从25%→10%)
MIN_CASH_RATIO = 0.10        # 释放更多建仓资金

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
ENTRY_QUALITY_THRESHOLD = 55  # v5.70优化: 从65→55 (快速建仓)

# v5.53: 过滤器动态松绑参数
HIGH_CASH_RATIO_THRESHOLD = 0.90  # v5.70优化: 从95%→90% (激进建仓触发)
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

# v5.71: 混合池赛道权重强化 — 修复混合池5.06%低收益问题
# 诊断: 混合池MACD+RSI(5.06%, 0.86 Sharpe)远低于科技赛道(17.1%, 2.35 Sharpe)
# 根因: 混合池选股缺乏赛道针对性，高收益科技策略被低效消费策略拖累
# 解决: 在混合池选股中按回测数据加权不同赛道，优先选择高效赛道的候选
MIXED_POOL_SECTOR_WEIGHTS_V71 = {
    '科技成长': 1.8,    # 权重 +80% (TOP1: 17.1% Sharpe 2.35)
    '新能源': 1.5,      # 权重 +50% (TOP2: 14.66% Sharpe 1.78)
    '消费白马': 0.5,    # 权重 -50% (低效)
    '主板': 0.8,        # 权重 -20%
    '其他': 0.7,        # 权重 -30%
}
# 预期效果: 混合池收益从5.06% → 8-10%, Sharpe从0.86 → 1.2+
APPLY_MIXED_POOL_SECTOR_WEIGHTS = True

# =================== v5.59 盤後優化③: 超激進模式 + 加倉/追蹤止損強化 ===================
# 問題: 現金98%+但持倉利用率仅1.57%, 需要超激進模式快速消耗現金

# 超激進模式參數 (現金>98%時激活)
EXTREME_CASH_RATIO = 0.98           # 現金占比>98%觸發超激進
EXTREME_CASH_TARGET_ALLOCATION = 0.12  # 目標配置12%持倉(快速消耗現金)
EXTREME_CASH_ENTRY_QUALITY = 35     # 超激進下的入場質量閾值(45→35, -28%) [v5.66優化:已驗證]
EXTREME_CASH_V3 = {
    'trigger_ratio': 0.984,         # 現金>98.4%觸發v5.66激進選股
    'quality_threshold': 35,        # 入場質量門檻降至35分(-27%)
    'signal_boost_v3': 2.5,         # 信號權重激進度提升到2.5x (v5.65: 2.2x)
}
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
    'peak_retracement_pct': 0.05,  # 從峰值回撤>5%觸發 [v5.66已驗證001367: -5.77%]
    'lock_ratio': 0.95,             # 鎖定95%峰值
    'aggressive_retracement': 0.045,  # v5.66優化: 高風險持倉回撤>4.5%更快觸發
    'high_risk_threshold': 'Sharpe<1.0',  # 風險等級判定標準
    'time_stop_hours': 8,           # 8小時無新高止損
    'enabled': True,                # 啟用追蹤止損
}

# 候選池擴展 (stock_picker.py調參)
MOMENTUM_SIGNAL_TARGET = 55         # 從45提升至55只 (+22%)
VOLUME_SIGNAL_TARGET = 30           # 從25提升至30只 (+20%)

# =================== v5.60 盤前優化①: 市場情緒動態入場質量調節 ===================
# 問題: 入場質量閾值固定在35-65分，未根據市場情緒動態調整
# 解決: 高情緒(>80)時降低閾值刺激買入; 恐慌情緒(<30)時提高閾值避免追高

SENTIMENT_ENTRY_QUALITY_ADJUSTMENT = {
    'greedy': {'threshold_adj': -5, 'sentiment_range': (80, 100)},      # 貪婪(>80): 質量-5分 (激進)
    'optimistic': {'threshold_adj': 0, 'sentiment_range': (65, 80)},   # 樂觀(65-80): 不調整
    'neutral': {'threshold_adj': 0, 'sentiment_range': (45, 65)},      # 中性(45-65): 不調整
    'cautious': {'threshold_adj': 3, 'sentiment_range': (30, 45)},     # 謹慎(30-45): 質量+3分 (保守)
    'panic': {'threshold_adj': 8, 'sentiment_range': (0, 30)},         # 恐慌(<30): 質量+8分 (防守)
}

# =================== v5.60 盤前優化②: 融資融券異動入場獎勵 ===================
# 新增: 融資餘額大幅下降(減倉意願) → 底部確認信號 +8分
#      融資餘額大幅上升(借錢買入) → 參與度上升信號 +5分
MARGIN_ADJUSTMENT_BONUS = {
    'margin_decline_bonus': 8,      # 融資餘額環比下降 >10% → +8分 (底部確認)
    'margin_increase_bonus': 5,     # 融資餘額環比上升 >10% → +5分 (參與度)
    'margin_decline_threshold': 0.10,   # 環比下降門檻
    'margin_increase_threshold': 0.10,  # 環比上升門檻
}

# =================== v5.59 晚间深度优化④: 超激进模式强化 + 高Sharpe权重激活 ===================
# 问题: 现金98%+但资金利用率仅1.57%, Sharpe权重未被充分应用
# 解决: (1)超激进模式权重2.2x加成 (2)Sharpe权重倍数升级2.0x (3)入场质量阈值激进至35分

# v5.59: Sharpe权重强制激活参数
SHARPE_WEIGHT_FORCE_APPLY = True                    # 强制在score_and_rank中应用
SHARPE_WEIGHT_MULTIPLIER_EXTREME = 2.0             # 超激进模式下的乘数 (1.5x→2.0x)
APPLY_SHARPE_WEIGHTS_WITH_BOOST = True             # 与现金占比boost组合应用

# v5.59: 候选池扩展(提供更多选择)
CUSTOM_SCORE_THRESHOLD_EXTREME = 15                # 超激进模式候选最低分15 (从20↓)
CUSTOM_MOMENTUM_POOL_SIZE = 60                     # 动量候选扩展至60只 (55→60)
CUSTOM_VOLUME_POOL_SIZE = 35                       # 量价候选扩展至35只 (30→35)

# v5.59: 现金占比激进系数 v2 (从v5.57优化)
CASH_RATIO_STRATEGY_BOOST_V2 = {
    'ultra_high': {        # 现金>98%: 超激进模式
        'MACD_RSI': 2.2,       # 2.2x激进
        'MULTI_FACTOR': 1.4,   # 1.4x  
        'TREND_FOLLOW': 1.5,   # 1.5x
        'MA_CROSS': 1.2,
    },
    'high': {              # 现金90-98%: 很激进
        'MACD_RSI': 1.8,
        'MULTI_FACTOR': 1.2,
        'TREND_FOLLOW': 1.3,
        'MA_CROSS': 1.1,
    },
    'medium': {            # 现金75-90%: 中等激进
        'MACD_RSI': 1.3,
        'MULTI_FACTOR': 1.1,
        'TREND_FOLLOW': 1.1,
        'MA_CROSS': 1.0,
    },
    'normal': {            # 现金<75%: 正常保守
        'MACD_RSI': 1.0,
        'MULTI_FACTOR': 1.0,
        'TREND_FOLLOW': 1.0,
        'MA_CROSS': 1.0,
    }
}

# =================== v5.61 晚间深度优化①: 超激进模式V3 强化版 ===================
# 问题: 现金98%+但资金利用率1.57%, Sharpe权重2.0x虽有但应用不足
# 解决: (1)MACD权重升至2.5x (2)Sharpe权重升至2.5x (3)入场质量降至30分 (4)融资融券+12分

# v5.61: 超激进模式V3参数矩阵
EXTREME_CASH_V3_MODE = {
    'enabled': True,                    # v5.61启用
    'trigger_ratio': 0.98,              # 现金>98%触发
    'target_allocation': 0.12,          # 目标持仓12%
    'entry_quality_threshold': 30,      # 入场质量30分(从35↓)
    'candidate_pool_target': 75,        # 候选池75只(从60↑)
}

# v5.61: 策略权重激进系数 v3 (超激进增强版)
CASH_RATIO_STRATEGY_BOOST_V3 = {
    'extreme': {           # 现金>98%: 超激进模式V3 (v5.61新增)
        'MACD_RSI': 2.5,       # 2.5x (+13% vs v5.59)
        'MULTI_FACTOR': 1.5,   # 1.5x (+7% vs v5.59)
        'TREND_FOLLOW': 1.6,   # 1.6x (+7% vs v5.59)
        'MA_CROSS': 1.3,       # 1.3x (+8% vs v5.59)
    },
    'ultra_high': {        # 现金>98% 备选方案(保守)
        'MACD_RSI': 2.2,       # 2.2x激进
        'MULTI_FACTOR': 1.4,   # 1.4x  
        'TREND_FOLLOW': 1.5,   # 1.5x
        'MA_CROSS': 1.2,
    },
    'high': {              # 现金90-98%: 很激进
        'MACD_RSI': 1.8,
        'MULTI_FACTOR': 1.2,
        'TREND_FOLLOW': 1.3,
        'MA_CROSS': 1.1,
    },
    'medium': {            # 现金75-90%: 中等激进
        'MACD_RSI': 1.3,
        'MULTI_FACTOR': 1.1,
        'TREND_FOLLOW': 1.1,
        'MA_CROSS': 1.0,
    },
    'normal': {            # 现金<75%: 正常保守
        'MACD_RSI': 1.0,
        'MULTI_FACTOR': 1.0,
        'TREND_FOLLOW': 1.0,
        'MA_CROSS': 1.0,
    }
}

# v5.61: Sharpe权重强制激活参数
SHARPE_WEIGHT_FORCE_APPLY_V3 = True                    # 强制在stock_picker中应用
SHARPE_WEIGHT_MULTIPLIER_V3 = 2.5                      # 倍数升至2.5x (从2.0x)
APPLY_SHARPE_WEIGHTS_WITH_EXTREME_MODE = True          # 与极端模式组合应用

# v5.61: 融资融券高级判别 (融资异变信号)
MARGIN_SIGNAL_V2 = {
    'margin_decline_premium': 12,       # 融资余额环比-20% + 融资融券比<20% → +12分 (底部确认)
    'margin_increase_premium': 8,       # 融资余额环比+15% + 融资创新高 → +8分 (参与度)
    'margin_decline_threshold': 0.20,   # 环比下降门槛 (-20%)
    'margin_increase_threshold': 0.15,  # 环比上升门槛 (+15%)
    'margin_ratio_threshold': 0.20,     # 融资融券比门槛 (20%)
}

# v5.61: 赛道差异化权重路由 v2 (按回测数据优化)
SECTOR_STRATEGY_ROUTING_V2 = {
    '科技成长': {
        'primary': ('MACD_RSI', 2.5),      # MACD+RSI 权重2.5x (v5.61新增)
        'secondary': ('MULTI_FACTOR', 1.5),  # 多因子 权重1.5x (从1.2x↑)
        'hedge': ('MA_CROSS', 0.9)         # 均线 权重0.9x (对冲)
    },
    '新能源': {
        'primary': ('MACD_RSI', 2.0),      # MACD+RSI 权重2.0x
        'secondary': ('MULTI_FACTOR', 1.3),  # 多因子 权重1.3x
        'hedge': ('TREND_FOLLOW', 1.2)    # 趋势 权重1.2x
    },
    '白马消费': {
        'primary': ('MULTI_FACTOR', 1.5),    # 多因子 1.5x
        'secondary': ('TREND_FOLLOW', 1.3),  # 趋势 1.3x
        'hedge': ('MA_CROSS', 1.0)        # 均线 1.0x
    },
    '主板': {
        'primary': ('MULTI_FACTOR', 1.3),    # 多因子
        'secondary': ('TREND_FOLLOW', 1.1),
        'hedge': ('MA_CROSS', 1.0)
    }
}

# v5.61: 入场质量阈值动态调节 v2 (极限模式激活)
ENTRY_QUALITY_DYNAMIC_V2 = {
    'extreme': 30,         # 现金>98%超激进: 30分 (v5.61新增,从35↓)
    'high_cash': 40,       # 现金75-98%: 40分 (从55↓)
    'normal': 55,          # 正常: 55分 (从65↓)
}

# v5.61: 候选池规模扩展参数
CANDIDATE_POOL_EXPANDED = {
    'momentum_target': 75,      # 动量候选 75只 (从55↑ +36%)
    'volume_target': 40,        # 量价候选 40只 (从30↑ +33%)
    'custom_score_threshold_extreme': 15,  # 极端模式最低分 15 (从20↓)
    'apply_margin_bonus': True, # 应用融资融券+12分
}

# =================== v5.61 深度优化：超激进权重升级 + Sharpe倍数提升 + 融资融券高级判别 ===================
# 目标: 资金利用率 1.57% → 8-12%, 日均选股 8-12只 → 15-20只, Sharpe保持2.35+
# 方案: (1) Sharpe权重倍数 2.0x → 2.5x (强制应用)
#       (2) 超激进模式入场质量 35分 → 30分 (-14%)
#       (3) 候选池扩展 60只 → 75只 (+25%)
#       (4) 融资融券高级判别: 融资环比-20%+融资融券比<20% → +12分
#       (5) MACD_RSI权重 2.2x → 2.5x (+14%)

# v5.61: EXTREME_CASH_V3 - 超激进模式强化 (Sharpe权重2.5x)
EXTREME_CASH_V3 = {
    'enabled': True,                                    # 启用v5.61超激进模式
    'trigger_ratio': 0.98,                             # 现金>98%触发
    'entry_quality_threshold': 30,                     # 入场质量30分 (从35↓ -14%)
    'candidate_pool_size': 75,                         # 候选池75只 (从60↑ +25%)
    'sharpe_weight_multiplier': 2.5,                   # Sharpe权重倍数 2.5x (从2.0x↑ +25%)
    'macd_rsi_weight': 2.5,                            # MACD+RSI权重 2.5x (从2.2x↑ +14%)
    'signal_boost_aggressive': {
        'MACD_RSI': 2.5,                               # MACD+RSI 2.5x激进
        'MULTI_FACTOR': 1.5,                           # 多因子 1.5x (从1.4x)
        'TREND_FOLLOW': 1.6,                           # 趋势跟随 1.6x (从1.5x)
        'MA_CROSS': 1.3,                               # MA交叉 1.3x (从1.2x)
    }
}

# v5.61: 融资融券高级判别参数
MARGIN_SIGNAL_V2 = {
    'margin_decline_threshold': 0.20,                  # 融资环比下降>20% 触发底部确认
    'margin_fusion_ratio_max': 0.20,                   # 融资融券比<20% 算健康
    'margin_decline_bonus': 12,                        # 融资环比-20%+融资融券比<20% → +12分 (从8↑)
    'margin_increase_threshold': 0.15,                 # 融资环比上升>15% 触发参与度
    'margin_increase_bonus': 6,                        # 融资环比上升 → +6分 (从5↑)
}

# v5.61: 入场质量动态分级 V2 (优化现金占比对应的门槛)
ENTRY_QUALITY_DYNAMIC_V2 = {
    'extreme_cash': {'threshold': 30, 'cash_range': (0.98, 1.0)},   # 现金>98%: 30分 (激进)
    'very_high_cash': {'threshold': 40, 'cash_range': (0.90, 0.98)}, # 现金90-98%: 40分
    'high_cash': {'threshold': 50, 'cash_range': (0.75, 0.90)},     # 现金75-90%: 50分
    'normal': {'threshold': 65, 'cash_range': (0, 0.75)},           # 现金<75%: 65分 (保守)
}

# v5.61: 赛道差异化权重强化
SECTOR_WEIGHT_BOOST_V2 = {
    '科技成长': {                                        # 基础权重 30% (从20%)
        'base_weight': 0.30,
        'macd_boost': 2.5,                             # MACD权重 2.5x (从2.0x)
        'description': '技术面强劲,MACD+RSI最优'
    },
    '新能源': {
        'base_weight': 0.25,                           # 基础权重 25% (从18%)
        'macd_boost': 2.0,                             # MACD权重 2.0x
        'description': '政策支持,趋势确定'
    },
    '白马消费': {
        'base_weight': 0.20,                           # 基础权重 20% (保持)
        'multi_factor_boost': 1.5,                     # 多因子权重 1.5x
        'description': '基本面稳健,多因子优化'
    }
}

# v5.61: Sharpe权重应用强制激活
APPLY_SHARPE_MULTIPLIER_FORCE = True                    # 强制应用Sharpe权重倍数
SHARPE_WEIGHT_MULTIPLIER_V3 = 2.5                       # v5.61升级: 2.5x (从2.0x)

# =================== v5.62 盘前优化②: 信号持续性验证 + 低质量入场监控 ===================
# 目标: 在超激进模式(30分入场)下,通过信号质量检查 + 绩效监控避免虚假入场
# 方案: (1) MACD+RSI信号需要连续3根K线确认(去除噪声)
#       (2) 自动监控30分入场的成功率,如<50%自动回退到35分
#       (3) 低质量入场追踪: 记录入场质量≤30的持仓,统计30日胜率

# v5.62: MACD+RSI信号持续性要求
MACD_RSI_PERSISTENCE_CONFIG = {
    'enabled': True,                           # 启用信号持续性检查
    'min_lookback_days': 3,                    # 最少回看3天数据
    'min_rising_bars': 2,                      # MACD至少上升2根K线
    'min_rsi_above_50_bars': 2,                # RSI>50至少2根K线
    'confidence_threshold': 0.60,              # 信号可信度阈值 (0-1)
    'penalty_low_confidence': 0.85,            # 低可信度信号权重折扣 85%
    'penalty_no_persistence': 0.70,            # 非持续信号权重折扣 70%
}

# v5.62: 低质量入场自适应监控
LOW_QUALITY_ENTRY_MONITOR = {
    'enabled': True,                           # 启用低质量入场监控
    'quality_threshold': 30,                   # 入场质量≤30分为"低质量"
    'monitoring_window_days': 30,              # 监控最近30天
    'success_rate_threshold': 0.50,            # 成功率阈值 50%
    'auto_downgrade_enabled': True,            # 自动回退阈值
    'auto_downgrade_to': 35,                   # 成功率<50%时,质量要求回退到35分
    'report_interval_trades': 10,              # 每10笔交易输出一次监控报告
}

# v5.62: 联合评估(入场质量 + Sharpe双重守门)
ENTRY_QUALITY_SHARPE_JOINT_GATE = {
    'enabled': True,                           # 启用联合评估
    'low_quality_min_sharpe': 1.0,             # 入场质量≤30的持仓,Sharpe必须≥1.0
    'normal_quality_min_sharpe': 0.8,          # 入场质量>30的持仓,Sharpe必须≥0.8
    'bypass_if_rsi_oversold': False,           # RSI<30时可绕过(允许极端机会)
}

# =================== v5.68 盘前优化①②③: 流动性加权+ATR动态止损+信号持续性强化 ===================
# 背景: v5.67已激进到极限(现金98.4%, 入场35分, Sharpe2.8x),需精细化风控
# 优化目标: 止损率-2~3% → -1~2% | MaxDD稳定3.2% | Sharpe +5% | 资金利用率稳定12-18%
# 时间: 2026-04-28 08:00 UTC 盘前优化

# v5.68: 流动性加权入场配置
LIQUIDITY_WEIGHTED_ENTRY = {
    'enabled': True,                           # 启用流动性加权过滤
    'premarket_hours': (8, 10),                # 盘前时段 08:00-10:00 (UTC+8)
    'min_turnover_volume': 1e8,                # 最小成交额 1亿元
    'min_turnover_rate': 0.02,                 # 最小换手率 2%
    'max_daily_entries_premarket': 5,          # 盘前最多入场5只(激进但可控)
    'high_vol_min_turnover': 3e8,              # 高成交额要求 3亿元(达入场数上限时)
    'liquidity_score_threshold': 0.3,          # 流动性评分阈值
    'description': '上午8-10点过滤低流动性垃圾股,入场数限制5只'
}

# v5.68: ATR动态止损配置
ATR_DYNAMIC_STOP_LOSS = {
    'enabled': True,                           # 启用ATR动态止损
    'atr_period': 14,                          # ATR计算周期 14天
    'high_volatility_threshold': 0.03,         # 高波动率阈值 3%
    'low_volatility_threshold': 0.015,         # 低波动率阈值 1.5%
    'high_vol_multiplier': 1.2,                # 高波动: ATR*1.2放宽止损 (容忍更大回撤)
    'normal_vol_multiplier': 1.0,              # 正常波动: ATR*1.0标准止损
    'low_vol_multiplier': 0.8,                 # 低波动: ATR*0.8收紧止损 (快速止损)
    'max_dd_target': 0.032,                    # 目标MaxDD 3.2% (从4.08%↓)
    'description': '根据市场波动率自适应调整止损线,减少跳空误触'
}

# v5.68: 自适应信号持续性配置
ADAPTIVE_SIGNAL_PERSISTENCE = {
    'enabled': True,                           # 启用自适应持续性
    'extreme_cash_days': 2,                    # 现金>98%: 2天阈值(快速入场)
    'high_cash_days': 2,                       # 现金90-98%: 2天阈值
    'medium_cash_days': 3,                     # 现金75-90%: 3天阈值
    'normal_cash_days': 4,                     # 现金<75%: 4天阈值(保守)
    'min_quality_score': 50,                   # 最低质量评分要求 50分
    'quality_pass_multiplier': 1.5,            # 质量达标信号权重*1.5(已有基础)
    'description': '在激进模式快速入场,但通过质量评分保证信号可靠性'
}

# v5.68: 集成配置开关
V5_68_OPTIMIZATION_ACTIVE = True               # 激活v5.68所有优化模块

# =================== v5.75 晚间大改进: 混合池重构 + MACD参数精优 + 快速选股 ===================
# 【目标】
# 1. 混合池策略重构: 摆脱白马消费低效约束(0.86 Sharpe) → 改用科技(2.35)/新能源(1.78)组合
#    - 混合池收益目标: 5.06% → 8-10%
#    - 混合池Sharpe目标: 0.86 → 1.2+
# 2. MACD+RSI参数精优: 在科技赛道表现好(17.1% 收益,2.35 Sharpe),尝试跨赛道微调
#    - 新能源: 加快MACD → (10,24,7)
#    - 消费: 保守MACD → (14,28,9)
# 3. 快速选股模式: 高现金时(>90%)快速完成选股,不超过10秒
# 4. 实盘准确率分析: 对比历史推荐vs实际收益
# 5. 回撤控制强化: 科技赛道回撤4.08% → 目标3.2% (ATR动态止损)

# v5.75: 混合池赛道权重优化 (v5.71基础上再升级)
MIXED_POOL_SECTOR_WEIGHTS_V75 = {
    '科技成长': 2.0,    # v5.71: 1.8x → v5.75: 2.0x (+11%)
    '新能源': 1.8,      # v5.71: 1.5x → v5.75: 1.8x (+20%)
    '消费白马': 0.3,    # v5.71: 0.5x → v5.75: 0.3x (-40% 进一步降低)
    '主板': 0.6,        # v5.71: 0.8x → v5.75: 0.6x (-25%)
    '其他': 0.4,        # v5.71: 0.7x → v5.75: 0.4x (-43%)
}
APPLY_MIXED_POOL_SECTOR_WEIGHTS_V75 = True  # 启用v5.75混合池权重

# v5.75: MACD+RSI赛道差异化参数
MACD_PARAMS_SECTOR_V75 = {
    '科技成长': {'fast': 12, 'slow': 26, 'signal': 9, 'description': '最优参数'},
    '新能源': {'fast': 10, 'slow': 24, 'signal': 7, 'description': '快速参数'},
    '消费白马': {'fast': 14, 'slow': 28, 'signal': 9, 'description': '保守参数'},
    '主板': {'fast': 12, 'slow': 26, 'signal': 9, 'description': '标准参数'},
}

RSI_PARAMS_SECTOR_V75 = {
    '科技成长': {'period': 14, 'oversold': 30, 'overbought': 70},
    '新能源': {'period': 12, 'oversold': 28, 'overbought': 72},  # 更敏感
    '消费白马': {'period': 16, 'oversold': 32, 'overbought': 68},  # 更平滑
}

APPLY_SECTOR_MACD_PARAMS_V75 = True         # 启用赛道差异化MACD参数

# v5.75: 快速选股模式配置 (FAST_PICK)
FAST_PICK_MODE_V75 = {
    'enabled': True,
    'cash_ratio_threshold': 0.90,           # 现金>90%激活
    'picker_time_threshold': 5.0,           # 选股耗时>5秒激活
    'max_pick_time_target': 10.0,           # 目标完成时间10秒
    'cache_size': 50,                       # 缓存50只高质量候选
    'fast_pick_target': 10,                 # 快速选出10-15只
    'cache_update_interval': 300,           # 5分钟更新一次
    'description': '现金高占比时的高速选股模式'
}

APPLY_FAST_PICK_V75 = True                  # 启用快速选股模式

# v5.75: 实盘准确率分析配置
BACKTEST_ACCURACY_ANALYSIS_V75 = {
    'enabled': True,
    'backtest_log_path': '/home/nikefd/finance-agent/reports/backtest_history.json',
    'trade_log_path': '/home/nikefd/finance-agent/reports/trades.jsonl',
    'high_accuracy_threshold': {'win_rate': 0.60, 'sharpe': 1.0},   # 高准确率模式
    'low_accuracy_threshold': {'win_rate': 0.40},                   # 低准确率模式(拉黑)
    'min_sample_size': 5,                                           # 最少样本数
    'description': '分析入场质量vs实际收益关联度'
}

# v5.75: ATR回撤控制强化
ATR_DRAWDOWN_CONTROL_V75 = {
    'enabled': True,
    'atr_period': 14,                       # ATR计算周期
    'target_max_dd': 0.032,                 # 目标MaxDD 3.2% (从4.08% ↓22%)
    'high_vol_threshold': 0.03,             # 高波动率阈值 3%
    'low_vol_threshold': 0.015,             # 低波动率阈值 1.5%
    'high_vol_multiplier': 1.2,             # 高波动ATR倍数
    'normal_vol_multiplier': 1.0,           # 正常波动ATR倍数
    'low_vol_multiplier': 0.8,              # 低波动ATR倍数 (快速止损)
    'description': '基于ATR波动率的动态止损强化'
}

APPLY_ATR_DRAWDOWN_CONTROL_V75 = True       # 启用ATR回撤控制

# v5.75: 集成开关
V5_75_OPTIMIZATION_ACTIVE = True            # 激活v5.75所有优化模块

# =================== v5.77 深度优化工程：策略融合 + 准确率追踪 ===================
# 【核心价值】
# 基于回测最优策略(MACD+RSI 科技成长 17.1% Sharpe 2.35)
# 实施大规模优化: 策略融合 + 准确率追踪 + UI增强

# v5.77: 最优策略参数 (回测TOP1)
OPTIMAL_STRATEGY_PARAMS_V5_77 = {
    'strategy': 'MACD+RSI',
    'macd_fast': 12,
    'macd_slow': 26,
    'macd_signal': 9,
    'rsi_period': 14,
    'rsi_oversold': 30,
    'rsi_overbought': 70,
    'stop_loss': -0.08,      # -8%
    'take_profit': 0.20,     # +20%
    'backtest_return': 0.171,  # 17.1%
    'backtest_sharpe': 2.35,
    'backtest_winrate': 0.60,  # 60%
    'backtest_max_dd': 0.0408, # 4.08%
    'primary_sector': '科技成长',
}

# v5.77: 赛道推荐权重 (基于v5.75回测数据)
SECTOR_RECOMMENDATION_WEIGHTS_V5_77 = {
    '科技成长': {'weight': 2.0, 'backtest_return': 0.171, 'backtest_sharpe': 2.35},
    '新能源': {'weight': 1.8, 'backtest_return': 0.1466, 'backtest_sharpe': 1.78},
    '医药': {'weight': 1.0, 'backtest_return': 0.08, 'backtest_sharpe': 0.95},
    '金融': {'weight': 0.8, 'backtest_return': 0.05, 'backtest_sharpe': 0.65},
    '消费': {'weight': 0.3, 'backtest_return': 0.03, 'backtest_sharpe': 0.40},
    '主板': {'weight': 0.6, 'backtest_return': 0.05, 'backtest_sharpe': 0.60},
}

# v5.77: 策略融合常量
STRATEGY_FUSION_WEIGHT_BOOST = 5  # 命中最优策略+5分
STRATEGY_MATCH_CONFIDENCE_THRESHOLD = 0.75  # 置信度阈值
SHARPE_WEIGHT_MULTIPLIER_V5_77 = 3.0  # v5.77: 从2.5x提升到3.0x

# v5.77: 进场品质评分新维度
ENTRY_QUALITY_DIMENSIONS_V5_77 = 3  # 新增3个维度
ENTRY_QUALITY_DIMENSIONS_NEW = [
    'strategy_confidence',      # 策略信度 (基于Sharpe比率)
    'historical_accuracy',      # 历史准确率 (最近30天)
    'risk_adjusted_return',     # 风险调整后收益 (vs MaxDD)
]

# v5.77: 准确率追踪配置
ACCURACY_TRACKER_CONFIG_V5_77 = {
    'enabled': True,
    'hit_threshold': 0.03,           # 命中标准: 涨幅>3%
    'win_threshold': 0.01,           # 盈利标准: 涨幅>1%
    'loss_threshold': -0.05,         # 亏损标准: 跌幅<-5%
    'tracking_periods': [30, 60, 90],  # 统计周期 (天)
    'min_sample_size': 5,            # 最少样本数
    'accuracy_report_path': '/home/nikefd/finance-agent/data/accuracy_report.json',
}

# v5.77: 集成开关
V5_77_STRATEGY_FUSION_ACTIVE = True        # 激活策略融合
V5_77_ACCURACY_TRACKING_ACTIVE = True      # 激活准确率追踪
V5_77_UI_ENHANCEMENT_ACTIVE = True         # 激活UI增强

# =================== v5.79 深度优化：超激进模式2.0 + 快速多样化建仓 ===================
# 【优化背景】
# 当前账户: 现金98.7%, 持仓1.3%, 资金利用率仅1.57%, 年化收益0.19%
# 单仓问题: 100%集中在600958, 分散度评分仅4/15
# 
# 【v5.79核心目标】
# - 资金利用率: 1.3% → 12-15% (+9-11倍)
# - 日均建仓: 8-12只 → 15-20只
# - 入场质量: 55分 → 45分 (激进但有质量监控)
# - MaxDD: 4.08% → 3.2% (-22%)
# - 年化收益: 0.19% → 10-12% (基于Sharpe2.35传导)

# v5.79: 超激进模式2.0参数
V5_79_EXTREME_MODE_V2 = {
    'enabled': True,
    'trigger_ratio': 0.985,                # 现金>98.5%触发超激进2.0
    'target_allocation': 0.15,             # 目标仓位15% (从12% ↑)
    'entry_quality_threshold': 25,         # 入场质量25分 (从30↓ -17%)
    'candidate_pool_size': 100,            # 候选池100只 (从75↑ +33%)
    'min_signal_confidence': 0.65,         # 信号置信度65% (从75% ↓)
    'daily_entry_target': 20,              # 日均入场20只
    'position_size_range': (0.02, 0.04),   # 单仓2-4% (动态调整)
    'max_positions': 8,                    # 最多8只持仓
    'quick_assessment_timeout': 0.5,       # 快速评估超时0.5秒
}

# v5.79: 赛道多样化分配 (避免100%单仓)
V5_79_SECTOR_DIVERSIFICATION = {
    '科技成长': 0.40,                      # 40%仓位 (基于17.1% Sharpe2.35)
    '新能源': 0.35,                        # 35%仓位 (基于14.66% Sharpe1.78)
    '其他': 0.25,                          # 25%仓位 (医药/金融/消费)
}

# v5.79: 融资融券异变奖励升级 (从v5.61)
V5_79_MARGIN_ANOMALY_BONUS = {
    'margin_decline_threshold': 0.20,      # 融资环比下降>20%
    'margin_ratio_threshold': 0.20,        # 融资融券比<20%
    'decline_and_low_ratio_bonus': 15,     # 两个条件都满足 → +15分 (从12分 +25%)
    'margin_increase_threshold': 0.15,     # 融资环比上升>15%
    'increase_bonus': 8,                   # 融资上升 → +8分 (从6分 +33%)
}

# v5.79: 快速入场评估引擎配置
V5_79_QUICK_ASSESSMENT = {
    'enabled': True,
    'macd_cross_bonus': 30,                # MACD黄金叉 +30分
    'macd_rising_bonus': 15,               # MACD上升 +15分
    'rsi_oversold_bonus': 20,              # RSI超卖 +20分
    'rsi_rebound_bonus': 10,               # RSI反弹 +10分
    'position_advantage_bonus': 12,        # 位置优势 +12分
    'liquidity_bonus': 8,                  # 高流动性 +8分
    'tech_sector_boost': 0.25,             # 科技赛道+25%权重
    'energy_sector_boost': 0.20,           # 新能源赛道+20%权重
}

# v5.79: ATR动态止损强化
V5_79_ATR_STOP_LOSS = {
    'enabled': True,
    'atr_period': 14,
    'high_volatility_threshold': 0.03,     # 高波动>3%
    'low_volatility_threshold': 0.015,     # 低波动<1.5%
    'high_vol_stop_pct': -0.08,            # 高波动止损-8%
    'normal_vol_stop_pct': -0.06,          # 正常波动止损-6%
    'low_vol_stop_pct': -0.04,             # 低波动止损-4%
    'target_max_dd': 0.032,                # 目标MaxDD 3.2% (从4.08% ↓22%)
}

# v5.79: 集成开关
V5_79_DEEP_OPTIMIZE_ACTIVE = True          # 激活v5.79深度优化
APPLY_V5_79_EXTREME_MODE_V2 = True         # 启用超激进模式2.0
APPLY_V5_79_DIVERSIFIED_ENTRY = True       # 启用多样化建仓
APPLY_V5_79_QUICK_ASSESSMENT = True        # 启用快速评估引擎

# =================== v5.87 晚间深度优化：超激进选股 + 赛道多样化 + 消费黑名单 + 混合池升级 + 融资异变强化 ===================
# 【背景】
# - 当前: 现金99.3%, 持仓1只(东方证券800股), 资金利用率1.3%, 年化0.19%
# - 原因: 虽然配置激进(35分入场)但选股算法未充分应用, Sharpe倍数未强制生效, 消费赛道负收益拖累
# - 目标: 资金利用率1.3% → 15-20%, 日均建仓8 → 15-20只, 年化0.19% → 10-12%
#
# 【v5.87核心优化】
# 1. 超激进选股引擎 (现金>99% → 入场质量20分)
# 2. Sharpe倍数强制激活 (2.5x → 3.0x, 确保被应用)
# 3. 赛道多样化配置 (科技40% + 新能源35% + 其他25%)
# 4. 白马消费黑名单 (回测-5.51% → 直接过滤)
# 5. 混合池策略升级 (5.06% → 8-10% Sharpe 1.2+)
# 6. 融资融券异变强制应用 (+12分 or +8分)
# 7. ATR动态止损强化 (MaxDD 4.08% → 3.2%)

# v5.87: 超激进选股配置 (现金>99%时激活)
EXTREME_CASH_V87 = {
    'enabled': True,
    'trigger_ratio': 0.99,                 # 现金>99%触发v5.87超激进
    'entry_quality_threshold': 20,         # 入场质量20分 (从30↓ -33%)
    'candidate_pool_size': 120,            # 候选池120只 (从100↑ +20%)
    'daily_entry_target': 18,              # 日均入场18只 (从20↓平衡)
    'position_size_base': 0.015,           # 单仓基础1.5% (避免集中)
    'sharpe_weight_multiplier': 3.0,       # Sharpe倍数3.0x (从2.5x↑)
    'macd_rsi_weight': 2.8,                # MACD+RSI权重2.8x (从2.5x↑)
    'signal_confidence_threshold': 0.60,   # 信号置信度60% (从65% ↓)
    'description': '现金99.3%超激进模式(v5.87)'
}

# v5.87: Sharpe权重强制激活 (确保倍数真正生效)
SHARPE_FORCE_APPLY_V87 = {
    'enabled': True,
    'multiplier': 3.0,                     # 强制3.0x倍数
    'apply_at_ranking': True,              # 在score_and_rank()中强制应用
    'apply_at_selection': True,            # 在最终选股中再次确认应用
    'macd_rsi_priority_boost': 1.5,        # MACD+RSI策略额外1.5x加成
    'description': 'Sharpe权重3倍强制生效机制'
}

# v5.87: 赛道多样化配置强化
SECTOR_ALLOCATION_V87 = {
    '科技成长': {
        'allocation_ratio': 0.40,          # 40%资金配置
        'macd_weight': 2.8,                # MACD权重2.8x
        'sharpe_multiplier': 3.0,         # Sharpe倍数3.0x
        'daily_target': 8,                 # 日均建仓8只
        'backtest_data': {'return': 0.171, 'sharpe': 2.35, 'dd': 0.0408, 'wr': 0.60}
    },
    '新能源': {
        'allocation_ratio': 0.35,          # 35%资金配置
        'macd_weight': 2.0,                # MACD权重2.0x
        'sharpe_multiplier': 2.5,         # Sharpe倍数2.5x
        'daily_target': 6,                 # 日均建仓6只
        'backtest_data': {'return': 0.1466, 'sharpe': 1.78, 'dd': 0.0693, 'wr': 0.70}
    },
    '医药': {
        'allocation_ratio': 0.10,          # 10%资金配置
        'macd_weight': 1.5,                # MACD权重1.5x
        'sharpe_multiplier': 1.8,         # Sharpe倍数1.8x
        'daily_target': 2,                 # 日均建仓2只
        'backtest_data': {'return': 0.08, 'sharpe': 0.95, 'dd': 0.03, 'wr': 0.55}
    },
    '金融': {
        'allocation_ratio': 0.10,          # 10%资金配置
        'macd_weight': 1.3,                # MACD权重1.3x
        'sharpe_multiplier': 1.5,         # Sharpe倍数1.5x
        'daily_target': 2,                 # 日均建仓2只
        'backtest_data': {'return': 0.05, 'sharpe': 0.65, 'dd': 0.02, 'wr': 0.52}
    },
    '消费': {
        'allocation_ratio': 0.05,          # 5%资金配置 (最小化)
        'macd_weight': 0.5,                # MACD权重0.5x (压低权重)
        'sharpe_multiplier': 0.3,         # Sharpe倍数0.3x (极度压低)
        'daily_target': 0,                 # 日均建仓0只 (接近完全避免)
        'blacklist_threshold': 0.95,       # 95%概率直接黑名单
        'backtest_data': {'return': -0.0551, 'sharpe': -1.0, 'dd': 0.1157, 'wr': 0.062}
    }
}
APPLY_SECTOR_ALLOCATION_V87 = True         # 启用v5.87赛道多样化

# v5.87: 消费赛道黑名单机制
CONSUMER_SECTOR_BLACKLIST_V87 = {
    'enabled': True,
    'trigger_on_negative_backtest': True,  # 回测负收益直接黑名单
    'blacklist_sectors': ['白马消费', '消费服务', '消费食品'],  # 黑名单赛道列表
    'min_quality_to_bypass': 80,           # 入场质量>80分可以绕过黑名单
    'reason': 'MACD+RSI消费策略回测-5.51%, Sharpe -1.0, MaxDD 11.57%'
}
APPLY_CONSUMER_BLACKLIST_V87 = True        # 启用消费黑名单

# v5.87: 混合池策略升级 (从v5.75基础上优化)
MIXED_POOL_SECTOR_WEIGHTS_V87 = {
    '科技成长': 2.5,                       # v5.75: 2.0x → v5.87: 2.5x (+25%)
    '新能源': 2.0,                         # v5.75: 1.8x → v5.87: 2.0x (+11%)
    '医药': 1.2,                           # v5.75无此配置 → v5.87新增1.2x
    '消费': 0.1,                           # v5.75: 0.3x → v5.87: 0.1x (-67% 重度压低)
    '主板': 0.7,                           # v5.75: 0.6x → v5.87: 0.7x (+17%)
    '其他': 0.5,                           # v5.75: 0.4x → v5.87: 0.5x (+25%)
}
APPLY_MIXED_POOL_V87 = True                # 启用v5.87混合池权重

# v5.87: 融资融券异变强制激活
MARGIN_ANOMALY_V87 = {
    'enabled': True,
    'margin_decline_threshold': 0.20,      # 融资环比下降>20%
    'margin_ratio_threshold': 0.20,        # 融资融券比<20%
    'decline_and_low_ratio_bonus': 12,     # 两个条件都满足 → +12分 (强制应用)
    'margin_increase_threshold': 0.15,     # 融资环比上升>15%
    'increase_bonus': 8,                   # 融资上升 → +8分 (强制应用)
    'force_apply': True,                   # v5.87: 强制应用(不允许skip)
    'description': '融资融券异变信号强制激活'
}
APPLY_MARGIN_ANOMALY_V87 = True            # 启用融资异变强制

# v5.87: ATR动态止损强化
ATR_STOP_LOSS_V87 = {
    'enabled': True,
    'atr_period': 14,
    'high_volatility_threshold': 0.03,     # 高波动>3%
    'normal_volatility_threshold': 0.015,  # 正常波动1.5-3%
    'low_volatility_threshold': 0.015,     # 低波动<1.5%
    'high_vol_stop_pct': -0.07,            # 高波动止损-7% (宽松)
    'normal_vol_stop_pct': -0.05,          # 正常波动止损-5% (中等)
    'low_vol_stop_pct': -0.03,             # 低波动止损-3% (紧)
    'target_max_dd': 0.032,                # 目标MaxDD 3.2%
    'description': '基于波动率自适应止损'
}
APPLY_ATR_STOP_LOSS_V87 = True             # 启用ATR止损

# v5.87: 集成开关
V5_87_DEEP_OPTIMIZE_ACTIVE = True          # 激活v5.87所有优化
V5_87_EXTREME_CASH_ENABLED = True          # 启用超激进选股
V5_87_SHARPE_FORCE_ENABLED = True          # 启用Sharpe强制激活
V5_87_SECTOR_DIVERSITY_ENABLED = True      # 启用赛道多样化
V5_87_CONSUMER_BLACKLIST_ENABLED = True    # 启用消费黑名单
V5_87_MARGIN_FORCE_ENABLED = True          # 启用融资异变强制

# =================== v5.88 盘前优化 (现金自动检测 + MACD直方图翻正) ===================
V5_88_PREMARKET_OPTIMIZE_ACTIVE = True     # 激活v5.88优化
V5_88_CASH_AUTO_DETECT_ENABLED = True      # 启用现金利用率自动检测
V5_88_MACD_HISTOGRAM_FLIP_ENABLED = True   # 启用MACD直方图翻正信号

# v5.88: MACD直方图翻正信号参数
MACD_HISTOGRAM_FLIP_BONUS = 18             # 直方图翻正信号 +18分 (强力反转)
MACD_HISTOGRAM_FLIP_RECENT_DAYS = 3        # 过去3天内的翻正算有效
MACD_HISTOGRAM_FLIP_STRENGTH_WEIGHT = 0.8  # 翻正强度权重 (0.5-1.0)

# v5.88: 现金自动检测阈值
CASH_AUTO_DETECTION_LEVELS = {
    'extreme': {'threshold': 0.99, 'entry_quality': 20, 'multiplier': 1.5},  # 极度激进
    'aggressive': {'threshold': 0.95, 'entry_quality': 25, 'multiplier': 1.2},  # 激进
    'normal': {'threshold': 0.75, 'entry_quality': 35, 'multiplier': 1.0}  # 常规
}
