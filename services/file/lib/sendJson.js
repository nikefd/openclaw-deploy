// services/file/lib/sendJson.js
// JSON response writer with optional gzip (>1 KiB + accept-encoding).
// Pure on input → side-effect only on res. The compression decision is
// extracted as a separate pure helper for unit-testability.

'use strict';

const zlib = require('zlib');

const GZIP_THRESHOLD = 1024;

// Pure: decide whether to gzip based on accept-encoding + body size.
function shouldGzip(acceptEncoding, bodyLength) {
  if (!Number.isFinite(bodyLength) || bodyLength <= GZIP_THRESHOLD) return false;
  const ae = String(acceptEncoding || '');
  return /\bgzip\b/.test(ae);
}

function sendJson(req, res, obj) {
  const body = typeof obj === 'string' ? obj : JSON.stringify(obj);
  if (shouldGzip(req.headers['accept-encoding'], body.length)) {
    zlib.gzip(body, (err, buf) => {
      if (err) { res.end(body); return; }
      res.setHeader('Content-Encoding', 'gzip');
      res.setHeader('Vary', 'Accept-Encoding');
      res.end(buf);
    });
  } else {
    res.end(body);
  }
}

module.exports = { sendJson, shouldGzip, GZIP_THRESHOLD };
