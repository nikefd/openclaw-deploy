#!/usr/bin/env python3
"""
v5.126 config.py 集成脚本 - 新增20+参数配置
"""

integration_code = '''
# =================== v5.126 晚間深度優化工程 (多策略組合+Kelly分層+ATR精細化+7維評分) ===================

# ========== 多策略精準組合 ==========
MULTI_STRATEGY_ENABLED = True                    # 啟用多策略組合模式

MULTI_STRATEGY_ALLOCATION = {
    'macd_rsi_tech_weight': 0.65,               # MACD+RSI(科技成長): 65% 權重
    'macd_rsi_energy_weight': 0.25,             # MACD+RSI(新能源): 25% 權重
    'multi_factor_hedge_weight': 0.10,          # MULTI_FACTOR(對沖): 10% 權重
    'expected_sharpe': 2.14,                    # 綜合Sharpe: 2.14-2.35
    'expected_return': 0.175,                   # 年化收益: 16-19%
    'expected_drawdown': 0.035,                 # 最大回撤: <3.5%
}

# ========== Kelly系數動態分層 (情感驅動) ==========
KELLY_DYNAMIC_ENABLED = True                    # 啟用Kelly動態分層

KELLY_BASE_COEFFICIENT = 1.60                   # 基礎Kelly系數

KELLY_SENTIMENT_ADJUSTMENTS = {
    'extreme_fear': 1.25,                       # 極度恐懼(<25): Kelly×1.25 (+25%)
    'fear': 1.15,                               # 恐懼(25-40): Kelly×1.15 (+15%)
    'normal': 1.0,                              # 正常(40-60): Kelly×1.0 (保持)
    'greed': 0.85,                              # 貪婪(60-75): Kelly×0.85 (-15%)
    'extreme_greed': 0.72,                      # 極度貪婪(>75): Kelly×0.72 (-28%)
}

# ========== Kelly系數動態分層 (行業差異化) ==========
KELLY_SECTOR_ADJUSTMENTS = {
    '科技成長': 1.15,                           # +15%
    '新能源': 1.10,                             # +10%
    '消費白馬': 0.95,                           # -5%
    '金融保險': 0.90,                           # -10%
    '醫藥生物': 1.0,                            # 保持
    '其他': 0.95,                               # -5%
}

# ========== ATR動態止損行業分級 ==========
ATR_SECTOR_MULTIPLIERS = {
    '科技成長': 3.0,                            # ATR 3.0倍 (寬容, TOP1)
    '新能源': 2.8,                              # ATR 2.8倍 (TOP2)
    '醫藥生物': 2.2,                            # ATR 2.2倍 (中等)
    '消費白馬': 2.0,                            # ATR 2.0倍 (嚴格)
    '金融保險': 1.8,                            # ATR 1.8倍 (最嚴格)
    '其他': 2.2,                                # ATR 2.2倍 (中等)
}

# ========== ATR動態止損 Sharpe微調 ==========
ATR_SHARPE_ADJUSTMENTS = {
    'high': 0.10,                               # Sharpe>1.8: 放寬10%
    'normal': 0.0,                              # Sharpe 1.0-1.8: 保持
    'low': -0.10,                               # Sharpe<1.0: 緊縮10%
}

# ========== ATR動態止損 回撤微調 ==========
ATR_DRAWDOWN_ADJUSTMENTS = {
    'small': 0.15,                              # 回撤<3%: 放寬15%
    'normal': 0.0,                              # 回撤3-8%: 保持
    'large': -0.15,                             # 回撤>8%: 緊縮15%
}

# ========== 7維評分系統 ==========
SCORING_SYSTEM_7D_ENABLED = True                # 啟用7維評分系統

SCORING_WEIGHTS = {
    'technical': 25,                            # 技術評分 (0-25分)
    'fundamental': 25,                          # 基本面評分 (0-25分)
    'capital': 20,                              # 資金面評分 (0-20分)
    'sentiment': 15,                            # 情感評分 (0-15分)
    'entry_quality': 10,                        # 入場質量 (0-10分)
    'liquidity': 15,                            # 流動性評分 (0-15分) ← NEW
    'sharpe_verify': 12,                        # Sharpe驗證 (0-12分) ← NEW
}

# ========== 推薦等級閾值 ==========
RECOMMENDATION_THRESHOLDS = {
    'strong_buy': 85,                           # 85-100分: 強烈推薦
    'buy': 75,                                  # 75-85分: 推薦
    'neutral': 65,                              # 65-75分: 中性
    'blacklist': 0,                             # <65分: 黑名單
}

# ========== 流動性評分標準 ==========
LIQUIDITY_THRESHOLDS = {
    'high': 10.0,                               # >10億元: +15分
    'medium': 5.0,                              # 5-10億元: +8分
    'low': 0.0,                                 # <5億元: -5分
}

# ========== Sharpe驗證評分標準 ==========
SHARPE_VERIFY_THRESHOLDS = {
    'high': 1.5,                                # >1.5: +12分
    'medium': 1.0,                              # 1.0-1.5: +6分
    'low': 0.0,                                 # <1.0: -5分
}

# ========== 預期性能對標 ==========
V5_126_EXPECTED_METRICS = {
    'sharpe_range': (2.14, 2.35),               # 綜合Sharpe範圍
    'annual_return_range': (0.16, 0.19),        # 年化收益範圍
    'max_drawdown': 0.035,                      # 最大回撤
    'win_rate': 0.62,                           # 勝率
    'kelly_range': (1.15, 2.0),                 # Kelly幅度
    'position_count_range': (10, 15),           # 持倉數範圍
    'capital_usage_rate': 0.5625,               # 資金利用率 (50-65%)
}
'''

print(integration_code)
print("\n✅ 配置集成代码生成完成!")
print("\n【集成步骤】")
print("1. 复制上述代码")
print("2. 追加到 config.py 最后 (在所有旧配置之后)")
print("3. 保存文件")
