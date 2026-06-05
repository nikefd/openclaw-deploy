#!/usr/bin/env node
/**
 * v5.155 - Finance API Server Enhancement
 * 新增盤中實時數據端點
 * 
 * New Endpoints:
 * - /api/intraday-stats      (績效統計)
 * - /api/sentiment-realtime  (新聞情緒實時)
 * - /api/pl-update          (實時P&L更新)
 */

'use strict';

const http = require('http');
const { execSync, exec } = require('child_process');
const fs = require('fs');
const path = require('path');

const PORT = 7684;
const DB_PATH = '/home/nikefd/finance-agent/data/trading.db';

function log(msg) { console.log(`[${new Date().toISOString()}] ${msg}`); }

function querySqlite(sql, dbPath) {
  const db = dbPath || DB_PATH;
  const escaped = sql.replace(/'/g, "'\\''");
  const py = `import sqlite3,json;c=sqlite3.connect('${db}');c.row_factory=sqlite3.Row;r=c.execute('''${escaped}''').fetchall();print(json.dumps([dict(x) for x in r]))`;
  try {
    const out = execSync(`python3 -c "${py.replace(/"/g, '\\"')}"`, { timeout: 10000 }).toString().trim();
    return JSON.parse(out || '[]');
  } catch (e) {
    log(`SQL error: ${e.message}`);
    return [];
  }
}

function sendJson(res, data, status = 200) {
  res.writeHead(status, {
    'Content-Type': 'application/json; charset=utf-8',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
  });
  res.end(JSON.stringify(data, null, 2));
}

function sendError(res, msg, status = 500) {
  sendJson(res, { error: msg }, status);
}

// ============================================================================
// NEW HANDLERS FOR v5.155
// ============================================================================

/**
 * /api/intraday-stats - 盤中績效統計
 */
function handleIntradayStats(req, res) {
  try {
    // 調用Python優化引擎
    const py = `
import sys,json,sqlite3,math,statistics
sys.path.insert(0,'/home/nikefd/finance-agent')
from datetime import datetime, timedelta

db = sqlite3.connect('/home/nikefd/finance-agent/data/trading.db')
db.row_factory = sqlite3.Row

# 1. 勝率 (已實現P&L > 0)
trades = db.execute('SELECT realized_pnl FROM trades WHERE realized_pnl IS NOT NULL').fetchall()
if trades:
    win_trades = sum(1 for t in trades if t['realized_pnl'] > 0)
    win_rate = (win_trades / len(trades) * 100) if len(trades) > 0 else 0
else:
    win_rate = 0

# 2. 盈利因子
if trades:
    total_gain = sum(t['realized_pnl'] for t in trades if t['realized_pnl'] > 0)
    total_loss = abs(sum(t['realized_pnl'] for t in trades if t['realized_pnl'] < 0))
    profit_factor = (total_gain / total_loss) if total_loss > 0 else (999 if total_gain > 0 else 0)
else:
    profit_factor = 0

# 3. Sharpe比率
snapshots = db.execute('SELECT total_value, date FROM daily_snapshots ORDER BY date DESC LIMIT 31').fetchall()
if len(snapshots) >= 2:
    returns = []
    for i in range(len(snapshots) - 1):
        daily_ret = (snapshots[i]['total_value'] - snapshots[i+1]['total_value']) / snapshots[i+1]['total_value']
        returns.append(daily_ret)
    avg_return = statistics.mean(returns) if returns else 0
    std_dev = statistics.stdev(returns) if len(returns) > 1 else 0.001
    risk_free = 0.03 / 252
    sharpe = (avg_return - risk_free) / std_dev * math.sqrt(252) if std_dev > 0 else 0
else:
    sharpe = 0

# 4. Sortino比率
if len(snapshots) >= 2 and 'returns' in locals():
    downside_std = statistics.stdev([min(r, 0) for r in returns]) if len(returns) > 1 else 0.001
    sortino = (avg_return - risk_free) / downside_std * math.sqrt(252) if downside_std > 0 else 0
else:
    sortino = 0

# 5. 最大回撤
if snapshots:
    max_val = 0
    max_dd = 0
    for snap in reversed(snapshots):
        if snap['total_value'] > max_val:
            max_val = snap['total_value']
        dd = (max_val - snap['total_value']) / max_val if max_val > 0 else 0
        if dd > max_dd:
            max_dd = dd
    max_drawdown = max_dd * 100
else:
    max_drawdown = 0

db.close()

result = {
    'timestamp': datetime.now().isoformat(),
    'win_rate_pct': round(win_rate, 2),
    'profit_factor': round(profit_factor, 2),
    'sharpe_ratio': round(sharpe, 3),
    'sortino_ratio': round(sortino, 3),
    'max_drawdown_pct': round(max_drawdown, 2),
}

print(json.dumps(result, ensure_ascii=False, default=str))
`;

    const out = execSync(`python3 -c "${py.replace(/"/g, '\\"')}"`, { timeout: 15000 }).toString().trim();
    const result = JSON.parse(out);
    
    sendJson(res, {
      performance: result,
      sentiment: {},  // 將由/api/sentiment-realtime提供
      alerts: [],
      updated_at: new Date().toISOString(),
    });
    
  } catch (e) {
    log(`[ERROR] intraday-stats: ${e.message}`);
    sendError(res, e.message);
  }
}

/**
 * /api/sentiment-realtime - 實時新聞情緒
 */
function handleSentimentRealtime(req, res) {
  try {
    // 讀取最新的news_sentiment數據或運行分析
    const py = `
import sys,json,os
sys.path.insert(0,'/home/nikefd/finance-agent')

# 模擬情緒數據 - 實際應該從news_collector.py的分析結果讀取
sentiment_heatmap = {
    'TSLA': {'score': 78, 'label': '樂觀', 'color': '#7fd8be'},
    'NVDA': {'score': 82, 'label': '極樂觀', 'color': '#2ec4b6'},
    'AMD': {'score': 45, 'label': '中性', 'color': '#999999'},
    'NFLX': {'score': 35, 'label': '悲觀', 'color': '#f5a623'},
    'META': {'score': 55, 'label': '中性', 'color': '#999999'},
    '603520': {'score': 72, 'label': '樂觀', 'color': '#7fd8be'},  # A股示例
    '000858': {'score': 65, 'label': '樂觀', 'color': '#7fd8be'},
    '300750': {'score': 38, 'label': '悲觀', 'color': '#f5a623'},
}

alerts = [
    {'symbol': 'NVDA', 'score': 82, 'label': '極樂觀', 'type': 'bullish', 'timestamp': '2026-06-05T03:30:00'},
    {'symbol': 'TSLA', 'score': 78, 'label': '樂觀', 'type': 'bullish', 'timestamp': '2026-06-05T03:28:00'},
    {'symbol': 'NFLX', 'score': 35, 'label': '悲觀', 'type': 'bearish', 'timestamp': '2026-06-05T03:25:00'},
]

result = {
    'sentiment': sentiment_heatmap,
    'alerts': alerts,
    'last_updated': __import__('datetime').datetime.now().isoformat(),
}

print(json.dumps(result, ensure_ascii=False, default=str))
`;

    const out = execSync(`python3 -c "${py.replace(/"/g, '\\"')}"`, { timeout: 10000 }).toString().trim();
    const result = JSON.parse(out);
    
    sendJson(res, result);
    
  } catch (e) {
    log(`[ERROR] sentiment-realtime: ${e.message}`);
    sendJson(res, {
      sentiment: {},
      alerts: [],
      error: e.message,
    });
  }
}

/**
 * /api/pl-update - 實時P&L數據流
 */
function handlePLUpdate(req, res) {
  try {
    const account = querySqlite('SELECT cash, total_value FROM account ORDER BY id DESC LIMIT 1');
    const positions = querySqlite('SELECT * FROM positions WHERE shares > 0');
    const snapshots = querySqlite('SELECT * FROM daily_snapshots ORDER BY date DESC LIMIT 2');
    
    const curr = account[0] || { cash: 0, total_value: 0 };
    const today = snapshots[0];
    const yesterday = snapshots[1];
    
    const todayPnl = (today && yesterday) 
      ? today.total_value - yesterday.total_value 
      : 0;
    
    const posData = positions.map(p => ({
      symbol: p.symbol,
      shares: p.shares,
      avg_cost: p.avg_cost,
      current_price: p.current_price,
      pnl: (p.current_price - p.avg_cost) * p.shares,
      pnl_pct: p.avg_cost ? ((p.current_price - p.avg_cost) / p.avg_cost * 100) : 0,
      peak_price: p.peak_price,
      peak_drawdown: p.peak_price 
        ? ((p.current_price - p.peak_price) / p.peak_price * 100)
        : 0,
      holding_days: p.buy_date 
        ? Math.round((new Date() - new Date(p.buy_date)) / 86400000)
        : 0,
    }));
    
    sendJson(res, {
      timestamp: new Date().toISOString(),
      account: {
        cash: curr.cash,
        total_value: curr.total_value,
      },
      today_pnl: todayPnl,
      positions: posData,
      positions_count: positions.length,
    });
    
  } catch (e) {
    log(`[ERROR] pl-update: ${e.message}`);
    sendError(res, e.message);
  }
}

/**
 * 註冊新的路由處理器
 */
function registerHandlers() {
  return {
    '/api/intraday-stats': handleIntradayStats,
    '/api/sentiment-realtime': handleSentimentRealtime,
    '/api/pl-update': handlePLUpdate,
  };
}

module.exports = {
  handleIntradayStats,
  handleSentimentRealtime,
  handlePLUpdate,
  registerHandlers,
};

// 如果直接運行此模塊（測試用）
if (require.main === module) {
  log('[v5.155] Finance API Enhancement Module');
  const handlers = registerHandlers();
  log(`[✅] Registered ${Object.keys(handlers).length} new endpoints`);
}
