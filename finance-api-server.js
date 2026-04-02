#!/usr/bin/env node
'use strict';

const http = require('http');
const { execSync, exec } = require('child_process');
const fs = require('fs');
const path = require('path');

const PORT = 7684;
const DB_PATH = '/home/nikefd/finance-agent/data/trading.db';
const REPORTS_DIR = '/home/nikefd/finance-agent/reports';
const INITIAL_CAPITAL = 1000000;

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
    'Access-Control-Allow-Headers': 'Content-Type,Authorization',
  });
  res.end(JSON.stringify(data));
}

function sendError(res, msg, status = 500) {
  sendJson(res, { error: msg }, status);
}

function parseUrl(url) {
  const [pathname, qs] = url.split('?');
  const params = {};
  if (qs) qs.split('&').forEach(p => { const [k, v] = p.split('='); params[decodeURIComponent(k)] = decodeURIComponent(v || ''); });
  return { pathname, params };
}

// --- Handlers ---

function handleDashboard(req, res) {
  const accounts = querySqlite('SELECT * FROM account ORDER BY id DESC LIMIT 1');
  const positions = querySqlite('SELECT * FROM positions');
  const snapshots = querySqlite("SELECT * FROM daily_snapshots ORDER BY date DESC LIMIT 2");

  const account = accounts[0] || { cash: 0, total_value: 0 };
  const posData = positions.map(p => {
    const pnl = (p.current_price - p.avg_cost) * p.shares;
    const pnl_pct = p.avg_cost ? ((p.current_price - p.avg_cost) / p.avg_cost * 100) : 0;
    return { ...p, pnl: Math.round(pnl * 100) / 100, pnl_pct: Math.round(pnl_pct * 100) / 100 };
  });

  const today = snapshots[0];
  const yesterday = snapshots[1];
  const todayPnl = (today && yesterday) ? today.total_value - yesterday.total_value : 0;
  const totalReturnPct = account.total_value ? ((account.total_value - INITIAL_CAPITAL) / INITIAL_CAPITAL * 100) : 0;

  const sentimentScore = today ? (today.sentiment_score || 50) : 50;
  const sentimentLabel = sentimentScore >= 70 ? '乐观' : sentimentScore >= 40 ? '中性' : '悲观';

  sendJson(res, {
    account: { cash: account.cash, total_value: account.total_value, initial_capital: INITIAL_CAPITAL },
    positions: posData,
    sentiment: { score: sentimentScore, label: sentimentLabel },
    today_pnl: Math.round(todayPnl * 100) / 100,
    total_return_pct: Math.round(totalReturnPct * 100) / 100,
  });
}

function handleAnalysis(req, res) {
  // Find latest report
  let marketAnalysis = '';
  let reportDate = '';
  try {
    const files = fs.readdirSync(REPORTS_DIR).filter(f => f.endsWith('.md')).sort().reverse();
    if (files.length > 0) {
      reportDate = files[0].replace('.md', '');
      marketAnalysis = fs.readFileSync(path.join(REPORTS_DIR, files[0]), 'utf-8');
    }
  } catch (e) { log(`Reports read error: ${e.message}`); }

  const signals = querySqlite("SELECT * FROM signals ORDER BY created_at DESC LIMIT 10");
  const picks = signals.filter(s => s.direction === 'BUY').map(s => ({
    symbol: s.symbol, name: s.name, confidence: s.strength || 5,
    reason: s.reason || '', buy_price: 0, target_price: 0, stop_loss: 0,
  }));

  sendJson(res, { market_analysis: marketAnalysis, picks, date: reportDate });
}

function handleTrades(req, res, params) {
  let sql = 'SELECT * FROM trades WHERE 1=1';
  if (params.direction) sql += ` AND direction='${params.direction}'`;
  if (params.start) sql += ` AND trade_date>='${params.start}'`;
  if (params.end) sql += ` AND trade_date<='${params.end}'`;
  sql += ' ORDER BY trade_date DESC, id DESC';
  const trades = querySqlite(sql);

  // Calculate PnL for SELL trades by matching with earlier BUY trades
  const buyMap = {};  // symbol -> [{price, shares, date}]
  // Process in chronological order to build buy history
  const allTrades = querySqlite('SELECT * FROM trades ORDER BY trade_date ASC, id ASC');
  allTrades.forEach(t => {
    if (t.direction === 'BUY') {
      if (!buyMap[t.symbol]) buyMap[t.symbol] = [];
      buyMap[t.symbol].push({ price: t.price, shares: t.shares, remaining: t.shares });
    }
  });
  // Calculate avg cost per symbol
  const avgCosts = {};
  Object.keys(buyMap).forEach(sym => {
    const buys = buyMap[sym];
    const totalShares = buys.reduce((s, b) => s + b.shares, 0);
    const totalCost = buys.reduce((s, b) => s + b.price * b.shares, 0);
    avgCosts[sym] = totalShares > 0 ? totalCost / totalShares : 0;
  });
  // Attach pnl to sell trades
  trades.forEach(t => {
    if (t.direction === 'SELL' && avgCosts[t.symbol]) {
      t.pnl = Math.round((t.price - avgCosts[t.symbol]) * t.shares * 100) / 100;
    }
  });

  sendJson(res, { trades });
}

function handleReportsList(req, res) {
  try {
    const files = fs.readdirSync(REPORTS_DIR).filter(f => f.endsWith('.md')).sort().reverse();
    sendJson(res, { reports: files.map(f => ({ date: f.replace('.md', ''), filename: f })) });
  } catch (e) { sendJson(res, { reports: [] }); }
}

function handleReportDetail(req, res, date) {
  const filePath = path.join(REPORTS_DIR, `${date}.md`);
  try {
    const content = fs.readFileSync(filePath, 'utf-8');
    sendJson(res, { date, content });
  } catch (e) { sendError(res, '报告未找到', 404); }
}

function handleNews(req, res) {
  try {
    const py = `
import json
from data_collector import get_stock_news
df = get_stock_news()
items = []
if df is not None and not df.empty:
    for _, row in df.head(30).iterrows():
        items.append({
            "title": str(row.get("新闻标题", "")),
            "content": str(row.get("新闻内容", ""))[:200],
            "time": str(row.get("发布时间", "")),
            "source": str(row.get("文章来源", "")),
            "keyword": str(row.get("关键词", "")),
            "url": str(row.get("新闻链接", ""))
        })
print(json.dumps(items, ensure_ascii=False))
`;
    const out = execSync(`cd /home/nikefd/finance-agent && python3 -c '${py.replace(/'/g, "'\\''")}'`, { timeout: 30000 }).toString().trim();
    const news = JSON.parse(out || '[]');
    sendJson(res, { news });
  } catch (e) {
    log(`News error: ${e.message}`);
    sendJson(res, { news: [] });
  }
}

function handleChart(req, res) {
  const rows = querySqlite('SELECT date, total_value FROM daily_snapshots ORDER BY date ASC');
  const dates = rows.map(r => r.date);
  const values = rows.map(r => r.total_value);
  const returns = values.map(v => Math.round((v - INITIAL_CAPITAL) / INITIAL_CAPITAL * 10000) / 100);
  sendJson(res, { dates, values, returns });
}

let runState = { status: 'idle', log: '', startTime: null };
const RUN_LOG_FILE = '/tmp/finance-runner.log';

function handleRun(req, res) {
  if (runState.status === 'running') {
    return sendJson(res, { status: 'already_running', message: '分析正在运行中' });
  }

  log('Triggering daily_runner.py...');
  runState = { status: 'running', log: '', startTime: Date.now() };

  // Clear log file
  try { fs.writeFileSync(RUN_LOG_FILE, ''); } catch(e) {}

  const child = exec('cd /home/nikefd/finance-agent && python3 -u daily_runner.py 2>&1', { timeout: 300000 });

  child.stdout.on('data', (data) => {
    runState.log += data;
    try { fs.appendFileSync(RUN_LOG_FILE, data); } catch(e) {}
  });
  child.stderr.on('data', (data) => {
    runState.log += data;
    try { fs.appendFileSync(RUN_LOG_FILE, data); } catch(e) {}
  });
  child.on('close', (code) => {
    const elapsed = ((Date.now() - runState.startTime) / 1000).toFixed(1);
    const msg = code === 0 ? `\n✅ 分析完成 (耗时${elapsed}s)` : `\n❌ 分析失败 (code=${code}, 耗时${elapsed}s)`;
    runState.log += msg;
    runState.status = code === 0 ? 'done' : 'error';
    try { fs.appendFileSync(RUN_LOG_FILE, msg); } catch(e) {}
    log(`Runner finished: code=${code}, elapsed=${elapsed}s`);
  });

  sendJson(res, { status: 'running', message: '分析已触发' });
}

function handleRunStatus(req, res) {
  // Also try reading from log file if log is empty
  let logContent = runState.log;
  if (!logContent && runState.status === 'idle') {
    try { logContent = fs.readFileSync(RUN_LOG_FILE, 'utf-8'); } catch(e) {}
  }
  sendJson(res, { status: runState.status, log: logContent });
}

// --- Router ---

const server = http.createServer((req, res) => {
  if (req.method === 'OPTIONS') { sendJson(res, {}); return; }

  const { pathname, params } = parseUrl(req.url);
  log(`${req.method} ${pathname}`);

  try {
    if (pathname === '/api/finance/dashboard' && req.method === 'GET') return handleDashboard(req, res);
    if (pathname === '/api/finance/analysis' && req.method === 'GET') return handleAnalysis(req, res);
    if (pathname === '/api/finance/trades' && req.method === 'GET') return handleTrades(req, res, params);
    if (pathname === '/api/finance/reports' && req.method === 'GET') return handleReportsList(req, res);
    if (pathname === '/api/finance/news' && req.method === 'GET') return handleNews(req, res);
    if (pathname === '/api/finance/chart' && req.method === 'GET') return handleChart(req, res);
    if (pathname === '/api/finance/run' && req.method === 'POST') return handleRun(req, res);
    if (pathname === '/api/finance/run/status' && req.method === 'GET') return handleRunStatus(req, res);
    if (pathname === '/api/finance/changelog' && req.method === 'GET') {
      try {
        const content = fs.readFileSync('/home/nikefd/finance-agent/changelog.md', 'utf-8');
        return sendJson(res, { content });
      } catch(e) { return sendJson(res, { content: '暂无更新日志' }); }
    }
    if (pathname === '/api/finance/backtest' && req.method === 'GET') {
      try {
        const rows = querySqlite("SELECT id, strategy, start_date, end_date, initial_capital, final_value, total_return, max_drawdown, win_rate, total_trades, win_trades, loss_trades, sharpe_ratio, profit_factor, created_at FROM backtest_runs ORDER BY created_at DESC LIMIT 20",
          '/home/nikefd/finance-agent/data/backtest.db');
        return sendJson(res, { results: rows });
      } catch(e) { return sendJson(res, { results: [] }); }
    }
    if (pathname === '/api/finance/performance' && req.method === 'GET') {
      try {
        const py = `import json,sys; sys.path.insert(0,'/home/nikefd/finance-agent'); from performance_tracker import get_performance_summary, update_recommendation_outcomes; update_recommendation_outcomes(); print(json.dumps(get_performance_summary(), ensure_ascii=False, default=str))`;
        const out = execSync(`python3 -c "${py.replace(/"/g, '\\"')}"`, { timeout: 30000 }).toString().trim();
        return sendJson(res, JSON.parse(out));
      } catch(e) { return sendJson(res, { total_recommendations: 0, error: e.message }); }
    }
    if (pathname === '/api/finance/backtest/run' && req.method === 'POST') {
      log('Triggering backtest...');
      exec('cd /home/nikefd/finance-agent && python3 -u backtester.py >> /tmp/finance-backtest.log 2>&1', { timeout: 600000 }, (err) => {
        if (err) log('Backtest error: ' + err.message);
        else log('Backtest completed');
      });
      return sendJson(res, { status: 'running', message: '回测已触发' });
    }
    if (pathname === '/api/finance/live-status' && req.method === 'GET') {
      try {
        const py = `import json; from live_trader import check_live_readiness; print(json.dumps(check_live_readiness(), ensure_ascii=False, default=str))`;
        const out = execSync(`cd /home/nikefd/finance-agent && python3 -c "${py.replace(/"/g, '\\"')}"`, { timeout: 10000 }).toString().trim();
        return sendJson(res, JSON.parse(out));
      } catch(e) { return sendJson(res, { ready: false, error: e.message }); }
    }
    if (pathname === '/api/finance/regime' && req.method === 'GET') {
      try {
        const py = `import json,sys; sys.path.insert(0,'/home/nikefd/finance-agent'); from market_regime import detect_market_regime; print(json.dumps(detect_market_regime(), ensure_ascii=False, default=str))`;
        const out = execSync(`python3 -c "${py.replace(/"/g, '\\"')}"`, { timeout: 30000 }).toString().trim();
        return sendJson(res, JSON.parse(out));
      } catch(e) { return sendJson(res, { regime: 'unknown', error: e.message }); }
    }
    if (pathname === '/api/finance/datasources' && req.method === 'GET') {
      try {
        const py = `import json,sys; sys.path.insert(0,'/home/nikefd/finance-agent'); from datasource_monitor import get_health_summary; print(json.dumps(get_health_summary(24), ensure_ascii=False, default=str))`;
        const out = execSync(`python3 -c "${py.replace(/"/g, '\\"')}"`, { timeout: 10000 }).toString().trim();
        return sendJson(res, { sources: JSON.parse(out) });
      } catch(e) { return sendJson(res, { sources: [], error: e.message }); }
    }
    if (pathname === '/api/finance/datasources/check' && req.method === 'POST') {
      log('Triggering datasource health check...');
      exec('cd /home/nikefd/finance-agent && python3 -u datasource_monitor.py >> /tmp/ds-health.log 2>&1', { timeout: 120000 }, (err) => {
        if (err) log('Health check error: ' + err.message);
        else log('Health check completed');
      });
      return sendJson(res, { status: 'running', message: '健康检查已触发' });
    }

    // /api/finance/reports/:date
    const reportMatch = pathname.match(/^\/api\/finance\/reports\/(\d{4}-\d{2}-\d{2})$/);
    if (reportMatch && req.method === 'GET') return handleReportDetail(req, res, reportMatch[1]);

    sendError(res, 'Not Found', 404);
  } catch (e) {
    log(`Error: ${e.message}`);
    sendError(res, e.message);
  }
});

server.listen(PORT, () => log(`Finance API server running on port ${PORT}`));
