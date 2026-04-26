// streamPerf.js — pure perf state + summary formatting for one stream send().
//
// 职责：(1) 提供一个可选的 PerfTracker 状态机（fake-clock 可测）；
//      (2) 提供纯函数 buildPerfSummary，把 send() 里散落的 _perfXxx 局部变量
//          打包成"喂给 perfLog 的三段 payload"。
//
// 实际接入策略：先用 buildPerfSummary（轻接入，行为零变化），原 _perfXxx
// 局部变量保留；tracker 状态机暴露给未来其它页面/重构使用，本次不接入 send()
// （理由：原循环里 streaming/pause 累加依赖 typingRemoved 标志，复刻该行为
//  会把 tracker 变复杂，本次 phase 选轻接入路线）。

/**
 * 把 send() 里收集到的原始 perf 字段格式化成 3 段 perfLog payload。
 *
 * 输入：原始局部变量（容忍 NaN/undefined → 当 0 处理；pauses[] 截断到 10）。
 * 输出：{ tool, streaming, total } 三段，分别对应原代码：
 *   perfLog('tool',  _perfToolTotalMs,    {count, pauses})
 *   perfLog('streaming', _perfStreaming,  {chars, speed})
 *   perfLog('total', _perfTotal,          {ttft, http, streaming, toolPauses, toolMs, chars})
 *
 * 调用方仍然自己决定要不要发 'tool'（原代码：toolCount>0 才发）。
 *
 * @param {object} st
 * @param {number} st.totalMs
 * @param {number} st.ttftMs
 * @param {number} st.httpMs
 * @param {number} st.streamingMs
 * @param {number} st.toolCount
 * @param {number} st.toolTotalMs
 * @param {Array<{gap:number,at:number}>} [st.pauses]
 * @param {number} [st.fullLen]
 */
export function buildPerfSummary(st){
  const s=st||{};
  const num=(x)=>Number.isFinite(x)?x:0;
  const totalMs=num(s.totalMs);
  const ttftMs=num(s.ttftMs);
  const httpMs=num(s.httpMs);
  const streamingMs=num(s.streamingMs);
  const toolCount=num(s.toolCount);
  const toolTotalMs=num(s.toolTotalMs);
  const fullLen=num(s.fullLen);
  const pausesIn=Array.isArray(s.pauses)?s.pauses:[];
  const pauses=pausesIn.length>10?pausesIn.slice(0,10):pausesIn.slice();
  const speedCps=streamingMs>0?Math.round(fullLen/(streamingMs/1000)):0;

  return{
    tool:{
      value:toolTotalMs,
      meta:{count:toolCount,pauses},
    },
    streaming:{
      value:streamingMs,
      meta:{chars:fullLen,speed:speedCps},
    },
    total:{
      value:totalMs,
      meta:{
        ttft:Math.round(ttftMs),
        http:Math.round(httpMs),
        streaming:Math.round(streamingMs),
        toolPauses:toolCount,
        toolMs:Math.round(toolTotalMs),
        chars:fullLen,
      },
    },
  };
}

// ── PerfTracker（state machine）─────────────────────────────────
// 状态机版本：完整代替 _perfXxx 局部变量；本次 phase 不接入 send()，仅作为
// 未来 streamLoop 重构 / agents.html / finance dashboard 等场景的基础设施。
//
// 与 buildPerfSummary 区别：tracker 自己管时间累加，需要调用方按合约调用。
// 兼容 typingRemoved 语义：调用方在"首个有效 delta 到达"时调 arm()，arm 之前
// 的 markChunk 只更新 baseline 不累加 streaming/pause（与原代码一致）。

/**
 * @param {object} [opts]
 * @param {() => number} [opts.getNow]
 * @param {number}        [opts.pauseThresholdMs]   default 3000
 */
export function createPerfTracker(opts){
  const getNow=(opts&&typeof opts.getNow==='function')
    ?opts.getNow
    :(typeof performance!=='undefined'&&typeof performance.now==='function'
      ?()=>performance.now()
      :()=>Date.now());
  const pauseThresholdMs=(opts&&Number.isFinite(opts.pauseThresholdMs))?opts.pauseThresholdMs:3000;

  let startedAt=0;
  let lastChunkAt=0;
  let endedAt=0;
  let httpMs=0;
  let ttftMs=0;
  let streamingMs=0;
  let toolCount=0;
  let toolTotalMs=0;
  let fullLen=0;
  let armed=false;
  const pauses=[];

  function start(){
    startedAt=getNow();
    lastChunkAt=startedAt;
    endedAt=0;
    httpMs=0;ttftMs=0;streamingMs=0;
    toolCount=0;toolTotalMs=0;fullLen=0;armed=false;
    pauses.length=0;
  }
  function markHttp(){httpMs=getNow()-startedAt;return httpMs;}
  function markTtft(){ttftMs=getNow()-startedAt;return ttftMs;}
  function arm(){armed=true;lastChunkAt=getNow();}

  /**
   * 每次 reader chunk 调用。armed 之前只推进 baseline；之后按 gap 累加。
   * 返回 {gap, isPause}。
   */
  function markChunk(){
    const now=getNow();
    const gap=now-lastChunkAt;
    lastChunkAt=now;
    if(!armed)return{gap,isPause:false};
    if(gap>pauseThresholdMs){
      toolCount++;toolTotalMs+=gap;
      pauses.push({gap:Math.round(gap),at:Math.round(now-startedAt)});
      return{gap,isPause:true};
    }
    streamingMs+=gap;
    return{gap,isPause:false};
  }
  function setFullLen(n){if(Number.isFinite(n)&&n>=0)fullLen=n|0;}
  function end(){endedAt=getNow();return endedAt-startedAt;}

  function summary(){
    const totalMs=(endedAt||getNow())-startedAt;
    return buildPerfSummary({
      totalMs,ttftMs,httpMs,streamingMs,
      toolCount,toolTotalMs,
      pauses:pauses.slice(),fullLen,
    });
  }
  function state(){
    return{
      totalMs:(endedAt||getNow())-startedAt,
      ttftMs,httpMs,streamingMs,
      toolCount,toolTotalMs,
      pauses:pauses.slice(),fullLen,
    };
  }

  return{start,markHttp,markTtft,arm,markChunk,setFullLen,end,summary,state};
}
