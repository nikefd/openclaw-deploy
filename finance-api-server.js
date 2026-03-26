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

function querySqlite(sql) {
  const escaped = sql.replace(/'/g, "'\\''");
  const py = `import sqlite3,json;c=sqlite3.connect('${DB_PATH}');c.row_factory=sqlite3.Row;r=c.execute('''${escaped}''').fetchall();print(json.dumps([dict(x) for x in r]))`;
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
  sendJson(res, { trades: querySqlite(sql) });
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
  sendJson(res, { news: [] });
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
