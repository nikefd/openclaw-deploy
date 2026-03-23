const http=require('http'),fs=require('fs'),path=require('path');
const PORT=7682,ROOT=process.env.HOME;
const CHATS_FILE=path.join(ROOT,'.openclaw','chat-history.json');
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
  }else if(url.pathname==='/api/files/read'){
    const fp=url.searchParams.get('path');
    if(!fp){res.writeHead(400);res.end('{"error":"need path"}');return;}
    const r=path.resolve(fp);
    if(!r.startsWith(ROOT)){res.writeHead(403);res.end('{"error":"forbidden"}');return;}
    try{const s=fs.statSync(r);if(s.size>1048576){res.writeHead(413);res.end('{"error":"too big"}');return;}
      res.end(JSON.stringify({path:r,size:s.size,content:fs.readFileSync(r,'utf-8')}));
    }catch(e){res.writeHead(500);res.end(JSON.stringify({error:e.message}));}
  }else if(url.pathname==='/api/chats'&&req.method==='GET'){
    try{const d=fs.existsSync(CHATS_FILE)?fs.readFileSync(CHATS_FILE,'utf-8'):'[]';res.end(d);}
    catch(e){res.writeHead(500);res.end(JSON.stringify({error:e.message}));}
  }else if(url.pathname==='/api/chats'&&req.method==='POST'){
    try{const body=await readBody(req);JSON.parse(body);fs.mkdirSync(path.dirname(CHATS_FILE),{recursive:true});fs.writeFileSync(CHATS_FILE,body,'utf-8');res.end('{"ok":true}');}
    catch(e){res.writeHead(500);res.end(JSON.stringify({error:e.message}));}
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
  }else{res.writeHead(404);res.end('{"error":"not found"}');}
}).listen(PORT,'127.0.0.1',()=>console.log('ok'));
