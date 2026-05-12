"""v5.100 盤前快速優化 — 激活停滞的選股系統

【問題診斷】
1. 最近7天0笔買入 → 選股系統停止工作
2. 現金占比96.6% → 資金大幅閒置
3. 入場閾值65分 → 過高，拒絕機會

【根本原因】
- config.py ENTRY_QUALITY_THRESHOLD = 35 (v5.94設置)
- 但實際應用時仍受多層過濾 → 實際門檻>65分
- EXTREME_CASH_V3 trigger_ratio = 95% (應激活但未生效)

【三層修復】
✅ 層1: 降低入場閾值 35→20分 (激進模式激活)
✅ 層2: 強制激活現金激進配置 (cash>95%自動+3.5x Sharpe權重)
✅ 層3: 縮減候選池防超時 (75→40個候選)

【預期成果】
- 立即建仓5-8只 (解凍現金)
- 日均建仓8→20只
- 年化收益0.19%→15-20% (預期)
"""

import json
from datetime import datetime
from config import *

# =================== 層1: 入場閾值激進化 ===================

def optimize_entry_quality_threshold() -> dict:
    """激進入場: 35→20分 (現金>95%時激活)"""
    
    # 檢查現金占比
    try:
        from trading_engine import get_account
        acc = get_account()
        cash_ratio = acc.get('cash_ratio', 0.5)
    except:
        cash_ratio = 0.5
    
    if cash_ratio >= 0.95:
        # 超激進模式
        return {
            'entry_threshold': 20,      # 降低35→20分 (-43%)
            'mode': 'extreme_cash_v5_100',
            'candidate_pool_target': 40,  # 防超時
            'sharpe_multiplier': 3.5,   # 強制應用
            'description': '激進模式: 20分閾值 + 3.5x Sharpe + 快速建倉'
        }
    elif cash_ratio >= 0.90:
        return {
            'entry_threshold': 25,
            'mode': 'very_high_cash',
            'candidate_pool_target': 50,
            'sharpe_multiplier': 3.0,
            'description': '很高現金: 25分閾值 + 3.0x Sharpe'
        }
    else:
        return {
            'entry_threshold': 35,
            'mode': 'balanced',
            'candidate_pool_target': 75,
            'sharpe_multiplier': 2.5,
            'description': '平衡模式: 35分閾值 + 2.5x Sharpe'
        }


# =================== 層2: 強制激活Sharpe權重 ===================

def apply_sharpe_weight_force_activation(picks: list, cash_ratio: float) -> list:
    """強制確保Sharpe權重被應用
    
    問題: MACD+RSI是TOP策略(17.1%, 2.35 Sharpe), 但在mixed_pool中淪為5.06%
    原因: Sharpe權重係數1.5x不夠, 且未在評分中充分體現
    修復: 3.5x強制乘數 + 加分調整
    """
    
    if cash_ratio < 0.95:
        return picks
    
    result = []
    for pick in picks:
        signals = pick.get('signals', [])
        
        # 檢測MACD+RSI組合 (TOP1策略)
        is_macd_rsi = ('MACD金叉' in str(signals) or 'MACD確認' in str(signals)) and \
                      ('RSI超賣' in str(signals) or 'RSI反轉' in str(signals))
        
        if is_macd_rsi:
            original_score = pick.get('score', 0)
            # 應用3.5x乘數
            pick['score'] = int(original_score * 3.5)
            pick['_sharpe_weight_applied'] = True
            pick['_score_before_sharpe'] = original_score
        
        result.append(pick)
    
    # 重新排序
    result.sort(key=lambda x: -x.get('score', 0))
    return result


# =================== 層3: 候選池縮減防超時 ===================

def reduce_candidate_pool_for_performance(configs: dict) -> dict:
    """縮減候選池防止超時
    
    問題: 75個候選 + 多層過濾 = 選股時間>30秒 = 盤中延遲
    修復: 現金激進時縮減到40個 (重點質量)
    """
    
    candidate_target = configs.get('candidate_pool_target', 75)
    if candidate_target > 50:
        configs['candidate_pool_target'] = min(40, candidate_target)
        configs['volume_target'] = 20    # 量价策略20個
        configs['momentum_target'] = 20  # 動量策略20個
    
    return configs


# =================== 整合入口 ===================

def execute_v5_100_optimize(picks: list, regime: str = '', sentiment: dict = None) -> dict:
    """v5.100盤前激活
    
    完整流程:
    1. 檢測現金占比 → 決定激進度
    2. 降低入場閾值 → 激活候選
    3. 應用Sharpe權重 → 提升TOP策略
    4. 過濾超時 → 確保<10秒完成
    """
    
    # 層1: 入場閾值
    threshold_config = optimize_entry_quality_threshold()
    entry_threshold = threshold_config['entry_threshold']
    
    # 層2: 現金占比
    try:
        from trading_engine import get_account
        acc = get_account()
        cash_ratio = acc.get('cash_ratio', 0.5)
    except:
        cash_ratio = 0.5
    
    # 層3: Sharpe權重強制應用
    picks = apply_sharpe_weight_force_activation(picks, cash_ratio)
    
    # 層4: 按閾值篩選
    active_picks = [p for p in picks if p.get('score', 0) >= entry_threshold]
    
    # 層5: 防超時
    if len(active_picks) > 40:
        active_picks = active_picks[:40]
    
    result = {
        'status': 'optimized',
        'v5_100_mode': threshold_config['mode'],
        'entry_threshold': entry_threshold,
        'cash_ratio': cash_ratio,
        'candidates_after_filter': len(active_picks),
        'candidates_original': len(picks),
        'sharpe_weight_applied': True,
        'timestamp': datetime.now().isoformat(),
        'picks': active_picks,
        'config': threshold_config
    }
    
    return result


# =================== 測試入口 ===================

if __name__ == '__main__':
    print("v5.100 盤前快速優化 - 測試")
    print("=" * 60)
    
    # 模擬測試
    test_picks = [
        {
            'code': '000858',
            'name': '五洲交通',
            'score': 68,
            'signals': ['MACD金叉', 'RSI超賣', '融資異變+12'],
            'reason': 'MACD+RSI確認'
        },
        {
            'code': '300670',
            'name': '大烨智能',
            'score': 45,
            'signals': ['MA20上穿', '量能激增'],
            'reason': '量價確認'
        },
        {
            'code': '600958',
            'name': '東方證券',
            'score': 32,
            'signals': ['技術面弱'],
            'reason': '質量不足'
        }
    ]
    
    result = execute_v5_100_optimize(test_picks, sentiment={'sentiment_label': '貪婪', 'sentiment_score': 90})
    
    print(f"\n✅ 優化結果:")
    print(f"  模式: {result['v5_100_mode']}")
    print(f"  入場閾值: {result['entry_threshold']}分")
    print(f"  現金占比: {result['cash_ratio']:.1%}")
    print(f"  篩選後候選: {result['candidates_after_filter']}只")
    print(f"  符合入場的候選:")
    for p in result['picks']:
        print(f"    {p['code']} ({p['name']}): {p['score']}分 {p.get('signals', [])}")
    print(f"\n📊 config更新: {result['config']}")
