// tests/unit/streamFinalize.test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  buildFinalAssistantMessage,
  buildErrorBubbleText,
  lastUserContent,
} from '../../web/src/ui/streamFinalize.js';

// ── buildFinalAssistantMessage ──────────────────────────────────

test('buildFinalAssistantMessage: empty full → noop, returns copy', () => {
  const src=[{role:'user',content:'hi'}];
  const r=buildFinalAssistantMessage(src,'');
  assert.equal(r.action,'noop');
  assert.deepEqual(r.messages,src);
  assert.notEqual(r.messages,src,'must not return same reference');
});

test('buildFinalAssistantMessage: null full → noop', () => {
  const r=buildFinalAssistantMessage([{role:'user',content:'hi'}],null);
  assert.equal(r.action,'noop');
});

test('buildFinalAssistantMessage: non-string full → noop', () => {
  const r=buildFinalAssistantMessage([{role:'user',content:'hi'}],42);
  assert.equal(r.action,'noop');
});

test('buildFinalAssistantMessage: not-array messages → returns []', () => {
  const r=buildFinalAssistantMessage(null,'hello');
  assert.equal(r.action,'append');
  assert.deepEqual(r.messages,[{role:'assistant',content:'hello'}]);
});

test('buildFinalAssistantMessage: last is assistant placeholder → replace + drop _streaming', () => {
  const src=[
    {role:'user',content:'hi'},
    {role:'assistant',content:'partial...',_streaming:true},
  ];
  const r=buildFinalAssistantMessage(src,'final answer');
  assert.equal(r.action,'replace');
  assert.equal(r.messages.length,2);
  assert.deepEqual(r.messages[1],{role:'assistant',content:'final answer'});
  // 原数组未被修改
  assert.equal(src[1]._streaming,true);
  assert.equal(src[1].content,'partial...');
});

test('buildFinalAssistantMessage: last is assistant w/o _streaming → still replace', () => {
  const src=[
    {role:'user',content:'q'},
    {role:'assistant',content:'old'},
  ];
  const r=buildFinalAssistantMessage(src,'new');
  assert.equal(r.action,'replace');
  assert.equal(r.messages[1].content,'new');
  assert.equal('_streaming' in r.messages[1],false);
});

test('buildFinalAssistantMessage: last is user → append', () => {
  const src=[{role:'user',content:'q'}];
  const r=buildFinalAssistantMessage(src,'answer');
  assert.equal(r.action,'append');
  assert.equal(r.messages.length,2);
  assert.deepEqual(r.messages[1],{role:'assistant',content:'answer'});
});

test('buildFinalAssistantMessage: empty messages → append', () => {
  const r=buildFinalAssistantMessage([],'hi');
  assert.equal(r.action,'append');
  assert.deepEqual(r.messages,[{role:'assistant',content:'hi'}]);
});

test('buildFinalAssistantMessage: preserves other fields on replace', () => {
  const src=[
    {role:'assistant',content:'p',_streaming:true,timestamp:123,model:'gpt-4'},
  ];
  const r=buildFinalAssistantMessage(src,'final');
  assert.equal(r.messages[0].timestamp,123);
  assert.equal(r.messages[0].model,'gpt-4');
  assert.equal('_streaming' in r.messages[0],false);
});

// ── buildErrorBubbleText ────────────────────────────────────────

test('buildErrorBubbleText: with partial', () => {
  const t=buildErrorBubbleText('network died',true);
  assert.match(t,/⚠⏸ 连接中断: network died/);
  assert.match(t,/🔄 点击重试/);
  assert.match(t,/已保留上面的部分回复/);
});

test('buildErrorBubbleText: without partial', () => {
  const t=buildErrorBubbleText('boom',false);
  assert.match(t,/boom/);
  assert.equal(t.includes('已保留'),false);
});

test('buildErrorBubbleText: empty errMsg → fallback "连接中断"', () => {
  const t=buildErrorBubbleText('',false);
  assert.match(t,/⚠⏸ 连接中断: 连接中断/);
});

test('buildErrorBubbleText: non-string errMsg → fallback', () => {
  const t=buildErrorBubbleText(undefined,false);
  assert.match(t,/连接中断: 连接中断/);
});

// ── lastUserContent ─────────────────────────────────────────────

test('lastUserContent: empty/non-array → ""', () => {
  assert.equal(lastUserContent(null),'');
  assert.equal(lastUserContent([]),'');
  assert.equal(lastUserContent('nope'),'');
});

test('lastUserContent: returns last user content, ignoring assistant', () => {
  const src=[
    {role:'user',content:'first'},
    {role:'assistant',content:'reply'},
    {role:'user',content:'second'},
    {role:'assistant',content:'reply2'},
  ];
  assert.equal(lastUserContent(src),'second');
});

test('lastUserContent: no user → ""', () => {
  assert.equal(lastUserContent([{role:'assistant',content:'x'}]),'');
});

test('lastUserContent: skips malformed entries', () => {
  const src=[
    {role:'user',content:'ok'},
    null,
    {role:'user'},          // no content
    {role:'user',content:42}, // non-string
  ];
  assert.equal(lastUserContent(src),'ok');
});
