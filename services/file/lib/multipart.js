// services/file/lib/multipart.js
// Tiny multipart/form-data parser, split into pure helpers so we can test each
// piece without touching fs or HTTP.
//
// Functions:
//   getBoundary(contentType)
//     'multipart/form-data; boundary=xxx' → 'xxx' (or null on miss)
//   splitParts(buf, boundary)
//     Buffer + boundary string → array of part Buffers (each excludes the
//     boundary lines themselves). Trailing closing boundary is ignored.
//   parsePartHeaders(headerStr)
//     Header block string → {filename, field, contentType}
//   stripTrailingCrlf(buf)
//     Buffer → Buffer with trailing \r\n removed if present.
//   sanitizeFilename(name)
//     Allow [a-zA-Z0-9._-] + CJK, replace others with '_'.
//   makeUniqueName(filename, now)
//     Inject timestamp before extension to avoid collisions.
//   parseMultipart(buf, boundary)
//     Convenience: full pipeline → array of {field, filename, contentType, body}.
//
// All pure: no fs, no time (caller passes `now` to makeUniqueName).

'use strict';

function getBoundary(contentType) {
  if (typeof contentType !== 'string') return null;
  const m = contentType.match(/boundary=(.+)$/);
  return m ? m[1].replace(/^"(.*)"$/, '$1').trim() : null;
}

function splitParts(buf, boundary) {
  if (!Buffer.isBuffer(buf) || !boundary) return [];
  const bBuf = Buffer.from('--' + boundary);
  const parts = [];
  let start = 0;
  while (true) {
    const idx = buf.indexOf(bBuf, start);
    if (idx === -1) break;
    if (start > 0) {
      // The bytes between previous boundary end and this boundary start.
      // -2 trims the trailing \r\n that precedes the boundary line.
      const end = idx - 2 >= start ? idx - 2 : idx;
      parts.push(buf.slice(start, end));
    }
    start = idx + bBuf.length + 2; // skip boundary + \r\n
  }
  return parts;
}

function parsePartHeaders(headerStr) {
  const out = { field: null, filename: null, contentType: null };
  if (typeof headerStr !== 'string') return out;
  const fn = headerStr.match(/filename="([^"]*)"/);
  if (fn) out.filename = fn[1];
  const fld = headerStr.match(/name="([^"]+)"/);
  if (fld) out.field = fld[1];
  const ct = headerStr.match(/Content-Type:\s*([^\r\n]+)/i);
  if (ct) out.contentType = ct[1].trim();
  return out;
}

function stripTrailingCrlf(buf) {
  if (!Buffer.isBuffer(buf)) return buf;
  if (buf.length >= 2 && buf[buf.length - 2] === 13 && buf[buf.length - 1] === 10) {
    return buf.slice(0, buf.length - 2);
  }
  return buf;
}

function sanitizeFilename(name) {
  return String(name || '').replace(/[^a-zA-Z0-9._\-\u4e00-\u9fff]/g, '_');
}

function makeUniqueName(filename, now = Date.now()) {
  const sanitized = sanitizeFilename(filename);
  // path.extname-equivalent without bringing in path module (keep this pure)
  const dot = sanitized.lastIndexOf('.');
  const hasExt = dot > 0 && dot < sanitized.length - 1;
  const ext = hasExt ? sanitized.slice(dot) : '';
  const base = hasExt ? sanitized.slice(0, dot) : sanitized;
  return base + '_' + now + ext;
}

// Full pipeline: parse a multipart body into structured parts that contain
// file content. Non-file fields (no filename) are skipped.
function parseMultipart(buf, boundary) {
  if (!boundary) return [];
  const raw = splitParts(buf, boundary);
  const out = [];
  for (const part of raw) {
    const headerEnd = part.indexOf('\r\n\r\n');
    if (headerEnd === -1) continue;
    const headerStr = part.slice(0, headerEnd).toString();
    const body = stripTrailingCrlf(part.slice(headerEnd + 4));
    const meta = parsePartHeaders(headerStr);
    if (!meta.filename) continue; // skip non-file fields
    out.push({ ...meta, body });
  }
  return out;
}

module.exports = {
  getBoundary,
  splitParts,
  parsePartHeaders,
  stripTrailingCrlf,
  sanitizeFilename,
  makeUniqueName,
  parseMultipart,
};
