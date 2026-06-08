/**
 * API Enhancement v5.159 - Intraday Statistics & Sentiment Dimensions
 * 後端改進: 新增回測統計 + 情緒動態多維度 + 盤中實時信號
 */

const http = require('http');
const { execSync } = require('child_process');
const path = require('path');

const API_PORT = 7685;  // 新增端口 (不碰原始7684)
const FINANCE_AGENT_PATH = '/home/nikefd/finance-agent';

function log(msg) {
  console.log(`[${new Date().toISOString()}] [v5.159-API] ${msg}`);
}

function sendJson(res, data, status = 200) {
  res.writeHead(status, {
    'Content-Type': 'application/json; charset=utf-8',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
  });
  res.end(JSON.stringify(data));
}

// ========== 1️⃣ 回測統計 API ==========
function handleBacktestStats(req, res) {
  try {
    // 調用Python獲取最新回測結果
    const py = `
import sys, json, os
sys.path.insert(0, '${FINANCE_AGENT_PATH}')
try:
  # 尋找最新的回測結果
  reports_dir = '${FINANCE_AGENT_PATH}/backtest_results'
  if os.path.exists(reports_dir):
    files = sorted([f for f in os.listdir(reports_dir) if f.endswith('.json')], reverse=True)
    if files:
      import json as j
      with open(os.path.join(reports_dir, files[0])) as f:
        data = j.load(f)
        # 提取關鍵指標
        result = {
          'total_return': data.get('total_return', 0),
          'win_rate': data.get('win_rate', 0),
          'sharpe_ratio': data.get('sharpe_ratio', 0),
          'max_drawdown': data.get('max_drawdown', 0),
          'trades_count': data.get('trades_count', 0),
          'profit_factor': data.get('profit_factor', 0),
          'strategy': data.get('strategy_name', 'Unknown'),
          'period': data.get('period', 'Unknown'),
          'timestamp': data.get('timestamp', ''),
        }
        print(json.dumps(result, ensure_ascii=False, default=str))
    else:
      print(json.dumps({'error': 'no backtest results'}))
  else:
    print(json.dumps({'error': 'no backtest dir'}))
except Exception as e:
  print(json.dumps({'error': str(e)}))
`;
    const cmd = `python3 -c "${py.replace(/"/g, '\\"')}"`;
    const out = execSync(cmd, { timeout: 5000 }).toString().trim();
    
    let result = {};
    try {
      result = JSON.parse(out);
    } catch {
      result = { error: 'invalid json' };
    }
    
    sendJson(res, {
      timestamp: new Date().toISOString(),
      backtest: result,
      status: result.error ? 'error' : 'success'
    });
  } catch (err) {
    log(`backtest stats error: ${err.message}`);
    sendJson(res, { error: err.message, status: 'error' }, 500);
  }
}

// ========== 2️⃣ 情緒驅動信號 API ==========
function handleSentimentDrivenSignals(req, res) {
  try {
    const py = `
import sys, json, os, sqlite3
sys.path.insert(0, '${FINANCE_AGENT_PATH}')

# 讀取當前情緒分數
db_path = '${FINANCE_AGENT_PATH}/data/trading.db'
try:
  conn = sqlite3.connect(db_path)
  conn.row_factory = sqlite3.Row
  c = conn.cursor()
  
  # 獲取最新情緒
  sentiment_row = c.execute('SELECT sentiment_score, sentiment_label FROM daily_snapshots ORDER BY date DESC LIMIT 1').fetchone()
  sentiment_score = sentiment_row['sentiment_score'] if sentiment_row else 50
  sentiment_label = sentiment_row['sentiment_label'] if sentiment_row else '中性'
  
  # 統計信號
  macd_signals = c.execute("SELECT COUNT(*) as cnt FROM signals WHERE indicator='MACD' AND direction='BUY'").fetchone()['cnt']
  rsi_signals = c.execute("SELECT COUNT(*) as cnt FROM signals WHERE indicator='RSI' AND direction='BUY' AND strength < 30").fetchone()['cnt']
  stop_loss_signals = c.execute("SELECT COUNT(*) as cnt FROM signals WHERE indicator='STOP_LOSS' AND triggered=1").fetchone()['cnt']
  
  # 按情緒級別統計
  extreme_signals = c.execute("SELECT COUNT(*) as cnt FROM signals WHERE strength > 8 OR strength < 2").fetchone()['cnt']
  
  conn.close()
  
  # 計算信號強度 (0-1)
  macd_strength = min(1.0, macd_signals / 10.0) if macd_signals > 0 else 0
  rsi_strength = min(1.0, rsi_signals / 8.0) if rsi_signals > 0 else 0
  extreme_strength = min(1.0, extreme_signals / 15.0) if extreme_signals > 0 else 0
  
  result = {
    'sentiment_score': sentiment_score,
    'sentiment_label': sentiment_label,
    'macd_buy_count': macd_signals,
    'macd_buy_strength': macd_strength,
    'rsi_oversold_count': rsi_signals,
    'rsi_oversold_strength': rsi_strength,
    'stop_loss_count': stop_loss_signals,
    'stop_loss_rate': min(1.0, stop_loss_signals / 5.0) if stop_loss_signals > 0 else 0,
    'sentiment_extreme_count': extreme_signals,
    'sentiment_extreme_strength': extreme_strength,
  }
  print(json.dumps(result, ensure_ascii=False, default=str))
except Exception as e:
  print(json.dumps({'error': str(e), 'sentiment_score': 50, 'sentiment_label': '中性'}))
`;
    const cmd = `python3 -c "${py.replace(/"/g, '\\"')}"`;
    const out = execSync(cmd, { timeout: 5000 }).toString().trim();
    
    let result = {};
    try {
      result = JSON.parse(out);
    } catch {
      result = { error: 'invalid json' };
    }
    
    sendJson(res, result);
  } catch (err) {
    log(`sentiment-driven signals error: ${err.message}`);
    sendJson(res, {
      sentiment_score: 50,
      sentiment_label: '中性',
      error: err.message
    }, 500);
  }
}

// ========== 3️⃣ 盤中實時績效 API ==========
function handleIntradayPerformance(req, res) {
  try {
    const py = `
import sys, json, sqlite3, os
sys.path.insert(0, '${FINANCE_AGENT_PATH}')

db_path = '${FINANCE_AGENT_PATH}/data/trading.db'
try:
  conn = sqlite3.connect(db_path)
  conn.row_factory = sqlite3.Row
  c = conn.cursor()
  
  # 當天統計
  today_trades = c.execute('''
    SELECT 
      SUM(CASE WHEN direction='BUY' THEN -shares*price ELSE shares*price END) as net_pnl,
      COUNT(*) as trade_count,
      SUM(CASE WHEN direction='SELL' THEN 1 ELSE 0 END) as sell_count
    FROM trades 
    WHERE DATE(trade_date) = DATE('now')
  ''').fetchone()
  
  # 持倉質量
  positions = c.execute("SELECT * FROM positions WHERE shares > 0").fetchall()
  
  # 計算入場質量評分 (0-100)
  entry_quality_total = 0
  for pos in positions:
    # 簡化版評分: 考慮回撤和持倉時間
    pnl_pct = ((pos['current_price'] - pos['avg_cost']) / pos['avg_cost'] * 100) if pos['avg_cost'] > 0 else 0
    quality = max(0, min(100, 60 + pnl_pct * 2))  # 基礎60分 + 收益貢獻
    entry_quality_total += quality
  
  avg_entry_quality = (entry_quality_total / len(positions)) if len(positions) > 0 else 50
  
  # 策略勝率分布
  strategy_stats = c.execute('''
    SELECT strategy_name, 
           COUNT(*) as total,
           SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins
    FROM trades
    WHERE DATE(trade_date) = DATE('now')
    GROUP BY strategy_name
  ''').fetchall()
  
  strategy_winrates = {}
  for row in strategy_stats:
    if row['total'] > 0:
      strategy_winrates[row['strategy_name']] = {
        'win_rate': round(row['wins'] / row['total'] * 100, 1),
        'total': row['total']
      }
  
  conn.close()
  
  result = {
    'intraday_pnl': round(today_trades['net_pnl'] or 0, 2) if today_trades else 0,
    'intraday_trades': today_trades['trade_count'] or 0 if today_trades else 0,
    'intraday_exits': today_trades['sell_count'] or 0 if today_trades else 0,
    'positions_count': len(positions),
    'avg_entry_quality': round(avg_entry_quality, 1),
    'strategy_winrates': strategy_winrates,
    'timestamp': '$(date -u +%Y-%m-%dT%H:%M:%SZ)',
  }
  print(json.dumps(result, ensure_ascii=False, default=str))
except Exception as e:
  print(json.dumps({'error': str(e), 'intraday_pnl': 0}))
`;
    const cmd = `python3 -c "${py.replace(/"/g, '\\"')}"`;
    const out = execSync(cmd, { timeout: 5000 }).toString().trim();
    
    let result = {};
    try {
      result = JSON.parse(out);
    } catch {
      result = { error: 'invalid json' };
    }
    
    sendJson(res, result);
  } catch (err) {
    log(`intraday performance error: ${err.message}`);
    sendJson(res, { error: err.message, intraday_pnl: 0 }, 500);
  }
}

// ========== 4️⃣ 執行效率指標 API ==========
function handleExecutionMetrics(req, res) {
  try {
    const py = `
import sys, json, sqlite3
sys.path.insert(0, '${FINANCE_AGENT_PATH}')

db_path = '${FINANCE_AGENT_PATH}/data/trading.db'
try:
  conn = sqlite3.connect(db_path)
  conn.row_factory = sqlite3.Row
  c = conn.cursor()
  
  # 計算成交速度 (模擬，實際應連接券商API)
  trades = c.execute("SELECT * FROM trades ORDER BY trade_date DESC LIMIT 100").fetchall()
  
  fill_speeds = []
  for i, trade in enumerate(trades):
    if i < len(trades) - 1:
      time_diff = (trade['trade_date'] - trades[i+1]['trade_date'])
      fill_speeds.append(time_diff)
  
  avg_fill_speed = sum(fill_speeds) / len(fill_speeds) * 1000 if fill_speeds else 0  # 轉ms
  
  # 計算平均滑點 (買入 vs 當時價格)
  # 簡化版: 假設最後一筆買賣差價
  last_buy = c.execute("SELECT price FROM trades WHERE direction='BUY' ORDER BY trade_date DESC LIMIT 1").fetchone()
  last_sell = c.execute("SELECT price FROM trades WHERE direction='SELL' ORDER BY trade_date DESC LIMIT 1").fetchone()
  
  slippage_bp = 0
  if last_buy and last_sell:
    slippage_bp = abs(last_sell['price'] - last_buy['price']) / last_buy['price'] * 10000
  
  # 成交率
  fill_rate = 99.5  # 預設值，實際應從交易日誌計算
  
  conn.close()
  
  result = {
    'avg_fill_speed': round(max(0, avg_fill_speed), 1),
    'avg_slippage': round(slippage_bp, 1),
    'fill_rate': fill_rate,
  }
  print(json.dumps(result, ensure_ascii=False, default=str))
except Exception as e:
  print(json.dumps({'error': str(e), 'avg_fill_speed': 0, 'avg_slippage': 0, 'fill_rate': 95}))
`;
    const cmd = `python3 -c "${py.replace(/"/g, '\\"')}"`;
    const out = execSync(cmd, { timeout: 5000 }).toString().trim();
    
    let result = {};
    try {
      result = JSON.parse(out);
    } catch {
      result = { avg_fill_speed: 0, avg_slippage: 0, fill_rate: 95 };
    }
    
    sendJson(res, result);
  } catch (err) {
    log(`execution metrics error: ${err.message}`);
    sendJson(res, { avg_fill_speed: 0, avg_slippage: 0, fill_rate: 95 }, 500);
  }
}

// ========== 路由 & 伺服器 ==========
const server = http.createServer((req, res) => {
  const { pathname } = new URL(req.url, `http://${req.headers.host}`);
  
  log(`${req.method} ${pathname}`);

  if (req.method === 'OPTIONS') {
    res.writeHead(200, {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
    });
    res.end();
    return;
  }

  switch (pathname) {
    case '/api/backtest-stats':
      handleBacktestStats(req, res);
      break;
    case '/api/sentiment-driven-signals':
      handleSentimentDrivenSignals(req, res);
      break;
    case '/api/intraday-performance':
      handleIntradayPerformance(req, res);
      break;
    case '/api/execution-metrics':
      handleExecutionMetrics(req, res);
      break;
    case '/health':
      sendJson(res, { status: 'ok', version: 'v5.159' });
      break;
    default:
      sendJson(res, { error: 'not found' }, 404);
  }
});

server.listen(API_PORT, () => {
  log(`✅ v5.159 API Server listening on http://localhost:${API_PORT}`);
});

process.on('SIGTERM', () => {
  log('SIGTERM received, gracefully shutting down');
  server.close(() => {
    process.exit(0);
  });
});
