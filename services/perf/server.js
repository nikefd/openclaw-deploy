const http = require('http');
const fs = require('fs');
const path = require('path');

const PORT = 7687;
const LOG_DIR = '/home/nikefd/perf-logs';
const LOG_FILE = () => path.join(LOG_DIR, `perf-${new Date().toISOString().slice(0,10)}.jsonl`);

if (!fs.existsSync(LOG_DIR)) fs.mkdirSync(LOG_DIR, { recursive: true });

function cors(res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
}

const server = http.createServer((req, res) => {
  cors(res);
  if (req.method === 'OPTIONS') { res.writeHead(204); res.end(); return; }

  const url = new URL(req.url, `http://localhost:${PORT}`);

  // POST /api/perf/log — record a perf entry
  if (req.method === 'POST' && url.pathname === '/api/perf/log') {
    let body = '';
    req.on('data', c => body += c);
    req.on('end', () => {
      try {
        const entry = JSON.parse(body);
        entry._ts = Date.now();
        fs.appendFileSync(LOG_FILE(), JSON.stringify(entry) + '\n');
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end('{"ok":true}');
      } catch (e) {
        res.writeHead(400); res.end('{"error":"invalid json"}');
      }
    });
    return;
  }

  // GET /api/perf/logs — get recent logs
  if (req.method === 'GET' && url.pathname === '/api/perf/logs') {
    const days = parseInt(url.searchParams.get('days') || '7');
    const entries = [];
    const now = Date.now();
    for (let d = 0; d < days; d++) {
      const date = new Date(now - d * 86400000).toISOString().slice(0,10);
      const file = path.join(LOG_DIR, `perf-${date}.jsonl`);
      if (fs.existsSync(file)) {
        const lines = fs.readFileSync(file, 'utf-8').trim().split('\n').filter(Boolean);
        for (const line of lines) {
          try { entries.push(JSON.parse(line)); } catch {}
        }
      }
    }
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(entries));
    return;
  }

  // GET /api/perf/stats — aggregated stats
  if (req.method === 'GET' && url.pathname === '/api/perf/stats') {
    const days = parseInt(url.searchParams.get('days') || '7');
    const entries = [];
    const now = Date.now();
    for (let d = 0; d < days; d++) {
      const date = new Date(now - d * 86400000).toISOString().slice(0,10);
      const file = path.join(LOG_DIR, `perf-${date}.jsonl`);
      if (fs.existsSync(file)) {
        const lines = fs.readFileSync(file, 'utf-8').trim().split('\n').filter(Boolean);
        for (const line of lines) {
          try { entries.push(JSON.parse(line)); } catch {}
        }
      }
    }

    // Compute stats
    const byType = {};
    for (const e of entries) {
      const t = e.type || 'unknown';
      if (!byType[t]) byType[t] = { count: 0, totalMs: 0, min: Infinity, max: 0, values: [] };
      const dur = e.durationMs || 0;
      byType[t].count++;
      byType[t].totalMs += dur;
      byType[t].min = Math.min(byType[t].min, dur);
      byType[t].max = Math.max(byType[t].max, dur);
      byType[t].values.push(dur);
    }

    for (const k in byType) {
      const s = byType[k];
      s.avg = Math.round(s.totalMs / s.count);
      s.values.sort((a,b) => a - b);
      s.p50 = s.values[Math.floor(s.values.length * 0.5)] || 0;
      s.p95 = s.values[Math.floor(s.values.length * 0.95)] || 0;
      s.p99 = s.values[Math.floor(s.values.length * 0.99)] || 0;
      if (s.min === Infinity) s.min = 0;
      delete s.values;
    }

    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ totalEntries: entries.length, byType, days }));
    return;
  }

  res.writeHead(404); res.end('not found');
});

server.listen(PORT, '127.0.0.1', () => {
  console.log(`Perf API listening on :${PORT}`);
});
