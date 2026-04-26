// tests/unit/streamPollLoop.test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  decodePollResponse,
  shouldFinish,
  computeTypewriterBatch,
  nextPumpDelay,
} from '../../web/src/ui/streamPollLoop.js';

// ── decodePollResponse ─────────────────────────────────────────

test('decodePollResponse: dispatch error → status=error', () => {
  const r=decodePollResponse(
    {dispatch:{status:'error',error:'boom'},text:'',ts:''},
    'old','old',
  );
  assert.equal(r.status,'error');
  assert.equal(r.errMsg,'boom');
});

test('decodePollResponse: dispatch error w/o message → fallback "unknown"', () => {
  const r=decodePollResponse({dispatch:{status:'error'}},'','');
  assert.equal(r.errMsg,'unknown');
});

test('decodePollResponse: text unchanged + ts unchanged → idle', () => {
  const r=decodePollResponse(
    {text:'old',ts:'t1'},
    't1','old',
  );
  assert.equal(r.status,'idle');
});

test('decodePollResponse: ts changed → progress', () => {
  const r=decodePollResponse(
    {text:'new content',ts:'t2'},
    't1','',
  );
  assert.equal(r.status,'progress');
  assert.equal(r.text,'new content');
  assert.equal(r.ts,'t2');
});

test('decodePollResponse: text changed (same ts) → progress (流式更新同一条)', () => {
  const r=decodePollResponse(
    {text:'longer text',ts:'t1'},
    't1','partial',
  );
  assert.equal(r.status,'progress');
});

test('decodePollResponse: dispatch done + idle within 15s → idle', () => {
  const r=decodePollResponse(
    {text:'',ts:'',dispatch:{status:'done',endedAt:1000}},
    '','',
    {now:5000,timeoutMs:15000},
  );
  assert.equal(r.status,'idle');
});

test('decodePollResponse: dispatch done + idle past timeout → timeout', () => {
  const r=decodePollResponse(
    {text:'',ts:'',dispatch:{status:'done',endedAt:1000}},
    '','',
    {now:20000,timeoutMs:15000},
  );
  assert.equal(r.status,'timeout');
});

test('decodePollResponse: timeout uses default 15_000', () => {
  const r=decodePollResponse(
    {text:'',ts:'',dispatch:{status:'done',endedAt:0}},
    '','',
    {now:16_000},
  );
  assert.equal(r.status,'timeout');
});

test('decodePollResponse: missing dispatch → idle if no new', () => {
  const r=decodePollResponse({text:'',ts:''},'','');
  assert.equal(r.status,'idle');
});

test('decodePollResponse: malformed input → safe defaults', () => {
  const r=decodePollResponse({},'','');
  assert.equal(r.status,'idle');
  assert.equal(r.text,'');
  assert.equal(r.ts,'');
});

// ── shouldFinish ───────────────────────────────────────────────

test('shouldFinish: empty text always false', () => {
  assert.equal(shouldFinish({stopReason:'stop',text:'',stable:10}),false);
  assert.equal(shouldFinish({text:''}),false);
});

test('shouldFinish: stopReason=stop + text → true', () => {
  assert.equal(shouldFinish({stopReason:'stop',text:'hi',stable:0}),true);
});

test('shouldFinish: stopReason=inFlight → false (still streaming)', () => {
  assert.equal(shouldFinish({stopReason:'inFlight',text:'hi',stable:0}),false);
});

test('shouldFinish: stopReason=streaming → false', () => {
  assert.equal(shouldFinish({stopReason:'streaming',text:'hi',stable:0}),false);
});

test('shouldFinish: stable >= 6 (default) + text → true', () => {
  assert.equal(shouldFinish({stable:6,text:'hi'}),true);
  assert.equal(shouldFinish({stable:5,text:'hi'}),false);
});

test('shouldFinish: custom stableThreshold', () => {
  assert.equal(shouldFinish({stable:3,text:'hi',stableThreshold:3}),true);
  assert.equal(shouldFinish({stable:2,text:'hi',stableThreshold:3}),false);
});

test('shouldFinish: nothing → false', () => {
  assert.equal(shouldFinish(),false);
  assert.equal(shouldFinish(null),false);
});

// ── computeTypewriterBatch ─────────────────────────────────────

test('computeTypewriterBatch: empty target → done immediately', () => {
  const r=computeTypewriterBatch('','');
  assert.deepEqual(r,{next:'',done:true,advanced:0});
});

test('computeTypewriterBatch: displayed=already done', () => {
  const r=computeTypewriterBatch('hello','hello');
  assert.equal(r.done,true);
  assert.equal(r.advanced,0);
});

test('computeTypewriterBatch: advances by 3 by default', () => {
  const r=computeTypewriterBatch('abc','abcdefghi');
  assert.equal(r.next,'abcdef');
  assert.equal(r.advanced,3);
  assert.equal(r.done,false);
});

test('computeTypewriterBatch: hits target on last batch', () => {
  const r=computeTypewriterBatch('abcdef','abcdefgh');
  assert.equal(r.next,'abcdefgh');
  assert.equal(r.advanced,2);
  assert.equal(r.done,true);
});

test('computeTypewriterBatch: custom batchSize', () => {
  const r=computeTypewriterBatch('','hello',2);
  assert.equal(r.next,'he');
  assert.equal(r.advanced,2);
  assert.equal(r.done,false);
});

test('computeTypewriterBatch: invalid batchSize falls back to 3', () => {
  const r=computeTypewriterBatch('','abcdefgh',-5);
  assert.equal(r.advanced,3);
  assert.equal(r.next,'abc');
});

test('computeTypewriterBatch: displayed longer than target → trim to target', () => {
  // 防御：刷新 chat 之类的边界情况
  const r=computeTypewriterBatch('hello world','hello');
  assert.equal(r.next,'hello');
  assert.equal(r.done,true);
});

test('computeTypewriterBatch: non-string inputs → empty', () => {
  const r=computeTypewriterBatch(null,undefined);
  assert.deepEqual(r,{next:'',done:true,advanced:0});
});

// ── nextPumpDelay ──────────────────────────────────────────────

test('nextPumpDelay: streaming → 25', () => {
  assert.equal(nextPumpDelay(false),25);
});

test('nextPumpDelay: finished → 15', () => {
  assert.equal(nextPumpDelay(true),15);
});
