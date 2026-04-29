#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v5.73 止損執行面板 (Stop Loss Execution Dashboard)
讀取 JSONL 日誌、統計信息、生成 API 數據

Features:
- 讀取止損日誌
- 計算統計指標 (今日止損次數、收益、勝率)
- 生成面板數據結構
"""

import json
from datetime import datetime, date
from pathlib import Path

LOG_FILE = '/home/nikefd/finance-agent/reports/stop_loss_execution_log.jsonl'
REPORTS_DIR = Path('/home/nikefd/finance-agent/reports')

def init_log_file():
    """初始化日誌文件"""
    if not Path(LOG_FILE).exists():
        Path(LOG_FILE).parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, 'w') as f:
            pass

def append_stop_loss_log(data):
    """追加止損日誌"""
    init_log_file()
    with open(LOG_FILE, 'a') as f:
        f.write(json.dumps(data, ensure_ascii=False) + '\n')

def get_stop_loss_dashboard():
    """生成止損執行面板數據"""
    init_log_file()
    
    all_records = []
    try:
        with open(LOG_FILE, 'r') as f:
            for line in f:
                if line.strip():
                    try:
                        all_records.append(json.loads(line))
                    except:
                        pass
    except:
        pass
    
    # 按日期分組
    today = str(date.today())
    today_records = [r for r in all_records if r.get('date') == today]
    
    # 計算統計
    total_stop_loss_triggered = sum(r.get('stop_loss_triggered', 0) for r in today_records)
    total_take_profit_triggered = sum(r.get('take_profit_triggered', 0) for r in today_records)
    total_positions_checked = sum(r.get('positions_checked', 0) for r in today_records)
    
    # 提取詳細信息
    details = []
    for record in today_records:
        if 'details' in record and isinstance(record['details'], list):
            details.extend(record['details'])
    
    # 止損效率 = 止損觸發數 / 持倉總數
    stop_loss_ratio = (total_stop_loss_triggered / total_positions_checked * 100) if total_positions_checked > 0 else 0
    
    # 獲取最近交易日的統計
    all_trading_days = {}
    for record in all_records:
        day = record.get('date', 'unknown')
        if day not in all_trading_days:
            all_trading_days[day] = {
                'stop_loss': 0,
                'take_profit': 0,
                'total_checked': 0,
                'details': []
            }
        all_trading_days[day]['stop_loss'] += record.get('stop_loss_triggered', 0)
        all_trading_days[day]['take_profit'] += record.get('take_profit_triggered', 0)
        all_trading_days[day]['total_checked'] += record.get('positions_checked', 0)
        if 'details' in record:
            all_trading_days[day]['details'].extend(record['details'])
    
    # 計算7日統計
    recent_days = sorted(all_trading_days.keys())[-7:]
    recent_stats = [all_trading_days[day] for day in recent_days]
    
    return {
        'timestamp': datetime.now().isoformat(),
        'today': {
            'date': today,
            'positions_checked': total_positions_checked,
            'stop_loss_triggered': total_stop_loss_triggered,
            'take_profit_triggered': total_take_profit_triggered,
            'stop_loss_ratio_pct': round(stop_loss_ratio, 2),
            'total_actions': total_stop_loss_triggered + total_take_profit_triggered,
            'details': details
        },
        'recent_7days': {
            'days': recent_days,
            'stats': recent_stats,
            'avg_daily_stop_loss': round(sum(s['stop_loss'] for s in recent_stats) / len(recent_stats), 2) if recent_stats else 0,
            'avg_daily_take_profit': round(sum(s['take_profit'] for s in recent_stats) / len(recent_stats), 2) if recent_stats else 0
        },
        'historical': {
            'total_records': len(all_records),
            'total_stop_loss_events': sum(r.get('stop_loss_triggered', 0) for r in all_records),
            'total_take_profit_events': sum(r.get('take_profit_triggered', 0) for r in all_records)
        }
    }

def get_stop_loss_by_code(code):
    """獲取特定股票的止損記錄"""
    init_log_file()
    
    matching_records = []
    try:
        with open(LOG_FILE, 'r') as f:
            for line in f:
                if line.strip() and code in line:
                    try:
                        record = json.loads(line)
                        if 'details' in record:
                            matching = [d for d in record['details'] if code in d]
                            if matching:
                                matching_records.append({
                                    'timestamp': record.get('timestamp'),
                                    'details': matching
                                })
                    except:
                        pass
    except:
        pass
    
    return matching_records


if __name__ == '__main__':
    # 初始化日誌文件
    init_log_file()
    
    # 測試記錄
    test_record = {
        'timestamp': datetime.now().isoformat(),
        'date': str(date.today()),
        'positions_checked': 5,
        'stop_loss_triggered': 1,
        'take_profit_triggered': 0,
        'details': [
            '🔴 001367 - 早期止損: 持倉2天虧-2.3%',
            '✅ 600958 - 監控中: 虧-1.1% (止損閾值-5%)'
        ]
    }
    
    # 打印儀錶板
    dashboard = get_stop_loss_dashboard()
    print(json.dumps(dashboard, ensure_ascii=False, indent=2))
