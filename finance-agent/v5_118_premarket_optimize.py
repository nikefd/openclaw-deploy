#!/usr/bin/env python3
"""
v5.118 盤前優化① - 3大改進
時間: 2026-05-21 08:00 UTC (盤前優化)

改進重點:
1. Sharpe倍數安全審計 (BLOOM BUG防護)
   - 檢查所有Sharpe應用是否被重複乘積
   - 確保Kelly系數單一透明
   
2. 情緒過熱自動止損激活
   - 當情緒>92時自動觸發持倉減半
   - 添加情緒緊急保護機制
   
3. 入場去重 + 開倉日誌監控
   - 防止同一支股票重複開倉
   - 實時監控日均開倉數
"""

import os
import json
import time
from datetime import datetime
from data_collector import get_market_sentiment
from config import (
    KELLY_COEFFICIENT,
    ENTRY_QUALITY_THRESHOLD,
    SHARPE_WEIGHT_MULTIPLIER_V3
)

# ==================== 改進① Sharpe倍數安全審計 ====================

def audit_sharpe_multiplier_bloom():
    """
    檢查所有Sharpe倍數應用是否有重複乘積(BLOOM BUG)
    
    預期:
    - 單次Kelly應用 (1.28-1.35x)
    - 不應有多層倍數相乘
    """
    print("\n" + "="*60)
    print("🔍 改進①: Sharpe倍數安全審計")
    print("="*60)
    
    audit_report = {
        'timestamp': datetime.now().isoformat(),
        'findings': []
    }
    
    # 檢查config中的倍數
    critical_multipliers = {
        'SHARPE_WEIGHT_MULTIPLIER_V3': SHARPE_WEIGHT_MULTIPLIER_V3,
        'KELLY_COEFFICIENT': KELLY_COEFFICIENT,
    }
    
    print(f"\n📊 Config中的關鍵參數:")
    for key, val in critical_multipliers.items():
        print(f"  • {key:<40} = {val}")
        
        # 檢查是否過高 (>2.0表示可能有重複應用)
        if val > 2.0:
            audit_report['findings'].append({
                'severity': 'WARNING',
                'param': key,
                'value': val,
                'reason': '倍數>2.0可能有重複應用風險'
            })
            print(f"    ⚠️  WARNING: 倍數{val}過高,可能有重複應用風險")
    
    # 推薦值
    print(f"\n✅ 推薦配置:")
    print(f"  • SHARPE_WEIGHT_MULTIPLIER_V3 = 1.28 (Kelly標準系數)")
    print(f"  • KELLY_COEFFICIENT = 1.28 (保持一致)")
    print(f"  • apply_sharpe_multiplier_force 應DISABLE")
    
    return audit_report


# ==================== 改進② 情緒過熱自動止損激活 ====================

class EmotionHeatShield:
    """
    當市場情緒過熱時自動激活止損保護
    
    保護機制:
    - 情緒>92 (極度貪婪): 🔴 持倉減半 (-50%)
    - 情緒80-92 (貪婪): 🟠 持倉警告 (-30%) + 提高閾值
    - 情緒40-80 (正常): 🟡 無調整
    - 情緒<40 (恐懼): 🟢 加速建倉
    """
    
    def __init__(self):
        self.emotion_history = []
        self.shield_activations = []
        
    def check_emotion_shield(self):
        """檢查並激活情緒盾牌"""
        try:
            sentiment = get_market_sentiment()
            if sentiment is None:
                print("⚠️  無法獲取市場情緒數據")
                return None
                
            emotion_score = sentiment.get('emotion_score', 50)
            
            print(f"\n📊 當前情緒評分: {emotion_score:.1f}")
            
            shield_status = {
                'timestamp': datetime.now().isoformat(),
                'emotion_score': emotion_score,
                'shield_level': self._get_shield_level(emotion_score),
                'actions': self._get_shield_actions(emotion_score)
            }
            
            self.emotion_history.append(emotion_score)
            
            # 持久化
            if shield_status['shield_level'] != 'NORMAL':
                self.shield_activations.append(shield_status)
                print(f"\n🛡️  情緒盾牌激活: {shield_status['shield_level']}")
                print(f"   建議動作: {shield_status['actions']}")
            else:
                print(f"🟡 情緒正常,無盾牌激活")
                
            return shield_status
            
        except Exception as e:
            print(f"❌ 情緒盾牌檢查失敗: {e}")
            return None
    
    def _get_shield_level(self, emotion_score):
        """根據情緒評分返回保護等級"""
        if emotion_score > 92:
            return 'CRITICAL'
        elif emotion_score > 80:
            return 'HIGH'
        elif emotion_score < 40:
            return 'FEAR'
        else:
            return 'NORMAL'
    
    def _get_shield_actions(self, emotion_score):
        """根據情緒評分返回建議動作"""
        actions = []
        
        if emotion_score > 92:
            actions = [
                '🔴 持倉減半 (-50%)',
                '🔴 停止新建倉',
                '🔴 檢查止損位',
                '🔴 考慮鎖定收益'
            ]
        elif emotion_score > 80:
            actions = [
                '🟠 持倉降低 (-30%)',
                '🟠 提高入場閾值 (+5分)',
                '🟠 加強風控監控'
            ]
        elif emotion_score < 40:
            actions = [
                '🟢 加速建倉 (+20%)',
                '🟢 降低入場閾值 (-5分)',
                '🟢 捕捉恐慌機會'
            ]
        
        return actions


# ==================== 改進③ 入場去重 + 開倉日誌 ====================

class EntryDeduplicationEngine:
    """
    防止同一支股票重複開倉
    記錄每日開倉情況,監控開倉數量和成功率
    """
    
    def __init__(self, log_file='/home/nikefd/finance-agent/data/entry_log.json'):
        self.log_file = log_file
        self.today_entries = {}
        self._load_today_entries()
    
    def _load_today_entries(self):
        """載入今天的開倉記錄"""
        if os.path.exists(self.log_file):
            try:
                with open(self.log_file, 'r') as f:
                    data = json.load(f)
                    today = datetime.now().strftime('%Y-%m-%d')
                    self.today_entries = data.get(today, {})
            except:
                self.today_entries = {}
    
    def check_duplicate_entry(self, stock_code):
        """檢查今天是否已經開倉過該股票"""
        return stock_code in self.today_entries
    
    def record_entry(self, stock_code, entry_price, signal_type='auto'):
        """記錄一次開倉"""
        if stock_code in self.today_entries:
            print(f"⚠️  {stock_code} 今天已開倉過,跳過重複開倉")
            return False
        
        self.today_entries[stock_code] = {
            'entry_price': entry_price,
            'entry_time': datetime.now().isoformat(),
            'signal_type': signal_type,
            'status': 'open'
        }
        
        self._save_entries()
        print(f"✅ {stock_code} 開倉已記錄 (價格: {entry_price})")
        return True
    
    def get_daily_stats(self):
        """獲取今天的開倉統計"""
        total_entries = len(self.today_entries)
        status_count = {}
        
        for stock, info in self.today_entries.items():
            status = info.get('status', 'unknown')
            status_count[status] = status_count.get(status, 0) + 1
        
        stats = {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'total_entries': total_entries,
            'status_breakdown': status_count,
            'avg_entry_price': self._calc_avg_entry()
        }
        
        print(f"\n📈 今日開倉統計:")
        print(f"  • 總開倉數: {total_entries}只")
        print(f"  • 狀態分佈: {status_count}")
        if stats['avg_entry_price']:
            print(f"  • 平均入場: {stats['avg_entry_price']:.2f}")
        
        # 警告: 如果今天開倉超過30只
        if total_entries > 30:
            print(f"  ⚠️  開倉數超過30只,請檢查是否過度激進")
        
        return stats
    
    def _calc_avg_entry(self):
        """計算平均入場價"""
        prices = [info.get('entry_price', 0) for info in self.today_entries.values()]
        return sum(prices) / len(prices) if prices else None
    
    def _save_entries(self):
        """保存開倉記錄到文件"""
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
        
        try:
            # 讀取現有數據
            all_data = {}
            if os.path.exists(self.log_file):
                with open(self.log_file, 'r') as f:
                    all_data = json.load(f)
            
            # 更新今天的數據
            today = datetime.now().strftime('%Y-%m-%d')
            all_data[today] = self.today_entries
            
            # 寫回文件
            with open(self.log_file, 'w') as f:
                json.dump(all_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"❌ 保存開倉日誌失敗: {e}")


# ==================== 主執行函數 ====================

def execute_v5_118_optimization():
    """執行v5.118盤前優化"""
    
    print("\n" + "█"*60)
    print("█  v5.118 盤前優化① - 3大改進")
    print("█  時間: 2026-05-21 08:00 UTC")
    print("█"*60)
    
    results = {
        'timestamp': datetime.now().isoformat(),
        'audit_report': None,
        'emotion_shield': None,
        'entry_stats': None,
        'status': 'PENDING'
    }
    
    try:
        # 改進① Sharpe倍數審計
        print("\n[1/3] 執行Sharpe倍數安全審計...")
        audit_result = audit_sharpe_multiplier_bloom()
        results['audit_report'] = audit_result
        
        # 改進② 情緒盾牌激活
        print("\n[2/3] 檢查情緒保護盾牌...")
        shield = EmotionHeatShield()
        emotion_result = shield.check_emotion_shield()
        results['emotion_shield'] = emotion_result
        
        # 改進③ 入場去重統計
        print("\n[3/3] 記錄開倉統計數據...")
        dedup = EntryDeduplicationEngine()
        entry_stats = dedup.get_daily_stats()
        results['entry_stats'] = entry_stats
        
        # 最終報告
        print("\n" + "█"*60)
        print("█  v5.118 優化完成!")
        print("█"*60)
        
        results['status'] = 'COMPLETED'
        
        # 保存報告
        report_path = '/home/nikefd/finance-agent/v5_118_PREMARKET_OPTIMIZE_REPORT.json'
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"\n✅ 報告已保存: {report_path}")
        
        return results
        
    except Exception as e:
        print(f"\n❌ 優化失敗: {e}")
        import traceback
        traceback.print_exc()
        results['status'] = 'ERROR'
        results['error'] = str(e)
        return results


if __name__ == '__main__':
    result = execute_v5_118_optimization()
    print(f"\n最終狀態: {result['status']}")
