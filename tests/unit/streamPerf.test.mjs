// tests/unit/streamPerf.test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { buildPerfSummary, createPerfTracker } from '../../web/src/ui/streamPerf.js';

// ── buildPerfSummary ───────────────────────────────────────────

test('buildPerfSummary: empty state → all zero', () => {
  const s=buildPerfSummary({});
  assert.equal(s.tool.value,0);
  assert.deepEqual(s.tool.meta,{count:0,pauses:[]});
  assert.equal(s.streaming.value,0);
  assert.deepEqual(s.streaming.meta,{chars:0,speed:0});
  assert.equal(s.total.value,0);
  assert.deepEqual(s.total.meta,{ttft:0,http:0,streaming:0,toolPauses:0,toolMs:0,chars:0});
});

test('buildPerfSummary: typical numbers', () => {
  const s=buildPerfSummary({
    totalMs:5200, ttftMs:500.4, httpMs:120.7,
    streamingMs:200, toolCount:1, toolTotalMs:4500,
    pauses:[{gap:4500,at:4200}], fullLen:420,
  });
  assert.equal(s.tool.value,4500);
  assert.equal(s.tool.meta.count,1);
  assert.deepEqual(s.tool.meta.pauses,[{gap:4500,at:4200}]);
  assert.equal(s.streaming.value,200);
  assert.equal(s.streaming.meta.chars,420);
  assert.equal(s.streaming.meta.speed,2100);          // 420 / 0.2s
  assert.equal(s.total.value,5200);
  assert.equal(s.total.meta.ttft,500);                // rounded
  assert.equal(s.total.meta.http,121);
  assert.equal(s.total.meta.streaming,200);
  assert.equal(s.total.meta.toolPauses,1);
  assert.equal(s.total.meta.toolMs,4500);
  assert.equal(s.total.meta.chars,420);
});

test('buildPerfSummary: NaN / undefined coerced to 0', () => {
  const s=buildPerfSummary({ttftMs:NaN,httpMs:undefined,streamingMs:'x'});
  assert.equal(s.total.meta.ttft,0);
  assert.equal(s.total.meta.http,0);
  assert.equal(s.streaming.value,0);
});

test('buildPerfSummary: pauses truncated to 10', () => {
  const pauses=Array.from({length:15},(_,i)=>({gap:1000+i,at:i*100}));
  const s=buildPerfSummary({pauses,toolCount:15,toolTotalMs:99999});
  assert.equal(s.tool.meta.pauses.length,10);
  assert.equal(s.tool.meta.count,15);             // count 不截断
});

test('buildPerfSummary: streamingMs=0 → speed=0 (no div by zero)', () => {
  const s=buildPerfSummary({streamingMs:0,fullLen:100});
  assert.equal(s.streaming.meta.speed,0);
});

test('buildPerfSummary: pauses must be array; non-array → empty', () => {
  const s=buildPerfSummary({pauses:'oops'});
  assert.deepEqual(s.tool.meta.pauses,[]);
});

test('buildPerfSummary: does not mutate input pauses', () => {
  const pauses=[{gap:1,at:1},{gap:2,at:2}];
  buildPerfSummary({pauses});
  assert.equal(pauses.length,2);
});

// ── createPerfTracker ──────────────────────────────────────────

function makeTracker(initial=0,opts={}){
  let now=initial;
  const tracker=createPerfTracker({getNow:()=>now,...opts});
  return{tracker,advance(ms){now+=ms;},get now(){return now;}};
}

test('tracker: fresh summary all zero', () => {
  const{tracker}=makeTracker(1000);
  tracker.start();
  const s=tracker.summary();
  assert.equal(s.total.value,0);
  assert.equal(s.streaming.value,0);
  assert.equal(s.tool.value,0);
});

test('tracker: markHttp / markTtft', () => {
  const{tracker,advance}=makeTracker(1000);
  tracker.start();
  advance(120); assert.equal(tracker.markHttp(),120);
  advance(380); assert.equal(tracker.markTtft(),500);
  const s=tracker.state();
  assert.equal(s.httpMs,120);
  assert.equal(s.ttftMs,500);
});

test('tracker: chunks before arm() do NOT accumulate streaming', () => {
  const{tracker,advance}=makeTracker(0);
  tracker.start();
  advance(50);  tracker.markChunk();        // unarmed — pure baseline
  advance(80);  tracker.markChunk();        // unarmed
  advance(100); tracker.markChunk();
  const s=tracker.state();
  assert.equal(s.streamingMs,0);
  assert.equal(s.toolCount,0);
});

test('tracker: arm() then chunks accumulate streaming', () => {
  const{tracker,advance}=makeTracker(0);
  tracker.start();
  advance(500); tracker.arm();              // typingRemoved baseline
  advance(50);  tracker.markChunk();
  advance(80);  tracker.markChunk();
  advance(70);  tracker.markChunk();
  const s=tracker.state();
  assert.equal(s.streamingMs,200);
});

test('tracker: arm() then huge gap → tool pause', () => {
  const{tracker,advance}=makeTracker(1000);
  tracker.start();
  tracker.arm();
  advance(100); tracker.markChunk();
  advance(5000); const r=tracker.markChunk();
  assert.equal(r.isPause,true);
  const s=tracker.state();
  assert.equal(s.toolCount,1);
  assert.equal(s.toolTotalMs,5000);
  assert.equal(s.streamingMs,100);
  assert.equal(s.pauses[0].gap,5000);
});

test('tracker: end() and summary', () => {
  const{tracker,advance}=makeTracker(0);
  tracker.start();
  advance(120); tracker.markHttp();
  advance(380); tracker.markTtft(); tracker.arm();
  advance(50); tracker.markChunk();
  advance(80); tracker.markChunk();
  tracker.setFullLen(420);
  advance(20);
  tracker.end();
  const s=tracker.summary();
  assert.equal(s.total.value,650);
  assert.equal(s.total.meta.ttft,500);
  assert.equal(s.total.meta.http,120);
  assert.equal(s.streaming.value,130);
  assert.equal(s.streaming.meta.chars,420);
});

test('tracker: start() resets', () => {
  const{tracker,advance}=makeTracker(0);
  tracker.start();
  tracker.arm();
  advance(5000); tracker.markChunk();
  tracker.setFullLen(100);
  tracker.start();
  const s=tracker.state();
  assert.equal(s.toolCount,0);
  assert.equal(s.toolTotalMs,0);
  assert.equal(s.streamingMs,0);
  assert.equal(s.fullLen,0);
});

test('tracker: setFullLen ignores invalid', () => {
  const{tracker}=makeTracker(0);
  tracker.start();
  tracker.setFullLen(50);
  tracker.setFullLen(-1);
  tracker.setFullLen(NaN);
  assert.equal(tracker.state().fullLen,50);
});
