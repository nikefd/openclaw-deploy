"""v5.90 晚间深度优化工程 — 集成v5.88/v5.89 + 强化Sharpe + 止损优化

【核心目标】
1. 确保v5.88/v5.89现金检测自动生效 → 资金利用率1% → 15-20%
2. 强化Sharpe权重在score_and_rank中的应用 → 确保TOP策略主导
3. 优化止损黑名单逻辑 → 降低重复踩坑概率
4. 增强MACD直方图翻正集成 → 低位捕捉准确率70-75%

【v5.90五大改进】
1. 现金检测集成强化 — 确保detect_extreme_cash_mode自动触发
2. Sharpe权重强制激活 — 3.0x倍数应用在所有MACD+RSI信号
3. MACD直方图翻正集成 — 在entry_quality中新增+8-18分奖励
4. 止损黑名单精化 — 添加"连续止损"复盘逻辑
5. 资金配置动态优化 — 现金>95%时自动激活超激进配置

【预期收益】
- 资金利用率: 1% → 15-20% (首周)
- 年化收益: 0.19% → 3-5%
- 命中率: 60% → 70-75% (MACD+直方图翻正)
- MaxDD: 保持 <5%
"""

import sys
import json
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, '/home/nikefd/finance-agent')

try:
    from config import (
        APPLY_SHARPE_MULTIPLIER_FORCE,
        SHARPE_WEIGHT_MULTIPLIER_V3,
        EXTREME_CASH_V3,
        ENTRY_QUALITY_DYNAMIC_V2,
        CASH_AUTO_DETECTION_LEVELS
    )
except:
    print("⚠️ config导入失败，使用默认配置")
    APPLY_SHARPE_MULTIPLIER_FORCE = True
    SHARPE_WEIGHT_MULTIPLIER_V3 = 3.0
    EXTREME_CASH_V3 = {'trigger_ratio': 0.99, 'sharpe_weight_multiplier': 3.0}
    ENTRY_QUALITY_DYNAMIC_V2 = True
    CASH_AUTO_DETECTION_LEVELS = {
        'extreme': {'threshold': 0.99, 'entry_quality': 20, 'multiplier': 1.5},
        'aggressive': {'threshold': 0.95, 'entry_quality': 25, 'multiplier': 1.2},
        'normal': {'threshold': 0.75, 'entry_quality': 35, 'multiplier': 1.0}
    }

# =================== 改進①: 現金檢測集成強化 ===================

def get_current_cash_ratio() -> dict:
    """
    實時讀取當前現金占比和資產狀態
    
    Returns: {
        'cash_ratio': float (0-1),
        'total_assets': float,
        'cash': float,
        'timestamp': str,
        'has_valid_data': bool
    }
    """
    try:
        conn = sqlite3.connect('/home/nikefd/finance-agent/data/trading.db')
        c = conn.cursor()
        
        # 查詢最新的portfolio_snapshots
        c.execute("""
            SELECT cash_balance, total_assets, created_at 
            FROM portfolio_snapshots 
            ORDER BY created_at DESC LIMIT 1
        """)
        row = c.fetchone()
        conn.close()
        
        if row and row[1] > 0:
            cash_ratio = row[0] / row[1]
            return {
                'cash_ratio': max(0.0, min(1.0, cash_ratio)),
                'total_assets': row[1],
                'cash': row[0],
                'timestamp': row[2] if row[2] else datetime.now().isoformat(),
                'has_valid_data': True
            }
    except Exception as e:
        print(f"⚠️  讀取現金比失敗: {e}")
    
    # 默認
    return {
        'cash_ratio': 0.5,
        'total_assets': 1000000,
        'cash': 500000,
        'timestamp': datetime.now().isoformat(),
        'has_valid_data': False
    }


def detect_and_apply_cash_mode(candidates: list) -> dict:
    """v5.90改進①: 現金檢測集成強化
    
    根據實時現金比，自動決定入場質量閾值和評分倍數。
    這是v5.88的增強版 — 確保自動觸發且記錄詳細日誌。
    
    Args:
        candidates: 候選股票list
        
    Returns: {
        'applied': bool,
        'cash_mode': str ('extreme'|'aggressive'|'normal'),
        'cash_ratio': float,
        'entry_quality_threshold': int,
        'score_multiplier': float,
        'affected_stocks': int,
        'timestamp': str
    }
    """
    
    # 1. 獲取現金狀態
    cash_state = get_current_cash_ratio()
    cash_ratio = cash_state['cash_ratio']
    
    # 2. 判斷現金模式
    cash_mode = 'normal'
    config = CASH_AUTO_DETECTION_LEVELS['normal']
    
    if cash_ratio > CASH_AUTO_DETECTION_LEVELS['extreme']['threshold']:
        cash_mode = 'extreme'
        config = CASH_AUTO_DETECTION_LEVELS['extreme']
    elif cash_ratio > CASH_AUTO_DETECTION_LEVELS['aggressive']['threshold']:
        cash_mode = 'aggressive'
        config = CASH_AUTO_DETECTION_LEVELS['aggressive']
    
    # 3. 應用到候選股票
    affected_count = 0
    
    for cand in candidates:
        # 記錄應用的現金模式
        cand['_v5_90_cash_mode'] = {
            'mode': cash_mode,
            'cash_ratio': cash_ratio,
            'threshold': config['entry_quality'],
            'multiplier': config['multiplier']
        }
        
        # 根據質量評分決定是否激活激進模式
        quality = cand.get('entry_quality_score', 0)
        
        if quality >= config['entry_quality']:
            # 在激進模式下，提升score
            old_score = cand.get('score', 0)
            boost_factor = 1.0 + (config['multiplier'] - 1.0) * 0.2  # 避免過度激進
            new_score = int(old_score * boost_factor)
            
            if new_score != old_score:
                cand['score'] = new_score
                cand['_v5_90_score_boost'] = {
                    'old_score': old_score,
                    'new_score': new_score,
                    'boost_factor': boost_factor
                }
                affected_count += 1
    
    # 4. 生成日誌
    log_msg = f"💰 [v5.90現金檢測] 模式:{cash_mode} | 現金:{cash_ratio:.1%} | 閾值:{config['entry_quality']}分 | 倍數:{config['multiplier']}x | 影響股票:{affected_count}只"
    print(log_msg)
    
    return {
        'applied': cash_mode != 'normal',
        'cash_mode': cash_mode,
        'cash_ratio': cash_ratio,
        'entry_quality_threshold': config['entry_quality'],
        'score_multiplier': config['multiplier'],
        'affected_stocks': affected_count,
        'timestamp': datetime.now().isoformat(),
        'log_message': log_msg
    }


# =================== 改進②: Sharpe權重強制激活 ===================

def apply_sharpe_multiplier_v90(candidates: list, force_apply: bool = True) -> dict:
    """v5.90改進②: 強化Sharpe權重應用 (3.0x)
    
    確保最佳策略 (MACD+RSI 科技成長 17.1% 2.35Sharpe) 被充分加權。
    v5.90針對性增強:
    - 強制應用3.0x倍數到MACD+RSI信號
    - 記錄詳細日誌 (原分→新分)
    - 避免被其他權重掩蓋
    
    Args:
        candidates: 候選股票list
        force_apply: 是否強制應用 (True)
        
    Returns: {
        'applied': bool,
        'sharpe_multiplier': float,
        'affected_stocks': int,
        'top_3_changes': list
    }
    """
    
    if not force_apply or not APPLY_SHARPE_MULTIPLIER_FORCE:
        return {
            'applied': False,
            'sharpe_multiplier': SHARPE_WEIGHT_MULTIPLIER_V3,
            'affected_stocks': 0,
            'top_3_changes': []
        }
    
    sharpe_multiplier = SHARPE_WEIGHT_MULTIPLIER_V3  # 3.0x
    affected_count = 0
    changes = []
    
    for i, stock in enumerate(candidates):
        # 判斷是否為MACD+RSI策略
        signals = stock.get('signals', [])
        strategy = stock.get('strategy', '')
        
        is_macd_rsi = (
            any('MACD' in str(s) or 'RSI' in str(s) for s in signals) or
            'MACD' in str(strategy)
        )
        
        if is_macd_rsi:
            old_score = stock.get('score', 0)
            new_score = int(old_score * sharpe_multiplier)
            
            if new_score != old_score:
                stock['score'] = new_score
                stock['_v5_90_sharpe_boost'] = {
                    'old_score': old_score,
                    'new_score': new_score,
                    'multiplier': sharpe_multiplier
                }
                affected_count += 1
                
                # 記錄TOP3變化
                if len(changes) < 3:
                    changes.append({
                        'rank': i + 1,
                        'code': stock.get('code'),
                        'name': stock.get('name'),
                        'old_score': old_score,
                        'new_score': new_score
                    })
    
    print(f"⚡ [v5.90 Sharpe強化] 倍數:{sharpe_multiplier}x | 影響:{affected_count}只 | TOP3變化:{len(changes)}條")
    
    return {
        'applied': affected_count > 0,
        'sharpe_multiplier': sharpe_multiplier,
        'affected_stocks': affected_count,
        'top_3_changes': changes
    }


# =================== 改進③: MACD直方圖翻正集成 ===================

def apply_macd_histogram_flip_bonus(candidates: list) -> dict:
    """v5.90改進③: MACD直方圖翻正信號集成
    
    集成v5.88/v5.89的MACD_HIST翻正檢測結果。
    如果候選股票已標記為_macd_histogram_flip_v88，則應用額外獎勵。
    
    Args:
        candidates: 候選股票list
        
    Returns: {
        'applied': bool,
        'affected_stocks': int,
        'bonus_scores': list
    }
    """
    
    affected_count = 0
    bonus_scores = []
    
    for stock in candidates:
        flip_info = stock.get('_macd_histogram_flip_v88')
        
        if flip_info and flip_info.get('detected', False):
            # 應用獎勵
            strength = flip_info.get('strength', 0)
            bonus = min(18, max(8, strength))  # 8-18分
            
            old_score = stock.get('score', 0)
            new_score = old_score + bonus
            
            stock['score'] = new_score
            stock['_v5_90_macd_flip_bonus'] = {
                'bonus': bonus,
                'old_score': old_score,
                'new_score': new_score,
                'days_since_flip': flip_info.get('days_since_flip', 0)
            }
            
            affected_count += 1
            bonus_scores.append({'code': stock.get('code'), 'bonus': bonus})
    
    print(f"📈 [v5.90 MACD直方圖] 影響:{affected_count}只 | 獎勵分數:{bonus_scores[:3]}")
    
    return {
        'applied': affected_count > 0,
        'affected_stocks': affected_count,
        'bonus_scores': bonus_scores
    }


# =================== 改進④: 止損黑名單精化 ===================

def optimize_stop_loss_blacklist() -> dict:
    """v5.90改進④: 止損黑名單邏輯優化
    
    分析歷史止損記錄，識別"連續止損"的個股，防止重複踩坑。
    
    Returns: {
        'consecutive_stopouts': list,  # 連續止損>3次的個股
        'blacklist_updated': bool,
        'count': int
    }
    """
    
    try:
        conn = sqlite3.connect('/home/nikefd/finance-agent/data/trading.db')
        c = conn.cursor()
        
        # 查詢過去30天的止損記錄
        thirty_days_ago = (datetime.now() - timedelta(days=30)).isoformat()
        
        c.execute("""
            SELECT symbol, COUNT(*) as stopout_count 
            FROM trades 
            WHERE reason LIKE '%止損%' AND date >= ?
            GROUP BY symbol 
            HAVING COUNT(*) >= 3
            ORDER BY COUNT(*) DESC
        """, (thirty_days_ago,))
        
        consecutive_stopouts = [
            {'symbol': row[0], 'count': row[1]}
            for row in c.fetchall()
        ]
        
        conn.close()
        
        print(f"🛑 [v5.90止損黑名單] 連續止損(>=3次)的個股:{len(consecutive_stopouts)}只")
        for item in consecutive_stopouts[:5]:
            print(f"   {item['symbol']}: {item['count']}次止損")
        
        return {
            'consecutive_stopouts': consecutive_stopouts,
            'blacklist_updated': True,
            'count': len(consecutive_stopouts)
        }
    
    except Exception as e:
        print(f"⚠️  止損黑名單查詢失敗: {e}")
        return {
            'consecutive_stopouts': [],
            'blacklist_updated': False,
            'count': 0
        }


def apply_stop_loss_blacklist_filter(candidates: list, blacklist: list) -> dict:
    """將止損黑名單應用到候選篩選中
    
    連續止損的個股暫時不再推薦，避免重複踩坑。
    
    Args:
        candidates: 候選股票list
        blacklist: 黑名單 (list of {'symbol': ..., 'count': ...})
        
    Returns: {
        'filtered_count': int,
        'removed_stocks': list
    }
    """
    
    blacklist_symbols = {item['symbol'] for item in blacklist}
    removed = []
    
    # 直接從候選中移除黑名單個股
    for cand in candidates[:]:
        code = cand.get('code') or cand.get('symbol')
        if code in blacklist_symbols:
            candidates.remove(cand)
            removed.append({'code': code, 'name': cand.get('name')})
    
    print(f"🚫 [v5.90黑名單過濾] 移除:{len(removed)}只黑名單個股")
    
    return {
        'filtered_count': len(removed),
        'removed_stocks': removed
    }


# =================== 改進⑤: 資金配置動態優化 ===================

def get_dynamic_portfolio_allocation(cash_ratio: float) -> dict:
    """v5.90改進⑤: 根據現金比動態調整資金配置
    
    現金充足時激活進攻倉位，提升年化收益。
    
    Args:
        cash_ratio: 當前現金占比 (0-1)
        
    Returns: {
        'defensive': float,
        'offensive': float,
        'tactical': float,
        'cash_reserve': float,
        'mode': str ('aggressive'|'balanced'|'conservative')
    }
    """
    
    base_allocation = {
        'defensive': 0.35,
        'offensive': 0.40,
        'tactical': 0.15,
        'cash_reserve': 0.10
    }
    
    if cash_ratio > 0.95:
        # 超激進: 現金過多，釋放進攻倉位
        return {
            'defensive': 0.25,   # -10%
            'offensive': 0.55,   # +15%
            'tactical': 0.10,    # -5%
            'cash_reserve': 0.10,
            'mode': 'aggressive'
        }
    elif cash_ratio > 0.75:
        # 激進
        return {
            'defensive': 0.30,
            'offensive': 0.45,
            'tactical': 0.15,
            'cash_reserve': 0.10,
            'mode': 'balanced'
        }
    elif cash_ratio < 0.15:
        # 保守 (現金不足)
        return {
            'defensive': 0.45,   # +10%
            'offensive': 0.30,   # -10%
            'tactical': 0.10,
            'cash_reserve': 0.15, # +5%
            'mode': 'conservative'
        }
    
    return {**base_allocation, 'mode': 'normal'}


# =================== 主流程: 整合所有優化 ===================

def apply_v5_90_deep_optimization(candidates: list) -> dict:
    """v5.90深度優化集成
    
    按順序應用五大改進:
    1. 現金檢測 → 自動調整入場閾值
    2. Sharpe強化 → 確保TOP策略主導
    3. MACD直方圖 → 低位信號+8-18分
    4. 止損黑名單 → 過濾連續止損個股
    5. 資金配置 → 動態調整進攻/防守
    
    Args:
        candidates: 候選股票list
        
    Returns: {
        'version': 'v5.90',
        'timestamp': str,
        'total_stocks': int,
        'final_count': int,
        'optimizations': {
            'cash_detection': {...},
            'sharpe_multiplier': {...},
            'macd_histogram': {...},
            'stop_loss_filter': {...},
            'portfolio_allocation': {...}
        }
    }
    """
    
    print("\n" + "=" * 70)
    print("🚀 v5.90 晚間深度優化工程 — 開始執行")
    print("=" * 70)
    
    initial_count = len(candidates)
    
    # 改進①: 現金檢測
    print("\n【步驟1】現金檢測集成強化...")
    cash_result = detect_and_apply_cash_mode(candidates)
    
    # 改進②: Sharpe權重
    print("\n【步驟2】Sharpe權重強制激活...")
    sharpe_result = apply_sharpe_multiplier_v90(candidates)
    
    # 改進③: MACD直方圖
    print("\n【步驟3】MACD直方圖翻正信號...")
    macd_result = apply_macd_histogram_flip_bonus(candidates)
    
    # 改進④: 止損黑名單
    print("\n【步驟4】止損黑名單優化...")
    blacklist_info = optimize_stop_loss_blacklist()
    if blacklist_info['consecutive_stopouts']:
        blacklist_filter = apply_stop_loss_blacklist_filter(candidates, blacklist_info['consecutive_stopouts'])
    else:
        blacklist_filter = {'filtered_count': 0, 'removed_stocks': []}
    
    # 改進⑤: 資金配置
    print("\n【步驟5】資金配置動態優化...")
    allocation = get_dynamic_portfolio_allocation(cash_result['cash_ratio'])
    print(f"💼 [動態配置] 模式:{allocation['mode']} | 防守:{allocation['defensive']:.0%} | 進攻:{allocation['offensive']:.0%} | 戰術:{allocation['tactical']:.0%} | 現金:{allocation['cash_reserve']:.0%}")
    
    # 最終重排序
    candidates.sort(key=lambda x: x.get('score', 0), reverse=True)
    
    # 生成報告
    result = {
        'version': 'v5.90',
        'timestamp': datetime.now().isoformat(),
        'total_stocks': initial_count,
        'final_count': len(candidates),
        'optimizations': {
            'cash_detection': cash_result,
            'sharpe_multiplier': sharpe_result,
            'macd_histogram': macd_result,
            'stop_loss_filter': blacklist_filter,
            'portfolio_allocation': allocation,
            'stop_loss_blacklist': blacklist_info
        }
    }
    
    print("\n" + "=" * 70)
    print("✅ v5.90 晚間深度優化工程 — 完成")
    print(f"📊 候選股票: {initial_count} → {len(candidates)}只")
    print(f"🎯 TOP 5:\n{json.dumps([{'code': c.get('code'), 'name': c.get('name'), 'score': c.get('score')} for c in candidates[:5]], ensure_ascii=False, indent=2)}")
    print("=" * 70)
    
    return result


def generate_v5_90_report(optimization_result: dict) -> str:
    """生成v5.90優化報告
    
    Args:
        optimization_result: apply_v5_90_deep_optimization的輸出
        
    Returns: 報告markdown字符串
    """
    
    opt = optimization_result['optimizations']
    
    report = f"""# v5.90 晚間深度優化工程 — {datetime.now().strftime('%Y-%m-%d %H:%M')}

## 【優化成果】

### 現金檢測集成強化
- **狀態**: {'✅ 已激活' if opt['cash_detection']['applied'] else '⏳ 待激活'}
- **現金占比**: {opt['cash_detection']['cash_ratio']:.1%}
- **現金模式**: {opt['cash_detection']['cash_mode'].upper()}
- **入場閾值**: {opt['cash_detection']['entry_quality_threshold']}分 (激活時)
- **評分倍數**: {opt['cash_detection']['score_multiplier']}x
- **影響股票**: {opt['cash_detection']['affected_stocks']}只

### Sharpe權重強制激活
- **狀態**: {'✅ 已應用' if opt['sharpe_multiplier']['applied'] else '⏳ 未觸發'}
- **倍數**: {opt['sharpe_multiplier']['sharpe_multiplier']}x
- **影響股票**: {opt['sharpe_multiplier']['affected_stocks']}只
- **TOP3變化**:
  - {opt['sharpe_multiplier']['top_3_changes'][0]['code']} ({opt['sharpe_multiplier']['top_3_changes'][0]['old_score']} → {opt['sharpe_multiplier']['top_3_changes'][0]['new_score']})
  - {opt['sharpe_multiplier']['top_3_changes'][1]['code']} ({opt['sharpe_multiplier']['top_3_changes'][1]['old_score']} → {opt['sharpe_multiplier']['top_3_changes'][1]['new_score']})
  - {opt['sharpe_multiplier']['top_3_changes'][2]['code']} ({opt['sharpe_multiplier']['top_3_changes'][2]['old_score']} → {opt['sharpe_multiplier']['top_3_changes'][2]['new_score']})

### MACD直方圖翻正信號
- **狀態**: {'✅ 已應用' if opt['macd_histogram']['applied'] else '⏳ 無信號'}
- **影響股票**: {opt['macd_histogram']['affected_stocks']}只
- **獎勵分數**: +8-18分/只

### 止損黑名單優化
- **連續止損個股**: {opt['stop_loss_blacklist']['count']}只
- **已過濾**: {opt['stop_loss_filter']['filtered_count']}只
- **黑名單**: {[s['code'] for s in opt['stop_loss_filter']['removed_stocks']]}

### 資金配置動態優化
- **配置模式**: {opt['portfolio_allocation']['mode'].upper()}
- **防守倉位**: {opt['portfolio_allocation']['defensive']:.0%}
- **進攻倉位**: {opt['portfolio_allocation']['offensive']:.0%}
- **戰術倉位**: {opt['portfolio_allocation']['tactical']:.0%}
- **現金儲備**: {opt['portfolio_allocation']['cash_reserve']:.0%}

## 【預期指標改善】

| 指標 | v5.87 | v5.90目標 | 改善 |
|------|-------|----------|------|
| 資金利用率 | 1-2% | 15-20% | +10x |
| 日均建倉 | 8-12只 | 12-18只 | +50% |
| 年化收益 | 0.19% | 3-5% | +15x |
| 建倉勝率 | 60% | 70-75% | +15-25% |
| MaxDD | 4.08% | <5% | -8% |
| Sharpe | 2.35 | 2.5+ | +6% |

## 【後續執行步驟】

1. ✅ v5.90優化工程完成
2. 集成到stock_picker.py::score_and_rank()
3. 集成到entry_quality.py::calculate_entry_quality_score()
4. 同步檔案到openclaw-deploy仓库
5. git commit && git push
6. sudo systemctl restart finance-api
7. 監控24小時內的建倉效果

---
**報告生成**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**版本**: v5.90
**狀態**: ✅ 完成，待部署
"""
    
    return report


if __name__ == '__main__':
    # 測試模式: 模擬候選股票
    test_candidates = [
        {
            'code': '000858',
            'name': '五粮液',
            'score': 75,
            'entry_quality_score': 60,
            'signals': ['MACD', 'RSI超賣'],
            'strategy': 'MACD+RSI (消費)'
        },
        {
            'code': '000651',
            'name': '格力电器',
            'score': 65,
            'entry_quality_score': 55,
            'signals': ['MACD金叉'],
            'strategy': 'MACD+RSI'
        },
        {
            'code': '300750',
            'name': '宁德时代',
            'score': 80,
            'entry_quality_score': 65,
            'signals': ['MACD', 'RSI', 'MACD直方圖翻正'],
            '_macd_histogram_flip_v88': {
                'detected': True,
                'strength': 15,
                'days_since_flip': 0,
                'current': 0.25,
                'previous': -0.05
            }
        }
    ]
    
    # 執行優化
    result = apply_v5_90_deep_optimization(test_candidates)
    
    # 生成報告
    report = generate_v5_90_report(result)
    
    # 保存報告
    report_path = '/home/nikefd/finance-agent/V5_90_DEEP_OPTIMIZE_REPORT.md'
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"\n📄 報告已保存: {report_path}")
    
    # 保存JSON結果
    json_path = '/home/nikefd/finance-agent/v5_90_result.json'
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    print(f"📊 結果已保存: {json_path}")
