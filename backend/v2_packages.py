import json
from pathlib import Path
from dataclasses import asdict
from app.domains.application.sandbox import SandboxPolicy
ROOT=Path('application_challenges')
common={'private':True,'version':'1.0.0','type':'module','dependencies':{'react':'19.2.0','react-dom':'19.2.0'},'devDependencies':{'typescript':'5.9.3','esbuild':'0.25.12','@types/react':'19.2.0','@types/react-dom':'19.2.0'}}
style='''*{box-sizing:border-box}body{margin:0;background:#f4f2ec;color:#232821;font:16px system-ui}header,footer{padding:24px clamp(20px,6vw,80px);border-bottom:1px solid #d9ddd0}header{display:flex;justify-content:space-between}main{max-width:1080px;margin:64px auto;padding:0 24px}h1{font-size:clamp(32px,5vw,52px);letter-spacing:-.05em;line-height:1.08}p{color:#63705f;line-height:1.6}small,.eyebrow{font-size:11px;letter-spacing:.13em;text-transform:uppercase}section{background:#fff;padding:32px;border:1px solid #dce0d3;border-radius:16px}form{display:grid;gap:18px;max-width:420px}label{display:grid;gap:8px;font-size:13px;font-weight:600}input,select,button{font:inherit;padding:12px;border:1px solid #bec8b5;border-radius:6px;max-width:100%}button{background:#364e38;color:white;cursor:pointer}button:focus-visible,input:focus-visible,select:focus-visible{outline:3px solid #859c67;outline-offset:3px}[role=alert]{color:#a03932;font-size:13px;margin:0}[role=status]{color:#376035}.products{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px;list-style:none;padding:0}.products li{padding:24px;background:#e8eddf;border-radius:10px}.controls{display:flex;gap:14px;align-items:end;flex-wrap:wrap}.controls label{flex:1}footer{margin-top:70px;font-size:12px}@media(max-width:600px){main{margin:32px auto}section{padding:20px}.products{grid-template-columns:1fr}.controls{align-items:stretch;flex-direction:column}}
'''
main='''import React from 'react';
import {createRoot} from 'react-dom/client';
import App from './App';
import './styles.css';
createRoot(document.getElementById('root')!).render(<><header><strong>forma / studio</strong><span>Thoughtfully simple.</span></header><main><App /></main><footer>Forma Studio · Made for everyday progress.</footer></>);
'''
signup='''import React, {useState} from 'react';
import {validate} from './validation';
export default function App(){
 const [email,setEmail]=useState(''),[password,setPassword]=useState('');
 const [errors,setErrors]=useState<{email?:string;password?:string}>({});
 const [done,setDone]=useState(false);
 function submit(e:React.FormEvent){e.preventDefault();const next=validate(email,password);setErrors(next);setDone(!Object.keys(next).length)}
 return <><p className="eyebrow">YOUR NEXT CHAPTER</p><h1>A little space.<br/>For big ideas.</h1><p>Join Forma and make room for your next project.</p><section><h2>Create your account</h2><form noValidate onSubmit={submit}><label>Email address<input name="email" aria-label="Email address" value={email} onChange={e=>{setEmail(e.target.value);setDone(false)}} aria-describedby="email-error"/></label><p id="email-error" role="alert">{errors.email}</p><label>Password<input name="password" aria-label="Password" type="password" value={password} onChange={e=>{setPassword(e.target.value);setDone(false)}} aria-describedby="password-error"/></label><p id="password-error" role="alert">{errors.password}</p><small>Use at least 8 characters.</small><button type="submit">Create account</button><p role="status">{done?'Account created':''}</p></form></section></>;
}
'''
validation="export function validate(email:string,password:string):{email?:string;password?:string}{ void email; void password; return {}; }\n"
products="export const products=[{id:1,name:'Field Notebook',category:'paper',price:12},{id:2,name:'Weekly Planner',category:'paper',price:24},{id:3,name:'Desk Lamp',category:'desk',price:48},{id:4,name:'Oak Stand',category:'desk',price:32},{id:5,name:'Canvas Tote',category:'carry',price:28},{id:6,name:'Travel Pouch',category:'carry',price:18}];\n"
filterapp='''import React,{useState} from 'react';
import {products} from './products';
import {filterProducts} from './filter';
export default function App(){
 const [query,setQuery]=useState(''),[category,setCategory]=useState('all');
 const shown=filterProducts(products,query,category);
 return <><p className="eyebrow">THE EVERYDAY COLLECTION</p><h1>Less clutter.<br/>More possibility.</h1><p>Useful objects for thoughtful work.</p><section><div className="controls"><label>Search<input aria-label="Search products" value={query} onChange={e=>setQuery(e.target.value)}/></label><label>Category<select aria-label="Category" value={category} onChange={e=>setCategory(e.target.value)}><option value="all">All products</option><option value="paper">Paper</option><option value="desk">Desk</option><option value="carry">Carry</option></select></label><button onClick={()=>setQuery('')}>Clear filters</button></div><p role="status">{shown.length} products</p><ul className="products">{shown.map(p=><li key={p.id}><small>{p.category}</small><h2>{p.name}</h2><p>${p.price}</p></li>)}</ul>{!shown.length&&<p data-testid="empty">No products found. Try another search.</p>}</section></>;
}
'''
filterfn="type Product={id:number;name:string;category:string;price:number};\nexport function filterProducts(items:Product[],query:string,category:string){void query;void category;return items;}\n"
def step(action,selector,value=None,count=None):
 d={'action':action,'selector':selector}
 if value is not None:d['value']=value
 if count is not None:d['count']=count
 return d
F=lambda s,v:step('fill',s,v)
C=lambda s:step('click',s)
T=lambda s,v:step('text',s,v)
N=lambda n:step('count','.products li',count=n)
# select uses a separate trusted action, never browser JavaScript.
S=lambda v:step('select','select',v)
def check(id,label,steps):return {'id':id,'implementation':'interaction','label':label,'parameters':{'viewports':['desktop'],'steps':steps}}
def submit(email,password,expected):return [F('[name=email]',email),F('[name=password]',password),C('button[type=submit]'),T('[role=status]',expected)]
signchecks=[
 check('bad_email','Malformed email is rejected',submit('not-an-email','abcdefgh','')+[T('#email-error','Enter a valid email address.')]),
 check('short_password','Passwords shorter than 8 characters are rejected',submit('alex@example.com','short','')+[T('#password-error','Use at least 8 characters.')]),
 check('valid_signup','A valid form creates an account',submit('alex@example.com','abcdefgh','Account created')),
 check('empty_fields','Required fields cannot be empty',submit('','','')+[T('#email-error','Enter a valid email address.'),T('#password-error','Use at least 8 characters.')]),
 check('trim_email','Email whitespace is normalized',submit('  alex@example.com  ','abcdefgh','Account created')),
 check('uncommon_email','Valid plus-address email works',submit('alex+notes@studio.example','abcdefgh','Account created')),
 check('password_boundary','Eight characters pass and seven fail',submit('a@example.com','1234567','')+submit('a@example.com','12345678','Account created')),
 check('correct_errors','Feedback clears when fields are corrected',submit('bad','x','')+[F('[name=email]','a@example.com'),F('[name=password]','abcdefgh'),T('#email-error',''),T('#password-error','')]),
 check('keyboard_submit','Enter submits the valid form',[F('[name=email]','a@example.com'),F('[name=password]','abcdefgh'),step('press','[name=password]','Enter'),T('[role=status]','Account created')]),
 check('page_preserved','Unrelated page content stays visible',[T('header strong','forma / studio'),T('footer','Forma Studio · Made for everyday progress.')])]
filterchecks=[
 check('category','Category selection narrows the product list',[S('desk'),N(2),T('.products li h2','Desk Lamp|Oak Stand')]),
 check('clear','Clear filters restores all products',[S('paper'),F('input','Notebook'),C('button'),N(6)]),
 check('empty','No-results state explains an empty list',[F('input','zzzzzz'),N(0),step('visible','[data-testid=empty]')]),
 check('combined','Search and category work together',[S('paper'),F('input','weekly'),N(1),T('.products h2','Weekly Planner')]),
 check('case_insensitive','Search ignores letter case',[F('input','nOtEbOoK'),N(1)]),
 check('whitespace','Search trims surrounding whitespace',[F('input','  lamp  '),N(1),T('.products h2','Desk Lamp')]),
 check('switch_category','Switching categories recomputes results',[S('desk'),N(2),S('carry'),N(2),T('.products li h2','Canvas Tote|Travel Pouch')]),
 check('keyboard_clear','Clear filters is keyboard accessible',[S('desk'),step('press','button','Enter'),N(6)]),
 check('data_preserved','All product names and prices remain unchanged',[N(6),T('.products h2','Field Notebook|Weekly Planner|Desk Lamp|Oak Stand|Canvas Tote|Travel Pouch'),T('.products li p','$12|$24|$48|$32|$28|$18')]),
 check('page_preserved','Unrelated page content stays visible',[T('header strong','forma / studio'),T('footer','Forma Studio · Made for everyday progress.')])]
for slug,title,app,helper,checks in [('broken-signup-validation','Broken Signup Validation',signup,('validation.ts',validation),signchecks),('product-filter','Product Filter',filterapp,('filter.ts',filterfn),filterchecks)]:
 root=ROOT/slug.replace('-','_'); starter=root/'starter';(starter/'src').mkdir(parents=True,exist_ok=True)
 def write(name,value):(starter/name).write_text(value,encoding='utf-8')
 write('src/main.tsx',main);write('src/App.tsx',app);write('src/'+helper[0],helper[1]);write('src/styles.css',style)
 if slug=='product-filter':write('src/products.ts',products)
 write('index.html','<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+title+'</title><link rel="stylesheet" href="/app.css"></head><body><div id="root"></div><script src="/app.js"></script></body></html>')
 write('package.json',json.dumps({'name':slug,**common},indent=2)+'\n')
 write('tsconfig.json',json.dumps({'compilerOptions':{'target':'ES2022','lib':['ES2022','DOM'],'jsx':'react-jsx','module':'ESNext','moduleResolution':'Bundler','strict':True,'noEmit':True,'skipLibCheck':True},'include':['src']},indent=2)+'\n')
 build={'id':'build','implementation':'build_succeeds','label':'App typechecks and builds','parameters':{}}
 protected={'id':'protected','implementation':'protected_files_unchanged','label':'Protected files stay unchanged','parameters':{}}
 defaults={'schema_version':1,'execution_mode':'sandboxed_executable','starter_project':slug,'page_source':'index.html','editable_files':['src/App.tsx','src/'+helper[0]],'build_command':['sandbox','build'],'build_output':'dist/index.html','visible_checks':['build',*[c['id'] for c in checks[:3]]],'hidden_checks':['build',*[c['id'] for c in checks],'protected'],'viewports':[{'id':'desktop','width':1280,'height':800,'label':'App view','screenshot':True},{'id':'mobile','width':390,'height':844,'label':'Phone','screenshot':True}],'limits':{'agent_timeout_seconds':90,'build_timeout_seconds':20,'browser_timeout_seconds':20,'max_file_bytes':32000,'max_files':2,'max_log_chars':2000}}
 manifest={'id':slug,'display_name':title,'description':'Fix interactive behavior while preserving the existing design and content.','defaults':defaults,'checks':[build,*checks,protected],'protected_paths':['package.json','package-lock.json','tsconfig.json','index.html','src/main.tsx','src/styles.css']+(['src/products.ts'] if slug=='product-filter' else []),'sandbox':asdict(SandboxPolicy())}
 (root/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
