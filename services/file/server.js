const http=require('http'),fs=require('fs'),path=require('path'),zlib=require('zlib');
const {exec}=require('child_process');
const {stripHeavy}=require('./lib/stripHeavy');
const {sendJson}=require('./lib/sendJson');
const {parseChatJsonl}=require('./lib/parseChatJsonl');
const EXEC_ENV=Object.assign({},process.env,{PATH:'/home/nikefd/.npm-global/bin:/usr/local/bin:/usr/bin:/bin:'+process.env.PATH});
const PORT=7682,ROOT=process.env.HOME;
const CHATS_FILE=path.join(ROOT,'.openclaw','chat-history.json');
const CHATS_DIR=path.join(ROOT,'.openclaw','chats');
const PERF_LOG_FILE=path.join(ROOT,'.openclaw','perf-log.json');function readBody(req){return new Promise((ok,no)=>{let d='';req.on('data',c=>d+=c);req.on('end',()=>ok(d));req.on('error',no);});}
http.createServer(async(req,res)=>{
  res.setHeader('Content-Type','application/json');
  const url=new URL(req.url,'http://localhost:'+PORT);
  if(url.pathname==='/api/files/list'){
    const dir=url.searchParams.get('path')||ROOT;
    const r=path.resolve(dir);
    if(!r.startsWith(ROOT)){res.writeHead(403);res.end('{"error":"forbidden"}');return;}
    try{
      const e=fs.readdirSync(r,{withFileTypes:true}).map(x=>{
        const fp=path.join(r,x.name),isDir=x.isDirectory();
        let size=null;try{if(!isDir)size=fs.statSync(fp).size;}catch{}
        return {name:x.name,path:fp,type:isDir?'dir':'file',size};
      }).filter(x=>!x.name.startsWith('.')).sort((a,b)=>a.type!==b.type?(a.type==='dir'?-1:1):a.name.localeCompare(b.name));
      res.end(JSON.stringify({path:r,parent:path.dirname(r),entries:e}));
    }catch(e){res.writeHead(500);res.end(JSON.stringify({error:e.message}));}
  }else if(url.pathname==='/api/files/download'){
    const fp=url.searchParams.get('path');
    if(!fp){res.writeHead(400);res.end('need path');return;}
    const r=path.resolve(fp);
    if(!r.startsWith(ROOT)){res.writeHead(403);res.end('forbidden');return;}
    try{
      const s=fs.statSync(r);
      if(s.size>50*1048576){res.writeHead(413);res.end('too big');return;}
      const name=path.basename(r);
      res.writeHead(200,{'Content-Type':'application/octet-stream','Content-Disposition':`attachment; filename="${encodeURIComponent(name)}"`, 'Content-Length':s.size});
      fs.createReadStream(r).pipe(res);
    }catch(e){res.writeHead(500);res.end(e.message);}
  }else if(url.pathname==='/api/files/read'){
    const fp=url.searchParams.get('path');
    if(!fp){res.writeHead(400);res.end('{"error":"need path"}');return;}
    const r=path.resolve(fp);
    if(!r.startsWith(ROOT)){res.writeHead(403);res.end('{"error":"forbidden"}');return;}
    try{const s=fs.statSync(r);if(s.size>1048576){res.writeHead(413);res.end('{"error":"too big"}');return;}
      res.end(JSON.stringify({path:r,size:s.size,content:fs.readFileSync(r,'utf-8')}));
    }catch(e){res.writeHead(500);res.end(JSON.stringify({error:e.message}));}
  }else if(url.pathname==='/api/chats'&&req.method==='GET'){
    // Default: return stripped list (no base64 images/attachments) + gzip.
    // Pass ?full=1 to get raw legacy behavior (heavy — avoid in UI).
    // Pass ?since=<ms> to only return chats with updatedAt > since (incremental sync).
    const wantFull=url.searchParams.get('full')==='1';
    const sinceRaw=url.searchParams.get('since');
    const since=sinceRaw?parseInt(sinceRaw,10):0;
    try{
      fs.mkdirSync(CHATS_DIR,{recursive:true});
      const files=fs.readdirSync(CHATS_DIR).filter(f=>f.endsWith('.json'));
      let all=[];
      if(files.length>0){
        all=files.map(f=>{try{return JSON.parse(fs.readFileSync(path.join(CHATS_DIR,f),'utf-8'));}catch{return null;}}).filter(Boolean);
      }else if(fs.existsSync(CHATS_FILE)){
        // Migrate legacy file to individual files
        const legacy=JSON.parse(fs.readFileSync(CHATS_FILE,'utf-8'));
        for(const c of legacy){if(c&&c.id){try{fs.writeFileSync(path.join(CHATS_DIR,c.id+'.json'),JSON.stringify(c),'utf-8');}catch{}}}
        all=legacy;
      }
      if(since&&!isNaN(since)){
        all=all.filter(c=>(c.updatedAt||0)>since);
      }
      all.sort((a,b)=>(b.updatedAt||0)-(a.updatedAt||0));
      const out=wantFull?all:all.map(stripHeavy);
      res.setHeader('X-Server-Time',String(Date.now()));
      sendJson(req,res,out);
    }catch(e){res.writeHead(500);res.end(JSON.stringify({error:e.message}));}
  }else if(url.pathname==='/api/chats'&&req.method==='POST'){
    // Legacy bulk save — still supported but also writes individual files
    try{const body=await readBody(req);const parsed=JSON.parse(body);
      fs.mkdirSync(CHATS_DIR,{recursive:true});
      for(const c of parsed){if(c&&c.id){fs.writeFileSync(path.join(CHATS_DIR,c.id+'.json'),JSON.stringify(c),'utf-8');}}
      // Also write legacy file for backward compat
      fs.mkdirSync(path.dirname(CHATS_FILE),{recursive:true});
      fs.writeFileSync(CHATS_FILE,body,'utf-8');res.end('{"ok":true}');}
    catch(e){res.writeHead(500);res.end(JSON.stringify({error:e.message}));}
  }else if(url.pathname.startsWith('/api/chats/')&&req.method==='GET'){
    // Fetch a single chat (full content, including images) for lazy-load.
    const chatId=url.pathname.slice('/api/chats/'.length);
    if(!chatId){res.writeHead(400);res.end('{"error":"need chat id"}');return;}
    try{
      const fp=path.join(CHATS_DIR,chatId+'.json');
      if(!fs.existsSync(fp)){res.writeHead(404);res.end('{"error":"not found"}');return;}
      const data=fs.readFileSync(fp,'utf-8');
      sendJson(req,res,data);
    }catch(e){res.writeHead(500);res.end(JSON.stringify({error:e.message}));}
  }else if(url.pathname.startsWith('/api/chats/')&&(req.method==='PUT'||req.method==='POST')){
    // Save single chat: PUT/POST /api/chats/:id (POST for sendBeacon compat)
    const chatId=url.pathname.slice('/api/chats/'.length);
    if(!chatId){res.writeHead(400);res.end('{"error":"need chat id"}');return;}
    try{
      const body=await readBody(req);const chat=JSON.parse(body);
      fs.mkdirSync(CHATS_DIR,{recursive:true});
      const fp=path.join(CHATS_DIR,chatId+'.json');
      // GUARD: refuse to overwrite a chat that has messages with one that has none.
      // This prevents buggy clients from wiping chats via stripped/empty snapshots.
      if(fs.existsSync(fp)){
        try{
          const existing=JSON.parse(fs.readFileSync(fp,'utf-8'));
          const existingLen=(existing.messages||[]).length;
          const incomingLen=(chat.messages||[]).length;
          if(existingLen>0&&incomingLen===0){
            console.warn('[chats] REFUSED empty overwrite for',chatId,'(existing='+existingLen+' msgs)');
            res.writeHead(409);res.end(JSON.stringify({error:'refusing to overwrite non-empty chat with empty',existingMessages:existingLen}));
            return;
          }
          // 🔒 GUARD: 服务端权威 —— 如果存盘的最后一条 assistant 已经是 finalized（没有 _streaming），
          // 而前端传来的还带着 _streaming（说明是流式中的旧快照）→ 拒绝覆盖。
          const prevLast=existing.messages?.[existing.messages.length-1];
          const incLast=chat.messages?.[chat.messages.length-1];
          if(prevLast?.role==='assistant'&&!prevLast._streaming&&
             incLast?.role==='assistant'&&incLast._streaming){
            console.warn('[chats] REFUSED streaming-over-final overwrite for',chatId);
            res.writeHead(409);res.end(JSON.stringify({error:'refusing to overwrite finalized assistant with in-flight streaming snapshot'}));
            return;
          }
          // 🔒 GUARD: 如果存盘的最后一条 assistant 比前端传来的同位置 assistant 更长，
          // 说明前端是旧快照 → 拒绝缩短。就治 4/24 那种“长回复被旧快照捧动”的情况。
          if(prevLast?.role==='assistant'&&incLast?.role==='assistant'&&
             typeof prevLast.content==='string'&&typeof incLast.content==='string'&&
             prevLast.content.length>incLast.content.length+20&&
             !prevLast._streaming){
            console.warn('[chats] REFUSED shrink overwrite for',chatId,'prev='+prevLast.content.length+' inc='+incLast.content.length);
            res.writeHead(409);res.end(JSON.stringify({error:'refusing to shrink finalized assistant message',prevLen:prevLast.content.length,incLen:incLast.content.length}));
            return;
          }
          // shrink-guard removed — it blocked legitimate post-stream saves
          // when the in-memory messages count was temporarily lower than the
          // last debounced snapshot. The empty-overwrite guard above is enough.
        }catch{}
      }
      fs.writeFileSync(fp,JSON.stringify(chat),'utf-8');
      res.end('{"ok":true}');
    }catch(e){res.writeHead(500);res.end(JSON.stringify({error:e.message}));}
  }else if(url.pathname.startsWith('/api/chats/')&&req.method==='DELETE'){
    // Delete single chat: DELETE /api/chats/:id
    const chatId=url.pathname.slice('/api/chats/'.length);
    if(!chatId){res.writeHead(400);res.end('{"error":"need chat id"}');return;}
    try{
      const fp=path.join(CHATS_DIR,chatId+'.json');
      if(fs.existsSync(fp))fs.unlinkSync(fp);
      res.end('{"ok":true}');
    }catch(e){res.writeHead(500);res.end(JSON.stringify({error:e.message}));}
  }else if(url.pathname==='/api/files/upload'&&req.method==='POST'){
    // Multipart file upload
    const ct=req.headers['content-type']||'';
    const m=ct.match(/boundary=(.+)/);
    if(!m){res.writeHead(400);res.end('{"error":"no boundary"}');return;}
    const boundary='--'+m[1];
    const chunks=[];
    req.on('data',c=>chunks.push(c));
    req.on('end',()=>{
      try{
        const buf=Buffer.concat(chunks);
        const targetDir=url.searchParams.get('dir');
        const UPLOAD_DIR=targetDir&&path.resolve(targetDir).startsWith(ROOT)?path.resolve(targetDir):path.join(ROOT,'uploads');
        fs.mkdirSync(UPLOAD_DIR,{recursive:true});
        // Parse multipart
        const bBuf=Buffer.from(boundary);
        const parts=[];
        let start=0;
        while(true){
          const idx=buf.indexOf(bBuf,start);
          if(idx===-1)break;
          if(start>0)parts.push(buf.slice(start,idx-2));// -2 for \r\n
          start=idx+bBuf.length+2;// skip boundary + \r\n
        }
        const results=[];
        for(const part of parts){
          const headerEnd=part.indexOf('\r\n\r\n');
          if(headerEnd===-1)continue;
          const headers=part.slice(0,headerEnd).toString();
          const body=part.slice(headerEnd+4);
          const fnMatch=headers.match(/filename="([^"]+)"/);
          if(!fnMatch)continue;
          const fieldMatch=headers.match(/name="([^"]+)"/);
          const field=fieldMatch?fieldMatch[1]:'file';
          // Sanitize filename
          let fn=fnMatch[1].replace(/[^a-zA-Z0-9._\-\u4e00-\u9fff]/g,'_');
          // Add timestamp to avoid collision
          const ext=path.extname(fn);
          const base=path.basename(fn,ext);
          const safeName=base+'_'+Date.now()+ext;
          const dest=path.join(UPLOAD_DIR,safeName);
          // Strip trailing \r\n if present
          let writeBody=body;
          if(body.length>=2&&body[body.length-2]===13&&body[body.length-1]===10){
            writeBody=body.slice(0,body.length-2);
          }
          fs.writeFileSync(dest,writeBody);
          results.push({field,name:fnMatch[1],savedAs:safeName,path:dest,size:writeBody.length});
        }
        res.end(JSON.stringify({ok:true,files:results}));
      }catch(e){res.writeHead(500);res.end(JSON.stringify({error:e.message}));}
    });
  }else if(url.pathname==='/api/files/write'&&req.method==='POST'){
    try{
      const body=JSON.parse(await readBody(req));
      if(!body.path||body.content==null){res.writeHead(400);res.end('{"error":"need path and content"}');return;}
      const r=path.resolve(body.path);
      if(!r.startsWith(ROOT)){res.writeHead(403);res.end('{"error":"forbidden"}');return;}
      fs.mkdirSync(path.dirname(r),{recursive:true});
      fs.writeFileSync(r,body.content,'utf-8');
      const s=fs.statSync(r);
      res.end(JSON.stringify({ok:true,path:r,size:s.size}));
    }catch(e){res.writeHead(500);res.end(JSON.stringify({error:e.message}));}
  // === NODE MANAGEMENT API ===
  }else if(url.pathname==='/api/tasks/list'&&req.method==='GET'){
    const qs=url.searchParams;
    const args=['tasks','list','--json'];
    const rt=qs.get('runtime');if(rt)args.push('--runtime',rt);
    const st=qs.get('status');if(st)args.push('--status',st);
    const cacheKey=args.join('|');
    global._tasksCache=global._tasksCache||{};
    global._tasksInFlight=global._tasksInFlight||{};
    const c=global._tasksCache[cacheKey];
    const now=Date.now();
    const FRESH=15000, STALE=10*60*1000;
    const doFetch=(cb)=>{
      if(global._tasksInFlight[cacheKey]){global._tasksInFlight[cacheKey].push(cb);return}
      global._tasksInFlight[cacheKey]=[cb];
      exec('openclaw '+args.join(' ')+' 2>&1',{env:EXEC_ENV,maxBuffer:10*1024*1024,timeout:45000},(e,o)=>{
        const waiters=global._tasksInFlight[cacheKey]||[];delete global._tasksInFlight[cacheKey];
        if(e){waiters.forEach(w=>w(e,null));return}
        try{JSON.parse(o);global._tasksCache[cacheKey]={t:Date.now(),data:o};waiters.forEach(w=>w(null,o))}catch(pe){waiters.forEach(w=>w(pe,o))}
      });
    };
    // 1) 新鲜缓存 → 直接返回
    if(c&&(now-c.t)<FRESH){res.setHeader('Content-Type','application/json');res.setHeader('X-Cache','HIT');res.end(c.data);return}
    // 2) 有用的旧缓存 → 先返回旧的，后台刷新
    if(c&&(now-c.t)<STALE){res.setHeader('Content-Type','application/json');res.setHeader('X-Cache','STALE');res.end(c.data);doFetch(()=>{});return}
    // 3) 完全冷启动 → 等一下
    doFetch((e,o)=>{
      if(e){res.writeHead(500);res.end(JSON.stringify({error:e.message,raw:String(o||'').slice(0,500)}));return}
      res.setHeader('Content-Type','application/json');res.setHeader('X-Cache','MISS');res.end(o);
    });
  }else if(url.pathname==='/api/nodes/status'&&req.method==='GET'){
    exec('openclaw nodes status --json 2>&1',{env:EXEC_ENV},(e,o)=>{
      if(e){res.writeHead(500);res.end(JSON.stringify({error:e.message}));return;}
      try{res.end(o);}catch{res.writeHead(500);res.end(JSON.stringify({error:'parse error',raw:o}));}
    });
  }else if(url.pathname==='/api/nodes/list'&&req.method==='GET'){
    exec('openclaw nodes list --json 2>&1',{env:EXEC_ENV},(e,o)=>{
      if(e){res.writeHead(500);res.end(JSON.stringify({error:e.message}));return;}
      try{res.end(o);}catch{res.writeHead(500);res.end(JSON.stringify({error:'parse error',raw:o}));}
    });
  }else if(url.pathname==='/api/devices/list'&&req.method==='GET'){
    exec('openclaw devices list --json 2>&1',{env:EXEC_ENV},(e,o)=>{
      if(e){res.writeHead(500);res.end(JSON.stringify({error:e.message}));return;}
      try{res.end(o);}catch{res.writeHead(500);res.end(JSON.stringify({error:'parse error',raw:o}));}
    });
  }else if(url.pathname==='/api/devices/approve'&&req.method==='POST'){
    readBody(req).then(body=>{
      const d=JSON.parse(body);
      if(!d.requestId){res.writeHead(400);res.end('{"error":"need requestId"}');return;}
      exec(`openclaw devices approve ${d.requestId} --json 2>&1`,{env:EXEC_ENV},(e,o)=>{
        if(e){res.writeHead(500);res.end(JSON.stringify({error:e.message,raw:o}));return;}
        res.end(JSON.stringify({ok:true,output:o.trim()}));
      });
    }).catch(e=>{res.writeHead(400);res.end(JSON.stringify({error:e.message}));});
  }else if(url.pathname==='/api/devices/reject'&&req.method==='POST'){
    readBody(req).then(body=>{
      const d=JSON.parse(body);
      if(!d.requestId){res.writeHead(400);res.end('{"error":"need requestId"}');return;}
      exec(`openclaw devices reject ${d.requestId} --json 2>&1`,{env:EXEC_ENV},(e,o)=>{
        if(e){res.writeHead(500);res.end(JSON.stringify({error:e.message,raw:o}));return;}
        res.end(JSON.stringify({ok:true,output:o.trim()}));
      });
    }).catch(e=>{res.writeHead(400);res.end(JSON.stringify({error:e.message}));});
  }else if(url.pathname==='/api/nodes/run'&&req.method==='POST'){
    readBody(req).then(body=>{
      const d=JSON.parse(body);
      if(!d.node||!d.command){res.writeHead(400);res.end('{"error":"need node and command"}');return;}
      const cmd=`openclaw nodes run --node ${JSON.stringify(d.node)} --raw ${JSON.stringify(d.command)} --json 2>&1`;
      exec(cmd,{timeout:30000,env:EXEC_ENV},(e,o)=>{
        if(e&&!o){res.writeHead(500);res.end(JSON.stringify({error:e.message}));return;}
        res.end(JSON.stringify({ok:true,output:o.trim()}));
      });
    }).catch(e=>{res.writeHead(400);res.end(JSON.stringify({error:e.message}));});
  }else if(url.pathname==='/api/nodes/exec'&&req.method==='POST'){
    readBody(req).then(body=>{
      const d=JSON.parse(body);
      if(!d.node||!d.command){res.writeHead(400);res.end('{"error":"need node and command"}');return;}
      const args=Array.isArray(d.command)?d.command:['/bin/sh','-c',d.command];
      const params=JSON.stringify({command:args,cwd:d.cwd||undefined});
      const cmd=`openclaw nodes invoke --node ${JSON.stringify(d.node)} --command system.run --params ${JSON.stringify(params)} --json 2>&1`;
      exec(cmd,{timeout:30000,env:EXEC_ENV,maxBuffer:5*1024*1024},(e,o)=>{
        if(e&&!o){res.writeHead(500);res.end(JSON.stringify({error:e.message}));return;}
        try{
          const result=JSON.parse(o);
          res.end(JSON.stringify({ok:result.ok,stdout:result.payload?.stdout||'',stderr:result.payload?.stderr||'',exitCode:result.payload?.exitCode}));
        }catch{res.end(JSON.stringify({ok:false,error:'parse error',raw:o.slice(0,2000)}));}
      });
    }).catch(e=>{res.writeHead(400);res.end(JSON.stringify({error:e.message}));});
  }else if(url.pathname==='/api/gateway/token'&&req.method==='GET'){
    try{
      const cfg=JSON.parse(fs.readFileSync(path.join(ROOT,'.openclaw','openclaw.json'),'utf-8'));
      const t=cfg?.gateway?.auth?.token;
      if(t)res.end(JSON.stringify({token:t}));
      else res.end(JSON.stringify({error:'token not found in config'}));
    }catch(ex){res.writeHead(500);res.end(JSON.stringify({error:'cannot read config: '+ex.message}));}
  }else if(url.pathname==='/api/gateway/info'&&req.method==='GET'){
    const hostname=require('os').hostname();
    exec('curl -s ifconfig.me 2>/dev/null',(e,ip)=>{
      const publicIp=(ip||'').trim();
      res.end(JSON.stringify({
        host:'zhangyangbin.com',
        port:18789,
        tls:false,
        wsPort:443,
        wsTls:true,
        publicIp,
        hostname,
        hint:`# 在远程机器上运行:\nnpm install -g openclaw\nexport OPENCLAW_GATEWAY_TOKEN=<token>\nopenclaw node run --host zhangyangbin.com --port 18789`
      }));
    });
  }else if(url.pathname==='/api/perf/log'&&req.method==='POST'){
    readBody(req).then(body=>{
      try{
        const data=JSON.parse(body);
        data.timestamp=Date.now();
        let logs=[];
        try{
          if(fs.existsSync(PERF_LOG_FILE)){
            const existing=fs.readFileSync(PERF_LOG_FILE,'utf-8');
            logs=JSON.parse(existing);
            if(!Array.isArray(logs))logs=[];
          }
        }catch{}
        logs.push(data);
        if(logs.length>10000)logs=logs.slice(-10000);
        fs.mkdirSync(path.dirname(PERF_LOG_FILE),{recursive:true});
        fs.writeFileSync(PERF_LOG_FILE,JSON.stringify(logs),'utf-8');
        res.end(JSON.stringify({ok:true}));
      }catch(e){res.writeHead(400);res.end(JSON.stringify({error:e.message}));}
    }).catch(e=>{res.writeHead(400);res.end(JSON.stringify({error:e.message}));});
  }else if(url.pathname==='/api/perf/log'&&req.method==='GET'){
    try{
      if(fs.existsSync(PERF_LOG_FILE)){
        const logs=fs.readFileSync(PERF_LOG_FILE,'utf-8');
        res.end(logs);
      }else{
        res.end(JSON.stringify([]));
      }
    }catch(e){res.writeHead(500);res.end(JSON.stringify({error:e.message}));}
  }else if(url.pathname==='/api/chat/history'&&req.method==='GET'){
    // 轮询拉取某个 chatId 的最新回复（直读 JSONL，不走 gateway）
    try{
      const chatId=url.searchParams.get('chatId');
      const agentId=url.searchParams.get('agent')||'opus';
      if(!chatId){res.writeHead(400);res.end(JSON.stringify({error:'chatId required'}));return;}
      // 附带 dispatch 状态：让前端知道 gateway 是还在忙、已结束、还是挂了
      const dispatch=global.__chatDispatch?.[chatId]||null;
      const sessionsMap=JSON.parse(fs.readFileSync(path.join(ROOT,'.openclaw','agents',agentId,'sessions','sessions.json'),'utf-8'));
      const key=`agent:${agentId}:openai-user:${chatId}`;
      const entry=sessionsMap[key];
      if(!entry){res.end(JSON.stringify({messages:[],status:'no-session'}));return;}
      const jsonlPath=path.join(ROOT,'.openclaw','agents',agentId,'sessions',entry.sessionId+'.jsonl');
      if(!fs.existsSync(jsonlPath)){res.end(JSON.stringify({messages:[],status:'no-file'}));return;}
      // 只读最后 ~64KB，够拿到最后一条 assistant
      const stat=fs.statSync(jsonlPath);
      const readFrom=Math.max(0,stat.size-65536);
      const fd=fs.openSync(jsonlPath,'r');const buf=Buffer.alloc(stat.size-readFrom);
      fs.readSync(fd,buf,0,buf.length,readFrom);fs.closeSync(fd);
      const lines=buf.toString('utf-8');
      const {text,stopReason,isStreaming,ts}=parseChatJsonl(lines);
      res.end(JSON.stringify({chatId,text,stopReason,isStreaming,ts,dispatch}));
    }catch(e){res.writeHead(500);res.end(JSON.stringify({error:e.message}));}
  }else if(url.pathname==='/api/copilot/stream'&&req.method==='POST'){
    // === 服务端流式代理 + 实时落盘 ===
    // 客户端 POST {chatId, model, messages, agentId?, user?, signal?}
    // 我们：
    //   1) 转发到本地 gateway /v1/chat/completions (stream:true)
    //   2) 把上游 SSE 原样透传给客户端
    //   3) 同时累积 delta，每 500ms debounce 写一次 chats/{chatId}.json
    //   4) 客户端断开 -> 仍继续读完上游、写完盘 (req.on('close') 不杀上游)
    //   5) [DONE] 时清掉 _streaming 标记并最终写一次
    let chatIdForLog='';
    try{
      const raw=await readBody(req);
      const body=JSON.parse(raw||'{}');
      const chatId=body.chatId||body.user;
      chatIdForLog=chatId||'?';
      if(!chatId){res.writeHead(400);res.end(JSON.stringify({error:'chatId required'}));return;}
      const model=body.model||'openclaw';
      const messages=Array.isArray(body.messages)?body.messages:[];
      // 取 token：优先 body.token (兼容用户态)，否则读本地 gateway config
      let token=body.token||'';
      if(!token){try{const cfg=JSON.parse(fs.readFileSync(path.join(ROOT,'.openclaw','openclaw.json'),'utf-8'));token=cfg?.gateway?.auth?.token||'';}catch{}}
      // SSE response head
      res.writeHead(200,{
        'Content-Type':'text/event-stream; charset=utf-8',
        'Cache-Control':'no-cache, no-transform',
        'Connection':'keep-alive',
        'X-Accel-Buffering':'no'
      });
      // 落盘 helpers
      const chatFp=path.join(CHATS_DIR,chatId+'.json');
      fs.mkdirSync(CHATS_DIR,{recursive:true});
      // 🆕 立刻把最新一条 user 消息 append 到 chat 文件（不依赖前端后续 PUT）
      // 这样就算流式结束后前端不 PUT，user 消息也已经持久化了
      try{
        const lastUser=[...messages].reverse().find(m=>m&&m.role==='user');
        if(lastUser){
          let chat=null;
          if(fs.existsSync(chatFp)){
            try{chat=JSON.parse(fs.readFileSync(chatFp,'utf-8'));}catch{chat=null;}
          }
          // 取 user content 的 string 表示（提前计算，新建 chat 时用它做 title）
          let userText='';
          if(typeof lastUser.content==='string')userText=lastUser.content;
          else if(Array.isArray(lastUser.content))userText=lastUser.content.filter(c=>c&&c.type==='text').map(c=>c.text).join('');
          if(!chat||typeof chat!=='object'){
            const autoTitle=(userText||'').slice(0,30)+((userText||'').length>30?'...':'')||'新对话';
            chat={id:chatId,title:autoTitle,agentId:body.agentId||'main',messages:[],createdAt:Date.now()};
          }
          if(!Array.isArray(chat.messages))chat.messages=[];
          // 如果已存在 chat 但 title 空（旧数据或上游 bug）+ 此刻是首条消息，补一个
          if(!chat.title&&chat.messages.length===0&&userText){
            chat.title=userText.slice(0,30)+(userText.length>30?'...':'');
          }
          // 去重：如果最后一条已经是相同内容的 user，跳过
          const last=chat.messages[chat.messages.length-1];
          const lastIsSameUser=last&&last.role==='user'&&(
            (typeof last.content==='string'&&last.content===userText)||
            JSON.stringify(last.content)===JSON.stringify(lastUser.content)
          );
          if(!lastIsSameUser){
            chat.messages.push({role:'user',content:lastUser.content});
            chat.updatedAt=Date.now();
            const tmp=chatFp+'.tmp';
            fs.writeFileSync(tmp,JSON.stringify(chat),'utf-8');
            fs.renameSync(tmp,chatFp);
            console.log('[copilot/stream] persisted user msg chatId='+chatId+' len='+userText.length);
          }
        }
      }catch(e){console.error('[copilot/stream] user-persist err',chatId,e.message);}
      // 串行化对单个文件的写：用 promise chain 避免并发覆盖
      global.__chatWriteLocks=global.__chatWriteLocks||{};
      function persist(full,done){
        const prev=global.__chatWriteLocks[chatId]||Promise.resolve();
        const next=prev.then(()=>new Promise(resolve=>{
          try{
            let chat=null;
            if(fs.existsSync(chatFp)){
              try{chat=JSON.parse(fs.readFileSync(chatFp,'utf-8'));}catch{chat=null;}
            }
            if(!chat||typeof chat!=='object'){
              // 科定验 fallback：新建时用第一条 user 做 title（和前端逻辑对齐）
              let firstUserText='';
              try{
                const fu=(body.messages||[]).find(m=>m&&m.role==='user');
                if(fu){
                  if(typeof fu.content==='string')firstUserText=fu.content;
                  else if(Array.isArray(fu.content))firstUserText=fu.content.filter(c=>c&&c.type==='text').map(c=>c.text).join('');
                }
              }catch{}
              const autoTitle=firstUserText.slice(0,30)+(firstUserText.length>30?'...':'')||'新对话';
              chat={id:chatId,title:autoTitle,agentId:body.agentId||'main',messages:[],createdAt:Date.now()};
            }
            if(!Array.isArray(chat.messages))chat.messages=[];
            // 找最后一条 assistant；如果是 _streaming 状态就更新，否则 push 一条新的
            let last=chat.messages[chat.messages.length-1];
            if(last&&last.role==='assistant'&&last._streaming){
              last.content=full;
              if(done)delete last._streaming;
            }else{
              const newMsg={role:'assistant',content:full};
              if(!done)newMsg._streaming=true;
              chat.messages.push(newMsg);
            }
            chat.updatedAt=Date.now();
            // 临时文件 + rename: 原子写
            const tmp=chatFp+'.tmp';
            fs.writeFileSync(tmp,JSON.stringify(chat),'utf-8');
            fs.renameSync(tmp,chatFp);
          }catch(e){console.error('[copilot/stream] persist err',chatId,e.message);}
          resolve();
        }));
        global.__chatWriteLocks[chatId]=next.catch(()=>{});
        return next;
      }
      // debounce 500ms
      let pending=null,lastWriteFull='';
      function schedulePersist(full){
        if(pending){pending.full=full;return;}
        pending={full,timer:null};
        const cur=pending;
        cur.timer=setTimeout(()=>{
          if(pending!==cur)return;
          const f=cur.full;pending=null;
          if(f===lastWriteFull)return;
          lastWriteFull=f;
          persist(f,false);
        },500);
      }
      // 客户端断开时只标记，不杀上游
      let clientClosed=false;
      req.on('close',()=>{clientClosed=true;console.log('[copilot/stream] client closed but continuing upstream chatId='+chatId);});
      // 发上游
      const payload=JSON.stringify({model,stream:true,user:chatId,messages});
      const gwReq=http.request({
        host:'127.0.0.1',port:18789,path:'/v1/chat/completions',method:'POST',
        headers:{'Authorization':'Bearer '+token,'Content-Type':'application/json','Accept':'text/event-stream'}
      },gwRes=>{
        if(gwRes.statusCode!==200){
          let errBuf='';gwRes.on('data',c=>errBuf+=c);
          gwRes.on('end',()=>{
            console.error('[copilot/stream] upstream non-200',chatId,gwRes.statusCode,errBuf.slice(0,300));
            const errEvent='data: '+JSON.stringify({error:{message:'upstream HTTP '+gwRes.statusCode,detail:errBuf.slice(0,500)}})+'\n\n';
            if(!clientClosed){try{res.write(errEvent);res.write('data: [DONE]\n\n');res.end();}catch{}}
          });
          return;
        }
        let full='',buf='';
        gwRes.on('data',chunk=>{
          // 透传给客户端（如果还没断）
          if(!clientClosed){try{res.write(chunk);}catch{clientClosed=true;}}
          // 解析累积 full
          buf+=chunk.toString('utf-8');
          const lines=buf.split('\n');buf=lines.pop();
          for(const line of lines){
            if(!line.startsWith('data: '))continue;
            const data=line.slice(6).trim();
            if(!data||data==='[DONE]')continue;
            try{
              const j=JSON.parse(data);
              const delta=j.choices?.[0]?.delta?.content;
              if(typeof delta==='string'&&delta.length)full+=delta;
            }catch{}
          }
          if(full)schedulePersist(full);
        });
        gwRes.on('end',()=>{
          // 终态写一次
          if(pending&&pending.timer){clearTimeout(pending.timer);}
          pending=null;
          persist(full,true).then(()=>{
            console.log('[copilot/stream] done chatId='+chatId+' bytes='+full.length+' clientClosed='+clientClosed);
          });
          if(!clientClosed){try{res.end();}catch{}}
        });
        gwRes.on('error',e=>{
          console.error('[copilot/stream] upstream err',chatId,e.message);
          if(full)persist(full,true);
          if(!clientClosed){try{res.write('data: '+JSON.stringify({error:{message:e.message}})+'\n\n');res.end();}catch{}}
        });
      });
      gwReq.on('error',e=>{
        console.error('[copilot/stream] gw req err',chatId,e.message);
        if(!clientClosed){try{res.write('data: '+JSON.stringify({error:{message:'gateway connect: '+e.message}})+'\n\n');res.end();}catch{}}
      });
      gwReq.setTimeout(600000,()=>{
        console.error('[copilot/stream] gw req timeout',chatId);
        gwReq.destroy(new Error('timeout'));
      });
      gwReq.write(payload);
      gwReq.end();
    }catch(e){
      console.error('[copilot/stream] fatal',chatIdForLog,e.message);
      try{if(!res.headersSent)res.writeHead(500);res.end(JSON.stringify({error:e.message}));}catch{}
    }
  }else if(url.pathname==='/api/chat/send'&&req.method==='POST'){
    // 根治方案：fire-and-forget 。前端只用来触发生成，不等响应流。
    // 本服务器进程内部调 gateway，连接稳定，不受手机切 app 影响。
    try{
      const body=await readBody(req);
      const j=JSON.parse(body||'{}');
      const chatId=j.chatId||j.user;
      if(!chatId){res.writeHead(400);res.end(JSON.stringify({error:'chatId required'}));return;}
      // 读 token
      let token='';
      try{const cfg=JSON.parse(fs.readFileSync(path.join(ROOT,'.openclaw','openclaw.json'),'utf-8'));token=cfg?.gateway?.auth?.token||'';}catch{}
      // 先把 gateway 请求发出去，再回 202（避免 res.end 后的微任务调度被吞）
      const payload={model:j.model||'openclaw',stream:false,user:chatId,messages:j.messages||[]};
      console.log('[chat/send] dispatch chatId='+chatId+' model='+payload.model+' msgs='+payload.messages.length);
      // 记录 dispatch 状态，供 /api/chat/history 回报给前端
      global.__chatDispatch=global.__chatDispatch||{};
      global.__chatDispatch[chatId]={status:'pending',startedAt:Date.now(),error:null,httpStatus:null};
      const gwReq=http.request({host:'127.0.0.1',port:18789,path:'/v1/chat/completions',method:'POST',headers:{'Authorization':'Bearer '+token,'Content-Type':'application/json','Connection':'close'}},gwRes=>{
        let buf='';gwRes.on('data',c=>buf+=c);
        gwRes.on('end',()=>{
          console.log('[chat/send] gw done chatId='+chatId+' status='+gwRes.statusCode+' bytes='+buf.length);
          const d=global.__chatDispatch[chatId]||{};
          d.httpStatus=gwRes.statusCode;
          d.endedAt=Date.now();
          if(gwRes.statusCode>=400){d.status='error';d.error='HTTP '+gwRes.statusCode+': '+buf.slice(0,300);}
          else{d.status='done';}
          // 🔥 提取 assistant 回复并写回 chat 文件（之前丢了这步，导致手机刷新后回复消失）
          try{
            const j2=JSON.parse(buf);
            const reply=j2?.choices?.[0]?.message?.content;
            if(reply){
              const chatPath=path.join(ROOT,'.openclaw','chats',chatId+'.json');
              fs.mkdirSync(path.dirname(chatPath),{recursive:true});
              let chatDoc;
              try{chatDoc=JSON.parse(fs.readFileSync(chatPath,'utf-8'));}
              catch{chatDoc={id:chatId,title:'',messages:[],createdAt:Date.now(),updatedAt:Date.now()};}
              if(!Array.isArray(chatDoc.messages))chatDoc.messages=[];
              // 避免重复写入（如果最后一条已是该 reply）
              const last=chatDoc.messages[chatDoc.messages.length-1];
              if(!last||last.role!=='assistant'||last.content!==reply){
                chatDoc.messages.push({role:'assistant',content:reply});
                chatDoc.updatedAt=Date.now();
                const tmp=chatPath+'.tmp';
                fs.writeFileSync(tmp,JSON.stringify(chatDoc),'utf-8');
                fs.renameSync(tmp,chatPath);
                console.log('[chat/send] persisted assistant reply chatId='+chatId+' len='+reply.length);
              }
            }
          }catch(persistErr){console.error('[chat/send] persist failed chatId='+chatId+':',persistErr.message);}
        });
      });
      gwReq.on('error',e=>{
        console.error('[chat/send] gw error chatId='+chatId+':',e.message);
        const d=global.__chatDispatch[chatId]||{};d.status='error';d.error=e.message;d.endedAt=Date.now();
      });
      gwReq.on('timeout',()=>{
        console.error('[chat/send] gw TIMEOUT chatId='+chatId);
        const d=global.__chatDispatch[chatId]||{};d.status='error';d.error='timeout';d.endedAt=Date.now();
        gwReq.destroy(new Error('timeout'));
      });
      gwReq.setTimeout(600000);
      gwReq.write(JSON.stringify(payload));
      gwReq.end();
      // 再返回 202
      res.writeHead(202,{'Content-Type':'application/json'});
      res.end(JSON.stringify({accepted:true,chatId}));
    }catch(e){try{res.writeHead(500);res.end(JSON.stringify({error:e.message}));}catch{}}
  }else{res.writeHead(404);res.end('{"error":"not found"}');}
}).listen(PORT,'127.0.0.1',()=>{
  console.log('ok');
  // 🔒 启动时自愈：扫描所有 chat，对超过 5 分钟未更新但还 _streaming=true 的消息清掉标记
  // （防止上一次进程崩溃 / 上游断连造成遗留脓数据）
  try{
    const chatsDir=path.join(ROOT,'.openclaw','chats');
    if(fs.existsSync(chatsDir)){
      const cutoff=Date.now()-5*60*1000;
      let cleaned=0,touched=0;
      for(const f of fs.readdirSync(chatsDir)){
        if(!f.endsWith('.json'))continue;
        const fp=path.join(chatsDir,f);
        try{
          const c=JSON.parse(fs.readFileSync(fp,'utf-8'));
          if(!Array.isArray(c.messages))continue;
          if((c.updatedAt||0)>cutoff)continue; // 还可能在跑，不动
          let dirty=false;
          for(const m of c.messages){
            if(m._streaming){delete m._streaming;dirty=true;cleaned++;}
          }
          if(dirty){
            const tmp=fp+'.tmp';
            fs.writeFileSync(tmp,JSON.stringify(c),'utf-8');
            fs.renameSync(tmp,fp);
            touched++;
          }
        }catch{}
      }
      if(cleaned>0)console.log('[startup-heal] cleaned '+cleaned+' stale _streaming flags across '+touched+' chats');
    }
  }catch(e){console.error('[startup-heal] err',e.message);}
  // 预热 tasks 缓存 + 每 10s 后台刷新，让用户始终命中 HIT
  const refreshTasks=()=>{
    exec('openclaw tasks list --json 2>&1',{env:EXEC_ENV,maxBuffer:10*1024*1024,timeout:30000},(e,o)=>{
      if(e)return;
      try{JSON.parse(o);global._tasksCache=global._tasksCache||{};global._tasksCache['tasks|list|--json']={t:Date.now(),data:o}}catch{}
    });
  };
  refreshTasks();
  setInterval(refreshTasks,60000);
});
