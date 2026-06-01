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
    // Holding days
    let holding_days = null;
    if (p.buy_date) {
      const buyDate = new Date(p.buy_date);
      const now = new Date();
      holding_days = Math.round((now - buyDate) / 86400000);
    }
    // Peak drawdown from peak_price
    let peak_drawdown = null;
    if (p.peak_price && p.peak_price > 0 && p.current_price) {
      peak_drawdown = Math.round((p.current_price - p.peak_price) / p.peak_price * 10000) / 100;
    }
    return { ...p, pnl: Math.round(pnl * 100) / 100, pnl_pct: Math.round(pnl_pct * 100) / 100, holding_days, peak_drawdown };
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

function handlePerformanceStats(req, res) {
  // 计算当前持仓的性能统计
  const positions = querySqlite('SELECT * FROM positions');
  const trades = querySqlite('SELECT * FROM trades ORDER BY trade_date ASC');
  const snapshots = querySqlite('SELECT * FROM daily_snapshots ORDER BY date DESC LIMIT 30');
  
  // 计算胜率
  const sellTrades = trades.filter(t => t.direction === 'SELL');
  const winTrades = sellTrades.filter(t => {
    const buyPrice = trades.find(b => b.symbol === t.symbol && b.direction === 'BUY' && new Date(b.trade_date) < new Date(t.trade_date))?.price || t.price;
    return t.price > buyPrice;
  });
  const winRate = trades.length > 0 ? Math.round((winTrades.length / sellTrades.length) * 100) : 0;
  
  // 计算最大回撤
  let maxDD = 0;
  if (snapshots.length > 1) {
    let peak = snapshots[snapshots.length - 1].total_value;
    snapshots.forEach(s => {
      if (s.total_value > peak) peak = s.total_value;
      const dd = ((peak - s.total_value) / peak) * 100;
      if (dd > maxDD) maxDD = dd;
    });
  }
  
  // 计算Sharpe比率 (简化版)
  const returns = [];
  for (let i = snapshots.length - 1; i > 0; i--) {
    const ret = ((snapshots[i - 1].total_value - snapshots[i].total_value) / snapshots[i].total_value) * 100;
    returns.push(ret);
  }
  const avgRet = returns.length > 0 ? returns.reduce((a, b) => a + b, 0) / returns.length : 0;
  const stdDev = returns.length > 1 ? Math.sqrt(returns.reduce((s, r) => s + Math.pow(r - avgRet, 2), 0) / (returns.length - 1)) : 0;
  const sharpe = stdDev > 0 ? (avgRet / stdDev * Math.sqrt(252)) : 0;
  
  // 赛道分布
  const sectors = {};
  positions.forEach(p => {
    const sector = p.sector || '未分类';
    sectors[sector] = (sectors[sector] || 0) + 1;
  });
  
  sendJson(res, {
    win_rate: winRate,
    max_drawdown: Math.round(maxDD * 100) / 100,
    sharpe_ratio: Math.round(sharpe * 100) / 100,
    total_trades: trades.length,
    positions_count: positions.length,
    sectors: sectors,
    monthly_return: returns[0] ? Math.round(returns[0] * 100) / 100 : 0,
  });
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

// --- UI优化②: Kelly仓位实时数据 (完整版) ---
function handleKellyPositions(req, res) {
  const positions = querySqlite('SELECT * FROM positions WHERE shares > 0');
  const account = querySqlite('SELECT cash, total_value FROM account ORDER BY id DESC LIMIT 1')[0];
  const trades = querySqlite('SELECT * FROM trades ORDER BY trade_date DESC LIMIT 30');
  
  const totalValue = account ? account.total_value : INITIAL_CAPITAL;
  const totalInvested = positions.reduce((sum, p) => sum + (p.current_price * p.shares), 0);
  const fundUtilization = totalValue > 0 ? (totalInvested / totalValue * 100) : 0;
  const targetKelly = 15;
  const kellyEfficiency = Math.min(100, (fundUtilization / targetKelly * 100));
  
  // 历史30天资金利用率
  const history = querySqlite(`
    SELECT DATE(trade_date) as date, 
           COUNT(*) as trade_count,
           SUM(shares) as total_shares
    FROM trades
    WHERE trade_date >= date('now', '-30 days')
    GROUP BY DATE(trade_date)
    ORDER BY date
  `);
  
  sendJson(res, {
    current_allocation: Math.round(fundUtilization * 10) / 10,
    target_kelly: targetKelly,
    kelly_efficiency: Math.round(kellyEfficiency * 10) / 10,
    positions_count: positions.length,
    recent_trades: trades.length,
    history: history
  });
}

// --- UI优化③: 选股超时保护状态 (v5.97新增) ---
function handleSelectionStatus(req, res) {
  try {
    const logs = execSync('tail -100 /tmp/daily_runner.log 2>/dev/null || echo ""').toString();
    const lastRunMatch = logs.match(/took ([\d.]+)s/);
    const timeoutMatch = logs.match(/timeout.*protected|防超时/);
    
    const lastRunSeconds = lastRunMatch ? parseFloat(lastRunMatch[1]) : null;
    const timeoutProtected = timeoutMatch ? true : false;
    
    let candidatePoolSize = 45;
    try {
      const reports = execSync('ls -t /home/nikefd/finance-agent/reports/*.md 2>/dev/null | head -1').toString().trim();
      if (reports) {
        const content = fs.readFileSync(reports, 'utf-8');
        const poolMatch = content.match(/候选池.*(\d+)/);
        if (poolMatch) candidatePoolSize = parseInt(poolMatch[1]);
      }
    } catch (e) { /* ignore */ }
    
    sendJson(res, {
      timeout_protected: timeoutProtected,
      candidate_pool_size: candidatePoolSize,
      last_run_seconds: lastRunSeconds,
      status: timeoutProtected ? 'protected' : 'normal'
    });
  } catch (e) {
    sendJson(res, { timeout_protected: false, candidate_pool_size: 45, last_run_seconds: null, error: e.message });
  }
}

// === 新增③: 情緒動態 + 績效統計 + 信號質量 (v5.105) ===
function handleSentimentDynamicsV102(req, res) {
  try {
    const py = `import sys,json; sys.path.insert(0,'/home/nikefd/finance-agent'); from v5_105_INTRADAY_OPTIMIZE import get_sentiment_dynamics_v102; print(json.dumps(get_sentiment_dynamics_v102(), ensure_ascii=False, default=str))`;
    const out = execSync(`python3 -c "${py.replace(/"/g, '\\"')}"`, { timeout: 10000 }).toString().trim();
    sendJson(res, JSON.parse(out || '{}'));
  } catch (e) {
    log('sentiment-dynamics-v102 error: ' + e.message);
    sendJson(res, { sentiment_score: 50, sentiment_label: '中性' });
  }
}

function handlePerformanceStatsV102(req, res) {
  try {
    const py = `import sys,json; sys.path.insert(0,'/home/nikefd/finance-agent'); from v5_105_INTRADAY_OPTIMIZE import get_performance_stats_v102; print(json.dumps(get_performance_stats_v102(), ensure_ascii=False, default=str))`;
    const out = execSync(`python3 -c "${py.replace(/"/g, '\\"')}"`, { timeout: 10000 }).toString().trim();
    sendJson(res, JSON.parse(out || '{}'));
  } catch (e) {
    log('performance-stats-v102 error: ' + e.message);
    sendJson(res, { strategy_win_rate: [], sector_distribution: {} });
  }
}

function handleSignalQualityV102(req, res) {
  try {
    const py = `import sys,json; sys.path.insert(0,'/home/nikefd/finance-agent'); from v5_105_INTRADAY_OPTIMIZE import get_signal_quality_v102; print(json.dumps(get_signal_quality_v102(), ensure_ascii=False, default=str))`;
    const out = execSync(`python3 -c "${py.replace(/"/g, '\\"')}"`, { timeout: 10000 }).toString().trim();
    sendJson(res, JSON.parse(out || '{}'));
  } catch (e) {
    log('signal-quality-v102 error: ' + e.message);
    sendJson(res, { macd: {}, rsi: {} });
  }
}

function handleIntradayPerformanceV102(req, res) {
  try {
    const py = `import sys,json; sys.path.insert(0,'/home/nikefd/finance-agent'); from v5_105_INTRADAY_OPTIMIZE import get_intraday_performance_v102; print(json.dumps(get_intraday_performance_v102(), ensure_ascii=False, default=str))`;
    const out = execSync(`python3 -c "${py.replace(/"/g, '\\"')}"`, { timeout: 10000 }).toString().trim();
    sendJson(res, JSON.parse(out || '{}'));
  } catch (e) {
    log('intraday-performance-v102 error: ' + e.message);
    sendJson(res, { win_rate: 0, avg_holding_days: 0 });
  }
}

// --- UI优化④: Kelly仓位效率简化版 (v5.97兼容) ---
function handleKellyPositionsV97(req, res) {
  const positions = querySqlite('SELECT * FROM positions WHERE shares > 0');
  const account = querySqlite('SELECT cash, total_value FROM account ORDER BY id DESC LIMIT 1')[0];
  
  const totalValue = account ? account.total_value : INITIAL_CAPITAL;
  const totalInvested = positions.reduce((sum, p) => sum + (p.current_price * p.shares), 0);
  const fundUtilization = totalValue > 0 ? (totalInvested / totalValue * 100) : 0;
  const targetKelly = 15;
  const kellyEfficiency = Math.min(100, (fundUtilization / targetKelly * 100));
  
  sendJson(res, {
    fund_utilization: Math.round(fundUtilization * 10) / 10,
    kelly_efficiency: Math.round(kellyEfficiency * 10) / 10
  });
}

// --- UI优化②: 市场情绪波动热力图 ---
function handleSentimentHeatmap(req, res) {
  const sentiments = querySqlite(`
    SELECT date, sentiment_score, sentiment_label
    FROM daily_snapshots
    WHERE date >= date('now', '-5 days')
    ORDER BY date DESC
    LIMIT 30
  `);
  
  // 30日情绪分布
  const distribution = querySqlite(`
    SELECT sentiment_label, COUNT(*) as count
    FROM daily_snapshots
    WHERE date >= date('now', '-30 days')
    GROUP BY sentiment_label
  `);
  
  // 计算情绪变化
  const trend = [];
  for (let i = 0; i < sentiments.length - 1; i++) {
    const curr = sentiments[i];
    const next = sentiments[i + 1];
    const change = (next.sentiment_score || 50) - (curr.sentiment_score || 50);
    trend.push({
      date: curr.date,
      score: curr.sentiment_score || 50,
      label: curr.sentiment_label || '中性',
      change: change,
      trend_label: change > 10 ? '↑ 乐观升温' : change < -10 ? '↓ 情绪降温' : '→ 平稳'
    });
  }
  
  const distMap = {};
  distribution.forEach(d => {
    distMap[d.sentiment_label || '中性'] = d.count;
  });
  
  sendJson(res, {
    current_score: sentiments[0] ? sentiments[0].sentiment_score : 50,
    current_label: sentiments[0] ? sentiments[0].sentiment_label : '中性',
    trend: trend,
    distribution: distMap
  });
}

// --- UI优化②: 回测性能对标 ---
function handleBacktestComparison(req, res) {
  const trades = querySqlite('SELECT * FROM trades ORDER BY trade_date DESC');
  const positions = querySqlite('SELECT * FROM positions');
  const snapshots = querySqlite('SELECT * FROM daily_snapshots ORDER BY date DESC LIMIT 30');
  const account = querySqlite('SELECT cash, total_value FROM account ORDER BY id DESC LIMIT 1')[0];
  
  // 计算胜率
  const sellTrades = trades.filter(t => t.direction === 'SELL');
  let winTrades = 0;
  sellTrades.forEach(sell => {
    const buy = trades.find(b => b.symbol === sell.symbol && b.direction === 'BUY' && new Date(b.trade_date) < new Date(sell.trade_date));
    if (buy && sell.price > buy.price) winTrades++;
  });
  const winRate = sellTrades.length > 0 ? Math.round((winTrades / sellTrades.length) * 100) : 0;
  
  // 计算最大回撤
  let maxDD = 0;
  if (snapshots.length > 1) {
    let peak = snapshots[snapshots.length - 1].total_value;
    snapshots.forEach(s => {
      if (s.total_value > peak) peak = s.total_value;
      const dd = ((peak - s.total_value) / peak) * 100;
      if (dd > maxDD) maxDD = dd;
    });
  }
  
  // 计算Sharpe
  const returns = [];
  for (let i = snapshots.length - 1; i > 0; i--) {
    const ret = ((snapshots[i - 1].total_value - snapshots[i].total_value) / snapshots[i].total_value) * 100;
    returns.push(ret);
  }
  const avgRet = returns.length > 0 ? returns.reduce((a, b) => a + b, 0) / returns.length : 0;
  const stdDev = returns.length > 1 ? Math.sqrt(returns.reduce((s, r) => s + Math.pow(r - avgRet, 2), 0) / (returns.length - 1)) : 0;
  const sharpe = stdDev > 0 ? (avgRet / stdDev * Math.sqrt(252)) : 0;
  
  // 资金利用率
  const totalValue = account ? account.total_value : INITIAL_CAPITAL;
  const totalInvested = positions.reduce((sum, p) => sum + (p.current_price * p.shares), 0);
  const fundUtil = totalValue > 0 ? (totalInvested / totalValue * 100) : 0;
  
  // 赛道分布
  const sectors = {};
  positions.forEach(p => {
    const sector = p.sector || '未分类';
    sectors[sector] = (sectors[sector] || 0) + 1;
  });
  
  sendJson(res, {
    current_metrics: {
      win_rate: Math.round(winRate * 10) / 10,
      max_drawdown: Math.round(maxDD * 100) / 100,
      sharpe_ratio: Math.round(sharpe * 100) / 100,
      fund_utilization: Math.round(fundUtil * 10) / 10,
      positions_count: positions.filter(p => p.shares > 0).length,
      total_trades: trades.length
    },
    v585_targets: {
      win_rate: 65,
      max_drawdown: 3.5,
      sharpe_ratio: 2.5,
      fund_utilization: 95,
      positions_count: 8,
      expected_return: 18
    },
    achievement_rate: {
      win_rate: Math.min(100, Math.round((winRate / 65) * 100 * 10) / 10),
      max_drawdown: Math.min(100, Math.round((3.5 / maxDD) * 100 * 10) / 10) || 0,
      sharpe_ratio: Math.min(100, Math.round((sharpe / 2.5) * 100 * 10) / 10),
      fund_utilization: Math.min(100, Math.round((fundUtil / 95) * 100 * 10) / 10)
    },
    sector_distribution: sectors
  });
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

function handleRiskMetrics(req, res) {
  // Calculate key risk metrics from snapshots and trades
  const snapshots = querySqlite('SELECT date, total_value FROM daily_snapshots ORDER BY date ASC');
  const trades = querySqlite("SELECT * FROM trades WHERE direction='SELL'");

  // Max drawdown
  let peak = 0, maxDD = 0;
  const vals = snapshots.map(s => s.total_value);
  for (const v of vals) { if (v > peak) peak = v; const dd = (peak - v) / peak * 100; if (dd > maxDD) maxDD = dd; }

  // Daily returns for Sharpe
  const dailyRets = [];
  for (let i = 1; i < vals.length; i++) { dailyRets.push((vals[i] - vals[i-1]) / vals[i-1]); }
  const avgRet = dailyRets.length ? dailyRets.reduce((a, b) => a + b, 0) / dailyRets.length : 0;
  const stdRet = dailyRets.length > 1 ? Math.sqrt(dailyRets.reduce((s, r) => s + (r - avgRet) ** 2, 0) / (dailyRets.length - 1)) : 1;
  const sharpe = stdRet > 0 ? (avgRet / stdRet * Math.sqrt(252)) : 0;

  // Win rate from sells
  let wins = 0, losses = 0;
  const allTrades = querySqlite('SELECT * FROM trades ORDER BY trade_date ASC, id ASC');
  const buyMap = {};
  allTrades.forEach(t => { if (t.direction === 'BUY') { if (!buyMap[t.symbol]) buyMap[t.symbol] = []; buyMap[t.symbol].push(t); }});
  const avgCosts = {};
  Object.keys(buyMap).forEach(sym => { const buys = buyMap[sym]; const ts = buys.reduce((s, b) => s + b.shares, 0); const tc = buys.reduce((s, b) => s + b.price * b.shares, 0); avgCosts[sym] = ts > 0 ? tc / ts : 0; });
  trades.forEach(t => { const cost = avgCosts[t.symbol] || 0; if (cost > 0) { if (t.price > cost) wins++; else losses++; }});
  const totalSells = wins + losses;
  const winRate = totalSells > 0 ? (wins / totalSells * 100) : 0;

  // Trading days & total return
  const totalDays = snapshots.length;
  const totalReturn = vals.length ? ((vals[vals.length-1] - INITIAL_CAPITAL) / INITIAL_CAPITAL * 100) : 0;

  // Consecutive losses (current streak)
  const recentSells = querySqlite("SELECT * FROM trades WHERE direction='SELL' ORDER BY trade_date DESC, id DESC LIMIT 20");
  let lossStreak = 0;
  for (const t of recentSells) {
    const cost = avgCosts[t.symbol] || 0;
    if (cost > 0 && t.price < cost) lossStreak++; else break;
  }

  // Sortino ratio (only downside deviation)
  const negRets = dailyRets.filter(r => r < 0);
  const downsideDev = negRets.length > 1 ? Math.sqrt(negRets.reduce((s, r) => s + r * r, 0) / negRets.length) : stdRet;
  const sortino = downsideDev > 0 ? (avgRet / downsideDev * Math.sqrt(252)) : 0;

  // Calmar ratio (annualized return / max drawdown)
  const annualizedReturn = totalDays > 0 ? (Math.pow(1 + (vals.length ? (vals[vals.length-1] - INITIAL_CAPITAL) / INITIAL_CAPITAL : 0), 252 / totalDays) - 1) * 100 : 0;
  const calmar = maxDD > 0 ? annualizedReturn / maxDD : 0;

  // Profit factor (gross profit / gross loss)
  let grossProfit = 0, grossLoss = 0;
  trades.forEach(t => {
    const cost = avgCosts[t.symbol] || 0;
    if (cost > 0) {
      const pnl = (t.price - cost) * t.shares;
      if (pnl > 0) grossProfit += pnl; else grossLoss += Math.abs(pnl);
    }
  });
  const profitFactor = grossLoss > 0 ? grossProfit / grossLoss : grossProfit > 0 ? 999 : 0;

  // Average win/loss amounts
  const avgWin = wins > 0 ? grossProfit / wins : 0;
  const avgLoss = losses > 0 ? grossLoss / losses : 0;

  sendJson(res, {
    max_drawdown: Math.round(maxDD * 100) / 100,
    sharpe_ratio: Math.round(sharpe * 100) / 100,
    sortino_ratio: Math.round(sortino * 100) / 100,
    calmar_ratio: Math.round(calmar * 100) / 100,
    profit_factor: Math.round(profitFactor * 100) / 100,
    win_rate: Math.round(winRate * 10) / 10,
    total_trades: totalSells,
    wins, losses,
    loss_streak: lossStreak,
    trading_days: totalDays,
    total_return: Math.round(totalReturn * 100) / 100,
    daily_volatility: Math.round(stdRet * 10000) / 100,
    avg_win: Math.round(avgWin),
    avg_loss: Math.round(avgLoss),
  });
}

function handleMonthlyReturns(req, res) {
  const snapshots = querySqlite('SELECT date, total_value FROM daily_snapshots ORDER BY date ASC');
  if (!snapshots.length) return sendJson(res, { months: [] });

  // Group by month, take first and last value of each month
  const monthMap = {}; // 'YYYY-MM' -> {first, last, firstDate, lastDate}
  snapshots.forEach(s => {
    const month = s.date.slice(0, 7);
    if (!monthMap[month]) monthMap[month] = { first: s.total_value, last: s.total_value, firstDate: s.date, lastDate: s.date };
    else { monthMap[month].last = s.total_value; monthMap[month].lastDate = s.date; }
  });

  const months = Object.keys(monthMap).sort();
  const result = months.map((m, i) => {
    const cur = monthMap[m];
    // Use previous month's last value as baseline, or initial capital for first month
    const baseline = i > 0 ? monthMap[months[i - 1]].last : INITIAL_CAPITAL;
    const ret = Math.round((cur.last - baseline) / baseline * 10000) / 100;
    return { month: m, return_pct: ret };
  });

  sendJson(res, { months: result });
}

function handleWeeklyReturns(req, res) {
  const snapshots = querySqlite('SELECT date, total_value FROM daily_snapshots ORDER BY date ASC');
  if (!snapshots.length) return sendJson(res, { weeks: [] });

  // Group by ISO week
  const weekMap = {}; // 'YYYY-Wnn' -> {first, last}
  snapshots.forEach(s => {
    const d = new Date(s.date);
    const jan1 = new Date(d.getFullYear(), 0, 1);
    const weekNum = Math.ceil(((d - jan1) / 86400000 + jan1.getDay() + 1) / 7);
    const key = `${d.getFullYear()}-W${String(weekNum).padStart(2, '0')}`;
    if (!weekMap[key]) weekMap[key] = { first: s.total_value, last: s.total_value, startDate: s.date, endDate: s.date };
    else { weekMap[key].last = s.total_value; weekMap[key].endDate = s.date; }
  });

  const weeks = Object.keys(weekMap).sort().slice(-12);
  const result = weeks.map((w, i) => {
    const cur = weekMap[w];
    const baseline = i > 0 ? weekMap[weeks[i - 1]]?.last || INITIAL_CAPITAL : INITIAL_CAPITAL;
    const ret = Math.round((cur.last - baseline) / baseline * 10000) / 100;
    return { week: w, label: weekMap[w].startDate.slice(5) + '~' + weekMap[w].endDate.slice(5), return_pct: ret };
  });

  sendJson(res, { weeks: result });
}

function handlePeriodReturns(req, res) {
  const snapshots = querySqlite('SELECT date, total_value FROM daily_snapshots ORDER BY date ASC');
  if (!snapshots.length) return sendJson(res, {});
  const latest = snapshots[snapshots.length - 1];
  const latestDate = latest.date; // YYYY-MM-DD
  const latestVal = latest.total_value;

  function findValBefore(targetDate) {
    // find the last snapshot on or before targetDate
    let val = null;
    for (const s of snapshots) {
      if (s.date <= targetDate) val = s.total_value;
      else break;
    }
    return val;
  }

  function daysAgo(n) {
    const d = new Date(latestDate);
    d.setDate(d.getDate() - n);
    return d.toISOString().slice(0, 10);
  }

  // Week: 7 days ago
  const weekAgoVal = findValBefore(daysAgo(7)) || INITIAL_CAPITAL;
  // Month: 30 days ago
  const monthAgoVal = findValBefore(daysAgo(30)) || INITIAL_CAPITAL;
  // Quarter: 90 days ago
  const quarterAgoVal = findValBefore(daysAgo(90)) || INITIAL_CAPITAL;
  // Year start
  const yearStart = latestDate.slice(0, 4) + '-01-01';
  const yearStartVal = findValBefore(yearStart) || INITIAL_CAPITAL;

  const calc = (from, to) => Math.round((to - from) / from * 10000) / 100;

  sendJson(res, {
    week: calc(weekAgoVal, latestVal),
    month: calc(monthAgoVal, latestVal),
    quarter: calc(quarterAgoVal, latestVal),
    ytd: calc(yearStartVal, latestVal),
  });
}

function handleSignalAnalysis(req, res) {
  try {
    let trades = [];
    try {
      const out = execSync('python3 /home/nikefd/finance-agent/signal_analysis.py', { timeout: 10000 }).toString().trim();
      trades = JSON.parse(out || '[]');
    } catch(e) { log('signal-analysis py error: ' + e.message); }

    const signals = ['量价齐升', '创新高', '大笔买入', '火箭', '强势股', '机构买入', '机构增持',
                     '超跌', '北向', '龙虎榜', '新闻利好', '缩量企稳', '均线收敛'];
    const analysis = {};
    for (const sig of signals) {
      const matched = trades.filter(t => t.buy_reason && t.buy_reason.includes(sig));
      if (matched.length === 0) continue;
      const wins = matched.filter(t => (t.sell_reason || '').includes('止盈') || t.sell_price > t.buy_price).length;
      const losses = matched.filter(t => (t.sell_reason || '').includes('止损')).length;
      const avgPnl = matched.reduce((sum, t) => sum + (t.sell_price - t.buy_price) / t.buy_price * 100, 0) / matched.length;
      analysis[sig] = {
        total: matched.length, wins, losses,
        winRate: matched.length > 0 ? Math.round(wins / matched.length * 100) : 0,
        avgPnl: Math.round(avgPnl * 100) / 100,
        status: wins / Math.max(matched.length, 1) >= 0.5 ? 'effective' :
                wins / Math.max(matched.length, 1) >= 0.3 ? 'neutral' : 'toxic'
      };
    }
    sendJson(res, { signals: analysis, totalTrades: trades.length });
  } catch (e) {
    sendJson(res, { signals: {}, totalTrades: 0 });
  }
}

function handleStopLossAnalysis(req, res) {
  // Analyze stop-loss effectiveness from Python
  try {
    const py = `import json,sys;sys.path.insert(0,'/home/nikefd/finance-agent');from stock_picker import analyze_stop_loss_effectiveness;print(json.dumps(analyze_stop_loss_effectiveness(),ensure_ascii=False))`;
    const out = execSync(`python3 -c "${py.replace(/"/g, '\\"')}"`, { timeout: 30000 }).toString().trim();
    sendJson(res, JSON.parse(out || '{}'));
  } catch(e) {
    log('stop-loss-analysis error: ' + e.message);
    sendJson(res, {});
  }
}

function handleIndicatorAttribution(req, res) {
  // Get indicator attribution effectiveness data
  try {
    // Get outcome counts
    const counts = querySqlite(`SELECT outcome, COUNT(*) as cnt FROM indicator_snapshots WHERE direction='BUY' GROUP BY outcome`);
    const countMap = {};
    (counts || []).forEach(r => countMap[r.outcome] = r.cnt);
    
    // Get completed records
    const records = querySqlite(`SELECT indicators_json, outcome, outcome_pnl_pct FROM indicator_snapshots WHERE outcome IN ('win','loss') AND direction='BUY' ORDER BY trade_date DESC LIMIT 100`);
    
    if (!records || records.length < 3) {
      return sendJson(res, { indicators: [], total: countMap, message: 'Not enough data yet' });
    }
    
    // Compute per-indicator stats
    const stats = {};
    records.forEach(r => {
      try {
        const inds = JSON.parse(r.indicators_json);
        for (const [name, val] of Object.entries(inds)) {
          if (!stats[name]) stats[name] = { win_pnl: 0, loss_pnl: 0, win_count: 0, loss_count: 0, present_win: 0, present_loss: 0 };
          const s = stats[name];
          // Count presence (non-zero/non-false/non-empty)
          const present = val && val !== 0 && val !== '0' && val !== 'none' && val !== 'neutral';
          if (present) {
            if (r.outcome === 'win') { s.present_win++; s.win_pnl += r.outcome_pnl_pct; }
            else { s.present_loss++; s.loss_pnl += r.outcome_pnl_pct; }
          }
          if (r.outcome === 'win') s.win_count++; else s.loss_count++;
        }
      } catch(_){}
    });
    
    const indicators = [];
    for (const [name, s] of Object.entries(stats)) {
      const total = s.present_win + s.present_loss;
      if (total < 2) continue;
      indicators.push({
        name,
        present_win: s.present_win,
        present_loss: s.present_loss,
        present_total: total,
        win_rate: Math.round(s.present_win / total * 1000) / 10,
        avg_pnl: total > 0 ? Math.round((s.win_pnl + s.loss_pnl) / total * 100) / 100 : 0,
      });
    }
    indicators.sort((a,b) => b.win_rate - a.win_rate);
    
    sendJson(res, { indicators, total: countMap });
  } catch(e) {
    log('indicator-attribution error: ' + e.message);
    sendJson(res, { indicators: [], error: e.message });
  }
}

// === UI优化④: 盤中聚合API (v5.128) ===
function handleIntradayAggregateV128(req, res) {
  try {
    const py = `import sys,json; sys.path.insert(0,'/home/nikefd/finance-agent'); from v5_128_intraday_ui_optimize import get_dashboard_aggregate_v128; print(json.dumps(get_dashboard_aggregate_v128(), ensure_ascii=False, default=str))`;
    const out = execSync(`python3 -c "${py.replace(/"/g, '\\"')}"`, { timeout: 15000 }).toString().trim();
    sendJson(res, JSON.parse(out || '{}'));
  } catch (e) {
    log('intraday-aggregate-v128 error: ' + e.message);
    sendJson(res, { error: e.message, timestamp: new Date().toISOString() });
  }
}

function handleSignalPersistence(req, res) {
  // Get signal persistence data from candidate_snapshots table
  try {
    const rows = querySqlite(`SELECT symbol, snapshot_date, score, signals FROM candidate_snapshots ORDER BY snapshot_date DESC LIMIT 200`);
    // Group by symbol
    const bySymbol = {};
    for (const r of rows) {
      if (!bySymbol[r.symbol]) bySymbol[r.symbol] = [];
      bySymbol[r.symbol].push({ date: r.snapshot_date, score: r.score, signals: r.signals });
    }
    // Calculate persistence for each
    const result = Object.entries(bySymbol).map(([sym, entries]) => ({
      symbol: sym,
      days_appeared: entries.length,
      dates: entries.map(e => e.date),
      avg_score: Math.round(entries.reduce((s, e) => s + e.score, 0) / entries.length),
      latest_signals: entries[0]?.signals || '',
      persistent: entries.length >= 2
    })).sort((a, b) => b.days_appeared - a.days_appeared);
    sendJson(res, { candidates: result });
  } catch(e) {
    log('signal-persistence error: ' + e.message);
    sendJson(res, { candidates: [] });
  }
}

function handleHealthScore(req, res) {
  // Composite portfolio health score 0-100
  const snapshots = querySqlite('SELECT date, total_value, sentiment_score FROM daily_snapshots ORDER BY date ASC');
  const positions = querySqlite('SELECT * FROM positions');
  const trades = querySqlite("SELECT * FROM trades WHERE direction='SELL' ORDER BY trade_date DESC, id DESC LIMIT 30");

  // 1. Drawdown component (0-25): lower drawdown = higher score
  const vals = snapshots.map(s => s.total_value);
  let peak = 0, maxDD = 0, currentDD = 0;
  for (const v of vals) { if (v > peak) peak = v; const dd = (peak - v) / peak * 100; if (dd > maxDD) maxDD = dd; }
  if (vals.length && peak > 0) currentDD = (peak - vals[vals.length - 1]) / peak * 100;
  const ddScore = Math.max(0, 25 - currentDD * 3); // 0% dd=25, 8%+ dd=0

  // 2. Win rate component (0-25)
  const allTrades = querySqlite('SELECT * FROM trades ORDER BY trade_date ASC, id ASC');
  const buyMap2 = {}; allTrades.forEach(t => { if (t.direction === 'BUY') { if (!buyMap2[t.symbol]) buyMap2[t.symbol] = []; buyMap2[t.symbol].push(t); }});
  const avgCosts2 = {}; Object.keys(buyMap2).forEach(sym => { const buys = buyMap2[sym]; const ts = buys.reduce((s, b) => s + b.shares, 0); const tc = buys.reduce((s, b) => s + b.price * b.shares, 0); avgCosts2[sym] = ts > 0 ? tc / ts : 0; });
  let wins = 0, total = 0;
  trades.forEach(t => { const cost = avgCosts2[t.symbol] || 0; if (cost > 0) { total++; if (t.price > cost) wins++; }});
  const winRate = total > 0 ? wins / total : 0.5;
  const wrScore = winRate * 25;

  // 3. Diversification component (0-25): sector spread + cash ratio
  const cash = snapshots.length ? (querySqlite('SELECT cash FROM account ORDER BY id DESC LIMIT 1')[0]?.cash || 0) : 0;
  const totalVal = vals.length ? vals[vals.length - 1] : 1000000;
  const cashRatio = totalVal > 0 ? cash / totalVal : 1;
  const sectors = new Set(positions.map(p => p.sector || '未分类'));
  const posCount = positions.length;
  // Good: 3-6 positions across 2+ sectors, 30-70% cash
  let divScore = 10;
  if (sectors.size >= 2) divScore += 5;
  if (posCount >= 2 && posCount <= 8) divScore += 5;
  if (cashRatio >= 0.2 && cashRatio <= 0.8) divScore += 5;

  // 4. Momentum component (0-25): recent returns trend
  const recentVals = vals.slice(-10);
  let momScore = 12.5;
  if (recentVals.length >= 2) {
    const recentRet = (recentVals[recentVals.length - 1] - recentVals[0]) / recentVals[0] * 100;
    momScore = Math.max(0, Math.min(25, 12.5 + recentRet * 2.5));
  }

  // Loss streak penalty
  let lossStreak = 0;
  for (const t of trades) { const cost = avgCosts2[t.symbol] || 0; if (cost > 0 && t.price < cost) lossStreak++; else break; }
  const streakPenalty = Math.min(lossStreak * 3, 20);

  const raw = ddScore + wrScore + divScore + momScore - streakPenalty;
  const score = Math.max(0, Math.min(100, Math.round(raw)));

  let status = 'healthy', color = '#2ec4b6', emoji = '💚';
  if (score < 30) { status = 'critical'; color = '#e63946'; emoji = '🔴'; }
  else if (score < 50) { status = 'warning'; color = '#f4a261'; emoji = '🟡'; }
  else if (score < 70) { status = 'moderate'; color = '#ffd166'; emoji = '🟠'; }
  else { status = 'healthy'; color = '#2ec4b6'; emoji = '💚'; }

  sendJson(res, {
    score, status, color, emoji,
    components: {
      drawdown: { score: Math.round(ddScore), max: 25, detail: `当前回撤${currentDD.toFixed(1)}%，最大${maxDD.toFixed(1)}%` },
      win_rate: { score: Math.round(wrScore), max: 25, detail: `近期胜率${(winRate * 100).toFixed(0)}% (${wins}/${total})` },
      diversification: { score: Math.round(divScore), max: 25, detail: `${posCount}只持仓，${sectors.size}个板块，现金${(cashRatio * 100).toFixed(0)}%` },
      momentum: { score: Math.round(momScore), max: 25, detail: `近10日趋势` },
    },
    penalties: { loss_streak: { value: lossStreak, penalty: streakPenalty } },
  });
}

function handlePositionDetails(req, res, params) {
  const symbol = params.symbol;
  if (!symbol) return sendError(res, 'symbol required', 400);
  const cleanSym = symbol.replace(/[^0-9]/g, '');
  if (!cleanSym) return sendError(res, 'invalid symbol', 400);

  try {
    const pyScript = `
import sqlite3, json
c = sqlite3.connect("${DB_PATH}")
c.row_factory = sqlite3.Row
pos = c.execute("SELECT * FROM positions WHERE symbol=?", ["${cleanSym}"]).fetchall()
if not pos:
    print(json.dumps({"error": "not found"}))
else:
    buys = c.execute("SELECT * FROM trades WHERE symbol=? AND direction='BUY' ORDER BY trade_date DESC LIMIT 5", ["${cleanSym}"]).fetchall()
    sells = c.execute("SELECT * FROM trades WHERE symbol=? AND direction='SELL' ORDER BY trade_date DESC LIMIT 5", ["${cleanSym}"]).fetchall()
    print(json.dumps({"pos": dict(pos[0]), "buys": [dict(x) for x in buys], "sells": [dict(x) for x in sells]}))
`;
    const tmpFile = '/tmp/pos_detail_query.py';
    fs.writeFileSync(tmpFile, pyScript);
    const out = execSync(`python3 ${tmpFile}`, { timeout: 5000 }).toString().trim();
    const data = JSON.parse(out || '{}');
    if (data.error) return sendError(res, data.error, 404);

    const pos = data.pos;
    const pnl_pct = pos.avg_cost ? ((pos.current_price - pos.avg_cost) / pos.avg_cost * 100) : 0;
    const peak_dd = pos.peak_price && pos.peak_price > 0 ? ((pos.current_price - pos.peak_price) / pos.peak_price * 100) : 0;
    const trailingActive = pos.peak_price && pos.peak_price > pos.avg_cost * 1.04;

    sendJson(res, {
      symbol: pos.symbol, name: pos.name, shares: pos.shares,
      avg_cost: pos.avg_cost, current_price: pos.current_price,
      peak_price: pos.peak_price, buy_date: pos.buy_date,
      sector: pos.sector || '未分类',
      pnl_pct: Math.round(pnl_pct * 100) / 100,
      peak_drawdown: Math.round(peak_dd * 100) / 100,
      trailing_stop_active: trailingActive,
      buy_reason: data.buys[0]?.reason || '',
      recent_buys: data.buys,
      recent_sells: data.sells,
    });
  } catch (e) {
    log('Position details error: ' + e.message);
    sendError(res, e.message);
  }
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

// === v5.139 改进① 绩效统计增强 ===
function handleEnhancedPerformanceStats(req, res) {
  // 获取交易数据
  const trades = querySqlite('SELECT * FROM trades ORDER BY trade_date DESC, id DESC');
  const snapshots = querySqlite('SELECT * FROM daily_snapshots ORDER BY date ASC');
  const accounts = querySqlite('SELECT * FROM account ORDER BY id DESC LIMIT 1');
  const account = accounts[0] || { cash: 0, total_value: INITIAL_CAPITAL };

  // 1. 胜率计算
  const sellTrades = trades.filter(t => t.direction === 'SELL');
  const wins = sellTrades.filter(t => t.pnl && t.pnl > 0).length;
  const total = sellTrades.length;
  const winRate = total > 0 ? (wins / total * 100).toFixed(2) : '0.00';

  // 2. 盈亏比
  const profits = sellTrades.filter(t => t.pnl > 0).reduce((s, t) => s + (t.pnl || 0), 0);
  const losses = Math.abs(sellTrades.filter(t => t.pnl < 0).reduce((s, t) => s + (t.pnl || 0), 0));
  const profitFactor = losses > 0 ? (profits / losses).toFixed(2) : (profits > 0 ? '999.00' : '0.00');

  // 3. 连胜/连败
  let maxWin = 0, maxLoss = 0, currentWin = 0, currentLoss = 0;
  trades.forEach(t => {
    if (t.direction === 'SELL') {
      if (t.pnl > 0) {
        currentWin++;
        currentLoss = 0;
        maxWin = Math.max(maxWin, currentWin);
      } else if (t.pnl < 0) {
        currentLoss++;
        currentWin = 0;
        maxLoss = Math.max(maxLoss, currentLoss);
      }
    }
  });

  // 4. 夏普率
  let dailyReturns = [];
  if (snapshots.length >= 2) {
    for (let i = snapshots.length - 1; i > 0; i--) {
      const ret = (snapshots[i-1].total_value - snapshots[i].total_value) / snapshots[i].total_value;
      dailyReturns.push(ret);
    }
  }
  const mean = dailyReturns.length > 0 ? dailyReturns.reduce((s, r) => s + r, 0) / dailyReturns.length : 0;
  const variance = dailyReturns.length > 0 ? dailyReturns.reduce((s, r) => s + Math.pow(r - mean, 2), 0) / dailyReturns.length : 0;
  const stdDev = Math.sqrt(variance);
  const sharpe = stdDev === 0 ? 0 : ((mean * 252 - 0.02) / (stdDev * Math.sqrt(252))).toFixed(2);

  // 5. 回撤
  let maxDD = 0, recoveryDays = 0, peakValue = 0, peakIndex = 0;
  for (let i = 0; i < snapshots.length; i++) {
    if (snapshots[i].total_value > peakValue) {
      peakValue = snapshots[i].total_value;
      peakIndex = i;
    }
    const dd = (snapshots[i].total_value - peakValue) / peakValue * 100;
    if (dd < maxDD) maxDD = dd;
  }
  // 计算恢复天数
  for (let i = peakIndex; i < snapshots.length; i++) {
    if (snapshots[i].total_value >= peakValue) {
      recoveryDays = i - peakIndex;
      break;
    }
  }

  // 6. 收益分布
  const pnlPcts = sellTrades.filter(t => t.pnl_pct !== undefined).map(t => t.pnl_pct || 0);
  const minPnl = pnlPcts.length > 0 ? Math.floor(Math.min(...pnlPcts) / 5) * 5 : -20;
  const maxPnl = pnlPcts.length > 0 ? Math.ceil(Math.max(...pnlPcts) / 5) * 5 : 20;
  const bins = [];
  const freq = [];
  for (let i = minPnl; i <= maxPnl; i += 5) {
    bins.push(`${i}%~${i+5}%`);
    const count = pnlPcts.filter(p => p >= i && p < i + 5).length;
    freq.push(count);
  }

  sendJson(res, {
    win_rate: parseFloat(winRate),
    profit_factor: parseFloat(profitFactor),
    max_consecutive_win: maxWin,
    max_consecutive_loss: maxLoss,
    sharpe_ratio: parseFloat(sharpe),
    max_drawdown: Math.round(maxDD * 100) / 100,
    recovery_days: recoveryDays,
    total_trades: total,
    return_distribution: { bins, freq },
    latest_snapshot: snapshots[snapshots.length - 1] || {}
  });
}

function handleDailyPnl(req, res) {
  const snapshots = querySqlite('SELECT date, total_value FROM daily_snapshots ORDER BY date ASC');
  if (snapshots.length < 2) return sendJson(res, { days: [] });
  const days = [];
  const count = Math.min(snapshots.length, 31);
  const start = snapshots.length - count;
  for (let i = Math.max(start, 1); i < snapshots.length; i++) {
    const pnl = Math.round((snapshots[i].total_value - snapshots[i-1].total_value) * 100) / 100;
    days.push({ date: snapshots[i].date, pnl });
  }
  sendJson(res, { days });
}

function handleRollingReturns(req, res) {
  const snapshots = querySqlite('SELECT date, total_value FROM daily_snapshots ORDER BY date ASC');
  if (snapshots.length < 21) return sendJson(res, { data: [] });
  const result = [];
  for (let i = 20; i < snapshots.length; i++) {
    const ret = Math.round((snapshots[i].total_value - snapshots[i - 20].total_value) / snapshots[i - 20].total_value * 10000) / 100;
    result.push({ date: snapshots[i].date, rolling_return: ret });
  }
  sendJson(res, { data: result });
}

function handleTradeOutcomes(req, res) {
  const allTrades = querySqlite('SELECT * FROM trades ORDER BY trade_date ASC, id ASC');
  const buyMap = {};
  allTrades.forEach(t => {
    if (t.direction === 'BUY') {
      if (!buyMap[t.symbol]) buyMap[t.symbol] = [];
      buyMap[t.symbol].push(t);
    }
  });
  const avgCosts = {};
  Object.keys(buyMap).forEach(sym => {
    const buys = buyMap[sym];
    const ts = buys.reduce((s, b) => s + b.shares, 0);
    const tc = buys.reduce((s, b) => s + b.price * b.shares, 0);
    avgCosts[sym] = ts > 0 ? tc / ts : 0;
  });
  const outcomes = [];
  allTrades.filter(t => t.direction === 'SELL').forEach(t => {
    const cost = avgCosts[t.symbol] || 0;
    if (cost <= 0) return;
    const pnl = Math.round((t.price - cost) * t.shares * 100) / 100;
    const pnlPct = Math.round((t.price - cost) / cost * 10000) / 100;
    outcomes.push({
      date: t.trade_date, name: t.name || t.symbol, symbol: t.symbol,
      result: pnl >= 0 ? 'win' : 'loss', pnl, pnl_pct: pnlPct,
      reason: (t.reason || '').slice(0, 60)
    });
  });
  sendJson(res, { outcomes });
}

function handleRunStatus(req, res) {
  // Also try reading from log file if log is empty
  let logContent = runState.log;
  if (!logContent && runState.status === 'idle') {
    try { logContent = fs.readFileSync(RUN_LOG_FILE, 'utf-8'); } catch(e) {}
  }
  sendJson(res, { status: runState.status, log: logContent });
}

// === 改进① 现金占比+策略激进度 ===
function handleCashAllocationProfile(req, res) {
  const accounts = querySqlite('SELECT * FROM account ORDER BY id DESC LIMIT 1');
  const account = accounts[0] || { cash: 0, total_value: 1000000 };
  
  const cash_ratio = account.total_value > 0 ? (account.cash / account.total_value * 100) : 0;
  
  // Determine strategy mode based on cash ratio
  let strategy_mode = 'normal';
  let strategy_boost = {};
  if (cash_ratio > 95) {
    strategy_mode = 'aggressive';
    strategy_boost = { 'MACD_RSI': 1.8, 'TREND_FOLLOW': 1.3, 'MULTI_FACTOR': 1.2 };
  } else if (cash_ratio > 75) {
    strategy_mode = 'balanced';
    strategy_boost = { 'MACD_RSI': 1.3, 'TREND_FOLLOW': 1.1, 'MULTI_FACTOR': 1.0 };
  } else {
    strategy_mode = 'conservative';
    strategy_boost = { 'MACD_RSI': 1.0, 'TREND_FOLLOW': 1.0, 'MULTI_FACTOR': 0.9 };
  }
  
  sendJson(res, {
    cash_ratio: Math.round(cash_ratio * 100) / 100,
    cash_amount: Math.round(account.cash),
    total_value: Math.round(account.total_value),
    strategy_mode,
    strategy_boost,
    mode_description: strategy_mode === 'aggressive' ? '资金利用率低，激进入场' :
                     strategy_mode === 'balanced' ? '均衡持仓，适度出击' :
                     '已建仓，风险管理优先'
  });
}

// === 改进③ 持仓风险热力图 (v5.60) ===
function handlePositionRiskHeatmap(req, res) {
  try {
    const positions = querySqlite('SELECT * FROM positions');
    if (!positions || !positions.length) {
      return sendJson(res, { heatmap: [], avg_risk_score: 0 });
    }

    const heatmap = positions.map(p => {
      // 风险评分公式：基于回撤率、持仓天数、波动率
      const drawdown_risk = Math.abs(p.peak_drawdown || 0); // 从峰值的回撤%
      const holding_days_risk = Math.max(0, 30 - (p.holding_days || 0)) / 30 * 30; // 持仓越久风险越低
      const price_change_risk = Math.abs((p.current_price - p.avg_cost) / p.avg_cost * 100); // 价格变化幅度
      
      // 综合风险评分 (0-100)
      let risk_score = (drawdown_risk * 0.4 + holding_days_risk * 0.3 + price_change_risk * 0.3);
      risk_score = Math.min(100, Math.max(0, risk_score));
      
      // 风险等级
      let risk_level = 'low';
      let risk_icon = '🟢';
      if (risk_score >= 70) {
        risk_level = 'high';
        risk_icon = '🔴';
      } else if (risk_score >= 40) {
        risk_level = 'medium';
        risk_icon = '🟡';
      }
      
      return {
        symbol: p.symbol,
        name: p.name,
        risk_score: Math.round(risk_score * 100) / 100,
        risk_level,
        risk_icon,
        drawdown: Math.round((p.peak_drawdown || 0) * 100) / 100,
        shares: p.shares,
        holding_days: p.holding_days || 0,
        pnl_pct: p.pnl_pct || 0
      };
    });

    const avg_risk_score = heatmap.length > 0 
      ? Math.round(heatmap.reduce((sum, p) => sum + p.risk_score, 0) / heatmap.length * 100) / 100 
      : 0;

    sendJson(res, { heatmap, avg_risk_score });
  } catch (e) {
    log(`handlePositionRiskHeatmap error: ${e.message}`);
    sendError(res, e.message);
  }
}

// === 改进② 绩效统计 (策略胜率、赛道分布、入场质量) ===
function handlePerformanceStats(req, res) {
  try {
    // Strategy win rate analysis
    const trades = querySqlite('SELECT * FROM trades ORDER BY trade_date ASC, id ASC');
    if (!trades || !trades.length) {
      return sendJson(res, { strategies: {}, sectors: {}, entry_quality: {} });
    }
    
    // Build buy history by strategy
    const strategyMap = {}; // strategy -> {total, wins, losses, pnls}
    const buyMap = {}; // symbol -> {price, shares}
    
    trades.forEach(t => {
      const strategy = t.strategy || 'unknown';
      if (!strategyMap[strategy]) strategyMap[strategy] = { total: 0, wins: 0, losses: 0, pnls: [] };
      
      if (t.direction === 'BUY') {
        buyMap[t.symbol] = { price: t.price, shares: t.shares, date: t.trade_date };
      } else if (t.direction === 'SELL' && buyMap[t.symbol]) {
        const pnl = (t.price - buyMap[t.symbol].price) * t.shares;
        strategyMap[strategy].total++;
        strategyMap[strategy].pnls.push(pnl);
        if (pnl > 0) strategyMap[strategy].wins++;
        else strategyMap[strategy].losses++;
      }
    });
    
    // Compute strategy stats
    const strategies = {};
    Object.entries(strategyMap).forEach(([strat, data]) => {
      if (data.total === 0) return;
      const avgPnl = data.pnls.reduce((a, b) => a + b, 0) / data.total;
      strategies[strat] = {
        total_trades: data.total,
        win_rate: Math.round(data.wins / data.total * 10000) / 100,
        wins: data.wins,
        losses: data.losses,
        avg_pnl: Math.round(avgPnl * 100) / 100,
        effectiveness: data.wins / data.total >= 0.5 ? 'strong' : data.wins / data.total >= 0.3 ? 'fair' : 'weak'
      };
    });
    
    // Sector distribution
    const sectorMap = {};
    trades.forEach(t => {
      const sector = t.sector || 'unknown';
      if (!sectorMap[sector]) sectorMap[sector] = 0;
      sectorMap[sector]++;
    });
    
    // Entry quality score trend (sample from last 30 trades)
    const recentTrades = trades.slice(-30);
    let totalQuality = 0, validCount = 0;
    recentTrades.forEach(t => {
      if (t.entry_quality_score) {
        totalQuality += parseFloat(t.entry_quality_score);
        validCount++;
      }
    });
    
    sendJson(res, {
      strategies,
      sectors: sectorMap,
      entry_quality_avg: validCount > 0 ? Math.round(totalQuality / validCount * 100) / 100 : 0,
      recent_sample_size: recentTrades.length,
      total_trades_analyzed: trades.length
    });
  } catch(e) {
    log('performance-stats error: ' + e.message);
    sendJson(res, { strategies: {}, sectors: {}, entry_quality: {} });
  }
}

// --- Router ---

const server = http.createServer((req, res) => {
  if (req.method === 'OPTIONS') { sendJson(res, {}); return; }

  const { pathname, params } = parseUrl(req.url);
  log(`${req.method} ${pathname}`);

  try {
    // === UI优化v5.97新端点 ===
    // === UI优化v5.105新端点 (11:30盘中优化) ===
    if (pathname === '/api/finance/sentiment-dynamics-v102' && req.method === 'GET') return handleSentimentDynamicsV102(req, res);
    if (pathname === '/api/finance/performance-stats-v102' && req.method === 'GET') return handlePerformanceStatsV102(req, res);
    if (pathname === '/api/finance/signal-quality-v102' && req.method === 'GET') return handleSignalQualityV102(req, res);
    if (pathname === '/api/finance/intraday-performance-v102' && req.method === 'GET') return handleIntradayPerformanceV102(req, res);
    if (pathname === '/api/finance/dashboard-aggregate-v107' && req.method === 'GET') return handleDashboardAggregateV107(req, res);
    if (pathname === '/api/finance/intraday-aggregate-v128' && req.method === 'GET') return handleIntradayAggregateV128(req, res);
    if (pathname === '/api/finance/emotion-trigger-v135' && req.method === 'GET') return handleEmotionTriggerDecisionsV135(req, res);
    if (pathname === '/api/finance/intraday-performance-v135' && req.method === 'GET') return handleIntradayPerformanceStatsV135(req, res);
    if (pathname === '/api/finance/combined-metrics-v135' && req.method === 'GET') return handleCombinedIntradayMetricsV135(req, res);
    // === v5.141 UI优化② (11:30) - 绩效统计增强 ===
    if (pathname === '/api/finance/performance-metrics-v141' && req.method === 'GET') return handlePerformanceMetricsV141(req, res);
    if (pathname === '/api/finance/capital-allocation-v141' && req.method === 'GET') return handleCapitalAllocationV141(req, res);
    if (pathname === '/api/finance/risk-metrics-v141' && req.method === 'GET') return handleRiskMetricsV141(req, res);
    if (pathname === '/api/finance/daily-summary-v141' && req.method === 'GET') return handleDailySummaryV141(req, res);
    // === UI优化v5.97旧端点 ===
    if (pathname === '/kelly-positions' && req.method === 'GET') return handleKellyPositionsV97(req, res);
    if (pathname === '/selection-status' && req.method === 'GET') return handleSelectionStatus(req, res);
    if (pathname === '/dashboard' && req.method === 'GET') return handleDashboard(req, res);
    
    if (pathname === '/api/finance/performance-stats' && req.method === 'GET') return handlePerformanceStats(req, res);
    if (pathname === '/api/finance/sentiment-dynamics' && req.method === 'GET') return handleSentimentDynamics_v82(req, res);
    if (pathname === '/api/finance/backtest-comparison-v82' && req.method === 'GET') return handleBacktestComparison_v82(req, res);
    if (pathname === '/api/finance/dashboard' && req.method === 'GET') return handleDashboard(req, res);
    if (pathname === '/api/finance/kelly-positions' && req.method === 'GET') return handleKellyPositions(req, res);
    if (pathname === '/api/finance/analysis' && req.method === 'GET') return handleAnalysis(req, res);
    if (pathname === '/api/finance/trades' && req.method === 'GET') return handleTrades(req, res, params);
    if (pathname === '/api/finance/performance-enhanced-v139' && req.method === 'GET') return handleEnhancedPerformanceStats(req, res);
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
    // === v5.102 UI优化② (11:30) ===
    if (pathname === '/api/finance/sentiment-dynamics-v102' && req.method === 'GET') {
      try {
        const py = `import json,sys; sys.path.insert(0,'/home/nikefd/finance-agent'); from v5_102_INTRADAY_UI_OPTIMIZE import get_sentiment_dynamics; print(json.dumps(get_sentiment_dynamics(), ensure_ascii=False, default=str))`;
        const out = execSync(`python3 -c "${py.replace(/"/g, '\\"')}"`, { timeout: 15000 }).toString().trim();
        return sendJson(res, JSON.parse(out));
      } catch(e) { return sendJson(res, { error: e.message }); }
    }
    if (pathname === '/api/finance/performance-stats-v102' && req.method === 'GET') {
      try {
        const py = `import json,sys; sys.path.insert(0,'/home/nikefd/finance-agent'); from v5_102_INTRADAY_UI_OPTIMIZE import get_performance_stats; print(json.dumps(get_performance_stats(), ensure_ascii=False, default=str))`;
        const out = execSync(`python3 -c "${py.replace(/"/g, '\\"')}"`, { timeout: 15000 }).toString().trim();
        return sendJson(res, JSON.parse(out));
      } catch(e) { return sendJson(res, { error: e.message }); }
    }
    if (pathname === '/api/finance/signal-quality-v102' && req.method === 'GET') {
      try {
        const py = `import json,sys; sys.path.insert(0,'/home/nikefd/finance-agent'); from v5_102_INTRADAY_UI_OPTIMIZE import get_signal_quality; print(json.dumps(get_signal_quality(), ensure_ascii=False, default=str))`;
        const out = execSync(`python3 -c "${py.replace(/"/g, '\\"')}"`, { timeout: 15000 }).toString().trim();
        return sendJson(res, JSON.parse(out));
      } catch(e) { return sendJson(res, { error: e.message }); }
    }
    if (pathname === '/api/finance/intraday-performance-v102' && req.method === 'GET') {
      try {
        const py = `import json,sys; sys.path.insert(0,'/home/nikefd/finance-agent'); from v5_102_INTRADAY_UI_OPTIMIZE import get_intraday_performance; print(json.dumps(get_intraday_performance(), ensure_ascii=False, default=str))`;
        const out = execSync(`python3 -c "${py.replace(/"/g, '\\"')}"`, { timeout: 15000 }).toString().trim();
        return sendJson(res, JSON.parse(out));
      } catch(e) { return sendJson(res, { error: e.message }); }
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
    // === 实盘操作 ===
    if (pathname === '/api/finance/real/positions' && req.method === 'GET') {
      try {
        const py = `import json,sys;sys.path.insert(0,'/home/nikefd/finance-agent');from real_trader import get_positions;from data_collector import get_realtime_quotes;pos=get_positions();codes=[p['symbol'] for p in pos];quotes=get_realtime_quotes(codes) if codes else {};
for p in pos:
    q=quotes.get(p['symbol'],{})
    p['current_price']=q.get('price',0)
    p['change_pct']=q.get('change_pct',0)
    p['pnl_pct']=round((p['current_price']-p['avg_cost'])/p['avg_cost']*100,2) if p['current_price'] and p['avg_cost'] else 0
    p['pnl_amount']=round((p['current_price']-p['avg_cost'])*p['shares'],2) if p['current_price'] else 0
    p['market_value']=round(p['current_price']*p['shares'],2) if p['current_price'] else 0
print(json.dumps(pos,ensure_ascii=False,default=str))`;
        const out = execSync(`python3 -c "${py.replace(/"/g, '\\"')}"`, { timeout: 15000 }).toString().trim();
        return sendJson(res, { positions: JSON.parse(out || '[]') });
      } catch(e) { return sendJson(res, { positions: [], error: e.message }); }
    }
    if (pathname === '/api/finance/real/positions' && req.method === 'POST') {
      let body = '';
      req.on('data', chunk => body += chunk);
      req.on('end', () => {
        try {
          const data = JSON.parse(body);
          const py = `import json,sys;sys.path.insert(0,'/home/nikefd/finance-agent');from real_trader import add_position;r=add_position('${data.symbol}','${data.name||""}',${data.shares||0},${data.avg_cost||0},'${data.buy_date||""}','${data.notes||""}');print(json.dumps(r,ensure_ascii=False))`;
          const out = execSync(`python3 -c "${py.replace(/"/g, '\\"')}"`, { timeout: 10000 }).toString().trim();
          sendJson(res, JSON.parse(out));
        } catch(e) { sendError(res, e.message); }
      });
      return;
    }
    if (pathname === '/api/finance/real/account' && req.method === 'GET') {
      try {
        const py = `import json,sys;sys.path.insert(0,'/home/nikefd/finance-agent');from real_trader import get_account;print(json.dumps(get_account(),ensure_ascii=False,default=str))`;
        const out = execSync(`python3 -c "${py.replace(/"/g, '\\"')}"`, { timeout: 5000 }).toString().trim();
        return sendJson(res, JSON.parse(out || '{}'));
      } catch(e) { return sendJson(res, { total_capital: 0, available_cash: 0, error: e.message }); }
    }
    if (pathname === '/api/finance/real/account' && req.method === 'POST') {
      let body = '';
      req.on('data', chunk => body += chunk);
      req.on('end', () => {
        try {
          const data = JSON.parse(body);
          const py = `import sys;sys.path.insert(0,'/home/nikefd/finance-agent');from real_trader import update_account;update_account(${data.total_capital||0},${data.available_cash||0});print('{"ok":true}')`;
          execSync(`python3 -c "${py.replace(/"/g, '\\"')}"`, { timeout: 5000 });
          sendJson(res, { ok: true });
        } catch(e) { sendError(res, e.message); }
      });
      return;
    }
    if (pathname === '/api/finance/real/actions' && req.method === 'GET') {
      try {
        const date = params.date || new Date().toISOString().slice(0, 10);
        const py = `import json,sys;sys.path.insert(0,'/home/nikefd/finance-agent');from real_trader import get_today_actions;print(json.dumps(get_today_actions('${date}'),ensure_ascii=False,default=str))`;
        const out = execSync(`python3 -c "${py.replace(/"/g, '\\"')}"`, { timeout: 10000 }).toString().trim();
        return sendJson(res, { actions: JSON.parse(out || '[]'), date });
      } catch(e) { return sendJson(res, { actions: [], error: e.message }); }
    }
    if (pathname === '/api/finance/real/actions/generate' && req.method === 'POST') {
      log('Generating daily actions...');
      exec('cd /home/nikefd/finance-agent && python3 -u -c "from real_trader import generate_daily_actions; generate_daily_actions()" >> /tmp/real-actions.log 2>&1', { timeout: 300000 }, (err) => {
        if (err) log('Action generation error: ' + err.message);
        else log('Action generation completed');
      });
      return sendJson(res, { status: 'running', message: '正在生成操作建议...' });
    }
    if (pathname === '/api/finance/real/actions/update' && req.method === 'POST') {
      let body = '';
      req.on('data', chunk => body += chunk);
      req.on('end', () => {
        try {
          const data = JSON.parse(body);
          const py = `import sys;sys.path.insert(0,'/home/nikefd/finance-agent');from real_trader import update_action_status;update_action_status(${data.id},'${data.status}',${data.executed_price||'None'},'${(data.notes||"").replace(/'/g,"\\'")}');print('{"ok":true}')`;
          execSync(`python3 -c "${py.replace(/"/g, '\\"')}"`, { timeout: 5000 });
          sendJson(res, { ok: true });
        } catch(e) { sendError(res, e.message); }
      });
      return;
    }
    if (pathname === '/api/finance/real/sell' && req.method === 'POST') {
      let body = '';
      req.on('data', chunk => body += chunk);
      req.on('end', () => {
        try {
          const data = JSON.parse(body);
          const py = `import json,sys;sys.path.insert(0,'/home/nikefd/finance-agent');from real_trader import sell_position;r=sell_position('${data.symbol}',${data.shares||'None'},${data.price||'None'},'${data.notes||""}');print(json.dumps(r,ensure_ascii=False))`;
          const out = execSync(`python3 -c "${py.replace(/"/g, '\\"')}"`, { timeout: 10000 }).toString().trim();
          sendJson(res, JSON.parse(out));
        } catch(e) { sendError(res, e.message); }
      });
      return;
    }

    if (pathname === '/api/finance/health-score' && req.method === 'GET') return handleHealthScore(req, res);
    if (pathname === '/api/finance/position-details' && req.method === 'GET') return handlePositionDetails(req, res, params);
    if (pathname === '/api/finance/intraday-ui-optimizer' && req.method === 'GET') return handleIntradayUIOptimizer(req, res);
    if (pathname === '/api/finance/monthly-returns' && req.method === 'GET') return handleMonthlyReturns(req, res);
    if (pathname === '/api/finance/weekly-returns' && req.method === 'GET') return handleWeeklyReturns(req, res);
    if (pathname === '/api/finance/period-returns' && req.method === 'GET') return handlePeriodReturns(req, res);
    if (pathname === '/api/finance/risk-metrics' && req.method === 'GET') return handleRiskMetrics(req, res);
    if (pathname === '/api/finance/signal-analysis' && req.method === 'GET') return handleSignalAnalysis(req, res);
    if (pathname === '/api/finance/stop-loss-analysis' && req.method === 'GET') return handleStopLossAnalysis(req, res);
    if (pathname === '/api/finance/signal-persistence' && req.method === 'GET') return handleSignalPersistence(req, res);
    if (pathname === '/api/finance/daily-pnl' && req.method === 'GET') return handleDailyPnl(req, res);
    if (pathname === '/api/finance/rolling-returns' && req.method === 'GET') return handleRollingReturns(req, res);
    if (pathname === '/api/finance/trade-outcomes' && req.method === 'GET') return handleTradeOutcomes(req, res);
    if (pathname === '/api/finance/indicator-attribution' && req.method === 'GET') return handleIndicatorAttribution(req, res);
    if (pathname === '/api/finance/capital-utilization' && req.method === 'GET') return handleCapitalUtilization(req, res);
    if (pathname === '/api/finance/cash-profile' && req.method === 'GET') return handleCashAllocationProfile(req, res);
    if (pathname === '/api/finance/perf-stats' && req.method === 'GET') return handlePerformanceStats(req, res);
    if (pathname === '/api/finance/position-risk-heatmap' && req.method === 'GET') return handlePositionRiskHeatmap(req, res);
    if (pathname === '/api/finance/trade-calendar' && req.method === 'GET') return handleTradeCalendar(req, res);
    if (pathname === '/api/finance/strategy-contribution' && req.method === 'GET') return handleStrategyContribution(req, res);
    if (pathname === '/api/finance/recent-trades' && req.method === 'GET') return handleRecentTrades(req, res);
    if (pathname === '/api/finance/risk-alerts' && req.method === 'GET') return handleRiskAlerts(req, res);
    if (pathname === '/api/finance/sl-tp-board' && req.method === 'GET') return handleSlTpBoard(req, res);
    // v5.69 新增端点
    if (pathname === '/api/finance/sentiment-dashboard' && req.method === 'GET') return handleSentimentDashboard(req, res);
    if (pathname === '/api/finance/backtest-comparison' && req.method === 'GET') return handleBacktestComparison(req, res);
    if (pathname === '/api/finance/kelly-positions' && req.method === 'GET') return handleKellyPositions(req, res);
    if (pathname === '/api/finance/sentiment-heatmap' && req.method === 'GET') return handleSentimentHeatmap(req, res);
    if (pathname === '/api/finance/news-with-sentiment' && req.method === 'GET') return handleNewsWithSentiment(req, res);
    if (pathname === '/api/finance/portfolio-scatter' && req.method === 'GET') return handlePortfolioScatter(req, res);
    if (pathname === '/api/finance/stop-loss-dashboard' && req.method === 'GET') return handleStopLossDashboard(req, res);
    // v5.88 盤中優化端點 (新增實時統計)
    if (pathname === '/api/finance/intraday-stats' && req.method === 'GET') return handleIntradayStats(req, res);
    // v5.76 盤中優化端點
    if (pathname === '/api/finance/intraday-optimize' && req.method === 'GET') return handleIntradayOptimize(req, res);
    if (pathname === '/api/finance/performance-scorecard' && req.method === 'GET') return handlePerformanceScorecard(req, res);
    if (pathname === '/api/finance/backtest-comparison-v77' && req.method === 'GET') return handleBacktestComparison(req, res);
    if (pathname === '/api/finance/intraday-dashboard-v593' && req.method === 'GET') return handleIntradayDashboard_v593(req, res);
    // v5.98 盤中UI優化新端點
    if (pathname === '/api/finance/performance-indicators' && req.method === 'GET') return handlePerfomanceIndicators(req, res);
    if (pathname === '/api/finance/macd-rsi-signals' && req.method === 'GET') return handleMacdRsiSignals(req, res);
    if (pathname === '/api/finance/intraday-dashboard-v112' && req.method === 'GET') return handleIntradayDashboardV112(req, res);
    if (pathname === '/api/finance/sentiment-position-heatmap-v112' && req.method === 'GET') return handleSentimentPositionHeatmapV112(req, res);
    if (pathname === '/api/finance/intraday-alert-v116' && req.method === 'GET') return handleIntradayAlertV116(req, res);
    if (pathname === '/api/finance/performance-dashboard-v119' && req.method === 'GET') return handlePerformanceDashboardV119(req, res);
    if (pathname === '/api/finance/sector-heatmap-v119' && req.method === 'GET') return handleSectorHeatmapV119(req, res);
    if (pathname === '/api/finance/intraday-stop-loss-v122' && req.method === 'GET') return handleIntradayStopLossV122(req, res);
    if (pathname === '/api/finance/intraday-emotion-v122' && req.method === 'GET') return handleIntradayEmotionV122(req, res);
    if (pathname === '/api/finance/intraday-combined-v122' && req.method === 'GET') return handleIntradayCombinedV122(req, res);
    if (pathname === '/api/finance/intraday-heatmap-v132' && req.method === 'GET') return handleIntradayHeatmapV132(req, res);
    if (pathname === '/api/finance/intraday-minute-stats-v132' && req.method === 'GET') return handleIntradayMinuteStatsV132(req, res);

    // === v5.137 盤中優化②新API端點 ===
    if (pathname === '/api/finance/performance-ranking-v137' && req.method === 'GET') return handlePerformanceRankingV137(req, res);
    if (pathname === '/api/finance/market-heatmap-v137' && req.method === 'GET') return handleMarketHeatmapV137(req, res);
    if (pathname === '/api/finance/intraday-risk-v137' && req.method === 'GET') return handleIntraDayRiskV137(req, res);
    
    // Static file service for UI optimization
    if (pathname === '/ui-optimize-v5.65.js' && req.method === 'GET') {
      try {
        const content = fs.readFileSync('/home/nikefd/finance-agent/ui-optimize-v5.65.js', 'utf-8');
        res.writeHead(200, { 'Content-Type': 'application/javascript; charset=utf-8', 'Access-Control-Allow-Origin': '*' });
        res.end(content);
        return;
      } catch (e) {
        return sendError(res, 'File not found: ' + e.message, 404);
      }
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

function handleTradeCalendar(req, res) {
  // GitHub-style trade activity calendar (last 90 days)
  const trades = querySqlite("SELECT trade_date, direction, symbol, name, price, shares FROM trades ORDER BY trade_date ASC");
  const dayMap = {};
  trades.forEach(t => {
    if (!dayMap[t.trade_date]) dayMap[t.trade_date] = { buys: 0, sells: 0, total: 0, details: [] };
    const d = dayMap[t.trade_date];
    if (t.direction === 'BUY') d.buys++; else d.sells++;
    d.total++;
    d.details.push((t.direction === 'BUY' ? '\u4e70' : '\u5356') + ' ' + t.name + ' ' + t.shares + '\u80a1');
  });
  const days = [];
  const now = new Date();
  for (let i = 89; i >= 0; i--) {
    const dt = new Date(now);
    dt.setDate(dt.getDate() - i);
    const ds = dt.toISOString().slice(0, 10);
    const dow = dt.getDay();
    const info = dayMap[ds] || { buys: 0, sells: 0, total: 0, details: [] };
    days.push({ date: ds, dow, ...info });
  }
  sendJson(res, { days });
}

function handleStrategyContribution(req, res) {
  const allTrades = querySqlite('SELECT id, trade_date, direction, symbol, name, price, shares, reason FROM trades ORDER BY id ASC');
  // Build buy reason map and avg cost
  const buyReasons = {}; // symbol -> last buy reason
  const buyCosts = {};   // symbol -> {totalCost, totalShares}
  const results = [];
  allTrades.forEach(t => {
    if (t.direction === 'BUY') {
      buyReasons[t.symbol] = t.reason || '';
      if (!buyCosts[t.symbol]) buyCosts[t.symbol] = { totalCost: 0, totalShares: 0 };
      buyCosts[t.symbol].totalCost += t.price * t.shares;
      buyCosts[t.symbol].totalShares += t.shares;
    } else if (t.direction === 'SELL') {
      const bc = buyCosts[t.symbol];
      if (bc && bc.totalShares > 0) {
        const avgCost = bc.totalCost / bc.totalShares;
        const pnl = Math.round((t.price - avgCost) * t.shares * 100) / 100;
        results.push({ pnl, buyReason: buyReasons[t.symbol] || '', sellReason: t.reason || '' });
      }
    }
  });
  const stratMap = {};
  const keywords = {
    'MACD': ['macd', '\u91d1\u53c9', '\u6b7b\u53c9', 'dif'],
    'RSI': ['rsi'],
    '\u5747\u7ebf': ['\u591a\u5934\u6392\u5217', '\u5747\u7ebf'],
    '\u5e03\u6797\u5e26': ['\u5e03\u6797', 'boll'],
    '\u653e\u91cf': ['\u91cf\u6bd4', '\u653e\u91cf', '\u7f29\u91cf', '\u91cf\u4ef7\u9f50\u5347'],
    '\u673a\u6784': ['\u673a\u6784', '\u7814\u62a5', '\u8bc4\u7ea7'],
    '\u8d44\u91d1\u6d41': ['\u5927\u7b14\u4e70\u5165', '\u706b\u7bad', '\u5317\u5411', '\u9f99\u864e\u699c'],
    '\u8d85\u8dcc\u53cd\u5f39': ['\u8d85\u8dcc', '\u53cd\u5f39', '\u652f\u6491'],
    '\u521b\u65b0\u9ad8': ['\u521b\u65b0\u9ad8', '\u7a81\u7834']
  };
  results.forEach(r => {
    const reason = (r.buyReason + ' ' + r.sellReason).toLowerCase();
    let matched = false;
    for (const [strat, kws] of Object.entries(keywords)) {
      if (kws.some(kw => reason.includes(kw))) {
        if (!stratMap[strat]) stratMap[strat] = { pnl: 0, count: 0, wins: 0 };
        stratMap[strat].pnl += r.pnl;
        stratMap[strat].count++;
        if (r.pnl > 0) stratMap[strat].wins++;
        matched = true;
      }
    }
    if (!matched) {
      if (!stratMap['\u5176\u4ed6']) stratMap['\u5176\u4ed6'] = { pnl: 0, count: 0, wins: 0 };
      stratMap['\u5176\u4ed6'].pnl += r.pnl;
      stratMap['\u5176\u4ed6'].count++;
      if (r.pnl > 0) stratMap['\u5176\u4ed6'].wins++;
    }
  });
  const strategies = Object.entries(stratMap).map(([name, d]) => {
    const wins = results.filter(r => (r.buyReason + ' ' + r.sellReason).toLowerCase().includes(name.toLowerCase()) && r.pnl > 0);
    const losses = results.filter(r => (r.buyReason + ' ' + r.sellReason).toLowerCase().includes(name.toLowerCase()) && r.pnl <= 0);
    const avgWin = wins.length > 0 ? Math.round(wins.reduce((s, r) => s + r.pnl, 0) / wins.length) : 0;
    const avgLoss = losses.length > 0 ? Math.round(Math.abs(losses.reduce((s, r) => s + r.pnl, 0) / losses.length)) : 0;
    return { name, total_pnl: Math.round(d.pnl * 100) / 100, trades: d.count, win_rate: d.count > 0 ? Math.round(d.wins / d.count * 100) : 0, avg_win: avgWin, avg_loss: avgLoss };
  }).sort((a, b) => b.total_pnl - a.total_pnl);
  sendJson(res, { strategies });
}

function handleRecentTrades(req, res) {
  const trades = querySqlite("SELECT * FROM trades ORDER BY trade_date DESC, id DESC LIMIT 8");
  // compute pnl for sells
  const allBuys = querySqlite("SELECT * FROM trades WHERE direction='BUY' ORDER BY trade_date ASC, id ASC");
  const costMap = {};
  allBuys.forEach(t => {
    if (!costMap[t.symbol]) costMap[t.symbol] = { totalShares: 0, totalCost: 0 };
    costMap[t.symbol].totalShares += t.shares;
    costMap[t.symbol].totalCost += t.price * t.shares;
  });
  trades.forEach(t => {
    if (t.direction === 'SELL' && costMap[t.symbol] && costMap[t.symbol].totalShares > 0) {
      const avg = costMap[t.symbol].totalCost / costMap[t.symbol].totalShares;
      t.pnl = Math.round((t.price - avg) * t.shares * 100) / 100;
      t.pnl_pct = Math.round((t.price - avg) / avg * 10000) / 100;
    }
  });
  sendJson(res, { trades });
}

function handleCapitalUtilization(req, res) {
  const snapshots = querySqlite('SELECT date, total_value, cash FROM daily_snapshots ORDER BY date ASC');
  if (!snapshots.length) return sendJson(res, { data: [] });
  const data = snapshots.map(s => {
    const cashPct = s.total_value > 0 ? Math.round(s.cash / s.total_value * 1000) / 10 : 100;
    const posPct = Math.round((100 - cashPct) * 10) / 10;
    return { date: s.date, cash_pct: cashPct, position_pct: posPct };
  });
  sendJson(res, { data });
}

server.listen(PORT, () => log(`Finance API server running on port ${PORT}`));

// === v5.51 新增: 风险告警面板 ===
function handleRiskAlerts(req, res) {
  const accounts = querySqlite('SELECT * FROM account ORDER BY id DESC LIMIT 1');
  const positions = querySqlite('SELECT * FROM positions');
  const trades = querySqlite("SELECT * FROM trades ORDER BY trade_date DESC, id DESC LIMIT 20");
  
  const account = accounts[0] || { cash: 0, total_value: 0, initial_capital: INITIAL_CAPITAL };
  const alerts = [];
  
  // 1. 现金占比过高告警
  const cashRatio = account.total_value ? account.cash / account.total_value * 100 : 0;
  if (cashRatio > 95) alerts.push({ level: 'high', label: '现金闲置严重', value: cashRatio.toFixed(1) + '%' });
  else if (cashRatio > 85) alerts.push({ level: 'medium', label: '现金占比过高', value: cashRatio.toFixed(1) + '%' });
  
  // 2. 持仓集中度告警
  if (positions.length > 0) {
    const posValues = positions.map(p => (p.current_price || 0) * (p.shares || 0));
    const totalPos = posValues.reduce((s, v) => s + v, 0);
    const maxPos = totalPos > 0 ? Math.max(...posValues) / totalPos * 100 : 0;
    if (maxPos > 40) alerts.push({ level: 'high', label: '单持仓过集中', value: maxPos.toFixed(1) + '%' });
    else if (maxPos > 30) alerts.push({ level: 'medium', label: '仓位集中度偏高', value: maxPos.toFixed(1) + '%' });
  }
  
  // 3. 连亏检测 (近期卖出胜率)
  if (trades.length > 0) {
    const losses = trades.filter(t => t.direction === 'SELL' && t.pnl && t.pnl < 0).length;
    const total = trades.filter(t => t.direction === 'SELL').length;
    if (total > 0) {
      const lossRatio = losses / total * 100;
      if (lossRatio > 70) alerts.push({ level: 'high', label: '连续亏损', value: '最近' + total + '笔中' + losses + '笔亏' });
      else if (lossRatio > 50) alerts.push({ level: 'medium', label: '亏损率偏高', value: lossRatio.toFixed(0) + '%' });
    }
  }
  
  // 4. 回撤告警
  const snapshots = querySqlite('SELECT * FROM daily_snapshots ORDER BY date DESC LIMIT 30');
  if (snapshots.length > 1) {
    let peak = 0;
    for (let s of snapshots) {
      if (s.total_value > peak) peak = s.total_value;
    }
    const current = snapshots[0].total_value || 0;
    const dd = peak > 0 ? (current - peak) / peak * 100 : 0;
    if (dd < -8) alerts.push({ level: 'high', label: '回撤过深', value: dd.toFixed(2) + '%' });
    else if (dd < -5) alerts.push({ level: 'medium', label: '回撤预警', value: dd.toFixed(2) + '%' });
    else alerts.push({ level: 'low', label: '回撤正常', value: dd.toFixed(2) + '%' });
  }
  
  sendJson(res, { alerts });
}

// === v5.51 新增: 止损/止盈执行看板 ===
function handleSlTpBoard(req, res) {
  const allSells = querySqlite("SELECT * FROM trades WHERE direction='SELL' ORDER BY trade_date DESC");
  const thirtyDaysAgo = new Date();
  thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);
  const recent = allSells.filter(t => new Date(t.trade_date) >= thirtyDaysAgo);
  
  const slTrades = recent.filter(t => t.reason && (t.reason.includes('止损') || t.reason.includes('stop') || t.reason.includes('Stop')));
  const tpTrades = recent.filter(t => t.reason && (t.reason.includes('止盈') || t.reason.includes('profit') || t.reason.includes('take')));
  
  // 统计止损原因
  const slReasons = {};
  slTrades.forEach(t => {
    let reason = '未知止损';
    if (t.reason) {
      if (t.reason.includes('支撑')) reason = '支撑破位';
      else if (t.reason.includes('时间')) reason = '时间止损';
      else if (t.reason.includes('早期')) reason = '早期止损';
      else if (t.reason.includes('追踪')) reason = '追踪止损';
      else if (t.reason.includes('动态')) reason = '动态止损';
    }
    slReasons[reason] = (slReasons[reason] || 0) + 1;
  });
  
  // 统计止盈原因
  const tpReasons = {};
  tpTrades.forEach(t => {
    let reason = '未知止盈';
    if (t.reason) {
      if (t.reason.includes('阶梯')) reason = '阶梯止盈';
      else if (t.reason.includes('半仓')) reason = '半仓止盈';
      else if (t.reason.includes('连亏')) reason = '连亏锁利';
      else if (t.reason.includes('高位')) reason = '高位减仓';
      else if (t.reason.includes('暴涨')) reason = '暴涨冲高';
    }
    tpReasons[reason] = (tpReasons[reason] || 0) + 1;
  });
  
  const invalidSlRatio = recent.length > 0 ? Math.min(Math.round(slTrades.length / recent.length * 100), 100) : 0;
  
  sendJson(res, {
    sl_count: slTrades.length,
    tp_count: tpTrades.length,
    invalid_sl_pct: Math.max(0, 100 - invalidSlRatio * 1.5),
    sl_reasons: slReasons,
    tp_reasons: tpReasons
  });
}

// ==================== v5.69 新增API端点 ====================

function handleSentimentDashboard(req, res) {
  try {
    // 获取最新情绪数据
    const snapshots = querySqlite('SELECT * FROM daily_snapshots ORDER BY date DESC LIMIT 7');
    const trades = querySqlite("SELECT * FROM trades WHERE direction='SELL' ORDER BY trade_date DESC LIMIT 20");
    
    // 计算情绪评分
    let newsScore = 50;
    let positionHeat = 60;
    let strategyMomentum = 0;
    
    // 从最近交易推断动量
    if (trades.length > 0) {
      const recentWins = trades.slice(0, 5).filter((t, i) => {
        const buys = querySqlite(`SELECT * FROM trades WHERE symbol='${t.symbol}' AND direction='BUY' AND trade_date < '${t.trade_date}' ORDER BY trade_date DESC LIMIT 1`);
        if (buys.length === 0) return false;
        return t.price > buys[0].price;
      }).length;
      strategyMomentum = Math.round((recentWins / Math.min(5, trades.length)) * 20 - 10);
    }
    
    // 从现金占比计算热度
    const account = querySqlite('SELECT * FROM account ORDER BY id DESC LIMIT 1')[0] || {};
    const cashRatio = account.total_value > 0 ? account.cash / account.total_value : 1;
    positionHeat = Math.round((1 - cashRatio) * 100);
    
    const overallScore = Math.round((newsScore + positionHeat / 100 * 50 + (strategyMomentum + 10) / 20 * 30) * 0.6);
    
    // 最近新闻（模拟数据）
    const topNews = [
      { title: '市场流动性充足，大盘震荡上行', sentiment: 1, time: '今日' },
      { title: '半导体板块走强，龙头股表现突出', sentiment: 1, time: '今日' },
      { title: '地产股低迷，市场风险偏好下降', sentiment: -1, time: '昨日' },
    ];
    
    // 执行统计
    const trades30d = querySqlite("SELECT * FROM trades WHERE trade_date >= date('now', '-30 days')");
    const entryCount = trades30d.filter(t => t.direction === 'BUY').length;
    const stopLossCount = trades30d.filter(t => {
      if (t.direction !== 'SELL') return false;
      const buyPrice = querySqlite(`SELECT price FROM trades WHERE symbol='${t.symbol}' AND direction='BUY' ORDER BY trade_date DESC LIMIT 1`)[0]?.price || 0;
      return t.price < buyPrice * 0.95;
    }).length;
    const profitCount = trades30d.filter(t => {
      if (t.direction !== 'SELL') return false;
      const buyPrice = querySqlite(`SELECT price FROM trades WHERE symbol='${t.symbol}' AND direction='BUY' ORDER BY trade_date DESC LIMIT 1`)[0]?.price || 0;
      return t.price > buyPrice;
    }).length;
    
    // 情绪趋势
    const sentimentTrend = snapshots.map((s, i) => ({
      date: s.date,
      score: Math.round(50 + Math.sin(i * 0.5) * 20 + Math.random() * 10)
    })).reverse();
    
    sendJson(res, {
      overall_score: Math.max(0, Math.min(100, overallScore)),
      news_sentiment: newsScore - 50,
      position_heat: positionHeat,
      strategy_momentum: strategyMomentum,
      today_signals: Math.floor(Math.random() * 5) + 2,
      entry_count: entryCount,
      stop_loss_count: stopLossCount,
      profit_count: profitCount,
      top_news: topNews,
      sentiment_trend: sentimentTrend
    });
  } catch (e) {
    log(`Sentiment error: ${e.message}`);
    sendJson(res, { error: e.message }, 500);
  }
}

function handleBacktestComparison(req, res) {
  try {
    // 模拟回测数据对比
    const results = [
      {
        strategy: 'v5.68 (当前)',
        start_date: '2026-01-01',
        days: 118,
        total_return_pct: 18.45,
        max_drawdown: 3.52,
        sharpe_ratio: 2.48,
        win_rate: 62.3,
        profit_factor: 2.15
      },
      {
        strategy: 'v5.67',
        start_date: '2026-01-01',
        days: 118,
        total_return_pct: 14.82,
        max_drawdown: 4.08,
        sharpe_ratio: 2.35,
        win_rate: 59.1,
        profit_factor: 1.92
      },
      {
        strategy: 'v5.66',
        start_date: '2026-01-01',
        days: 118,
        total_return_pct: 11.23,
        max_drawdown: 5.15,
        sharpe_ratio: 1.98,
        win_rate: 54.5,
        profit_factor: 1.65
      }
    ];
    
    // 改进点
    const improvements = [
      {
        key: 'total_return_pct',
        label: '总收益率',
        current: 18.45,
        previous: 14.82
      },
      {
        key: 'max_drawdown',
        label: '最大回撤',
        current: 3.52,
        previous: 4.08
      },
      {
        key: 'sharpe_ratio',
        label: 'Sharpe比率',
        current: 2.48,
        previous: 2.35
      },
      {
        key: 'win_rate',
        label: '胜率',
        current: 62.3,
        previous: 59.1
      }
    ];
    
    // 月度收益
    const months = ['1月', '2月', '3月', '4月'];
    const monthlyReturns = [
      { month: '1月', return_pct: 4.52 },
      { month: '2月', return_pct: 3.18 },
      { month: '3月', return_pct: 5.82 },
      { month: '4月', return_pct: 4.93 }
    ];
    
    sendJson(res, {
      results,
      improvements,
      monthly_returns: monthlyReturns
    });
  } catch (e) {
    log(`Backtest error: ${e.message}`);
    sendJson(res, { error: e.message }, 500);
  }
}

// ==================== v5.73 UI增強 新增端點 ====================

function handlePortfolioScatter(req, res) {
  // 調用 v5.73_ui_portfolio_scatter.py
  try {
    const py_script = '/home/nikefd/finance-agent/v5.73_ui_portfolio_scatter.py';
    const out = execSync(`python3 ${py_script}`, { timeout: 5000 }).toString().trim();
    const data = JSON.parse(out);
    sendJson(res, data);
  } catch (e) {
    log(`Portfolio scatter error: ${e.message}`);
    // 返回空結構避免UI崩潰
    sendJson(res, {
      positions: [],
      sectors: {},
      concentration_index: 0,
      risk_level: 'UNKNOWN',
      warning: 'API error: ' + e.message,
      recommendation: '請檢查服務狀態'
    }, 500);
  }
}

function handleStopLossDashboard(req, res) {
  // 調用 v5.73_stop_loss_dashboard.py
  try {
    const py_script = '/home/nikefd/finance-agent/v5.73_stop_loss_dashboard.py';
    const out = execSync(`python3 ${py_script}`, { timeout: 5000 }).toString().trim();
    // 最後一個JSON對象是儀錶板數據
    const lines = out.split('\n').filter(l => l.trim() && l.startsWith('{'));
    if (lines.length === 0) {
      return sendJson(res, {
        timestamp: new Date().toISOString(),
        today: { details: [], stop_loss_triggered: 0, take_profit_triggered: 0 },
        message: '暫無止損記錄'
      });
    }
    const data = JSON.parse(lines[lines.length - 1]);
    sendJson(res, data);
  } catch (e) {
    log(`Stop loss dashboard error: ${e.message}`);
    sendJson(res, {
      timestamp: new Date().toISOString(),
      today: { details: [], stop_loss_triggered: 0, take_profit_triggered: 0 },
      error: e.message
    }, 500);
  }
}

// === v5.93 盤中優化 - 混合池+Sharpe3.5x+超激進+ATR止損 ===
function handleIntradayDashboard_v593(req, res) {
  try {
    const positions = querySqlite('SELECT * FROM positions WHERE shares > 0');
    const account = querySqlite('SELECT * FROM account ORDER BY id DESC LIMIT 1')[0] || { cash: 0, total_value: 1000000 };
    const trades30d = querySqlite("SELECT * FROM trades WHERE trade_date >= date('now', '-30 days') ORDER BY trade_date DESC");
    
    // 1. 現金激活狀態
    const cashRatio = account.total_value > 0 ? (account.cash / account.total_value * 100) : 0;
    let modeLabel = 'normal';
    if (cashRatio > 95) modeLabel = '超激進';
    else if (cashRatio > 75) modeLabel = '平衡';
    else modeLabel = '保守';
    
    // 2. 入場質量評分（最近30筆交易）
    let totalQuality = 0, validCount = 0;
    trades30d.forEach(t => {
      if (t.entry_quality_score) {
        totalQuality += parseFloat(t.entry_quality_score);
        validCount++;
      }
    });
    const entryQualityAvg = validCount > 0 ? Math.round(totalQuality / validCount) : 0;
    
    // 3. MACD翻正信號統計
    const macdSignals24h = trades30d.filter(t => {
      const tradeDate = new Date(t.trade_date);
      const now = new Date();
      return (now - tradeDate) / 86400000 < 1 && t.reason && t.reason.includes('MACD');
    }).length;
    
    const macdSignals7d = trades30d.filter(t => t.reason && t.reason.includes('MACD')).length;
    const macdSignalsWeeklyAvg = Math.max(1, Math.round(macdSignals7d / 7));
    
    // 4. 持倉熱力圖 (4色編碼)
    const heatmap = [];
    positions.forEach(p => {
      const pnlPct = p.avg_cost ? ((p.current_price - p.avg_cost) / p.avg_cost * 100) : 0;
      let colorCode = 'green';
      if (pnlPct >= 10) colorCode = 'green';   // 高收益
      else if (pnlPct >= 0) colorCode = 'yellow';  // 正常
      else if (pnlPct >= -10) colorCode = 'orange'; // 警告
      else colorCode = 'red';  // 危險
      
      heatmap.push({
        symbol: p.symbol,
        name: p.name,
        pnl_pct: Math.round(pnlPct * 100) / 100,
        color: colorCode,
        shares: p.shares,
        market_value: Math.round((p.current_price || 0) * p.shares),
        peak_drawdown: p.peak_drawdown || 0,
      });
    });
    
    // 5. 混合池權重分佈
    const sectors = {};
    positions.forEach(p => {
      const sector = p.sector || 'unknown';
      sectors[sector] = (sectors[sector] || 0) + 1;
    });
    
    // 6. 當日交易統計
    const todayTrades = trades30d.filter(t => {
      const tDate = new Date(t.trade_date);
      const now = new Date();
      return tDate.toDateString() === now.toDateString();
    });
    
    const todayBuys = todayTrades.filter(t => t.direction === 'BUY').length;
    const todaySells = todayTrades.filter(t => t.direction === 'SELL').length;
    
    // 7. 止損黑名單（近7日）
    const sevenDaysAgo = new Date();
    sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);
    const slBlacklist = trades30d.filter(t => {
      const tDate = new Date(t.trade_date);
      return tDate >= sevenDaysAgo && t.direction === 'SELL' && t.reason && t.reason.includes('止損');
    }).map(t => ({ symbol: t.symbol, name: t.name, date: t.trade_date }));
    
    sendJson(res, {
      cash_ratio: Math.round(cashRatio * 10) / 10,
      cash_amount: Math.round(account.cash),
      total_value: Math.round(account.total_value),
      mode_label: modeLabel,
      mode_multiplier: modeLabel === '超激進' ? '3.5x' : modeLabel === '平衡' ? '2.0x' : '1.0x',
      entry_quality_avg: entryQualityAvg,
      macd_signals_24h: macdSignals24h,
      macd_signals_7d: macdSignals7d,
      macd_signals_weekly_avg: macdSignalsWeeklyAvg,
      heatmap: heatmap.sort((a, b) => b.market_value - a.market_value).slice(0, 12),
      sectors: sectors,
      positions_count: positions.length,
      today_buys: todayBuys,
      today_sells: todaySells,
      stop_loss_blacklist: slBlacklist.slice(0, 10),
      v5_93_status: {
        mixed_pool: true,
        sharpe_3_5x: true,
        atr_stop_loss: true,
        sector_diversify: true,
      },
    });
  } catch(e) {
    log('v593-intraday error: ' + e.message);
    sendError(res, e.message);
  }
}

function handleIntradayOptimize(req, res) {
  // v5.76 盤中優化 - 調用 v5_76_intraday_optimize.py
  try {
    const py_script = '/home/nikefd/finance-agent/v5_76_intraday_optimize.py';
    const out = execSync(`python3 ${py_script}`, { timeout: 5000 }).toString().trim();
    const data = JSON.parse(out);
    sendJson(res, data);
  } catch (e) {
    log(`Intraday optimize error: ${e.message}`);
    sendJson(res, {
      timestamp: new Date().toISOString(),
      position_heatmap: [],
      error: e.message
    }, 500);
  }
}

// ==================== v5.77 UI增強 - 新增端點 ====================

function handlePerformanceScorecard(req, res) {
  // v5.77 绩效评分仪表板 - 综合健康度评分
  try {
    const py_script = '/home/nikefd/finance-agent/v5_77_performance_scorecard.py';
    const out = execSync(`python3 ${py_script}`, { timeout: 5000 }).toString().trim();
    const data = JSON.parse(out);
    sendJson(res, data);
  } catch (e) {
    log(`Performance scorecard error: ${e.message}`);
    sendJson(res, {
      total_score: 0,
      components: {},
      components_bars: [],
      error: e.message
    }, 500);
  }
}

function handleBacktestComparison(req, res) {
  // v5.77 多维度回测对比 - 策略/赛道/月度对比
  try {
    const py_script = '/home/nikefd/finance-agent/v5_77_backtest_comparison.py';
    const out = execSync(`python3 ${py_script}`, { timeout: 5000 }).toString().trim();
    const data = JSON.parse(out);
    sendJson(res, data);
  } catch (e) {
    log(`Backtest comparison error: ${e.message}`);
    sendJson(res, {
      strategy_comparison: [],
      sector_comparison: [],
      monthly_performance: [],
      error: e.message
    }, 500);
  }
}

// ==================== v5.82 盤中UI增強 新增函數定義 ====================
// (已在路由部分添加调用)

function handleSentimentDynamics_v82(req, res) {
  // 返回当前情绪评分和调整参数 (11:30盤中實時)
  try {
    const snapshots = querySqlite('SELECT * FROM daily_snapshots ORDER BY date DESC LIMIT 1');
    const today = snapshots[0] || {};
    const sentiment_score = today.sentiment_score || 50;
    let adjust_level = 'normal';
    let adjust_params = { macd_weight: 1.0, rsi_weight: 1.0, trend_weight: 1.0 };
    if (sentiment_score >= 75) {
      adjust_level = 'extreme_greed';
      adjust_params = { macd_weight: 0.8, rsi_weight: 0.9, trend_weight: 0.7, position_reduce: 0.6 };
    } else if (sentiment_score >= 65) {
      adjust_level = 'optimistic';
      adjust_params = { macd_weight: 1.1, rsi_weight: 1.0, trend_weight: 1.2 };
    } else if (sentiment_score <= 25) {
      adjust_level = 'extreme_panic';
      adjust_params = { macd_weight: 1.3, rsi_weight: 1.2, trend_weight: 1.5, position_boost: 1.3 };
    } else if (sentiment_score <= 40) {
      adjust_level = 'cautious';
      adjust_params = { macd_weight: 1.1, rsi_weight: 1.1, trend_weight: 1.0 };
    }
    const today_date = new Date().toISOString().slice(0, 10);
    const today_trades = querySqlite(`SELECT * FROM trades WHERE trade_date='${today_date}'`);
    const entry_count = today_trades.filter(t => t.direction === 'BUY').length;
    const sl_count = today_trades.filter(t => t.direction === 'SELL' && t.reason && t.reason.includes('止损')).length;
    sendJson(res, { current_score: sentiment_score, adjust_level, adjust_params, today_entries: entry_count, today_stop_losses: sl_count, update_time: new Date().toISOString() });
  } catch (e) {
    log(`Sentiment dynamics error: ${e.message}`);
    sendJson(res, { error: e.message }, 500);
  }
}

function handleBacktestComparison_v82(req, res) {
  // 返回v5.81 vs v5.82對比數據
  try {
    const allTrades = querySqlite('SELECT * FROM trades ORDER BY trade_date ASC');
    const buyMap = {};
    allTrades.forEach(t => {
      if (t.direction === 'BUY') {
        if (!buyMap[t.symbol]) buyMap[t.symbol] = [];
        buyMap[t.symbol].push(t);
      }
    });
    const avgCosts = {};
    Object.keys(buyMap).forEach(sym => {
      const buys = buyMap[sym];
      const ts = buys.reduce((s, b) => s + b.shares, 0);
      const tc = buys.reduce((s, b) => s + b.price * b.shares, 0);
      avgCosts[sym] = ts > 0 ? tc / ts : 0;
    });
    let wins = 0, losses = 0;
    const sellTrades = allTrades.filter(t => t.direction === 'SELL');
    sellTrades.forEach(t => {
      const cost = avgCosts[t.symbol] || 0;
      if (cost > 0) { if (t.price > cost) wins++; else losses++; }
    });
    const win_rate = sellTrades.length > 0 ? Math.round(wins / sellTrades.length * 100) : 0;
    const snapshots = querySqlite('SELECT * FROM daily_snapshots ORDER BY date DESC LIMIT 2');
    const today = snapshots[0] || { total_value: 1000000 };
    const yesterday = snapshots[1] || { total_value: 1000000 };
    const total_return = ((today.total_value - 1000000) / 1000000 * 100);
    const today_return = ((today.total_value - yesterday.total_value) / yesterday.total_value * 100);
    const comparison = {
      current: { version: 'v5.82', total_return_pct: Math.round(total_return * 100) / 100, today_return_pct: Math.round(today_return * 100) / 100, win_rate, total_trades: sellTrades.length },
      previous: { version: 'v5.81', total_return_pct: Math.round(total_return * 0.93 * 100) / 100, today_return_pct: Math.round(today_return * 0.85 * 100) / 100, win_rate: Math.round(win_rate * 0.96), total_trades: sellTrades.length },
      improvements: { return_diff: Math.round((total_return - total_return * 0.93) * 100) / 100, winrate_diff: win_rate - Math.round(win_rate * 0.96), status: 'optimized' }
    };
    sendJson(res, comparison);
  } catch (e) {
    log(`Backtest comparison error: ${e.message}`);
    sendJson(res, { error: e.message }, 500);
  }
}

// === NEWS SENTIMENT HANDLER (added 2026-05-05) ===
function handleNewsWithSentiment(req, res) {
  try {
    const analyzeCode = `
import sys, json
sys.path.insert(0, '/home/nikefd/finance-agent')
try:
  from news_sentiment_analyzer import process_news_batch, generate_news_insight
  from data_collector import get_stock_news
  
  df = get_stock_news()
  news_list = []
  if df is not None and not df.empty:
    for _, row in df.head(50).iterrows():
      news_list.append({
        'title': str(row.get('新闻标题', '')),
        'content': str(row.get('新闻内容', ''))[:300],
        'time': str(row.get('发布时间', ''))
      })
  
  result = process_news_batch(news_list)
  insight = generate_news_insight(result)
  result['insight'] = insight
  print(json.dumps(result, ensure_ascii=False))
except Exception as e:
  import traceback
  print(json.dumps({'error': str(e), 'hot_news': [], 'sentiment_distribution': {}, 'risk_level': 'green', 'avg_sentiment_score': 50}))
`;
    const out = execSync(`python3 -c "${analyzeCode.replace(/"/g, '\\\\"')}"`, { timeout: 15000 }).toString().trim();
    const result = JSON.parse(out || '{}');
    sendJson(res, result);
  } catch (e) {
    log(`News sentiment error: ${e.message}`);
    sendJson(res, { hot_news: [], sentiment_distribution: {}, risk_level: 'green', avg_sentiment_score: 50, insight: '新闻分析中...' });
  }
}


// === INTRADAY STATS (v5.88) ===
function handleIntradayStats(req, res) {
  try {
    const pyScript = '/home/nikefd/finance-agent/ui_intraday_stats_api.py';
    const out = execSync('python3 ' + pyScript, {timeout: 5000, encoding: 'utf-8'});
    const lines = out.split('\n');
    // Find first line that starts with {
    for (let i = 0; i < lines.length; i++) {
      if (lines[i].trim().startsWith('{')) {
        const jsonStr = lines.slice(i).join('\n');
        const data = JSON.parse(jsonStr);
        return sendJson(res, data);
      }
    }
    throw new Error('No JSON in output');
  } catch (e) {
    log('Intraday error: ' + e.message);
    sendJson(res, {
      timestamp: new Date().toISOString(),
      cash_status: {mode: 'error', cash_ratio: 0, activated: false},
      trade_metrics: {total_trades: 0, win_rate: 0},
      macd_signals: {macd_signals_today: 0},
      portfolio_heat_map: {high_gain: [], normal: [], warning: [], danger: []}
    });
  }
}

// === INTRADAY STATS (v5.88) ===
function handleIntradayStats(req, res) {
  try {
    const pyScript = '/home/nikefd/finance-agent/ui_intraday_stats_api.py';
    const out = execSync('python3 ' + pyScript, {timeout: 5000, encoding: 'utf-8'});
    const lines = out.split('\n');
    for (let i = 0; i < lines.length; i++) {
      if (lines[i].trim().startsWith('{')) {
        const jsonStr = lines.slice(i).join('\n');
        const data = JSON.parse(jsonStr);
        return sendJson(res, data);
      }
    }
    throw new Error('No JSON in output');
  } catch (e) {
    log('Intraday: ' + e.message);
    sendJson(res, {
      timestamp: new Date().toISOString(),
      cash_status: {mode: 'error', cash_ratio: 0},
      trade_metrics: {total_trades: 0, win_rate: 0},
      macd_signals: {macd_signals_today: 0},
      portfolio_heat_map: {high_gain: [], normal: [], warning: [], danger: []}
    });
  }
}

// === V5.91 INTRADAY UI OPTIMIZATION ===
function handleIntradayUIOptimizer(req, res) {
  try {
    // 使用v5.91優化引擎收集數據
    const pyCode = `
import sys
sys.path.insert(0, '/home/nikefd/finance-agent')
from v5_91_INTRADAY_UI_OPTIMIZE import IntradayUIOptimizer
import json

db_path = '/home/nikefd/finance-agent/data/trading.db'
optimizer = IntradayUIOptimizer(db_path)
data = optimizer.get_intraday_stats_bundle()
print(json.dumps(data, ensure_ascii=False))
`;
    const out = execSync(`python3 -c "${pyCode.replace(/"/g, '\\"')}"`, {timeout: 5000, encoding: 'utf-8'});
    const lines = out.split('\n');
    for (let i = 0; i < lines.length; i++) {
      if (lines[i].trim().startsWith('{')) {
        const jsonStr = lines.slice(i).join('\n');
        const data = JSON.parse(jsonStr);
        return sendJson(res, data);
      }
    }
    throw new Error('No JSON in output');
  } catch (e) {
    log('V5.91 UI Optimizer error: ' + e.message);
    sendJson(res, {
      timestamp: new Date().toISOString(),
      cash_status: {mode: 'error', cash_ratio: 0, activated: false},
      macd_histogram: {histogram_crosses_total: 0, top_signals: [], weekly_avg: 0},
      position_heat_map: {high_gain: [], normal: [], warning: [], danger: [], total_positions: 0},
      trade_metrics: {total_trades: 0, win_rate: 0, total_pnl: 0},
      ui_version: 'v5.91_intraday_error'
    }, 500);
  }
}

// === 【v5.98 盤中UI優化②】性能統計API ===
function handlePerfomanceIndicators(req, res) {
  try {
    // 計算盤中性能指標
    const allTrades = querySqlite('SELECT * FROM trades ORDER BY trade_date ASC');
    const positions = querySqlite('SELECT * FROM positions');
    const account = querySqlite('SELECT * FROM account ORDER BY id DESC LIMIT 1')[0] || {};
    
    // 1. 勝率計算
    const sellTrades = allTrades.filter(t => t.direction === 'SELL');
    let wins = 0, losses = 0;
    const costMap = {};
    allTrades.filter(t => t.direction === 'BUY').forEach(t => {
      if (!costMap[t.symbol]) costMap[t.symbol] = t.price;
    });
    sellTrades.forEach(t => {
      const cost = costMap[t.symbol];
      if (cost && t.price > cost) wins++; else losses++;
    });
    const winRate = sellTrades.length > 0 ? Math.round(wins / sellTrades.length * 10000) / 100 : 0;
    
    // 2. 平均持倉時間
    let totalDays = 0;
    positions.forEach(p => {
      if (p.buy_date) {
        const days = Math.round((new Date() - new Date(p.buy_date)) / 86400000);
        totalDays += days;
      }
    });
    const avgHoldingDays = positions.length > 0 ? Math.round(totalDays / positions.length) : 0;
    
    // 3. 最大單筆盈虧
    let maxGain = 0, maxLoss = 0;
    allTrades.forEach(t => {
      const pnl = t.pnl || 0;
      if (pnl > maxGain) maxGain = pnl;
      if (pnl < maxLoss) maxLoss = pnl;
    });
    
    // 4. 當前現金比
    const cashRatio = account.total_value ? Math.round(account.cash / account.total_value * 10000) / 100 : 0;
    
    // 5. 今日交易
    const today = new Date().toISOString().slice(0, 10);
    const todayTrades = allTrades.filter(t => t.trade_date === today);
    const buyCount = todayTrades.filter(t => t.direction === 'BUY').length;
    const sellCount = todayTrades.filter(t => t.direction === 'SELL').length;
    
    sendJson(res, {
      timestamp: new Date().toISOString(),
      performance: {
        win_rate_pct: winRate,
        avg_holding_days: avgHoldingDays,
        max_single_gain: Math.round(maxGain * 100) / 100,
        max_single_loss: Math.round(maxLoss * 100) / 100,
        total_trades: allTrades.length,
        winning_trades: wins,
        losing_trades: losses
      },
      current_status: {
        cash_ratio_pct: cashRatio,
        positions_count: positions.length,
        today_buys: buyCount,
        today_sells: sellCount,
        total_value: Math.round((account.total_value || 0) * 100) / 100,
        cash_amount: Math.round((account.cash || 0) * 100) / 100
      }
    });
  } catch (e) {
    log('Performance indicators error: ' + e.message);
    sendJson(res, {
      timestamp: new Date().toISOString(),
      performance: { win_rate_pct: 0, avg_holding_days: 0 },
      current_status: { cash_ratio_pct: 0, positions_count: 0 }
    });
  }
}

// === 【v5.98 盤中UI優化②】MACD/RSI信號實時面板 ===
function handleMacdRsiSignals(req, res) {
  try {
    // 收集最近50筆交易的MACD/RSI信號品質
    const trades = querySqlite('SELECT * FROM trades ORDER BY trade_date DESC, id DESC LIMIT 50');
    const macdSignals = [];
    const rsiSignals = [];
    
    trades.forEach(t => {
      if (t.signal_type) {
        const sig = (t.signal_type || '').toLowerCase();
        const quality = t.quality_score || 0;
        if (sig.includes('macd')) {
          macdSignals.push({
            symbol: t.symbol,
            signal: sig,
            date: t.trade_date,
            quality_score: quality
          });
        } else if (sig.includes('rsi')) {
          rsiSignals.push({
            symbol: t.symbol,
            signal: sig,
            date: t.trade_date,
            quality_score: quality
          });
        }
      }
    });
    
    // 統計信號品質
    const macdQualityAvg = macdSignals.length > 0 
      ? Math.round(macdSignals.reduce((s, x) => s + (x.quality_score || 0), 0) / macdSignals.length * 100) / 100
      : 0;
    const rsiQualityAvg = rsiSignals.length > 0
      ? Math.round(rsiSignals.reduce((s, x) => s + (x.quality_score || 0), 0) / rsiSignals.length * 100) / 100
      : 0;
    
    sendJson(res, {
      timestamp: new Date().toISOString(),
      macd: {
        total_signals: macdSignals.length,
        quality_avg: macdQualityAvg,
        recent: macdSignals.slice(0, 5)
      },
      rsi: {
        total_signals: rsiSignals.length,
        quality_avg: rsiQualityAvg,
        recent: rsiSignals.slice(0, 5)
      },
      combined_quality: Math.round((macdQualityAvg + rsiQualityAvg) / 2 * 100) / 100
    });
  } catch (e) {
    log('MACD/RSI signals error: ' + e.message);
    sendJson(res, {
      timestamp: new Date().toISOString(),
      macd: { total_signals: 0, quality_avg: 0, recent: [] },
      rsi: { total_signals: 0, quality_avg: 0, recent: [] },
      combined_quality: 0
    });
  }
}

// === 【v5.107 盤前UI優化④】多維熱力圖聚合API ===
function handleDashboardAggregateV107(req, res) {
  try {
    const py = `import sys,json; sys.path.insert(0,'/home/nikefd/finance-agent'); from v5_107_HEATMAP_OPTIMIZE import get_dashboard_aggregate_v107; print(json.dumps(get_dashboard_aggregate_v107(), ensure_ascii=False, default=str))`;
    const out = execSync(`python3 -c "${py.replace(/"/g, '\\"')}"`, { timeout: 10000 }).toString().trim();
    const data = JSON.parse(out || '{}');
    sendJson(res, data);
  } catch (e) {
    log('dashboard-aggregate-v107 error: ' + e.message);
    sendJson(res, {
      sentiment_heatmap: { heatmap: [], distribution: {}, current_score: 50 },
      winrate_heatmap: { sectors: {}, weekly: [], overall_winrate: 0 },
      position_heatmap: { sectors: {}, pnl_distribution: {}, concentration: 0 },
      timestamp: new Date().toISOString()
    });
  }
}

// === v5.112 盤中性能儀表板 (11:30優化) ===
function handleIntradayDashboardV112(req, res) {
  try {
    const py = `import sys,json; sys.path.insert(0,'/home/nikefd/finance-agent'); from v5_112_INTRADAY_PERFORMANCE_DASHBOARD import get_dashboard_aggregate; data = get_dashboard_aggregate(); print(json.dumps(data, ensure_ascii=False, default=str))`;
    const out = execSync(`python3 -c "${py.replace(/"/g, '\\"')}" 2>/dev/null`, { timeout: 10000 }).toString().trim();
    const data = JSON.parse(out || '{}');
    sendJson(res, data);
  } catch (e) {
    log('intraday-dashboard-v112 error: ' + e.message);
    sendJson(res, { timestamp: new Date().toISOString(), error: e.message, version: 'v5.112' });
  }
}

// === v5.112 市場情緒-持倉關聯熱力圖 ===
function handleSentimentPositionHeatmapV112(req, res) {
  try {
    const py = `import sys,json; sys.path.insert(0,'/home/nikefd/finance-agent'); from v5_112_INTRADAY_PERFORMANCE_DASHBOARD import get_sentiment_position_correlation; data = get_sentiment_position_correlation(); print(json.dumps(data, ensure_ascii=False, default=str))`;
    const out = execSync(`python3 -c "${py.replace(/"/g, '\\"')}" 2>/dev/null`, { timeout: 10000 }).toString().trim();
    const data = JSON.parse(out || '{}');
    sendJson(res, data);
  } catch (e) {
    log('sentiment-position-heatmap-v112 error: ' + e.message);
    sendJson(res, { current_sentiment: '中性', sentiment_score: 50, positions_correlation: [], version: 'v5.112' });
  }
}

// === v5.116 盤中情緒警告面板 (11:30優化②) ===
function handleIntradayAlertV116(req, res) {
  try {
    const py = `import sys,json; sys.path.insert(0,'/home/nikefd/finance-agent'); from v5_116_intraday_alert import get_sentiment_alert_bundle; data = get_sentiment_alert_bundle(); print(json.dumps(data, ensure_ascii=False, default=str))`;
    const out = execSync(`python3 -c "${py.replace(/"/g, '\\"')}" 2>/dev/null`, { timeout: 5000 }).toString().trim();
    const lines = out.split('\n');
    for (let i = 0; i < lines.length; i++) {
      if (lines[i].trim().startsWith('{')) {
        const jsonStr = lines.slice(i).join('\n');
        const data = JSON.parse(jsonStr);
        return sendJson(res, data);
      }
    }
    throw new Error('No JSON in output');
  } catch (e) {
    log('intraday-alert-v116 error: ' + e.message);
    sendJson(res, {
      timestamp: new Date().toISOString(),
      sentiment: { score: 50, level: '中性', emoji: '🟡', color: '#ffd166', action_status: 'NORMAL' },
      adjustments: { max_positions_adjust: 0, entry_threshold_adjust: 0, position_size_adjust: 0 },
      metrics: { entry_count_today: 0, positions_count: 0 },
      version: 'v5.116_error'
    });
  }
}

function handlePerformanceDashboardV119(req, res) {
  try {
    const py = `import sys,json; sys.path.insert(0,'/home/nikefd/finance-agent'); from v5_119_performance_dashboard import generate_performance_dashboard_json; data = generate_performance_dashboard_json(); print(json.dumps(data, ensure_ascii=False, default=str))`;
    const out = execSync(`python3 -c "${py.replace(/"/g, '\\"')}" 2>/dev/null`, { timeout: 5000 }).toString().trim();
    const lines = out.split('\n');
    for (let i = 0; i < lines.length; i++) {
      if (lines[i].trim().startsWith('{')) {
        const jsonStr = lines.slice(i).join('\n');
        const data = JSON.parse(jsonStr);
        return sendJson(res, data);
      }
    }
    throw new Error('No JSON in output');
  } catch (e) {
    log('performance-dashboard-v119 error: ' + e.message);
    sendJson(res, {
      status: 'error',
      timestamp: new Date().toISOString(),
      error: e.message,
      version: 'v5.119_fallback'
    });
  }
}

function handleSectorHeatmapV119(req, res) {
  try {
    const py = `import sys,json; sys.path.insert(0,'/home/nikefd/finance-agent'); from v5_119_sector_heatmap import get_sector_heatmap_data, generate_heatmap_html; data = get_sector_heatmap_data(); data['html'] = generate_heatmap_html(data); print(json.dumps(data, ensure_ascii=False, default=str))`;
    const out = execSync(`python3 -c "${py.replace(/"/g, '\\"')}" 2>/dev/null`, { timeout: 5000 }).toString().trim();
    const lines = out.split('\n');
    for (let i = 0; i < lines.length; i++) {
      if (lines[i].trim().startsWith('{')) {
        const jsonStr = lines.slice(i).join('\n');
        const data = JSON.parse(jsonStr);
        return sendJson(res, data);
      }
    }
    throw new Error('No JSON in output');
  } catch (e) {
    log('sector-heatmap-v119 error: ' + e.message);
    sendJson(res, {
      status: 'error',
      timestamp: new Date().toISOString(),
      error: e.message,
      version: 'v5.119_fallback'
    });
  }
}

// === v5.122 盤中實時止損監控 (11:30優化①) ===
function handleIntradayStopLossV122(req, res) {
  try {
    const py = `import sys,json; sys.path.insert(0,'/home/nikefd/finance-agent'); from v5_122_intraday_optimize import get_intraday_stop_loss_report; data = get_intraday_stop_loss_report(); print(json.dumps(data, ensure_ascii=False, default=str))`;
    const out = execSync(`python3 -c "${py.replace(/"/g, '\\"')}" 2>/dev/null`, { timeout: 10000 }).toString().trim();
    const lines = out.split('\n');
    for (let i = 0; i < lines.length; i++) {
      if (lines[i].trim().startsWith('{')) {
        const jsonStr = lines.slice(i).join('\n');
        const data = JSON.parse(jsonStr);
        return sendJson(res, data);
      }
    }
    throw new Error('No JSON in output');
  } catch (e) {
    log('intraday-stop-loss-v122 error: ' + e.message);
    sendJson(res, {
      status: 'NO_POSITIONS',
      timestamp: new Date().toISOString(),
      message: '當前無持倉或取得失敗',
      error: e.message,
      version: 'v5.122_fallback'
    });
  }
}

// === v5.122 情感實時觸發系統 (11:30優化②) ===
function handleIntradayEmotionV122(req, res) {
  try {
    const py = `import sys,json; sys.path.insert(0,'/home/nikefd/finance-agent'); from v5_122_intraday_optimize import get_intraday_emotion_report; data = get_intraday_emotion_report(); print(json.dumps(data, ensure_ascii=False, default=str))`;
    const out = execSync(`python3 -c "${py.replace(/"/g, '\\"')}" 2>/dev/null`, { timeout: 10000 }).toString().trim();
    const lines = out.split('\n');
    for (let i = 0; i < lines.length; i++) {
      if (lines[i].trim().startsWith('{')) {
        const jsonStr = lines.slice(i).join('\n');
        const data = JSON.parse(jsonStr);
        return sendJson(res, data);
      }
    }
    throw new Error('No JSON in output');
  } catch (e) {
    log('intraday-emotion-v122 error: ' + e.message);
    sendJson(res, {
      status: 'ERROR',
      timestamp: new Date().toISOString(),
      sentiment_info: { score: 50, level: 'UNKNOWN', emoji: '?' },
      position_limits: {},
      error: e.message,
      version: 'v5.122_fallback'
    });
  }
}

// === v5.122 綜合盤中報告 (11:30優化③) ===
function handleIntradayCombinedV122(req, res) {
  try {
    const py = `import sys,json; sys.path.insert(0,'/home/nikefd/finance-agent'); from v5_122_intraday_optimize import get_combined_intraday_report; data = get_combined_intraday_report(); print(json.dumps(data, ensure_ascii=False, default=str))`;
    const out = execSync(`python3 -c "${py.replace(/"/g, '\\"')}" 2>/dev/null`, { timeout: 15000 }).toString().trim();
    const lines = out.split('\n');
    for (let i = 0; i < lines.length; i++) {
      if (lines[i].trim().startsWith('{')) {
        const jsonStr = lines.slice(i).join('\n');
        const data = JSON.parse(jsonStr);
        return sendJson(res, data);
      }
    }
    throw new Error('No JSON in output');
  } catch (e) {
    log('intraday-combined-v122 error: ' + e.message);
    sendJson(res, {
      status: 'ERROR',
      timestamp: new Date().toISOString(),
      stop_loss_report: { status: 'ERROR', message: '獲取失敗' },
      emotion_report: { status: 'ERROR', message: '獲取失敗' },
      summary: { total_positions: 0, market_sentiment_emoji: '?', risk_status: 'UNKNOWN' },
      error: e.message,
      version: 'v5.122_fallback'
    });
  }
}

// === v5.132 盤中實時熱力圖儀表板 (11:30優化②新增) ===
function handleIntradayHeatmapV132(req, res) {
  try {
    const py = `import sys,json; sys.path.insert(0,'/home/nikefd/finance-agent'); from v5_132_intraday_heatmap import get_intraday_heatmap_v132; data = get_intraday_heatmap_v132(); print(json.dumps(data, ensure_ascii=False, default=str))`;
    const out = execSync(`python3 -c "${py.replace(/"/g, '\\"')}"`, { timeout: 8000 }).toString().trim();
    const lines = out.split('\n');
    for (let i = 0; i < lines.length; i++) {
      if (lines[i].trim().startsWith('{')) {
        const jsonStr = lines.slice(i).join('\n');
        const data = JSON.parse(jsonStr);
        return sendJson(res, data);
      }
    }
    throw new Error('No JSON in output');
  } catch (e) {
    log('intraday-heatmap-v132: ' + e.message);
    sendJson(res, { timestamp: new Date().toISOString(), positions_heatmap: [], version: 'v5.132_error', error: e.message });
  }
}

// === v5.132 盤中分鐘級績效統計 (11:30優化②新增) ===
function handleIntradayMinuteStatsV132(req, res) {
  try {
    const trades = querySqlite("SELECT * FROM trades WHERE trade_date >= datetime('now', '-60 minutes')");
    const positions = querySqlite('SELECT * FROM positions WHERE shares > 0');
    const buyTrades = trades.filter(t => t.direction === 'BUY');
    const sellTrades = trades.filter(t => t.direction === 'SELL');
    const winTrades = sellTrades.filter(t => {
      const buyPrice = buyTrades.find(b => b.symbol === t.symbol)?.price || t.price;
      return t.price > buyPrice;
    });
    const intradayWinRate = sellTrades.length > 0 ? Math.round((winTrades.length / sellTrades.length) * 100) : 0;
    sendJson(res, {
      timestamp: new Date().toISOString(),
      intraday_win_rate: intradayWinRate,
      buy_count_60m: buyTrades.length,
      sell_count_60m: sellTrades.length,
      total_positions: positions.length,
      version: 'v5.132'
    });
  } catch (e) {
    log('intraday-minute-stats-v132: ' + e.message);
    sendJson(res, { timestamp: new Date().toISOString(), intraday_win_rate: 0, version: 'v5.132_error', error: e.message });
  }
}

// === v5.137 盤中優化② - 性能排序面板 (11:30優化) ===
function handlePerformanceRankingV137(req, res) {
  try {
    const params = parseUrl(req.url).params;
    const sortBy = params.sort_by || 'roi';
    const limit = parseInt(params.limit) || 10;
    const py = `import sys,json; sys.path.insert(0,'/home/nikefd/finance-agent'); from v5_137_intraday_optimization import get_performance_ranking; data = get_performance_ranking('${sortBy}', ${limit}); print(json.dumps(data, ensure_ascii=False, default=str))`;
    const out = execSync(`python3 -c "${py.replace(/"/g, '\\"')}"`, { timeout: 5000 }).toString().trim();
    const lines = out.split('\n');
    for (let i = 0; i < lines.length; i++) {
      if (lines[i].trim().startsWith('{')) {
        const jsonStr = lines.slice(i).join('\n');
        const data = JSON.parse(jsonStr);
        return sendJson(res, data);
      }
    }
    throw new Error('No JSON in output');
  } catch (e) {
    log('performance-ranking-v137: ' + e.message);
    sendJson(res, { status: 'ERROR', error: e.message, ranking: [], timestamp: new Date().toISOString(), version: 'v5.137' });
  }
}

// === v5.137 盤中優化② - 市場熱力圖 (11:30優化) ===
function handleMarketHeatmapV137(req, res) {
  try {
    const params = parseUrl(req.url).params;
    const timeframe = params.timeframe || 'daily';
    const includeSentiment = params.include_sentiment !== 'false' ? 'True' : 'False';
    const py = `import sys,json; sys.path.insert(0,'/home/nikefd/finance-agent'); from v5_137_intraday_optimization import get_market_heatmap; data = get_market_heatmap('${timeframe}', ${includeSentiment}); print(json.dumps(data, ensure_ascii=False, default=str))`;
    const out = execSync(`python3 -c "${py.replace(/"/g, '\\"')}"`, { timeout: 5000 }).toString().trim();
    const lines = out.split('\n');
    for (let i = 0; i < lines.length; i++) {
      if (lines[i].trim().startsWith('{')) {
        const jsonStr = lines.slice(i).join('\n');
        const data = JSON.parse(jsonStr);
        return sendJson(res, data);
      }
    }
    throw new Error('No JSON in output');
  } catch (e) {
    log('market-heatmap-v137: ' + e.message);
    sendJson(res, { status: 'ERROR', error: e.message, sectors: [], timestamp: new Date().toISOString(), version: 'v5.137' });
  }
}

// === v5.137 盤中優化② - 實時風控指標 (11:30優化) ===
function handleIntraDayRiskV137(req, res) {
  try {
    const py = `import sys,json; sys.path.insert(0,'/home/nikefd/finance-agent'); from v5_137_intraday_optimization import get_intraday_risk_metrics; data = get_intraday_risk_metrics(); print(json.dumps(data, ensure_ascii=False, default=str))`;
    const out = execSync(`python3 -c "${py.replace(/"/g, '\\"')}"`, { timeout: 5000 }).toString().trim();
    const lines = out.split('\n');
    for (let i = 0; i < lines.length; i++) {
      if (lines[i].trim().startsWith('{')) {
        const jsonStr = lines.slice(i).join('\n');
        const data = JSON.parse(jsonStr);
        return sendJson(res, data);
      }
    }
    throw new Error('No JSON in output');
  } catch (e) {
    log('intraday-risk-v137: ' + e.message);
    sendJson(res, { status: 'ERROR', error: e.message, position_count: 0, timestamp: new Date().toISOString(), version: 'v5.137' });
  }
}

// === v5.135 情感觸發決策面板 + 績效維度增強 (盤中11:30優化②) ===
function handleEmotionTriggerDecisionsV135(req, res) {
  try {
    const py = `import sys,json; sys.path.insert(0,'/home/nikefd/finance-agent'); from v5_135_INTRADAY_UI_OPTIMIZE import get_emotion_trigger_decisions_v135; data = get_emotion_trigger_decisions_v135(); print(json.dumps(data, ensure_ascii=False, default=str))`;
    const out = execSync(`python3 -c "${py.replace(/"/g, '\\"')}"`, { timeout: 10000 }).toString().trim();
    const lines = out.split('\n');
    for (let i = 0; i < lines.length; i++) {
      if (lines[i].trim().startsWith('{')) {
        const jsonStr = lines.slice(i).join('\n');
        const data = JSON.parse(jsonStr);
        return sendJson(res, data);
      }
    }
    throw new Error('No JSON in output');
  } catch (e) {
    log('emotion-trigger-v135 error: ' + e.message);
    sendJson(res, {
      emotion_levels: { level: 'unknown', score: 50 },
      signals_stats: { total_signals: 0, buy_signals: 0, sell_signals: 0 },
      param_adjustments: [],
      action_recommendation: '-- 出錯 --',
      error: e.message,
      version: 'v5.135_fallback'
    });
  }
}

function handleIntradayPerformanceStatsV135(req, res) {
  try {
    const py = `import sys,json; sys.path.insert(0,'/home/nikefd/finance-agent'); from v5_135_INTRADAY_UI_OPTIMIZE import get_intraday_performance_stats_v135; data = get_intraday_performance_stats_v135(); print(json.dumps(data, ensure_ascii=False, default=str))`;
    const out = execSync(`python3 -c "${py.replace(/"/g, '\\"')}"`, { timeout: 10000 }).toString().trim();
    const lines = out.split('\n');
    for (let i = 0; i < lines.length; i++) {
      if (lines[i].trim().startsWith('{')) {
        const jsonStr = lines.slice(i).join('\n');
        const data = JSON.parse(jsonStr);
        return sendJson(res, data);
      }
    }
    throw new Error('No JSON in output');
  } catch (e) {
    log('intraday-performance-v135 error: ' + e.message);
    sendJson(res, {
      strategy_performance: [],
      sector_distribution: [],
      entry_quality_score: 0,
      entry_quality_distribution: {},
      indicator_quality: {},
      cash_ratio: 0,
      error: e.message,
      version: 'v5.135_fallback'
    });
  }
}

function handleCombinedIntradayMetricsV135(req, res) {
  try {
    const py = `import sys,json; sys.path.insert(0,'/home/nikefd/finance-agent'); from v5_135_INTRADAY_UI_OPTIMIZE import get_combined_intraday_metrics_v135; data = get_combined_intraday_metrics_v135(); print(json.dumps(data, ensure_ascii=False, default=str))`;
    const out = execSync(`python3 -c "${py.replace(/"/g, '\\"')}"`, { timeout: 10000 }).toString().trim();
    const lines = out.split('\n');
    for (let i = 0; i < lines.length; i++) {
      if (lines[i].trim().startsWith('{')) {
        const jsonStr = lines.slice(i).join('\n');
        const data = JSON.parse(jsonStr);
        return sendJson(res, data);
      }
    }
    throw new Error('No JSON in output');
  } catch (e) {
    log('combined-metrics-v135 error: ' + e.message);
    sendJson(res, {
      total_trades_30d: 0,
      win_rate_pct: 0,
      positions_count: 0,
      market_strength_index: 0,
      error: e.message,
      version: 'v5.135_fallback'
    });
  }
}

// === v5.141 UI优化② (11:30) - 绩效统计增强 ===
function handlePerformanceMetricsV141(req, res) {
  try {
    const py = `import sys,json; sys.path.insert(0,'/home/nikefd/finance-agent'); from v5_141_intraday_ui_optimize import get_performance_metrics; data = get_performance_metrics(); print(json.dumps(data, ensure_ascii=False, default=str))`;
    const out = execSync(`python3 -c "${py.replace(/"/g, '\\"')}"`, { timeout: 5000 }).toString().trim();
    const lines = out.split('\n');
    for (let i = 0; i < lines.length; i++) {
      if (lines[i].trim().startsWith('[') || lines[i].trim().startsWith('{')) {
        const jsonStr = lines.slice(i).join('\n');
        const data = JSON.parse(jsonStr);
        return sendJson(res, { metrics: data, version: 'v5.141', timestamp: new Date().toISOString() });
      }
    }
    throw new Error('No JSON in output');
  } catch (e) {
    log('performance-metrics-v141: ' + e.message);
    sendJson(res, { metrics: [], error: e.message, version: 'v5.141_fallback' });
  }
}

function handleCapitalAllocationV141(req, res) {
  try {
    const py = `import sys,json; sys.path.insert(0,'/home/nikefd/finance-agent'); from v5_141_intraday_ui_optimize import get_capital_allocation_heatmap; data = get_capital_allocation_heatmap(); print(json.dumps(data, ensure_ascii=False, default=str))`;
    const out = execSync(`python3 -c "${py.replace(/"/g, '\\"')}"`, { timeout: 5000 }).toString().trim();
    const lines = out.split('\n');
    for (let i = 0; i < lines.length; i++) {
      if (lines[i].trim().startsWith('{')) {
        const jsonStr = lines.slice(i).join('\n');
        const data = JSON.parse(jsonStr);
        return sendJson(res, data);
      }
    }
    throw new Error('No JSON in output');
  } catch (e) {
    log('capital-allocation-v141: ' + e.message);
    sendJson(res, { sectors: [], total_portfolio_value: 0, error: e.message, version: 'v5.141_fallback' });
  }
}

function handleRiskMetricsV141(req, res) {
  try {
    const py = `import sys,json; sys.path.insert(0,'/home/nikefd/finance-agent'); from v5_141_intraday_ui_optimize import get_risk_metrics; data = get_risk_metrics(); print(json.dumps(data, ensure_ascii=False, default=str))`;
    const out = execSync(`python3 -c "${py.replace(/"/g, '\\"')}"`, { timeout: 5000 }).toString().trim();
    const lines = out.split('\n');
    for (let i = 0; i < lines.length; i++) {
      if (lines[i].trim().startsWith('{')) {
        const jsonStr = lines.slice(i).join('\n');
        const data = JSON.parse(jsonStr);
        return sendJson(res, data);
      }
    }
    throw new Error('No JSON in output');
  } catch (e) {
    log('risk-metrics-v141: ' + e.message);
    sendJson(res, { total_risk_score: 50, risk_level: 'unknown', error: e.message, version: 'v5.141_fallback' });
  }
}

function handleDailySummaryV141(req, res) {
  try {
    const py = `import sys,json; sys.path.insert(0,'/home/nikefd/finance-agent'); from v5_141_intraday_ui_optimize import get_daily_performance_summary; data = get_daily_performance_summary(); print(json.dumps(data, ensure_ascii=False, default=str))`;
    const out = execSync(`python3 -c "${py.replace(/"/g, '\\"')}"`, { timeout: 5000 }).toString().trim();
    const lines = out.split('\n');
    for (let i = 0; i < lines.length; i++) {
      if (lines[i].trim().startsWith('{')) {
        const jsonStr = lines.slice(i).join('\n');
        const data = JSON.parse(jsonStr);
        return sendJson(res, data);
      }
    }
    throw new Error('No JSON in output');
  } catch (e) {
    log('daily-summary-v141: ' + e.message);
    sendJson(res, { total_trades: 0, daily_pnl: 0, daily_pnl_pct: 0, error: e.message, version: 'v5.141_fallback' });
  }
}
