// streamFinalize.js — pure helpers to finalize an assistant message after a stream ends.
//
// 不做 DOM、不做网络、不做 perfLog——这些副作用留给 index.html 的调用方。
// 模块的职责：
//   1) buildFinalAssistantMessage: 把 chat.messages 数组按"流式刚结束"的语义合成一份新数组
//      （上一条是占位 assistant 就覆盖；否则 append）
//   2) buildErrorBubbleText: 生成"⚠⏸ 连接中断"提示气泡的文本（含可选"已保留部分回复"后缀）
//
// 设计约束：
// - 输入数组不被原地修改；返回 {messages, action: 'replace'|'append'|'noop'}
// - `full` 为空字符串/falsy 时返回 noop（success/error 路径都需要：什么也别塞）

/**
 * 合成"流式结束"后的 chat.messages。
 *
 * 规则（与 index.html 原内联逻辑对齐）：
 *   - 若 full 为空 → noop（不动 messages）
 *   - 若最后一条是 assistant → 覆盖 content，并清掉 _streaming 标记
 *   - 否则 → append 一条 { role:'assistant', content:full }
 *
 * @param {Array<{role:string,content:string,_streaming?:boolean}>} messages
 * @param {string} full
 * @returns {{messages:Array, action:'replace'|'append'|'noop'}}
 */
export function buildFinalAssistantMessage(messages, full){
  const arr=Array.isArray(messages)?messages:[];
  if(!full||typeof full!=='string'){
    return{messages:arr.slice(),action:'noop'};
  }
  const next=arr.slice();
  const last=next[next.length-1];
  if(last&&last.role==='assistant'){
    const merged={...last,content:full};
    delete merged._streaming;
    next[next.length-1]=merged;
    return{messages:next,action:'replace'};
  }
  next.push({role:'assistant',content:full});
  return{messages:next,action:'append'};
}

/**
 * 生成 "⚠⏸ 连接中断" 提示气泡文本。
 *
 * @param {string} errMsg              错误描述（默认 "连接中断"）
 * @param {boolean} hasPartial         是否已保留部分回复
 * @returns {string}
 */
export function buildErrorBubbleText(errMsg, hasPartial){
  const safeErr=(typeof errMsg==='string'&&errMsg.trim())?errMsg:'连接中断';
  const tail=hasPartial?'（已保留上面的部分回复）':'';
  return '⚠⏸ 连接中断: '+safeErr+'\n\n🔄 点击重试'+tail;
}

/**
 * 找到最后一条 user 消息的 content（用于"点击重试"恢复输入框）。
 *
 * @param {Array<{role:string,content:string}>} messages
 * @returns {string}
 */
export function lastUserContent(messages){
  if(!Array.isArray(messages))return'';
  for(let i=messages.length-1;i>=0;i--){
    const m=messages[i];
    if(m&&m.role==='user'&&typeof m.content==='string')return m.content;
  }
  return'';
}
