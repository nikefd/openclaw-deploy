const http=require('http'),fs=require('fs'),path=require('path');
const PORT=7682,ROOT=process.env.HOME;
http.createServer((req,res)=>{
  res.setHeader('Content-Type','application/json');
  const url=new URL(req.url,'http://localhost:'+PORT);
  if(url.pathname==='/api/files/list'){
    const dir=url.searchParams.get('path')||ROOT;
    const r=path.resolve(dir);
    if(!r.startsWith(ROOT)){res.writeHead(403);res.end('{"error":"forbidden"}');return;}
    try{
      const e=fs.readdirSync(r,{withFileTypes:true}).map(x=>({name:x.name,path:path.join(r,x.name),type:x.isDirectory()?'dir':'file'})).filter(x=>!x.name.startsWith('.')).sort((a,b)=>a.type!==b.type?(a.type==='dir'?-1:1):a.name.localeCompare(b.name));
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
  }else{res.writeHead(404);res.end('{"error":"not found"}');}
}).listen(PORT,'127.0.0.1',()=>console.log('ok'));
