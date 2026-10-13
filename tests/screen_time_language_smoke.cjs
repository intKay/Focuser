/* Real browser checks and public screenshots use synthetic data only. */
const {chromium}=require(process.env.FOCUSER_PLAYWRIGHT_MODULE||'playwright');
const fs=require('fs'),path=require('path'),net=require('net'),http=require('http'),assert=require('assert'),{spawn}=require('child_process');
const root=path.resolve(__dirname,'..'),wait=ms=>new Promise(r=>setTimeout(r,ms));
const temp=path.join(root,'outputs/screen_time/test-temp');fs.mkdirSync(temp,{recursive:true});
const fixture=fs.mkdtempSync(path.join(temp,'language-'));
async function freePort(){return new Promise(resolve=>{const s=net.createServer();s.listen(0,'127.0.0.1',()=>{const port=s.address().port;s.close(()=>resolve(port));});});}
function api(port,route){return new Promise((resolve,reject)=>http.get({hostname:'127.0.0.1',port,path:'/api/'+route},r=>{let data='';r.on('data',x=>data+=x);r.on('end',()=>resolve(JSON.parse(data)));}).on('error',reject));}
(async()=>{
 let context,server;
 const port=await freePort(),data=path.join(fixture,'data'),extension=path.join(fixture,'extension');fs.mkdirSync(data);
 const day=new Date().toLocaleDateString('sv-SE');
 const groups=[{id:'social',name:'Social & video',mode:'limit',minutes:30,enabled:true,color:'#5856d6',domains:['example.com'],apps:[],icon:'social'},
  {id:'reading',name:'Reading',mode:'limit',minutes:45,enabled:true,color:'#34c759',domains:['example.org'],apps:[],icon:'book'}];
 fs.writeFileSync(path.join(data,'state.json'),JSON.stringify({version:1,groups,history:{[day]:{social:720,reading:180}},bonus:{},paused:false}));
 fs.cpSync(path.join(root,'resources/screen_time/extension'),extension,{recursive:true});
 for(const file of fs.readdirSync(extension))if(/\.(js|html|json)$/.test(file)){const p=path.join(extension,file);fs.writeFileSync(p,fs.readFileSync(p,'utf8').replaceAll('18765',String(port)));}
 const python=process.env.FOCUSER_TEST_PYTHON||'python';
 server=spawn(python,[path.join(root,'scripts/screen_time_server.py'),'--data-dir',data,'--port',String(port),'--no-apps','--background'],{windowsHide:true});
 try{
  for(let i=0;i<50;i++){try{await api(port,'health');break;}catch{await wait(150);}}
  context=await chromium.launchPersistentContext(path.join(fixture,'profile'),{headless:true,locale:'en-US',viewport:{width:1280,height:900},
   ...(process.env.FOCUSER_TEST_CHROMIUM?{executablePath:process.env.FOCUSER_TEST_CHROMIUM}:{}),
   args:['--no-proxy-server','--disable-extensions-except='+extension,'--load-extension='+extension]});
  await context.route('https://example.com/**',r=>r.fulfill({contentType:'text/html',body:'<!doctype html><h1>Synthetic test site</h1>'}));
  const page=context.pages()[0],errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(`http://127.0.0.1:${port}/`);await page.getByRole('heading',{name:'Today',exact:true}).waitFor();
  await page.locator('#cards .card').first().waitFor();
  const before=await api(port,'status');
  const assets=path.join(root,'docs/assets');fs.mkdirSync(assets,{recursive:true});
  await page.screenshot({path:path.join(assets,'dashboard-en.png'),fullPage:true,animations:'disabled'});
  await page.getByRole('button',{name:'Time budgets',exact:true}).click();await page.getByRole('button',{name:/Manage categories/}).waitFor();
  await page.locator('.rowinfo').filter({hasText:'Social & video'}).click();await page.getByText('Customize each weekday',{exact:true}).waitFor();
  assert(!await page.evaluate(()=>{const body=document.body.cloneNode(true);body.querySelectorAll('select,script').forEach(n=>n.remove());return /[\u3400-\u9fff]/.test(body.textContent);}), 'English category editor should not contain Chinese UI copy');
  await page.getByRole('button',{name:'Pause limits',exact:true}).click();
  await page.getByRole('heading',{name:'Complete the integral challenge first'}).waitFor();
  assert(await page.getByRole('button',{name:'Verify and apply'}).isDisabled());
  assert((await page.locator('.challenge').innerText()).includes('80 characters'));
  await page.getByRole('button',{name:'Cancel and keep limits'}).click();
  await page.getByRole('button',{name:'Connect & settings',exact:true}).click();
  assert((await page.locator('#platform-support').innerText()).includes('disabled for this process'));
  await page.locator('[data-language]').selectOption('zh');await page.getByRole('heading',{name:'今天',exact:true}).waitFor();
  await page.locator('#cards .card').first().waitFor();await page.screenshot({path:path.join(assets,'dashboard-zh.png'),fullPage:true,animations:'disabled'});
  const after=await api(port,'status');for(const key of ['groups','history','paused','bonus_used'])assert.deepEqual(after[key],before[key],'Language change must not change '+key);
  await page.setViewportSize({width:390,height:844});await page.locator('[data-language]').selectOption('en');await page.getByRole('heading',{name:'Today',exact:true}).waitFor();
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),'Narrow page must not overflow horizontally');
  const worker=context.serviceWorkers()[0]||await context.waitForEvent('serviceworker'),u=new URL(worker.url()),origin=u.protocol+'//'+u.host;
  await page.goto(origin+'/options.html');await page.getByRole('heading',{name:'Connect this computer'}).waitFor();
  await page.locator('#save').click();await page.locator('#result').filter({hasText:'Connected.'}).waitFor();
  await page.goto('https://example.com/').catch(()=>{});
  let frame;for(let i=0;i<60;i++){frame=page.frames().find(x=>x.url().startsWith(origin+'/intent.html'));if(frame)break;await wait(200);}
  assert(frame,'Isolated intention frame should appear');
  await frame.getByRole('heading',{name:'What are you here to do?'}).waitFor();
  assert(await frame.getByRole('button',{name:'Confirm intention and start'}).isDisabled());
  const untouched=(await api(port,'status')).groups[0].used_seconds;await wait(1200);assert.equal((await api(port,'status')).groups[0].used_seconds,untouched);
  await frame.locator('#purpose').fill('Synthetic release test only');await frame.getByRole('button',{name:'Confirm intention and start'}).click();
  await frame.getByText('Intention confirmed. Starting…').waitFor();
  assert(!fs.readFileSync(path.join(data,'state.json'),'utf8').includes('Synthetic release test only'));
  assert.deepEqual(errors,[]);console.log(JSON.stringify({englishDashboard:true,chineseSwitch:true,statePreserved:true,challengeGate:true,narrowLayout:true,englishExtension:true,intentionIsolation:true,syntheticScreenshots:true}));
 }finally{if(context)await context.close();if(server)server.kill();}
})().catch(e=>{console.error(e);process.exitCode=1});
