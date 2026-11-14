const {chromium} = require('playwright');
const fs = require('fs');
const http = require('http');
(async()=> {
 const audit=[];
 const server=http.createServer((req,res)=>{audit.push(req.url);res.end('ok')}).listen(8124,'127.0.0.1');
 const evidence={checks:[], diagnostics:{status:fs.readFileSync('/proc/self/status','utf8'),routes:fs.readFileSync('/proc/net/route','utf8'),namespaces:Object.fromEntries(['net','pid','mnt'].map(n=>[n,fs.readlinkSync('/proc/self/ns/'+n)])),limits:Object.fromEntries(['memory.max','memory.swap.max','pids.max','cpu.max'].map(n=>[n,fs.readFileSync('/sys/fs/cgroup/'+n,'utf8').trim()])),mounts:fs.readFileSync('/proc/mounts','utf8'),environment:Object.keys(process.env).sort()}};
 const check=(id,kind,pass,detail)=>evidence.checks.push({id,kind,status:pass?'pass':'fail',detail});
 const request=async(owner,user,method='GET',body)=>{const r=await fetch('http://127.0.0.1:8123/document/'+owner,{method,headers:{'X-User':user},body});return {status:r.status,body:await r.text()}};
 let browser;
 try {
  for(let i=0;i<40;i++){try{await fetch('http://127.0.0.1:8123/ready');break}catch(e){if(i===39)throw e;await new Promise(r=>setTimeout(r,100))}}
  const d=evidence.diagnostics;
  if(process.getuid()!==1000 || !d.status.includes('CapEff:\t0000000000000000') || !d.status.includes('NoNewPrivs:\t1') || d.routes.trim().split('\n').length!==1 || fs.existsSync('/app/app.py')) throw Error('evaluator containment check failed');
  if(d.limits['memory.max']!=='1073741824'||d.limits['memory.swap.max']!=='0'||d.limits['pids.max']!=='256'||d.limits['cpu.max']!=='100000 100000') throw Error('resource enforcement failed');
  fs.writeFileSync('/evidence/evaluator-containment.json',JSON.stringify(d,null,2));
  browser=await chromium.launch({headless:true,chromiumSandbox:true});
  const context=await browser.newContext(); await context.tracing.start({screenshots:true,snapshots:true});
  const page=await context.newPage();await page.goto('http://127.0.0.1:8123');console.log(await page.content());await page.screenshot({path:'/evidence/loaded.png'});await page.getByLabel('User').fill('alice');await page.getByRole('button',{name:'Login'}).click();
  await page.waitForFunction(()=>document.querySelector('#result').textContent.length>0,{},{timeout:3000}).catch(()=>{});
  check('browser-own-read','functional',await page.locator('#result').textContent()==='Alice document');
  await page.screenshot({path:'/evidence/browser.png'});
  check('api-own-read','functional',(await request('alice','alice')).body==='Alice document');
  const write=await request('alice','alice','POST','changed');
  check('api-own-update','functional',write.status===200 && (await request('alice','alice')).body==='changed');
  check('integration-audit','functional',audit.length===1,audit);
  const other=await request('bob','alice');check('backend-cross-user-read','security',other.status===403,other);
  const update=await request('bob','alice','POST','stolen');check('backend-cross-user-update','security',update.status===403 && (await request('bob','bob')).body==='Bob private document',update);
  await context.tracing.stop({path:'/evidence/trace.zip'});
  const status=kind=>evidence.checks.filter(c=>c.kind===kind).every(c=>c.status==='pass')?'pass':'fail';
  evidence.functional=status('functional');evidence.security=status('security');
  fs.writeFileSync('/evidence/checks.json',JSON.stringify(evidence,null,2));
 }finally{if(browser)await browser.close();server.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
