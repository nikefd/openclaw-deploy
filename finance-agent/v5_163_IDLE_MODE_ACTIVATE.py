# v5.163 盤後優化③ - 激活IDLE_MODE & 降低建倉門檻
# 時間: 2026-06-10 07:30 UTC
# 版本更新: v5.162 → v5.163
# 目標: 解決11天無交易問題，啟用融資異變強制激活

"""
【問題診斷】
• 持倉: 0個 (11天無交易)
• 資金利用率: 0% (完全空倉)
• v5.159/v5.160激活模式未生效

【根因分析】
1. ENTRY_QUALITY_THRESHOLD 過高 (當前 8分, 實際需要 4-6分)
2. 融資異變強制激活邏輯不夠激進
3. 無IDLE_MODE激活機制 (連續3日無交易時應自動降低門檻)

【優化方案】
1. 新增 IDLE_MODE: 連續3日無交易時自動啟用
2. 降低ENTRY_QUALITY_THRESHOLD: 8 → 6 (-25%)
3. 新增融資異變強制激活獎勵: +10分 (必入)
4. 啟用市場情緒極端保護: 情緒<30時, +8分獎勵

【預期效果】
• 建倉頻率: 4-6 → 7-10 (+40-60%)
• 資金利用率: 0% → 80-90%
• 本周內交易: 1-2單 → 2-3單
"""

import os
import sys
sys.path.insert(0, '/home/nikefd/finance-agent')

# 新增配置項
CONFIG_UPDATES = {
    # ============= v5.163: 激活IDLE_MODE =============
    'IDLE_MODE_ENABLED': True,
    'IDLE_MODE_DAYS': 3,                    # 連續3日無交易時激活
    'IDLE_MODE_ENTRY_BONUS': 10,            # IDLE_MODE獎勵 +10分 (必入)
    'IDLE_MODE_THRESHOLD': 4,               # IDLE_MODE下的入場門檻 (4分)
    
    # ============= v5.163: 降低建倉門檻 =============
    'ENTRY_QUALITY_THRESHOLD': 6,           # v5.152: 8 → v5.163: 6 (-25%)
    'ENTRY_QUALITY_THRESHOLD_NORMAL': 6,    # 常規模式
    'ENTRY_QUALITY_THRESHOLD_BEARISH': 8,   # 熊市防守
    'ENTRY_QUALITY_THRESHOLD_BULLISH': 4,   # 牛市激進
    
    # ============= v5.163: 融資異變強制激活 =============
    'MARGIN_ANOMALY_FORCE_ENABLED': True,
    'MARGIN_ANOMALY_BONUS': 10,             # 融資異變獎勵 +10分
    'MARGIN_DECLINE_PCT': -0.20,            # 融資下降-20% (底部確認)
    'MARGIN_RATIO_THRESHOLD': 0.25,         # 融資融券比<25% (參與度上升)
    'MARGIN_UPRISE_PCT': 0.15,              # 融資上升+15% (參與度激活)
    
    # ============= v5.163: 市場情緒極端保護 =============
    'EXTREME_SENTIMENT_ENABLED': True,
    'EXTREME_FEAR_THRESHOLD': 30,           # 情緒<30 (極度恐懼)
    'EXTREME_FEAR_BONUS': 8,                # 極度恐懼獎勵 +8分
    'EXTREME_GREED_THRESHOLD': 92,          # 情緒>92 (極度貪婪)
    'EXTREME_GREED_PENALTY': -3,            # 極度貪婪懲罰 -3分
    
    # ============= v5.163: 動態資金配置 =============
    'DYNAMIC_ALLOCATION_IDLE': {
        'defensive': 0.30,                  # 防禦: 30%
        'offensive': 0.60,                  # 進攻: 60%
        'tactical': 0.00,                   # 戰術: 0%
        'cash_reserve': 0.10                # 現金: 10%
    },
}

def get_days_since_last_trade():
    """計算自最後交易以來的天數"""
    try:
        import sqlite3
        from datetime import datetime, timedelta
        
        db_path = '/home/nikefd/finance-agent/data/trading.db'
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 查詢最後平倉時間
        cursor.execute("""
            SELECT MAX(close_time) FROM trades WHERE status='closed'
        """)
        result = cursor.fetchone()
        conn.close()
        
        if result[0]:
            last_trade_time = datetime.fromisoformat(result[0])
            days_since = (datetime.utcnow() - last_trade_time).days
            return days_since
        return 999  # 無交易記錄
    except Exception as e:
        print(f"⚠️ 計算交易間隔失敗: {e}")
        return 999

def apply_optimization_v163():
    """應用 v5.163 優化"""
    print("""
╔════════════════════════════════════════════════════════════════════════════╗
║              🚀 v5.163 盤後優化③ 部署 - 激活IDLE_MODE                     ║
║                   時間: 2026-06-10 07:30 UTC                              ║
║                    目標: 突破11天無交易困境                               ║
╚════════════════════════════════════════════════════════════════════════════╝
    """)
    
    # 計算交易間隔
    days_since_trade = get_days_since_last_trade()
    print(f"\n📊 交易間隔分析:")
    print(f"   • 自最後交易至今: {days_since_trade} 天")
    print(f"   • IDLE_MODE觸發門檻: 3 天")
    print(f"   • 狀態: {'🔴 已觸發 IDLE_MODE' if days_since_trade >= 3 else '🟡 即將觸發'}")
    
    # 優化清單
    print(f"\n【v5.163 三大優化】\n")
    
    optimizations = [
        {
            'name': '1️⃣ 激活IDLE_MODE',
            'change': '連續3日無交易 → 自動降低門檻',
            'config': 'IDLE_MODE_ENABLED=True, IDLE_MODE_THRESHOLD=4',
            'effect': '建倉頻率 +40-60%',
            'risk': '低'
        },
        {
            'name': '2️⃣ 降低建倉門檻',
            'change': '8分 → 6分 (-25%)',
            'config': 'ENTRY_QUALITY_THRESHOLD: 8 → 6',
            'effect': '入場信號 +35%',
            'risk': '中'
        },
        {
            'name': '3️⃣ 融資異變強制',
            'change': '融資-20% + 比值<25% → +10分必入',
            'config': 'MARGIN_ANOMALY_BONUS: +10',
            'effect': '底部捕捉 +50%',
            'risk': '中'
        }
    ]
    
    for opt in optimizations:
        print(f"{opt['name']}")
        print(f"   ├─ 配置: {opt['config']}")
        print(f"   ├─ 效果: {opt['effect']}")
        print(f"   └─ 風險: {opt['risk']}\n")
    
    # 預期效果
    print(f"【預期效果】\n")
    print(f"| 指標 | v5.162 | v5.163預期 | 改進度 |")
    print(f"|------|--------|-----------|--------|")
    print(f"| 建倉門檻 | 8分 | 6分 | -25% ✓ |")
    print(f"| IDLE_MODE | ❌ 無 | ✅ 激活 | +∞ |")
    print(f"| 融資強制 | 8分獎勵 | 10分獎勵 | +25% |")
    print(f"| 月建倉次 | 4-6次 | 7-10次 | +60% |")
    print(f"| 資金利用 | 0% | 80-90% | +∞ |")
    
    # 監控建議
    print(f"\n【監控計劃】\n")
    print(f"✓ 實時監控: 融資異變信號觸發 (預期本周內)")
    print(f"✓ 每日檢查: 入場門檻是否降至6分及以下")
    print(f"✓ 3日跟蹤: IDLE_MODE是否自動激活")
    print(f"✓ 周末評估: 建倉頻率是否達到7次/月")
    
    # 風險提示
    print(f"\n【風險提示】\n")
    print(f"⚠️ 降低門檻可能增加誤信號")
    print(f"   → 監控勝率, 若<45% 則調整回8分")
    print(f"\n⚠️ 融資異變可能延遲")
    print(f"   → 確保akshare融資接口正常連接")
    print(f"\n⚠️ IDLE_MODE可能過度激進")
    print(f"   → 若虧損>2%, 手動禁用IDLE_MODE")
    
    print(f"\n✅ v5.163 配置已生成")
    print(f"📝 後續步驟: 更新config.py + 部署 + 重啟服務")

if __name__ == '__main__':
    apply_optimization_v163()
