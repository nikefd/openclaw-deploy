// streamRecovery.js — visibilitychange + reader-stale watchdog (pure logic).
//
// 调用方持有 reader / _needRecover 标志位 / 真实 document，本模块只做：
//   "visible 且 streaming 中且 last chunk 距今超过阈值" → 触发 onStale 回调
//
// 设计原则：
// - 不引用全局 document / performance / streamingChats（全部走依赖注入）
// - reader.cancel() 不在模块里调，由调用方在 onStale 回调里执行
// - 仅暴露纯检查函数 + 一个轻量工厂；attach/detach 由调用方包一层 addEventListener

/**
 * 单次检查：visible + streaming + gap>=threshold → 返回 true（应 stale）
 *
 * @param {object} ctx
 * @param {() => boolean} ctx.isVisible
 * @param {() => boolean} ctx.isStreaming
 * @param {() => number}  ctx.getLastChunkAt   // 时间戳（ms，performance.now() 量纲）
 * @param {() => number}  ctx.getNow           // 当前时间（ms）
 * @param {number}        ctx.staleThresholdMs
 * @returns {boolean}
 */
export function shouldRecover(ctx){
  if(!ctx)return false;
  const{isVisible,isStreaming,getLastChunkAt,getNow,staleThresholdMs}=ctx;
  if(typeof isVisible!=='function'||!isVisible())return false;
  if(typeof isStreaming!=='function'||!isStreaming())return false;
  if(typeof getLastChunkAt!=='function'||typeof getNow!=='function')return false;
  const last=Number(getLastChunkAt());
  const now=Number(getNow());
  if(!Number.isFinite(last)||!Number.isFinite(now))return false;
  const threshold=Number(staleThresholdMs);
  if(!Number.isFinite(threshold)||threshold<0)return false;
  return (now-last)>=threshold;
}

/**
 * 工厂：返回 { check, onVisibilityChange }，由调用方 addEventListener。
 *
 * onStale 只在第一次满足条件时触发；重复触发无害但调用方可自己幂等保护。
 *
 * @param {object} opts
 * @param {() => boolean} opts.isVisible
 * @param {() => boolean} opts.isStreaming
 * @param {() => number}  opts.getLastChunkAt
 * @param {() => number}  [opts.getNow]              默认 performance.now (浏览器) / Date.now (fallback)
 * @param {number}        [opts.staleThresholdMs]    默认 60_000
 * @param {() => void}    opts.onStale
 */
export function createStreamRecovery(opts){
  if(!opts||typeof opts.onStale!=='function'){
    throw new TypeError('createStreamRecovery: onStale callback is required');
  }
  const getNow=typeof opts.getNow==='function'
    ?opts.getNow
    :(typeof performance!=='undefined'&&typeof performance.now==='function'
      ?()=>performance.now()
      :()=>Date.now());
  const ctx={
    isVisible:opts.isVisible,
    isStreaming:opts.isStreaming,
    getLastChunkAt:opts.getLastChunkAt,
    getNow,
    staleThresholdMs:Number.isFinite(opts.staleThresholdMs)?opts.staleThresholdMs:60000,
  };
  let fired=false;
  function check(){
    if(fired)return false;
    if(shouldRecover(ctx)){
      fired=true;
      try{opts.onStale();}catch(e){
        // 调用方负责日志；这里不抛
        if(typeof console!=='undefined')console.error('[streamRecovery] onStale threw',e);
      }
      return true;
    }
    return false;
  }
  return{
    check,
    onVisibilityChange:check,   // 直接当 visibilitychange listener 用
    hasFired:()=>fired,
  };
}
