// Trusted controller; this file is installed into a read-only prepared image.
import fs from 'node:fs/promises';
import path from 'node:path';
import http from 'node:http';
import os from 'node:os';
import net from 'node:net';
import {spawn} from 'node:child_process';
import {performance} from 'node:perf_hooks';
import {chromium, expect} from '@playwright/test';

let input='';
for await(const chunk of process.stdin){input+=chunk;if(input.length>2000000)process.exit(2)}
const request=JSON.parse(input);
const metrics={};
async function command(id,argv,seconds){
 const start=performance.now();
 const child=spawn(argv[0],argv.slice(1),{cwd:'/work',env:{PATH:'/usr/local/bin:/usr/bin:/bin',HOME:'/tmp',NODE_ENV:'production'},stdio:['ignore','pipe','pipe']});
 // Discard untrusted compiler output, never let pipes or diagnostic storage grow.
 child.stdout.on('data',()=>{});child.stderr.on('data',()=>{});
 let timeout=false;const timer=setTimeout(()=>{timeout=true;child.kill('SIGKILL')},seconds*1000);
 const code=await new Promise(resolve=>{child.on('error',()=>resolve(-1));child.on('close',resolve)});
 clearTimeout(timer);metrics[id]=(performance.now()-start)/1000;
 return {command_id:id,exit_code:code,stdout:'',stderr:'',duration_seconds:metrics[id],timed_out:timeout,resource_limited:code===137};
}
async function browser(){return chromium.launch({headless:true,chromiumSandbox:true,args:['--disable-dev-shm-usage']})}
if(request.probe_timeout){await new Promise(resolve=>setTimeout(resolve,30000));process.exit(0)}
if(request.probe){
 const network_blocked=await new Promise(resolve=>{const socket=net.connect({host:'1.1.1.1',port:443});socket.setTimeout(1000);socket.on('connect',()=>{socket.destroy();resolve(false)});socket.on('error',()=>resolve(true));socket.on('timeout',()=>{socket.destroy();resolve(true)})});
 await fs.writeFile('/work/probe','allowed');
 const root_readonly=await fs.writeFile('/runtime/probe','blocked').then(()=>false,()=>true);
 const host_paths_absent=!(await fs.stat('/var/run/docker.sock').catch(()=>null))&&!(await fs.stat('/host').catch(()=>null))&&!(await fs.stat('/root/.env').catch(()=>null));
 const secrets_absent=!Object.keys(process.env).some(k=>/GROQ|SUPABASE|DATABASE|ADMIN|SECRET|TOKEN/.test(k));
 process.stdout.write(JSON.stringify({network_blocked,secrets_absent,host_paths_absent,workspace_writable:(await fs.readFile('/work/probe','utf8'))==='allowed',root_readonly,non_root:process.getuid()!==0}));process.exit(0);
}
if(request.health){
 // These files expose the container's actual delegated cgroup, not CLI configuration.
 const memory=Number((await fs.readFile('/sys/fs/cgroup/memory.max','utf8')).trim());
 const pids=Number((await fs.readFile('/sys/fs/cgroup/pids.max','utf8')).trim());
 const cpu=(await fs.readFile('/sys/fs/cgroup/cpu.max','utf8')).trim().split(' ').map(Number);
 if(!Number.isFinite(memory)||memory>1073741824||!Number.isFinite(pids)||pids>256||!Number.isFinite(cpu[0])||cpu[0]/cpu[1]>2)process.exit(2);
 if(Object.keys(os.networkInterfaces()).some(n=>n!=='lo')||process.getuid()===0)process.exit(2);
 if(await fs.stat('/var/run/docker.sock').catch(()=>null))process.exit(2);
 const b=await browser();await b.close();process.stdout.write(JSON.stringify({healthy:true}));process.exit(0);
}
for(const [name,encoded] of Object.entries(request.files)){
 if(!/^[a-zA-Z0-9_./-]+$/.test(name)||name.split('/').some(p=>!p||p==='.'||p==='..')||path.isAbsolute(name))process.exit(2);
 const target=path.join('/work',name);await fs.mkdir(path.dirname(target),{recursive:true});await fs.writeFile(target,Buffer.from(encoded,'base64'));
}
await fs.symlink('/runtime/node_modules','/work/node_modules','dir');
const typecheck=await command('typecheck',['node','/runtime/node_modules/typescript/bin/tsc','--project','/work/tsconfig.json'],Math.min(request.build_timeout,20));
const build=typecheck.exit_code===0?await command('build',['/runtime/node_modules/.bin/esbuild','src/main.tsx','--bundle','--outfile=dist/app.js','--platform=browser','--format=iife','--define:process.env.NODE_ENV="production"'],Math.min(request.build_timeout,20)):typecheck;
const result={build:build.exit_code===0,checks:{},screenshots:[],commands:[typecheck,build],metrics};
if(!result.build){process.stdout.write(JSON.stringify(result));process.exit(0)}
await fs.copyFile('/work/index.html','/work/dist/index.html');
// Only these immutable generated assets can be requested. No file:// routes, no source files.
const assets=new Map(await Promise.all([['/','index.html','text/html'],['/app.js','app.js','text/javascript'],['/app.css','app.css','text/css']].map(async([url,file,mime])=>[url,{body:await fs.readFile('/work/dist/'+file),mime}])));
const server=http.createServer((req,res)=>{const asset=assets.get(req.url);if(!asset){res.writeHead(404);res.end();return}res.writeHead(200,{'Content-Type':asset.mime,'Cache-Control':'no-store','Content-Security-Policy':"default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src data:; connect-src 'none'; form-action 'none'; base-uri 'none'"});res.end(asset.body)});
await new Promise(resolve=>server.listen(4173,'127.0.0.1',resolve));
const start=performance.now();const b=await browser();
async function pageFor(view){
 const context=await b.newContext({viewport:{width:view.width,height:view.height},serviceWorkers:'block',acceptDownloads:false,locale:'en-US',timezoneId:'UTC',reducedMotion:'reduce'});
 await context.route('**/*',r=>r.request().url().startsWith('http://127.0.0.1:4173/')?r.continue():r.abort());
 const page=await context.newPage();page.setDefaultTimeout(1500);page.on('dialog',d=>d.dismiss());
 await page.goto('http://127.0.0.1:4173/',{waitUntil:'load',timeout:5000});await page.locator('#root > header').waitFor();
 return {context,page};
}
try{
 // Capture fresh public state before hidden interactions. Never screenshot a hidden scenario.
 for(const view of request.viewports.filter(v=>v.screenshot)){let context;try{const entry=await pageFor(view);context=entry.context;const page=entry.page;result.screenshots.push({viewport:view.id,png:(await page.screenshot({animations:'disabled'})).toString('base64')})}catch{}finally{if(context)await context.close()}}
 for(const check of request.checks){let context;try{
   const view=request.viewports.find(v=>v.id===check.parameters.viewports[0]);
   const entry=await pageFor(view);context=entry.context;const page=entry.page;
   for(const step of check.parameters.steps){const locator=page.locator(step.selector);
     switch(step.action){
       case 'fill':await locator.fill(step.value);break;
       case 'select':await locator.selectOption(step.value);break;
       case 'click':await locator.click();break;
       case 'press':await locator.press(step.value);break;
       case 'count':await expect(locator).toHaveCount(step.count);break;
       case 'visible':await expect(locator).toBeVisible();break;
       case 'hidden':await expect(locator).toBeHidden();break;
       case 'text':await expect(locator).toHaveText(step.value.includes('|')?step.value.split('|'):step.value);break;
       default:throw new Error('Unsupported trusted action');
     }
   }
   result.checks[check.id]=true;
 }catch{result.checks[check.id]=false}finally{if(context)await context.close()}}
}finally{await b.close();await new Promise(resolve=>server.close(resolve));metrics.browser=(performance.now()-start)/1000}
process.stdout.write(JSON.stringify(result));
