// streamPollLoop.js — pure helpers for the mobile fire-and-forget + poll path.
//
// 背景：手机端切 app / 锁屏会让 SSE reader 假死。所以走另一条路：
//   1) POST /api/chat/send 触发后端 fire-and-forget
//   2) 轮询 GET /api/chat/history 拿最新 assistant 文本
//   3) 用打字机效果把文本逐字追加到 bubble，模拟流式
//
// 这条路径的"决策逻辑"（什么时候算 error / 什么时候算 done / 怎么算字符
// 进度）抽到这里，可以 fake-clock 单测；DOM/网络/setTimeout 全部留给
// index.html 的调用方。

/**
 * 解读一次 /api/chat/history 的响应。
 *
 * 返回 status：
 *   'error'    — dispatch 已经失败，立刻停轮询并展示错误
 *   'timeout'  — dispatch done 但文本一直不刷新（gateway 没写 session）
 *   'idle'     — 本轮还没拿到新回复（baseline 没变）
 *   'progress' — 拿到新文本，应触发打字机
 *
 * @param {object} d                  history 端点返回的 JSON
 * @param {string} baselineTs         发送前快照的 ts
 * @param {string} baselineText       发送前快照的 text
 * @param {object} [opts]
 * @param {number} [opts.now]         当前时间（ms），默认 Date.now()
 * @param {number} [opts.timeoutMs]   dispatch done 后宽容时间，默认 15_000
 * @returns {{status:'error'|'timeout'|'idle'|'progress', text:string, ts:string, errMsg?:string}}
 */
export function decodePollResponse(d,baselineTs,baselineText,opts){
  const text=(d&&typeof d.text==='string')?d.text:'';
  const ts=(d&&typeof d.ts==='string')?d.ts:'';
  const dispatch=d&&d.dispatch;
  if(dispatch&&dispatch.status==='error'){
    return{status:'error',text,ts,errMsg:dispatch.error||'unknown'};
  }
  const isNew=(ts&&ts!==baselineTs)||(text&&text!==baselineText);
  if(!isNew){
    if(dispatch&&dispatch.status==='done'&&Number.isFinite(dispatch.endedAt)){
      const now=(opts&&Number.isFinite(opts.now))?opts.now:Date.now();
      const timeoutMs=(opts&&Number.isFinite(opts.timeoutMs))?opts.timeoutMs:15000;
      if(now-dispatch.endedAt>timeoutMs){
        return{status:'timeout',text,ts};
      }
    }
    return{status:'idle',text,ts};
  }
  return{status:'progress',text,ts};
}

/**
 * 判断本轮是否应该结束轮询。
 *
 * 规则（与原代码一致）：
 *   - dispatch.stopReason 不是 'inFlight' / 'streaming' 且已有 text → 结束
 *   - text 已经稳定（stable >= stableThreshold 次没变）且非空 → 结束
 *
 * @param {object} args
 * @param {string} [args.stopReason]
 * @param {string} args.text
 * @param {number} args.stable
 * @param {number} [args.stableThreshold]   default 6
 * @returns {boolean}
 */
export function shouldFinish(args){
  if(!args)return false;
  const{stopReason,text,stable}=args;
  const threshold=Number.isFinite(args.stableThreshold)?args.stableThreshold:6;
  if(!text)return false;
  if(stopReason&&stopReason!=='inFlight'&&stopReason!=='streaming')return true;
  if(stable>=threshold)return true;
  return false;
}

/**
 * 打字机：从 displayed 长度推进到 pendingFull，每次最多追 batchSize 个字符。
 *
 * @param {string} displayed
 * @param {string} pendingFull
 * @param {number} [batchSize]   default 3
 * @returns {{next:string, done:boolean, advanced:number}}
 */
export function computeTypewriterBatch(displayed,pendingFull,batchSize){
  const cur=typeof displayed==='string'?displayed:'';
  const target=typeof pendingFull==='string'?pendingFull:'';
  const size=Number.isFinite(batchSize)&&batchSize>0?Math.floor(batchSize):3;
  if(cur.length>=target.length){
    return{next:cur.length>target.length?cur.slice(0,target.length):cur,done:true,advanced:0};
  }
  const advance=Math.min(size,target.length-cur.length);
  const next=target.slice(0,cur.length+advance);
  return{next,done:next.length>=target.length,advanced:advance};
}

/**
 * 打字机下一帧的延迟。
 *   - 流式仍在进行 → 25ms（慢一点显得自然）
 *   - 流式已收尾 → 15ms（赶紧把残留追完）
 *
 * @param {boolean} finished
 * @returns {number}
 */
export function nextPumpDelay(finished){
  return finished?15:25;
}
