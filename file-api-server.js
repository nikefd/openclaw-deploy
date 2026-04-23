const http=require('http'),fs=require('fs'),path=require('path'),zlib=require('zlib');
const {exec}=require('child_process');
// Strip large base64 payloads (images/attachments) from a chat for the summary list.
// Keeps message text for client-side search; marks messages so UI can lazy-load full content.
function stripHeavy(chat){
  if(!chat||!Array.isArray(chat.messages))return chat;
  let hadHeavy=false;
  const messages=chat.messages.map(m=>{
    if(!m||typeof m!=='object')return m;
    const out={...m};
    let touched=false;
    if(Array.isArray(out.images)&&out.images.length){
      // Keep count, drop base64 data
      const n=out.images.length;
      out.images=Array(n).fill('[image]');
      touched=true;
    }
    if(Array.isArray(out.attachments)&&out.attachments.length){
      out.attachments=out.attachments.map(a=>{
        if(!a||typeof a!=='object')return a;
        const { data, content, base64, ...rest }=a;
        if(data||content||base64)touched=true;
        return rest;
      });
    }
    if(typeof out.image==='string'&&out.image.length>200){out.image='[image]';touched=true;}
    if(touched){out._stripped=true;hadHeavy=true;}
    return out;
  });
  return hadHeavy?{...chat,messages,_stripped:true}:chat;
}
function sendJson(req,res,obj){
  const body=typeof obj==='string'?obj:JSON.stringify(obj);
  const ae=String(req.headers['accept-encoding']||'');
  if(/\bgzip\b/.test(ae)&&body.length>1024){
    zlib.gzip(body,(err,buf)=>{
      if(err){res.end(body);return;}
      res.setHeader('Content-Encoding','gzip');
      res.setHeader('Vary','Accept-Encoding');
      res.end(buf);
    });
  }else{res.end(body);}
}
const EXEC_ENV=Object.assign({},process.env,{PATH:'/home/nikefd/.npm-global/bin:/usr/local/bin:/usr/bin:/bin:'+process.env.PATH});
const PORT=7682,ROOT=process.env.HOME;
const CHATS_FILE=path.join(ROOT,'.openclaw','chat-history.json');
const CHATS_DIR=path.join(ROOT,'.openclaw','chats');
const PERF_LOG_FILE=path.join(ROOT,'.openclaw','perf-log.json');
function readBody(req){return new Promise((ok,no)=>{let d='';req.on('data',c=>d+=c);req.on('end',()=>ok(d));req.on('error',no);});}
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
    const wantFull=url.searchParams.get('full')==='1';
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
      all.sort((a,b)=>(b.updatedAt||0)-(a.updatedAt||0));
      const out=wantFull?all:all.map(stripHeavy);
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
      fs.writeFileSync(path.join(CHATS_DIR,chatId+'.json'),JSON.stringify(chat),'utf-8');
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
    exec('openclaw '+args.join(' ')+' 2>&1',{env:EXEC_ENV,maxBuffer:10*1024*1024},(e,o)=>{
      if(e){res.writeHead(500);res.end(JSON.stringify({error:e.message,raw:o}));return;}
      try{JSON.parse(o);res.end(o);}catch{res.writeHead(500);res.end(JSON.stringify({error:'parse error',raw:o}));}
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
  }else{res.writeHead(404);res.end('{"error":"not found"}');}
}).listen(PORT,'127.0.0.1',()=>console.log('ok'));
