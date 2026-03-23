const http = require('http');
const fs = require('fs');
const path = require('path');
const os = require('os');

const AGENTS_DIR = path.join(os.homedir(), '.openclaw/agents');
const PORT = 7684;

// Model pricing per 1M tokens (USD)
const PRICING = {
  'claude-opus-4': { input: 15, output: 75, cacheRead: 1.5, cacheWrite: 18.75 },
  'claude-sonnet-4': { input: 3, output: 15, cacheRead: 0.3, cacheWrite: 3.75 },
  'claude-3.5-sonnet': { input: 3, output: 15, cacheRead: 0.3, cacheWrite: 3.75 },
  'claude-3-opus': { input: 15, output: 75, cacheRead: 1.5, cacheWrite: 18.75 },
  'gpt-4o': { input: 2.5, output: 10, cacheRead: 1.25, cacheWrite: 2.5 },
  'gpt-4o-mini': { input: 0.15, output: 0.6, cacheRead: 0.075, cacheWrite: 0.15 },
  'o3': { input: 10, output: 40, cacheRead: 2.5, cacheWrite: 10 },
  'default': { input: 3, output: 15, cacheRead: 0.3, cacheWrite: 3.75 },
};

function getPrice(modelId) {
  if (!modelId) return PRICING['default'];
  const lower = modelId.toLowerCase();
  for (const [key, val] of Object.entries(PRICING)) {
    if (lower.includes(key)) return val;
  }
  return PRICING['default'];
}

function calcCost(usage, pricing) {
  return (
    (usage.input * pricing.input +
      usage.output * pricing.output +
      usage.cacheRead * pricing.cacheRead +
      usage.cacheWrite * pricing.cacheWrite) / 1_000_000
  );
}

let cache = { data: null, ts: 0 };
const CACHE_TTL = 30_000; // 30s

async function aggregateUsage() {
  if (cache.data && Date.now() - cache.ts < CACHE_TTL) return cache.data;

  const agentDirs = fs.readdirSync(AGENTS_DIR).filter(d => {
    const sp = path.join(AGENTS_DIR, d, 'sessions');
    try { return fs.statSync(sp).isDirectory(); } catch { return false; }
  });
  const daily = {};
  const models = {};
  const agents = {}; // agent -> { input, output, ... }
  let totalInput = 0, totalOutput = 0, totalCacheRead = 0, totalCacheWrite = 0, totalCost = 0;
  let sessionCount = 0;

  for (const agent of agentDirs) {
    const sessDir = path.join(AGENTS_DIR, agent, 'sessions');
    const files = fs.readdirSync(sessDir).filter(f => f.endsWith('.jsonl'));

  for (const file of files) {
    const fp = path.join(sessDir, file);
    let content;
    try { content = fs.readFileSync(fp, 'utf-8'); } catch { continue; }

    let sInput = 0, sOutput = 0, sCR = 0, sCW = 0, model = '', firstTs = '';
    const lines = content.split('\n').filter(Boolean);

    for (const line of lines) {
      let d;
      try { d = JSON.parse(line); } catch { continue; }

      if (d.modelId) model = d.modelId;
      if (!firstTs && d.timestamp) firstTs = d.timestamp;

      const msg = d.message || {};
      const u = msg.usage || d.usage;
      if (u && typeof u.input === 'number') {
        sInput += u.input || 0;
        sOutput += u.output || 0;
        sCR += u.cacheRead || 0;
        sCW += u.cacheWrite || 0;
      }
    }

    if (sInput + sOutput + sCR + sCW === 0) continue;
    sessionCount++;

    const pricing = getPrice(model);
    const sCost = calcCost({ input: sInput, output: sOutput, cacheRead: sCR, cacheWrite: sCW }, pricing);

    totalInput += sInput; totalOutput += sOutput; totalCacheRead += sCR; totalCacheWrite += sCW; totalCost += sCost;

    // Daily aggregation
    const date = firstTs ? firstTs.slice(0, 10) : 'unknown';
    if (!daily[date]) daily[date] = { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, cost: 0, sessions: 0 };
    daily[date].input += sInput;
    daily[date].output += sOutput;
    daily[date].cacheRead += sCR;
    daily[date].cacheWrite += sCW;
    daily[date].cost += sCost;
    daily[date].sessions++;

    // Model aggregation
    const mKey = model || 'unknown';
    if (!models[mKey]) models[mKey] = { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, cost: 0, sessions: 0 };
    models[mKey].input += sInput;
    models[mKey].output += sOutput;
    models[mKey].cacheRead += sCR;
    models[mKey].cacheWrite += sCW;
    models[mKey].cost += sCost;
    models[mKey].sessions++;

    // Agent aggregation
    if (!agents[agent]) agents[agent] = { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, cost: 0, sessions: 0 };
    agents[agent].input += sInput;
    agents[agent].output += sOutput;
    agents[agent].cacheRead += sCR;
    agents[agent].cacheWrite += sCW;
    agents[agent].cost += sCost;
    agents[agent].sessions++;
  }
  } // end agentDirs loop

  const result = {
    summary: {
      totalInput, totalOutput, totalCacheRead, totalCacheWrite,
      totalTokens: totalInput + totalOutput + totalCacheRead + totalCacheWrite,
      estimatedCost: Math.round(totalCost * 10000) / 10000,
      sessionCount,
      note: 'Cost is estimated based on standard API pricing. github-copilot tokens may be included in your subscription.'
    },
    daily: Object.entries(daily).sort(([a], [b]) => a.localeCompare(b)).map(([date, d]) => ({
      date, ...d, cost: Math.round(d.cost * 10000) / 10000
    })),
    models: Object.entries(models).sort(([, a], [, b]) => (b.input + b.output) - (a.input + a.output)).map(([model, d]) => ({
      model, ...d, cost: Math.round(d.cost * 10000) / 10000
    })),
    agents: Object.entries(agents).sort(([, a], [, b]) => (b.input + b.output) - (a.input + a.output)).map(([agent, d]) => ({
      agent, ...d, cost: Math.round(d.cost * 10000) / 10000
    })),
    pricing: PRICING,
    generatedAt: new Date().toISOString()
  };

  cache = { data: result, ts: Date.now() };
  return result;
}

const server = http.createServer(async (req, res) => {
  // CORS
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Cookie');

  if (req.method === 'OPTIONS') { res.writeHead(204); res.end(); return; }

  if (req.url === '/api/usage' && req.method === 'GET') {
    try {
      const data = await aggregateUsage();
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(data));
    } catch (e) {
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: e.message }));
    }
  } else {
    res.writeHead(404); res.end('Not found');
  }
});

server.listen(PORT, '127.0.0.1', () => {
  console.log(`Usage API running on http://127.0.0.1:${PORT}`);
});
