from pathlib import Path
p=Path('app/infrastructure/application/sandbox.py');s=p.read_text(encoding='utf-8').replace('[asdict(v) for v in config.viewports if v.screenshot]','[asdict(v) for v in config.viewports]');p.write_text(s,encoding='utf-8')
p=Path('sandbox_runtime/runner.mjs');s=p.read_text(encoding='utf-8');s=s.replace("import os from 'node:os';","import os from 'node:os';\nimport net from 'node:net';")
s=s.replace('if(request.health){', '''if(request.probe_timeout){await new Promise(resolve=>setTimeout(resolve,30000));process.exit(0)}
if(request.probe){
 const network_blocked=await new Promise(resolve=>{const socket=net.connect({host:'1.1.1.1',port:443});socket.setTimeout(1000);socket.on('connect',()=>{socket.destroy();resolve(false)});socket.on('error',()=>resolve(true));socket.on('timeout',()=>{socket.destroy();resolve(true)})});
 await fs.writeFile('/work/probe','allowed');
 const root_readonly=await fs.writeFile('/runtime/probe','blocked').then(()=>false,()=>true);
 const host_paths_absent=!(await fs.stat('/var/run/docker.sock').catch(()=>null))&&!(await fs.stat('/host').catch(()=>null))&&!(await fs.stat('/root/.env').catch(()=>null));
 const secrets_absent=!Object.keys(process.env).some(k=>/GROQ|SUPABASE|DATABASE|ADMIN|SECRET|TOKEN/.test(k));
 process.stdout.write(JSON.stringify({network_blocked,secrets_absent,host_paths_absent,workspace_writable:(await fs.readFile('/work/probe','utf8'))==='allowed',root_readonly,non_root:process.getuid()!==0}));process.exit(0);
}
if(request.health){''')
s=s.replace('for(const view of request.viewports){const {page,context}=await pageFor(view);try{result.screenshots.push', 'for(const view of request.viewports.filter(v=>v.screenshot)){let context;try{const entry=await pageFor(view);context=entry.context;const page=entry.page;result.screenshots.push')
s=s.replace('finally{await context.close()}}','catch{}finally{if(context)await context.close()}}')
s=s.replace('const entry=await pageFor(request.viewports[0]);','const view=request.viewports.find(v=>v.id===check.parameters.viewports[0]);\n   const entry=await pageFor(view);')
p.write_text(s,encoding='utf-8')
