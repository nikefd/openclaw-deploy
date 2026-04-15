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

  sendJson(res, {
    max_drawdown: Math.round(maxDD * 100) / 100,
    sharpe_ratio: Math.round(sharpe * 100) / 100,
    win_rate: Math.round(winRate * 10) / 10,
    total_trades: totalSells,
    wins, losses,
    loss_streak: lossStreak,
    trading_days: totalDays,
    total_return: Math.round(totalReturn * 100) / 100,
    daily_volatility: Math.round(stdRet * 10000) / 100, // as percentage
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

    // /api/finance/reports/:date
    const reportMatch = pathname.match(/^\/api\/finance\/reports\/(\d{4}-\d{2}-\d{2})$/);
    if (reportMatch && req.method === 'GET') return handleReportDetail(req, res, reportMatch[1]);

    sendError(res, 'Not Found', 404);
  } catch (e) {
    log(`Error: ${e.message}`);
    sendError(res, e.message);
  }
});

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
