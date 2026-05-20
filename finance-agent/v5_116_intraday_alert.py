#!/usr/bin/env python3
"""
V5.116 盤中情緒警告面板 - 2026-05-20 03:30 UTC
功能: 實時情緒指標警告 + 建倉調整 + 風控提示
集成: API /api/finance/intraday-alert-v116
"""

import json
import sys
from datetime import datetime

def get_sentiment_alert_bundle():
    """
    生成實時情緒警告面板數據
    返回: {
        timestamp, 
        sentiment_status (評分/級別/警告顏色),
        adjustment_params (自動參數調整),
        action_flags (建倉/止損標記),
        ui_indicators (UI展示指標)
    }
    """
    try:
        sys.path.insert(0, '/home/nikefd/finance-agent')
        import sqlite3
        from data_collector import get_market_sentiment_safe
        
        db = sqlite3.connect('/home/nikefd/finance-agent/data/trading.db')
        db.row_factory = sqlite3.Row
        
        # 1. 當前市場情緒評分
        try:
            sentiment_data = get_market_sentiment_safe()
            sentiment_score = sentiment_data.get('score', 50)
        except:
            sentiment_score = 50  # 默認中性
        
        # 2. 情緒等級判定
        if sentiment_score >= 90:
            level = "極度貪婪"
            color = "#e63946"  # 紅色
            emoji = "🔴"
            position_action = "HALT"  # 停止建倉
            position_limit = -50  # 最大持倉↓50%
        elif sentiment_score >= 80:
            level = "貪婪"
            color = "#ffa500"  # 橙色
            emoji = "🟠"
            position_action = "CAUTION"  # 謹慎建倉
            position_limit = -30
        elif sentiment_score >= 60:
            level = "樂觀"
            color = "#2ec4b6"  # 綠色
            emoji = "🟢"
            position_action = "NORMAL"  # 正常建倉
            position_limit = 0
        elif sentiment_score >= 40:
            level = "中性"
            color = "#ffd166"  # 黃色
            emoji = "🟡"
            position_action = "NORMAL"  # 正常建倉
            position_limit = 0
        elif sentiment_score >= 20:
            level = "悲觀"
            color = "#8ecae6"  # 淡藍
            emoji = "🔵"
            position_action = "AGGRESSIVE"  # 積極建倉
            position_limit = +20
        else:
            level = "恐懼"
            color = "#1f77b4"  # 深藍
            emoji = "🔷"
            position_action = "AGGRESSIVE_MAX"  # 最大激進
            position_limit = +30
        
        # 3. 自動參數調整
        adjustment_params = {
            "max_positions_adjust": position_limit,  # 最大持倉調整
            "entry_threshold_adjust": -5 if sentiment_score >= 80 else (+5 if sentiment_score <= 20 else 0),  # 入場閾值調整
            "position_size_adjust": -20 if sentiment_score >= 90 else (-10 if sentiment_score >= 80 else (+20 if sentiment_score <= 20 else 0)),  # 單只持倉調整
            "cash_hold_ratio": min(0.8, max(0.1, (100 - sentiment_score) / 100))  # 建議現金比
        }
        
        # 4. 實時交易指標
        trades_24h = db.execute("SELECT * FROM trades WHERE trade_date = date('now') ORDER BY id DESC").fetchall()
        entry_count_today = sum(1 for t in trades_24h if t['direction'] == 'BUY')
        exit_count_today = sum(1 for t in trades_24h if t['direction'] == 'SELL')
        
        # 計算入場品質
        entry_quality = 0
        if entry_count_today > 0:
            entry_trades = [t for t in trades_24h if t['direction'] == 'BUY']
            entry_quality = sum(t.get('entry_quality_score', 75) or 75 for t in entry_trades) / len(entry_trades)
        
        # 5. 持倉數據
        positions = db.execute("SELECT * FROM positions").fetchall()
        pos_count = len(positions)
        total_pnl = sum(float((p['current_price'] or 0) - (p['avg_cost'] or 0)) * (p['shares'] or 0) for p in positions)
        
        # 6. 止損狀態
        stop_loss_triggers = db.execute(
            "SELECT COUNT(*) as cnt FROM positions WHERE (peak_price - current_price) / peak_price >= 0.08"
        ).fetchone()['cnt']
        
        action_flags = {
            "building_allowed": position_action != "HALT",
            "entry_quality_check": entry_quality >= 70,
            "stop_loss_active": stop_loss_triggers > 0,
            "cash_reserve_ready": adjustment_params["cash_hold_ratio"] > 0.3
        }
        
        # 7. UI 指標
        ui_indicators = {
            "signal_lights": {
                "entry_signal": "🟢" if entry_count_today > 0 else "⚪",
                "stop_loss_signal": "🔴" if stop_loss_triggers > 0 else "⚪",
                "position_concentration": "🟠" if pos_count > 8 else "🟢" if pos_count > 0 else "⚪"
            },
            "status_badges": [
                {"label": "情緒", "value": f"{sentiment_score} - {level}", "color": color},
                {"label": "建倉", "value": f"{entry_count_today}買/{exit_count_today}賣", "color": "#2ec4b6" if entry_count_today > exit_count_today else "#e63946"},
                {"label": "持倉", "value": f"{pos_count}只 ¥{total_pnl:,.0f}", "color": "#2ec4b6" if total_pnl > 0 else "#e63946"}
            ]
        }
        
        db.close()
        
        return {
            "timestamp": datetime.now().isoformat(),
            "sentiment": {
                "score": sentiment_score,
                "level": level,
                "emoji": emoji,
                "color": color,
                "action_status": position_action
            },
            "adjustments": adjustment_params,
            "actions": action_flags,
            "metrics": {
                "entry_count_today": entry_count_today,
                "exit_count_today": exit_count_today,
                "entry_quality_avg": round(entry_quality, 2),
                "positions_count": pos_count,
                "total_pnl": round(total_pnl, 2),
                "stop_loss_triggers": stop_loss_triggers
            },
            "ui": ui_indicators,
            "version": "v5.116"
        }
    
    except Exception as e:
        import traceback
        return {
            "timestamp": datetime.now().isoformat(),
            "error": str(e),
            "sentiment": {
                "score": 50,
                "level": "中性",
                "emoji": "🟡",
                "color": "#ffd166",
                "action_status": "NORMAL"
            },
            "version": "v5.116_error"
        }


if __name__ == "__main__":
    data = get_sentiment_alert_bundle()
    print(json.dumps(data, ensure_ascii=False, indent=2))
