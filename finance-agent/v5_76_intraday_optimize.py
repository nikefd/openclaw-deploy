#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v5.76 盤中優化② - UI增強 + 資金配置建議
功能:
  1. 持倉風險熱力圖 (持倉天數x回撤%x波動率 → 風險等級)
  2. 資金配置建議面板 (現金比例x賽道權重 → 建議配置)
"""

import json
import sqlite3
import math
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = '/home/nikefd/finance-agent/data/trading.db'
CONFIG_FILE = '/home/nikefd/finance-agent/config.py'

def get_positions():
    """讀取當前持倉"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM positions WHERE shares > 0')
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_account():
    """讀取賬戶信息"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM account ORDER BY id DESC LIMIT 1')
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else {}

def calc_holding_days(buy_date_str):
    """計算持倉天數"""
    if not buy_date_str:
        return 0
    try:
        buy_date = datetime.fromisoformat(buy_date_str.replace('Z', '+00:00'))
        now = datetime.now(buy_date.tzinfo) if buy_date.tzinfo else datetime.now()
        return max(0, (now - buy_date).days)
    except:
        return 0

def calc_risk_score(pos):
    """
    計算持倉風險評分 (0-100)
    因子:
      1. 回撤深度 (peak_drawdown): -5%以下=高風險
      2. 持倉時間 (holding_days): <2天或>30天=高風險
      3. 波動率 (近日): >3%=中風險
      4. 頭寸占比: >10%=中風險
    
    返回: {score, level, factors}
    """
    score = 0
    factors = []
    
    # 1. 回撤深度 (-5% = 25分, -10% = 40分, -15% = 50分)
    drawdown = pos.get('peak_drawdown', 0) or 0
    if drawdown < -15:
        score += 50
        factors.append(f"深度回撤 {drawdown:.2f}%")
    elif drawdown < -10:
        score += 40
        factors.append(f"中度回撤 {drawdown:.2f}%")
    elif drawdown < -5:
        score += 25
        factors.append(f"淺度回撤 {drawdown:.2f}%")
    
    # 2. 持倉天數 (太短=容易波動, 太長=錯誤積累)
    holding_days = calc_holding_days(pos.get('buy_date'))
    if holding_days < 2:
        score += 15
        factors.append(f"新建倉位 {holding_days}天")
    elif holding_days > 30:
        score += 20
        factors.append(f"長期持倉 {holding_days}天")
    
    # 3. 持倉占比 (估計市值/總資產)
    position_pct = pos.get('position_pct', 0) or 0
    if position_pct > 10:
        score += 15
        factors.append(f"頭寸集中 {position_pct:.1f}%")
    
    # 4. 盈虧百分比 (盈利>+5% = 低風險, 虧損>-3% = 高風險)
    pnl_pct = pos.get('pnl_pct', 0) or 0
    if pnl_pct < -5:
        score += 25
        factors.append(f"深度虧損 {pnl_pct:.2f}%")
    elif pnl_pct < -2:
        score += 15
        factors.append(f"輕度虧損 {pnl_pct:.2f}%")
    elif pnl_pct > 8:
        score -= 10  # 盈利充分, 可考慮止盈
        factors.append(f"高位盈利 {pnl_pct:.2f}%")
    
    # 轉換風險等級
    if score >= 70:
        level = 'CRITICAL'  # 紅 - 立即關注
    elif score >= 40:
        level = 'HIGH'      # 橙 - 需要監控
    elif score >= 20:
        level = 'MEDIUM'    # 黃 - 正常監控
    else:
        level = 'LOW'       # 綠 - 穩定
    
    return {
        'score': max(0, min(100, score)),
        'level': level,
        'factors': factors[:3]  # 只返回top 3因子
    }

def generate_position_heatmap():
    """
    生成持倉風險熱力圖
    返回: [{code, name, risk_score, risk_level, holding_days, drawdown, pnl_pct}]
    """
    positions = get_positions()
    heatmap = []
    
    for pos in positions:
        holding_days = calc_holding_days(pos.get('buy_date'))
        risk = calc_risk_score({
            **pos,
            'holding_days': holding_days,
            'position_pct': pos.get('position_pct', 0)
        })
        
        heatmap.append({
            'code': pos.get('symbol') or pos.get('stock_code', 'N/A'),
            'name': pos.get('name') or pos.get('stock_name', ''),
            'risk_score': risk['score'],
            'risk_level': risk['level'],
            'risk_factors': risk['factors'],
            'holding_days': holding_days,
            'drawdown_pct': round(pos.get('peak_drawdown', 0) or 0, 2),
            'pnl_pct': round(pos.get('pnl_pct', 0) or 0, 2),
            'shares': pos.get('shares', 0),
            'market_value': round(pos.get('current_price', 0) * pos.get('shares', 0), 0),
            'current_price': round(pos.get('current_price', 0), 2)
        })
    
    # 排序: CRITICAL > HIGH > MEDIUM > LOW
    level_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
    heatmap.sort(key=lambda x: (level_order[x['risk_level']], -x['risk_score']))
    
    return heatmap

def calc_allocation_suggestion(account, positions):
    """
    生成資金配置建議
    基於:
      1. 當前現金比例
      2. 實現倉位分散
      3. 賽道權重優化
    
    返回: {cash_ratio, aggressive_mode, suggestions: [{sector, current_pct, target_pct, action}]}
    """
    total_value = account.get('total_value', 1000000)
    cash = account.get('cash', total_value)
    cash_ratio = cash / total_value if total_value > 0 else 1.0
    
    # 現金比例決定激進度
    if cash_ratio > 0.95:
        mode = 'AGGRESSIVE'
        desc = "現金充足, 積極建倉"
        cash_target = 0.70  # 目標持倉占30%
    elif cash_ratio > 0.80:
        mode = 'NORMAL'
        desc = "適度配置"
        cash_target = 0.80  # 目標持倉占20%
    elif cash_ratio > 0.60:
        mode = 'CAUTIOUS'
        desc = "謹慎建倉"
        cash_target = 0.75  # 目標持倉占25%
    else:
        mode = 'FULL_INVESTED'
        desc = "滿倉運作"
        cash_target = 0.50  # 保留應急金
    
    # 賽道權重 (v5.75優化)
    sector_targets = {
        '科技成長': 0.35,
        '新能源': 0.25,
        '消費白馬': 0.15,
        '醫藥健康': 0.15,
        '其他': 0.10
    }
    
    # 計算當前賽道分佈
    sector_current = {}
    total_pos_value = 0
    for pos in positions:
        sector = pos.get('sector', '其他')
        market_value = pos.get('current_price', 0) * pos['shares']
        sector_current[sector] = sector_current.get(sector, 0) + market_value
        total_pos_value += market_value
    
    # 生成建議
    suggestions = []
    if total_pos_value > 0:
        for sector, target_pct in sector_targets.items():
            current_pct = sector_current.get(sector, 0) / total_pos_value if total_pos_value > 0 else 0
            target_pct_actual = target_pct * (1 - cash_target)  # 調整為實際投資金額的占比
            
            if current_pct < target_pct_actual * 0.8:
                action = "🟢 增配"
            elif current_pct > target_pct_actual * 1.2:
                action = "🔴 減配"
            else:
                action = "⚪ 保持"
            
            suggestions.append({
                'sector': sector,
                'current_pct': round(current_pct * 100, 1),
                'target_pct': round(target_pct_actual * 100, 1),
                'action': action
            })
    
    return {
        'cash_ratio': round(cash_ratio * 100, 1),
        'cash_amount': round(cash, 0),
        'total_invested': round(total_pos_value, 0),
        'mode': mode,
        'mode_desc': desc,
        'cash_target_pct': round(cash_target * 100, 1),
        'suggestions': suggestions
    }

def generate_report():
    """生成完整報告"""
    account = get_account()
    positions = get_positions()
    
    heatmap = generate_position_heatmap()
    allocation = calc_allocation_suggestion(account, positions)
    
    # 風險統計
    risk_summary = {
        'critical': sum(1 for h in heatmap if h['risk_level'] == 'CRITICAL'),
        'high': sum(1 for h in heatmap if h['risk_level'] == 'HIGH'),
        'medium': sum(1 for h in heatmap if h['risk_level'] == 'MEDIUM'),
        'low': sum(1 for h in heatmap if h['risk_level'] == 'LOW'),
        'avg_risk_score': round(sum(h['risk_score'] for h in heatmap) / len(heatmap), 1) if heatmap else 0
    }
    
    report = {
        'timestamp': datetime.now().isoformat(),
        'account': {
            'total_value': account.get('total_value', 0),
            'cash': account.get('cash', 0),
            'total_positions': len(positions)
        },
        'position_heatmap': heatmap,
        'risk_summary': risk_summary,
        'allocation': allocation
    }
    
    return report

if __name__ == '__main__':
    report = generate_report()
    print(json.dumps(report, ensure_ascii=False, indent=2))
