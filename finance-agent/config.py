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
