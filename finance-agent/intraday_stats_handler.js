#!/usr/bin/env node
'use strict';

// 新增 handleIntradayStats handler (v5.88)
function handleIntradayStats(req, res) {
  try {
    const pyCode = `
import sys, json
sys.path.insert(0, '/home/nikefd/finance-agent')
try:
  from ui_intraday_stats_api import IntradayStatsCollector
  collector = IntradayStatsCollector()
  stats = collector.collect_all_stats()
  collector.close()
  print(json.dumps(stats, ensure_ascii=False))
except Exception as e:
  import traceback
  traceback.print_exc()
  print(json.dumps({
    'timestamp': '',
    'cash_status': {'mode': 'unknown', 'cash_ratio': 0},
    'trade_metrics': {'total_trades': 0, 'win_rate': 0},
    'macd_signals': {'macd_signals_today': 0},
    'portfolio_heat_map': {'high_gain': [], 'normal': [], 'warning': [], 'danger': []}
  }))
`;
    const { execSync } = require('child_process');
    const out = execSync(`python3 -c "${pyCode.replace(/"/g, '\\"')}"`, { timeout: 10000 }).toString().trim();
    const result = JSON.parse(out || '{}');
    console.log(`[handleIntradayStats] Success: cash_mode=${result.cash_status?.mode}`);
    
    // Return response
    const http = require('http');
    res.writeHead(200, {
      'Content-Type': 'application/json; charset=utf-8',
      'Access-Control-Allow-Origin': '*'
    });
    res.end(JSON.stringify(result));
  } catch (e) {
    console.log(`[handleIntradayStats] Error: ${e.message}`);
    res.writeHead(500, {
      'Content-Type': 'application/json; charset=utf-8',
      'Access-Control-Allow-Origin': '*'
    });
    res.end(JSON.stringify({
      timestamp: new Date().toISOString(),
      cash_status: { mode: 'error', cash_ratio: 0, activated: false },
      trade_metrics: { total_trades: 0, win_rate: 0, avg_pnl_pct: 0 },
      macd_signals: { macd_signals_today: 0, histogram_crosses_today: 0 },
      portfolio_heat_map: { high_gain: [], normal: [], warning: [], danger: [] }
    }));
  }
}

module.exports = { handleIntradayStats };
