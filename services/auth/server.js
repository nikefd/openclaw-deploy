const http = require('http');
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

const COOKIE_SECRET = 'e2014d2b4042fb98de33a5f5cae1abbb8bd8657b74b2bc7cdf2b18e1faa19fd8';
const TOTP_SECRET_B32 = 'R7QSQGEENL655V4YK7DSUFUHO4GPXMNJ';
const TOTP_ISSUER = 'OpenClaw';
const TOTP_ACCOUNT = 'nikefd';

// --- Demo codes storage ---
const DEMO_CODES_FILE = path.join(__dirname, 'demo-codes.json');
function loadDemoCodes() {
  try { return JSON.parse(fs.readFileSync(DEMO_CODES_FILE, 'utf8')); } catch { return []; }
}
function saveDemoCodes(codes) {
  fs.writeFileSync(DEMO_CODES_FILE, JSON.stringify(codes, null, 2));
}

// --- Base32 decode ---
function base32Decode(str) {
  const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';
  let bits = '';
  for (const c of str.toUpperCase()) {
    const val = alphabet.indexOf(c);
    if (val === -1) continue;
    bits += val.toString(2).padStart(5, '0');
  }
  const bytes = [];
  for (let i = 0; i + 8 <= bits.length; i += 8) {
    bytes.push(parseInt(bits.slice(i, i + 8), 2));
  }
  return Buffer.from(bytes);
}

// --- TOTP ---
function generateTOTP(secretB32, time = Date.now()) {
  const key = base32Decode(secretB32);
  const counter = Math.floor(time / 1000 / 30);
  const buf = Buffer.alloc(8);
  buf.writeUInt32BE(Math.floor(counter / 0x100000000), 0);
  buf.writeUInt32BE(counter & 0xffffffff, 4);
  const hmac = crypto.createHmac('sha1', key).update(buf).digest();
  const offset = hmac[hmac.length - 1] & 0xf;
  const code = ((hmac[offset] & 0x7f) << 24 | hmac[offset + 1] << 16 | hmac[offset + 2] << 8 | hmac[offset + 3]) % 1000000;
  return code.toString().padStart(6, '0');
}

function verifyTOTP(token, secretB32) {
  const now = Date.now();
  for (const offset of [0, -30000, 30000]) {
    if (generateTOTP(secretB32, now + offset) === token) return true;
  }
  return false;
}

// --- Cookie auth ---
function sign(data) { return crypto.createHmac('sha256', COOKIE_SECRET).update(data).digest('hex'); }
function makeCookie(user) {
  const exp = Date.now() + 86400000 * 7;
  const payload = user + ':' + exp;
  return payload + ':' + sign(payload);
}
function verifyCookie(c) {
  if (!c) return false;
  const parts = c.split(':');
  if (parts.length !== 3) return false;
  const [user, exp, sig] = parts;
  if (Date.now() > parseInt(exp)) return false;
  return sign(user + ':' + exp) === sig;
}

// --- Demo cookie ---
function makeDemoCookie(code, durationMs) {
  const exp = Date.now() + durationMs;
  const payload = 'demo:' + code + ':' + exp;
  return payload + ':' + sign(payload);
}
function verifyDemoCookie(c) {
  if (!c) return false;
  const parts = c.split(':');
  if (parts.length !== 4) return false;
  const [prefix, code, exp, sig] = parts;
  if (prefix !== 'demo') return false;
  if (Date.now() > parseInt(exp)) return false;
  return sign('demo:' + code + ':' + exp) === sig;
}

// --- Helpers ---
function parseCookies(header) {
  return (header || '').split(';').reduce((a, c) => {
    const eq = c.indexOf('=');
    if (eq > 0) a[c.slice(0, eq).trim()] = c.slice(eq + 1).trim();
    return a;
  }, {});
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    let body = '';
    req.on('data', d => body += d);
    req.on('end', () => { try { resolve(JSON.parse(body)); } catch (e) { reject(e); } });
    req.on('error', reject);
  });
}

function json(res, status, data) {
  res.writeHead(status, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify(data));
}

function generateCode() {
  // 6-char alphanumeric, easy to type
  const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'; // no I/O/0/1
  let code = '';
  for (let i = 0; i < 6; i++) code += chars[crypto.randomInt(chars.length)];
  return code;
}

// --- Server ---
http.createServer(async (req, res) => {
  const url = new URL(req.url, 'http://localhost');
  const cookies = parseCookies(req.headers.cookie);

  // === Admin auth verify ===
  if (url.pathname === '/auth/verify') {
    if (verifyCookie(cookies.oc_session)) {
      res.writeHead(200); res.end('ok');
    } else {
      res.writeHead(401); res.end('unauthorized');
    }
    return;
  }

  // === Demo auth verify (for nginx sub-request) ===
  if (url.pathname === '/auth/demo-verify') {
    // Allow if admin OR has valid demo cookie
    if (verifyCookie(cookies.oc_session) || verifyDemoCookie(cookies.oc_demo)) {
      res.writeHead(200); res.end('ok');
    } else {
      res.writeHead(401); res.end('unauthorized');
    }
    return;
  }

  // === Admin login (TOTP) ===
  if (url.pathname === '/auth/login' && req.method === 'POST') {
    try {
      const { code } = await readBody(req);
      const token = String(code || '').replace(/\s/g, '');
      if (token.length === 6 && verifyTOTP(token, TOTP_SECRET_B32)) {
        const cookie = makeCookie(TOTP_ACCOUNT);
        res.writeHead(200, {
          'Content-Type': 'application/json',
          'Set-Cookie': 'oc_session=' + cookie + '; Path=/; HttpOnly; SameSite=Strict; Secure; Max-Age=604800'
        });
        res.end(JSON.stringify({ ok: true }));
      } else {
        json(res, 401, { error: 'invalid code' });
      }
    } catch (e) {
      json(res, 400, { error: 'bad request' });
    }
    return;
  }

  // === Demo login (access code) ===
  if (url.pathname === '/auth/demo-login' && req.method === 'POST') {
    try {
      const { code } = await readBody(req);
      const inputCode = String(code || '').trim().toUpperCase();
      const codes = loadDemoCodes();
      const now = Date.now();
      const entry = codes.find(c => c.code === inputCode && c.expiresAt > now);
      if (entry) {
        // Duration = remaining time of the code, capped by the code's accessDuration
        const remaining = entry.expiresAt - now;
        const duration = Math.min(entry.accessDurationMs || remaining, remaining);
        const cookie = makeDemoCookie(inputCode, duration);
        const maxAge = Math.ceil(duration / 1000);
        // Track usage
        entry.usedCount = (entry.usedCount || 0) + 1;
        entry.lastUsedAt = now;
        saveDemoCodes(codes);
        res.writeHead(200, {
          'Content-Type': 'application/json',
          'Set-Cookie': 'oc_demo=' + cookie + '; Path=/demos; HttpOnly; SameSite=Strict; Secure; Max-Age=' + maxAge
        });
        res.end(JSON.stringify({ ok: true, expiresIn: duration, label: entry.label }));
      } else {
        json(res, 401, { error: '无效或已过期的访问码' });
      }
    } catch (e) {
      json(res, 400, { error: 'bad request' });
    }
    return;
  }

  // === Admin logout ===
  if (url.pathname === '/auth/logout') {
    res.writeHead(200, {
      'Content-Type': 'application/json',
      'Set-Cookie': 'oc_session=; Path=/; HttpOnly; SameSite=Strict; Secure; Max-Age=0'
    });
    res.end(JSON.stringify({ ok: true }));
    return;
  }

  // === Demo codes CRUD (admin only) ===
  if (url.pathname === '/auth/demo-codes') {
    if (!verifyCookie(cookies.oc_session)) {
      json(res, 401, { error: 'unauthorized' });
      return;
    }

    if (req.method === 'GET') {
      // List all codes
      const codes = loadDemoCodes();
      json(res, 200, codes);
      return;
    }

    if (req.method === 'POST') {
      // Create new code
      try {
        const body = await readBody(req);
        const label = body.label || '';
        const durationHours = body.durationHours || 24; // code validity
        const accessDurationHours = body.accessDurationHours || durationHours; // session duration after redeem
        const code = generateCode();
        const entry = {
          code,
          label,
          createdAt: Date.now(),
          expiresAt: Date.now() + durationHours * 3600000,
          accessDurationMs: accessDurationHours * 3600000,
          usedCount: 0,
          lastUsedAt: null,
        };
        const codes = loadDemoCodes();
        codes.push(entry);
        saveDemoCodes(codes);
        json(res, 200, entry);
      } catch (e) {
        json(res, 400, { error: 'bad request' });
      }
      return;
    }

    if (req.method === 'DELETE') {
      // Delete a code
      const codeToDelete = url.searchParams.get('code');
      if (!codeToDelete) { json(res, 400, { error: 'missing code param' }); return; }
      let codes = loadDemoCodes();
      codes = codes.filter(c => c.code !== codeToDelete.toUpperCase());
      saveDemoCodes(codes);
      json(res, 200, { ok: true });
      return;
    }
  }

  res.writeHead(404); res.end('not found');
}).listen(7683, '127.0.0.1', () => console.log('Auth server on :7683'));
