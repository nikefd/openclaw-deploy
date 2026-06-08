const http = require('http');
const crypto = require('crypto');

const COOKIE_SECRET = 'e2014d2b4042fb98de33a5f5cae1abbb8bd8657b74b2bc7cdf2b18e1faa19fd8';
const TOTP_SECRET_B32 = 'R7QSQGEENL655V4YK7DSUFUHO4GPXMNJ';
const TOTP_ISSUER = 'OpenClaw';
const TOTP_ACCOUNT = 'nikefd';

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

  // === Admin logout ===
  if (url.pathname === '/auth/logout') {
    res.writeHead(200, {
      'Content-Type': 'application/json',
      'Set-Cookie': 'oc_session=; Path=/; HttpOnly; SameSite=Strict; Secure; Max-Age=0'
    });
    res.end(JSON.stringify({ ok: true }));
    return;
  }

  res.writeHead(404); res.end('not found');
}).listen(7683, '127.0.0.1', () => console.log('Auth server on :7683'));
