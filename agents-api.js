const http = require('http');
const fs = require('fs');
const path = require('path');
const os = require('os');
const { URL } = require('url');

const PORT = 7685;
const DATA_DIR = path.join(os.homedir(), 'agent-data');

// ─── AI News Agent ───
const AI_NEWS_DIR = path.join(DATA_DIR, 'ai-news');
const AI_NEWS_FILE = path.join(AI_NEWS_DIR, 'articles.json');

function loadNews() {
  try { return JSON.parse(fs.readFileSync(AI_NEWS_FILE, 'utf-8')); }
  catch { return []; }
}
function saveNews(data) {
  fs.mkdirSync(AI_NEWS_DIR, { recursive: true });
  fs.writeFileSync(AI_NEWS_FILE, JSON.stringify(data, null, 2));
}

// ─── Fitness Agent ───
const FITNESS_DIR = path.join(DATA_DIR, 'fitness');
const FITNESS_LOG_FILE = path.join(FITNESS_DIR, 'logs.json');
const FITNESS_PROFILE_FILE = path.join(FITNESS_DIR, 'profile.json');
const FITNESS_CHAT_FILE = path.join(FITNESS_DIR, 'chats.json');

function loadFitnessLogs() {
  try { return JSON.parse(fs.readFileSync(FITNESS_LOG_FILE, 'utf-8')); }
  catch { return []; }
}
function saveFitnessLogs(data) {
  fs.mkdirSync(FITNESS_DIR, { recursive: true });
  fs.writeFileSync(FITNESS_LOG_FILE, JSON.stringify(data, null, 2));
}
function loadFitnessProfile() {
  try { return JSON.parse(fs.readFileSync(FITNESS_PROFILE_FILE, 'utf-8')); }
  catch { return { climbingGrade: '', goals: '', notes: '' }; }
}
function saveFitnessProfile(data) {
  fs.mkdirSync(FITNESS_DIR, { recursive: true });
  fs.writeFileSync(FITNESS_PROFILE_FILE, JSON.stringify(data, null, 2));
}
function loadFitnessChats() {
  try { return JSON.parse(fs.readFileSync(FITNESS_CHAT_FILE, 'utf-8')); }
  catch { return []; }
}
function saveFitnessChats(data) {
  fs.mkdirSync(FITNESS_DIR, { recursive: true });
  fs.writeFileSync(FITNESS_CHAT_FILE, JSON.stringify(data, null, 2));
}

// ─── Helpers ───
function readBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    req.on('data', c => chunks.push(c));
    req.on('end', () => { try { resolve(JSON.parse(Buffer.concat(chunks).toString())); } catch(e) { reject(e); } });
    req.on('error', reject);
  });
}

function json(res, data, status = 200) {
  res.writeHead(status, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' });
  res.end(JSON.stringify(data));
}

// ─── Server ───
const server = http.createServer(async (req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  if (req.method === 'OPTIONS') { res.writeHead(204); res.end(); return; }

  const url = new URL(req.url, `http://127.0.0.1:${PORT}`);
  const p = url.pathname;

  try {
    // ─── AI News ───
    if (p === '/api/agents/ai-news/articles' && req.method === 'GET') {
      return json(res, loadNews());
    }
    if (p === '/api/agents/ai-news/articles' && req.method === 'POST') {
      // Add or replace articles (from cron or manual trigger)
      const body = await readBody(req);
      // body: { articles: [...], mode: 'append' | 'replace' }
      let current = loadNews();
      if (body.mode === 'replace') {
        current = body.articles || [];
      } else {
        // append, dedupe by title
        const existing = new Set(current.map(a => a.title));
        for (const a of (body.articles || [])) {
          if (!existing.has(a.title)) { current.unshift(a); existing.add(a.title); }
        }
      }
      // Keep max 200 articles
      if (current.length > 200) current = current.slice(0, 200);
      saveNews(current);
      return json(res, { ok: true, count: current.length });
    }
    if (p === '/api/agents/ai-news/articles' && req.method === 'DELETE') {
      // Delete by id
      const body = await readBody(req);
      let current = loadNews();
      current = current.filter(a => a.id !== body.id);
      saveNews(current);
      return json(res, { ok: true });
    }
    if (p === '/api/agents/ai-news/pin' && req.method === 'POST') {
      const body = await readBody(req);
      let current = loadNews();
      const a = current.find(x => x.id === body.id);
      if (a) a.pinned = !a.pinned;
      saveNews(current);
      return json(res, { ok: true });
    }

    // ─── Fitness ───
    if (p === '/api/agents/fitness/profile' && req.method === 'GET') {
      return json(res, loadFitnessProfile());
    }
    if (p === '/api/agents/fitness/profile' && req.method === 'POST') {
      const body = await readBody(req);
      saveFitnessProfile(body);
      return json(res, { ok: true });
    }
    if (p === '/api/agents/fitness/logs' && req.method === 'GET') {
      return json(res, loadFitnessLogs());
    }
    if (p === '/api/agents/fitness/logs' && req.method === 'POST') {
      const body = await readBody(req);
      const logs = loadFitnessLogs();
      body.id = Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
      body.createdAt = new Date().toISOString();
      logs.unshift(body);
      if (logs.length > 500) logs.length = 500;
      saveFitnessLogs(logs);
      return json(res, { ok: true, log: body });
    }
    if (p === '/api/agents/fitness/logs' && req.method === 'DELETE') {
      const body = await readBody(req);
      let logs = loadFitnessLogs();
      logs = logs.filter(l => l.id !== body.id);
      saveFitnessLogs(logs);
      return json(res, { ok: true });
    }
    if (p === '/api/agents/fitness/chats' && req.method === 'GET') {
      return json(res, loadFitnessChats());
    }
    if (p === '/api/agents/fitness/chats' && req.method === 'POST') {
      const body = await readBody(req);
      const chats = loadFitnessChats();
      chats.push({ role: 'user', content: body.message, ts: new Date().toISOString() });
      if (chats.length > 200) chats.splice(0, chats.length - 200);
      saveFitnessChats(chats);
      return json(res, { ok: true });
    }
    if (p === '/api/agents/fitness/chats/reply' && req.method === 'POST') {
      const body = await readBody(req);
      const chats = loadFitnessChats();
      chats.push({ role: 'assistant', content: body.message, ts: new Date().toISOString() });
      saveFitnessChats(chats);
      return json(res, { ok: true });
    }

    res.writeHead(404); res.end('Not found');
  } catch(e) {
    json(res, { error: e.message }, 500);
  }
});

server.listen(PORT, '127.0.0.1', () => console.log(`Agents API on http://127.0.0.1:${PORT}`));
