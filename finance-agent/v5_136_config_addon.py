"""
v5.136 配置集成方案
====================
對 config.py 的參數修改清單
"""

# =================== v5.136 晚間深度優化⑤ 配置變更 ===================

# 原值: MACD_RSI_SIGNAL_BOOST = 1.8
# 新值: MACD_RSI_SIGNAL_BOOST = 2.0
# 說明: TOP1策略(17.1%, 60%, 2.35 Sharpe)權重激進提升 (+11%)
# 理由: 回測數據驗證MACD+RSI為最優策略，需要2.0x信號加權
MACD_RSI_SIGNAL_BOOST = 2.0  # v5.136: +11% 回測TOP策略激進

# 原值: TECH_GROWTH_WEIGHT_BOOST = 0.40
# 新值: TECH_GROWTH_WEIGHT_BOOST = 0.45
# 說明: 科技成長赛道權重激進優化 (+12.5%)
# 理由: TOP1策略為科技成長，需加強此赛道的選股權重
TECH_GROWTH_WEIGHT_BOOST = 0.45  # v5.136: +12.5% 科技成長優先級

# 原值: ENTRY_QUALITY_THRESHOLD = 15
# 新值: ENTRY_QUALITY_THRESHOLD = 15 (保留)
# 但新增動態閾值: ENTRY_QUALITY_DYNAMIC_THRESHOLDS
ENTRY_QUALITY_THRESHOLD = 15  # 保留為全局默認

# 新增: 動態入場門檻系統 (v5.136)
ENTRY_QUALITY_DYNAMIC_THRESHOLDS = {
    'normal': 55,              # 正常市場: 現金30-75%, 胜率60%+
    'high_cash': 45,           # 現金充足: 75-95%時激進建倉
    'extreme_cash': 35,        # 現金激進: >95%時超激進20分入場
    'low_winrate': 75,         # 低胜率: <50%時謹慎75分
    'high_concentration': 70   # 高集中: >30%時風控70分
}

# 新增: 梯度止盈系統 (v5.136)
GRADIENT_TAKE_PROFIT_ENABLED = True
GRADIENT_TAKE_PROFIT_CONFIG = {
    'tier1': {
        'profit_target': 0.05,      # +5%
        'sell_ratio': 0.40,
        'reason': '快速鎖定利潤'
    },
    'tier2': {
        'profit_target': 0.10,      # +10%
        'sell_ratio': 0.30,
        'reason': '保留中倉續持'
    },
    'tier3': {
        'profit_target': 0.15,      # +15%
        'sell_ratio': 1.0,
        'reason': '完全出場止盈'
    }
}

# 新增: 多週期確認系統 (v5.136)
MULTI_PERIOD_CONFIRMATION_ENABLED = True
MULTI_PERIOD_CONFIRMATION_RULES = {
    'STRONG_BUY': {
        'condition': '日線金叉 + 週線金叉 + 月線向上',
        'signal_boost': 20,
        'entry_threshold': 65,
        'kelly_multiplier': 1.2
    },
    'BUY': {
        'condition': '日線金叉 + 週線金叉',
        'signal_boost': 15,
        'entry_threshold': 70,
        'kelly_multiplier': 1.1
    },
    'WEAK_BUY': {
        'condition': '僅日線金叉',
        'signal_boost': 8,
        'entry_threshold': 75,
        'kelly_multiplier': 1.0
    },
    'SELL': {
        'condition': '週期死叉',
        'signal_penalty': -15,
        'auto_exit': True,
        'kelly_multiplier': 0.7
    }
}

# 新增: 風險加權評分系統 (v5.136)
RISK_WEIGHTED_SCORING_ENABLED = True
RISK_WEIGHTED_SCORING_MATRIX = {
    'macd_rsi': {'weight': 0.25, 'reason': 'TOP1策略主力'},
    'volume_confirm': {'weight': 0.25, 'reason': '多週期成交量確認'},
    'sentiment': {'weight': 0.20, 'reason': '新聞情感面'},
    'weekly_confirm': {'weight': 0.15, 'reason': '週線共振'},
    'risk_control': {'weight': 0.15, 'reason': '風控懲罰'}
}

RISK_PENALTIES_MATRIX = {
    'high_concentration': {
        'threshold': 0.30,
        'penalty': -20,
        'label': '極度風險(>30%集中度)'
    },
    'medium_concentration': {
        'threshold': 0.20,
        'penalty': -10,
        'label': '中度風險(20-30%集中度)'
    },
    'high_volatility': {
        'threshold': 0.40,
        'penalty': -5,
        'label': '高波動(>40%)'
    },
    'stale_position': {
        'threshold': 90,  # days
        'penalty': -3,
        'label': '陳舊持倉(>90天)'
    }
}

# 新增: 情感驅動參數調整系統 (v5.136)
SENTIMENT_DRIVEN_ADJUSTMENT_V136 = {
    'extreme_greed': {
        'score_range': (85, 100),
        'label': '極度貪婪',
        'kelly_multiplier': 0.70,
        'entry_threshold_delta': 8,
        'cash_ratio_delta': 0.05,
        'action': '減倉觀望'
    },
    'greed': {
        'score_range': (70, 85),
        'label': '貪婪',
        'kelly_multiplier': 0.90,
        'entry_threshold_delta': 4,
        'cash_ratio_delta': 0.02,
        'action': '適度減倉'
    },
    'optimistic': {
        'score_range': (55, 70),
        'label': '樂觀',
        'kelly_multiplier': 1.0,
        'entry_threshold_delta': 0,
        'cash_ratio_delta': 0.0,
        'action': '正常執行'
    },
    'neutral': {
        'score_range': (40, 55),
        'label': '中性',
        'kelly_multiplier': 1.0,
        'entry_threshold_delta': 0,
        'cash_ratio_delta': 0.0,
        'action': '保持中立'
    },
    'cautious': {
        'score_range': (25, 40),
        'label': '謹慎',
        'kelly_multiplier': 1.10,
        'entry_threshold_delta': -4,
        'cash_ratio_delta': -0.02,
        'action': '加倉試單'
    },
    'fear': {
        'score_range': (10, 25),
        'label': '恐慌',
        'kelly_multiplier': 1.20,
        'entry_threshold_delta': -8,
        'cash_ratio_delta': -0.04,
        'action': '逆向加倉'
    },
    'extreme_fear': {
        'score_range': (0, 10),
        'label': '極度恐慌',
        'kelly_multiplier': 1.30,
        'entry_threshold_delta': -12,
        'cash_ratio_delta': -0.06,
        'action': '全力抄底'
    }
}

# 原值: KELLY_MAX_POSITION = 0.065
# 新值: KELLY_MAX_POSITION = 0.072
# 說明: Kelly持倉激進提升 (+10.8%)
# 理由: TOP1策略驗證60%胜率，2.35 Sharpe，激進Kelly配置合理
KELLY_MAX_POSITION = 0.072  # v5.136: +10.8% 激進Kelly (7.2%)

# 原值: KELLY_COEFFICIENT = 1.65
# 新值: KELLY_COEFFICIENT = 1.75
# 說明: Kelly係數激進提升 (+6.1%)
KELLY_COEFFICIENT = 1.75  # v5.136: +6.1% 激進Kelly係數

# 新增: Kelly激進門檻
KELLY_MIN_WINRATE_FOR_AGGRESSIVE = 0.60  # 胜率≥60%時激進Kelly

# 原值: TRAILING_STOP_PCT = 0.05
# 新值: TRAILING_STOP_PCT = 0.04
# 說明: 尾隨止損更嚴格 (-20%)
# 理由: 基於TOP回測MAX_DRAWDOWN 4.08%，4%止損是安全邊際
TRAILING_STOP_PCT = 0.04  # v5.136: -20% 尾隨止損 (4%)

# 原值: DYNAMIC_STOP_LOSS_MAX = 0.15
# 新值: DYNAMIC_STOP_LOSS_MAX = 0.12
# 說明: 動態止損最大值優化 (-20%)
# 理由: TOP回測4.08% MAX_DRAWDOWN × 3倍安全邊際 = 12.24%
DYNAMIC_STOP_LOSS_MAX = 0.12  # v5.136: -20% 安全邊際 (12%)

# 新增: 行業自適應MACD配置 (v5.136)
SECTOR_MACD_CONFIGS_V136 = {
    '科技成長': {
        'macd_fast': 12,
        'macd_slow': 26,
        'macd_signal': 9,
        'signal_weight_multiplier': 1.8,
        'rsi_oversold': 28,
        'rsi_overbought': 72,
        'confirmation_strength': 'strong'
    },
    '新能源': {
        'macd_fast': 10,
        'macd_slow': 24,
        'macd_signal': 8,
        'signal_weight_multiplier': 1.6,
        'rsi_oversold': 30,
        'rsi_overbought': 70,
        'confirmation_strength': 'medium'
    },
    '金融': {
        'macd_fast': 14,
        'macd_slow': 28,
        'macd_signal': 10,
        'signal_weight_multiplier': 1.2,
        'rsi_oversold': 32,
        'rsi_overbought': 68,
        'confirmation_strength': 'weak'
    },
    '醫療': {
        'macd_fast': 13,
        'macd_slow': 27,
        'macd_signal': 9,
        'signal_weight_multiplier': 1.3,
        'rsi_oversold': 30,
        'rsi_overbought': 70,
        'confirmation_strength': 'medium'
    },
    '消費': {
        'macd_fast': 14,
        'macd_slow': 28,
        'macd_signal': 10,
        'signal_weight_multiplier': 1.1,
        'rsi_oversold': 35,
        'rsi_overbought': 65,
        'confirmation_strength': 'weak'
    }
}

# 新增: 實時績效儀表板啟用 (v5.136)
INTRADAY_PERFORMANCE_DASHBOARD_ENABLED = True
DASHBOARD_UPDATE_INTERVAL = 600  # 10分鐘更新一次 (盤中)

# =================== v5.136 優化總結 ===================
"""
配置變更清單 (8項):

1. MACD_RSI_SIGNAL_BOOST:              1.8 → 2.0   (+11%)
   - TOP1策略(17.1%, 60%, 2.35)權重激進

2. TECH_GROWTH_WEIGHT_BOOST:           0.40 → 0.45 (+12.5%)
   - 科技成長赛道優先級提升

3. ENTRY_QUALITY_DYNAMIC_THRESHOLDS:   新增
   - 動態入場門檻系統 (現金+胜率+風險自適應)

4. GRADIENT_TAKE_PROFIT_ENABLED:       新增
   - 梯度止盈系統 (3層:5%, 10%, 15%)

5. MULTI_PERIOD_CONFIRMATION_ENABLED:  新增
   - 多週期確認系統 (日+週+月三級共振)

6. KELLY_MAX_POSITION:                 0.065 → 0.072 (+10.8%)
   - Kelly激進持倉 (7.2%)

7. KELLY_COEFFICIENT:                  1.65 → 1.75 (+6.1%)
   - Kelly係數激進

8. 止損系統優化:
   - TRAILING_STOP_PCT:        0.05 → 0.04 (-20%)
   - DYNAMIC_STOP_LOSS_MAX:    0.15 → 0.12 (-20%)

預期改進:
✅ 推薦命中率: 0% → 50%+ (重大改進)
✅ 資本周轉: 1x → 3x (梯度止盈)
✅ 入場品質: 0/6 → 4+/6 (多週期確認)
✅ 風控品質: 基礎 → 多維度 (風險加權)
⭐ 平均持倉: 30天 → 10-20天
⭐ 執行速度: 10-30s → <8s

集成步驟:
1. 複製本文件的配置到 config.py
2. 在 stock_picker.py 中集成多週期確認
3. 在 position_manager.py 中集成梯度止盈 + Kelly動態計算
4. 在 daily_runner.py 中啟用儀表板
5. 測試命中率 (預期50%+)
6. 部署至 openclaw-deploy
"""
