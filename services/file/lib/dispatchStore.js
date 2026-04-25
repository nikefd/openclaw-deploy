// services/file/lib/dispatchStore.js
// State machine for /api/chat/send dispatch tracking.
//
// /api/chat/send is fire-and-forget: it kicks off a gateway call then returns
// 202 immediately. The gateway round-trip continues in the background. The
// frontend polls /api/chat/history which reads back this state to know whether
// the dispatch is still pending, completed, or errored.
//
// Status transitions:
//   markPending → 'pending'
//   markDone    → 'done'
//   markError   → 'error'
//
// Storage is shared via global.__chatDispatch so /api/chat/history (still
// inline in server.js for now) can read it. All writes funnel through this
// module so the shape stays consistent.
//
// Pure-ish: side effect is limited to the global map. _reset() is for tests.

'use strict';

function _store() {
  if (!global.__chatDispatch) global.__chatDispatch = {};
  return global.__chatDispatch;
}

function markPending(chatId, { startedAt = Date.now() } = {}) {
  if (!chatId) return null;
  const rec = { status: 'pending', startedAt, error: null, httpStatus: null };
  _store()[chatId] = rec;
  return rec;
}

function markDone(chatId, { httpStatus = null, endedAt = Date.now() } = {}) {
  if (!chatId) return null;
  const rec = _store()[chatId] || {};
  rec.status = 'done';
  rec.httpStatus = httpStatus;
  rec.endedAt = endedAt;
  _store()[chatId] = rec;
  return rec;
}

function markError(chatId, { error = 'unknown', httpStatus = null, endedAt = Date.now() } = {}) {
  if (!chatId) return null;
  const rec = _store()[chatId] || {};
  rec.status = 'error';
  rec.error = error;
  if (httpStatus !== null && httpStatus !== undefined) rec.httpStatus = httpStatus;
  rec.endedAt = endedAt;
  _store()[chatId] = rec;
  return rec;
}

function get(chatId) {
  if (!chatId) return null;
  return _store()[chatId] || null;
}

function _reset() {
  global.__chatDispatch = {};
}

module.exports = {
  markPending,
  markDone,
  markError,
  get,
  _reset,
};
