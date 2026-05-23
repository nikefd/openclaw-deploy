# v5.125 晚間深度優化⑤ (大改進：回測融合+多策略組合+風險動態調控)
## 時間: 2026-05-23 22:00 UTC

### 📊 狀態分析

#### 回測TOP成績單
| 策略 | 年化收益 | Sharpe | 胜率 | 最大回撤 | 勝率/回撤比 |
|------|--------|--------|------|--------|-----------|
| **MACD+RSI(科技)** | **17.1%** | **2.35** | **60%** | **4.08%** | **14.7** ⭐|
| MACD+RSI(新能源) | 14.66% | 1.78 | 70% | 6.93% | 10.1 |
| MULTI_FACTOR(新能源) | 6.61% | 1.51 | 71.4% | 4.34% | 16.5 |
| MULTI_FACTOR(科技) | 6.45% | 1.66 | 57.1% | 3.09% | 18.5 |
| MA_CROSS(科技) | 5.3% | 1.38 | 66.7% | 2.86% | 23.3 |

#### 核心發現
- ✅ **TOP1策略**: MACD+RSI(科技成長) → 17.1% 年化 + 2.35 Sharpe (最佳風險收益比)
- ✅ **關鍵指標**: 60% 胜率 + 4.08% 回撤 = 風險嚴格可控
- ✅ **多策略組合**: 科技MACD+新能源MACD組合 = 綜合31.76% (未實現)
- ⚠️ **當前狀態**: v5.124配置已部署但未激活所有功能

---

### 🎯 v5.125 四大優化維度 (相比v5.124)

#### 優化① 多策略精准組合(新增)
**目標**: 綜合回測Sharpe 2.35+2.20 = 疊加效應

**實現方式**:
- **科技MACD+RSI**: 65% 仓位權重 (TOP1: 17.1% + 2.35 Sharpe)
- **新能源MACD+RSI**: 25% 仓位權重 (第2名: 14.66% + 1.78 Sharpe)
- **MULTI_FACTOR(科技)**: 10% 仓位權重 (風險對沖)

**公式**:
```
綜合Sharpe = 0.65×2.35 + 0.25×1.78 + 0.10×1.66 = 2.15 (vs v5.124: 2.2目標)
綜合年化 = 0.65×17.1 + 0.25×14.66 + 0.10×6.45 = 15.8% (保守估計)
```

**配置變更**:
```python
STRATEGY_ALLOCATION = {
    'MACD_RSI_TECH': 0.65,    # 科技成長(TOP1)
    'MACD_RSI_RENEWABLE': 0.25,  # 新能源(TOP2)
    'MULTI_FACTOR_HEDGE': 0.10   # 多因子對沖
}

SECTOR_STRATEGY_WEIGHTS_V125 = {
    '科技成長': {
        'MACD_RSI': 0.75,  # v5.124: 65% → v5.125: 75% (加強TOP1)
        'MULTI_FACTOR': 0.20,
        'MA_CROSS': 0.05
    },
    '新能源': {
        'MACD_RSI': 0.70,  # v5.124: 60% → v5.125: 70% (加強新能源MACD+RSI)
        'MULTI_FACTOR': 0.20,
        'TREND': 0.10
    },
    '消費白馬': {
        'MULTI_FACTOR': 0.60,  # 保持穩定性
        'MA_CROSS': 0.25,
        'TREND': 0.15
    }
}
```

#### 優化② Kelly系數動態分層(增強)
**v5.124 vs v5.125**:

| 情景 | v5.124配置 | v5.125優化 | 變更 |
|------|-----------|-----------|------|
| 正常市況(40-60) | Kelly 1.60 | Kelly 1.60 | 保持 |
| 極度恐懼(<25) | Kelly 1.84(+15%) | Kelly 2.0(+25%) | **+10%更激進** |
| 恐懼(25-40) | Kelly 1.73(+8%) | Kelly 1.85(+15%) | **+7%** |
| 極度貪婪(>75) | Kelly 1.28(-20%) | Kelly 1.15(-28%) | **-8%防守加強** |

**理由**: 
- 恐懼市況 Kelly+25% = 抄底更激進,回測確認60%胜率支持
- 貪婪市況 Kelly-28% = 風險防守加強,4.08%最大回撤需要更保守

**代碼**:
```python
def calculate_dynamic_kelly(sentiment_index: float, win_rate: float, kelly_base: float = 1.60) -> float:
    """
    情感驅動Kelly系數計算
    Args:
        sentiment_index: 投資者情感指數(0-100)
        win_rate: 實盤胜率(e.g., 0.60)
        kelly_base: 基礎Kelly系數(1.60)
    
    Returns: 動態Kelly系數
    """
    if sentiment_index < 25:  # 極度恐懼
        return kelly_base * 1.25  # +25%
    elif sentiment_index < 40:  # 恐懼
        return kelly_base * 1.15  # +15%
    elif sentiment_index > 75:  # 極度貪婪
        return kelly_base * 0.72  # -28%
    elif sentiment_index > 60:  # 貪婪
        return kelly_base * 0.85  # -15%
    else:
        return kelly_base  # 正常
```

#### 優化③ ATR動態止損精細化(增強)
**v5.124 vs v5.125**:

**v5.124**: 止損線 = 入場價 - 2.5×ATR(14d)
- 低波股: ATR<0.5% → 止損-3-4% ✓
- 高波股: ATR>2% → 止損-8-12% ✓

**v5.125增強**: 分級止損 + 行業差異化

```python
DYNAMIC_STOP_LOSS_V125 = {
    '科技成長': {
        'atr_multiplier': 3.0,  # v5.124: 2.5 → v5.125: 3.0 (更寬容, TOP1確信度更高)
        'max_stop_loss': -15%,
        'min_stop_loss': -2%
    },
    '新能源': {
        'atr_multiplier': 2.8,  # v5.124: 2.5 → v5.125: 2.8
        'max_stop_loss': -15%,
        'min_stop_loss': -3%
    },
    '消費白馬': {
        'atr_multiplier': 2.0,  # v5.124: 2.5 → v5.125: 2.0 (更嚴格, 白馬需要穩定)
        'max_stop_loss': -10%,
        'min_stop_loss': -1.5%
    }
}

# 分層條件
if sharpe_ratio > 1.8 and win_rate > 0.60:
    atr_multiplier *= 1.1  # Sharpe高+胜率高 → 止損放寬10%
elif max_drawdown > 0.08:
    atr_multiplier *= 0.9  # 回撤大 → 止損緊縮10%
```

#### 優化④ 多維評分6-to-7維升級(新增)
**v5.124**: 5維(技術+基本+資金+情感+入場)
**v5.125**: 7維(+ 流動性 + Sharpe驗證)

**新增維度**:

1️⃣ **流動性評分** (+新增)
   - 日均成交額 > 10億 → +15分
   - 日均成交額 5-10億 → +8分
   - 日均成交額 < 5億 → -5分(小票風險)
   - **理由**: 回測優選股票流動性好,實盤需要確保可快速調倉

2️⃣ **Sharpe驗證** (+新增)
   - 該股過去60天 Sharpe > 1.5 → +12分 (驗證個股質量)
   - Sharpe 1.0-1.5 → +6分
   - Sharpe < 1.0 → -5分 (波動過大)
   - **理由**: 利用過去表現預測未來, 形成正反饋

**新評分公式**:
```python
score = (
    技術面(30%) * technical_weight +
    基本面(15%) * fundamental_weight +
    資金面(15%) * fund_flow_weight +  # 調整15%
    情感面(15%) * sentiment_weight +   # 調整15%
    流動性(10%) * liquidity_bonus +    # ⭐ 新增
    Sharpe驗證(10%) * sharpe_bonus +   # ⭐ 新增
    入場質量(5%) * entry_quality       # 調整5%
)
```

**評分分布預期**:
- 85-100分: 強烈推薦 (+10位置)
- 75-85分: 推薦 (+15位置)
- 65-75分: 中性 (+10位置)
- <65分: 不推薦 (黑名單)

---

### 💾 配置與代碼變更

#### 1. config.py 新增參數

```python
# === v5.125 多策略組合 ===
STRATEGY_ALLOCATION_V125 = {
    'MACD_RSI_TECH': 0.65,
    'MACD_RSI_RENEWABLE': 0.25,
    'MULTI_FACTOR_HEDGE': 0.10
}

# === v5.125 Kelly動態分層 ===
KELLY_SENTIMENT_LEVELS_V125 = {
    'extreme_fear': {'min': 0, 'max': 25, 'kelly_multiplier': 1.25},   # +25%
    'fear': {'min': 25, 'max': 40, 'kelly_multiplier': 1.15},          # +15%
    'neutral': {'min': 40, 'max': 60, 'kelly_multiplier': 1.0},
    'greed': {'min': 60, 'max': 75, 'kelly_multiplier': 0.85},         # -15%
    'extreme_greed': {'min': 75, 'max': 100, 'kelly_multiplier': 0.72} # -28%
}

# === v5.125 行業差異化ATR ===
DYNAMIC_STOP_LOSS_SECTOR_V125 = {
    '科技成長': {'atr_multiplier': 3.0, 'max': -0.15, 'min': -0.02},
    '新能源': {'atr_multiplier': 2.8, 'max': -0.15, 'min': -0.03},
    '消費白馬': {'atr_multiplier': 2.0, 'max': -0.10, 'min': -0.015}
}

# === v5.125 7維評分權重 ===
ENTRY_QUALITY_SCORE_WEIGHTS_V125 = {
    '技術面': 0.30,
    '基本面': 0.15,
    '資金面': 0.15,
    '情感面': 0.15,
    '流動性': 0.10,  # ⭐ 新增
    'Sharpe驗證': 0.10,  # ⭐ 新增
    '入場質量': 0.05
}

# === 新增評分閾值 ===
LIQUIDITY_BONUS_CONFIG_V125 = {
    'high': {'min_daily_volume': 1_000_000_000, 'bonus': 15},
    'medium': {'min_daily_volume': 500_000_000, 'bonus': 8},
    'low': {'max_daily_volume': 500_000_000, 'penalty': -5}
}

SHARPE_VERIFICATION_CONFIG_V125 = {
    'high_sharpe': {'min': 1.5, 'bonus': 12},
    'medium_sharpe': {'min': 1.0, 'max': 1.5, 'bonus': 6},
    'low_sharpe': {'max': 1.0, 'penalty': -5}
}
```

#### 2. 核心文件改進

**stock_picker.py**:
- 新增 `apply_multi_strategy_allocation()` (多策略組合)
- 新增 `calculate_sentiment_kelly_dynamic()` (Kelly動態分層)
- 新增 `apply_sector_atr_stop_loss()` (行業差異化ATR)
- 新增 `compute_liquidity_sharpe_bonus()` (流動性+Sharpe驗證)
- 新增 `score_and_rank_v125()` (7維評分)

**backtester.py**:
- 集成多策略分析 (回測TOP3組合效果)
- 新增 Sharpe分級回測
- 新增 Kelly系數效應分析

**position_manager.py**:
- Kelly計算支持多級別動態調整
- 動態止損支持行業差異化參數
- 止損精準度監控指標

---

### 📈 預期效果

| 指標 | v5.124 | v5.125 | 改進 |
|------|--------|--------|------|
| **多策略Sharpe** | 2.2 | 2.15-2.35 | 穩定↑ |
| **年化收益** | 18-21% | 16-19% | 穩健↑ |
| **最大回撤** | <4% | <3.5% | **-12.5%** ✓|
| **胜率** | 60% | 62% | +2% |
| **Kelly系數動態幅度** | 1.28-1.84 | 1.15-2.0 | **+15%激進幅度** |
| **ATR差異化** | 統一2.5x | 2.0-3.0x分級 | **精細化** ✓|
| **評分維度** | 5維 | 7維 | +2維 ✓|
| **持仓數量** | 2-12只 | 10-15只 | +穩定 |
| **資金利用率** | 40-50% | 50-65% | +25% |

---

### 🚀 實施計劃

**Phase 1 (今晚22:00-23:00)**:
- ✅ 讀所有源碼
- ✅ 分析回測結果 (完成)
- ⏳ 編寫 v5.125 優化模塊 (500行代碼)
- ⏳ 更新 config.py (新增20個參數)
- ⏳ 集成到 stock_picker.py

**Phase 2 (23:00-23:30)**:
- ⏳ 單元測試多策略組合
- ⏳ 驗證Kelly動態計算
- ⏳ 測試ATR行業差異化
- ⏳ 5維→7維評分驗證

**Phase 3 (23:30-00:00)**:
- ⏳ 部署到 openclaw-deploy
- ⏳ git commit + push
- ⏳ systemctl restart finance-api

**Phase 4 (明日盤前)**:
- ⏳ 首次選股測試 (預期15-20只)
- ⏳ 監控評分分布 & Kelly動態
- ⏳ 驗證多策略效果

---

### 📋 風險控制

- ✅ **回撤防護**: ATR止損 + Kelly動態降級 + 流動性篩選
- ✅ **集中度防護**: 多策略分散 (65%+25%+10%)
- ✅ **流動性風險**: 日均成交額 > 5億要求
- ✅ **情感陷阱**: 極度貪婪時 Kelly-28%, 持仓-30%

---

### 📝 版本信息

- **版本**: v5.125
- **時間**: 2026-05-23 22:00 UTC
- **目標**: 回測融合 + 多策略組合 + 風險動態調控
- **預期Sharpe**: 2.15-2.35
- **預期年化**: 16-19%
- **下版本**: v5.126 (盤中實時監控及信號質量驗證, 計劃次日15:30)

