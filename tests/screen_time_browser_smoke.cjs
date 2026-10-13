/* Opt-in real-browser regression. Temporary profiles and ports, no live data. */
const {chromium}=require(process.env.FOCUSER_PLAYWRIGHT_MODULE||'playwright');
const fs=require('fs'),path=require('path'),http=require('http'),net=require('net'),assert=require('assert'),{spawn}=require('child_process');
const root=path.resolve(__dirname,'..');
const wait=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const tempRoot=path.join(root,'outputs/screen_time/test-temp');fs.mkdirSync(tempRoot,{recursive:true});
const fixture=fs.mkdtempSync(path.join(tempRoot,'browser-'));
const day=new Date().toLocaleDateString('sv-SE');
function freePort(){return new Promise(resolve=>{const server=net.createServer();server.listen(0,'127.0.0.1',()=>{const port=server.address().port;server.close(()=>resolve(port));});});}
function api(port,route,body){return new Promise((resolve,reject)=>{const req=http.request({hostname:'127.0.0.1',port,path:'/api/'+route,method:body?'POST':'GET',headers:body?{'Content-Type':'application/json'}:{}},r=>{let data='';r.on('data',part=>data+=part);r.on('end',()=>resolve({code:r.statusCode,data:JSON.parse(data)}));});req.on('error',reject);req.end(body?JSON.stringify(body):undefined);});}
async function ready(port){for(let i=0;i<60;i++){try{if((await api(port,'health')).code===200)return;}catch{}await wait(200);}throw Error('Fixture service did not start');}
(async()=>{
 let context,server,other;const checks={},errors=[];
 const port=await freePort(),otherPort=await freePort();
 const data=path.join(fixture,'data');fs.mkdirSync(data);
 fs.writeFileSync(path.join(data,'state.json'),JSON.stringify({version:1,paused:false,bonus:{},history:{[day]:{social:60}},groups:[{id:'douyin',name:'抖音',mode:'block',minutes:0,enabled:true,color:'#ff375f',domains:['douyin.com'],apps:[]},{id:'social',name:'浏览器隔离测试',mode:'limit',minutes:1,enabled:true,color:'#5856d6',domains:['example.com'],apps:[]}]}));
 const extension=path.join(fixture,'extension');fs.cpSync(path.join(root,'resources/screen_time/extension'),extension,{recursive:true});
 // Seed a fixture-only default so no worker ever probes the user's 18765 port.
 for(const file of fs.readdirSync(extension))if(/\.(js|html)$/.test(file)){const p=path.join(extension,file);fs.writeFileSync(p,fs.readFileSync(p,'utf8').replaceAll('18765',String(port)));}
 const python=process.env.FOCUSER_TEST_PYTHON||'python';
 function start(port,data){return spawn(python,[path.join(root,'scripts/screen_time_server.py'),'--port',String(port),'--data-dir',data,'--no-apps','--no-ui'],{windowsHide:true,env:{...process.env,PYTHONUTF8:'1'}});}
 try{
  server=start(port,data);await ready(port);other=start(otherPort,path.join(fixture,'other-data'));await ready(otherPort);
  context=await chromium.launchPersistentContext(path.join(fixture,'profile'),{headless:true,locale:'zh-CN',...(process.env.FOCUSER_TEST_CHROMIUM?{executablePath:process.env.FOCUSER_TEST_CHROMIUM}:{}),viewport:{width:1280,height:900},args:['--no-proxy-server','--disable-extensions-except='+extension,'--load-extension='+extension]});
  await context.route('https://example.com/**',route=>route.fulfill({contentType:'text/html',body:'<!doctype html><title>Isolated site</title><h1>Fixture page</h1>'}));
  const worker=context.serviceWorkers()[0]||await context.waitForEvent('serviceworker');const workerURL=new URL(worker.url());const extensionOrigin=workerURL.protocol+'//'+workerURL.host;
  const page=context.pages()[0];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:'+port+'/');await page.locator('#cards .card').first().waitFor();
  checks.controlPage=await page.locator('#title').innerText()==='今天';
  await page.getByRole('button',{name:'连接与设置',exact:true}).click();
  checks.downloadLinks=await page.locator('a[href="/extensions/chromium.zip"]').count()===1;
  checks.browserOnlyCapability=(await page.locator('#platform-support').innerText()).includes('禁用了');
  await page.screenshot({path:path.join(fixture,'setup.png'),fullPage:true});
  await page.getByRole('button',{name:'暂停限制',exact:true}).click();
  checks.challengeDisabled=await page.getByRole('button',{name:'验算并执行'}).isDisabled();
  await page.getByRole('button',{name:'保留限制，取消'}).click();checks.cancelKeepsLimits=!(await api(port,'status')).data.paused;
  await page.goto(extensionOrigin+'/options.html');await page.locator('#port').waitFor();
  await page.locator('#port').fill(String(port));await page.locator('#save').click();await page.locator('#result').filter({hasText:'已连接'}).waitFor();checks.optionsConnect=true;
  await page.locator('#port').fill(String(otherPort));await page.locator('#save').click();await page.locator('#result').filter({hasText:'不同的数据'}).waitFor();checks.otherDataRejected=true;
  await page.goto('https://example.com/').catch(()=>{});
  try{await page.getByRole('button',{name:'再使用 1 分钟'}).waitFor({timeout:10000});}catch(error){
   await page.screenshot({path:path.join(fixture,'failure.png'),fullPage:true});
   console.log(JSON.stringify({url:page.url(),body:await page.locator('body').innerText(),stored:await worker.evaluate(()=>chrome.storage.local.get()),rules:await worker.evaluate(()=>chrome.declarativeNetRequest.getDynamicRules()),status:(await api(port,'status')).data,errors},null,2));throw error;
  }checks.exhaustedBlocked=true;
  await page.getByRole('button',{name:'再使用 1 分钟'}).click();
  let purpose;
  for(let i=0;i<50;i++){purpose=page.frames().find(frame=>frame.url().startsWith(extensionOrigin+'/intent.html'));if(purpose)break;await wait(200);}
  assert(purpose,'Isolated intention frame must appear');
  await purpose.getByRole('textbox',{name:'本次使用用途'}).waitFor({timeout:10000});
  const before=(await api(port,'status')).data.groups.find(g=>g.id==='social').used_seconds;await wait(1500);
  checks.unconfirmedNotCharged=(await api(port,'status')).data.groups.find(g=>g.id==='social').used_seconds===before;
  checks.emptyPurposeDisabled=await purpose.getByRole('button',{name:'确认用途，开始使用'}).isDisabled();
  await purpose.getByRole('textbox',{name:'本次使用用途'}).fill('只用于隔离发布验收，不属于真实使用');
  await purpose.getByRole('button',{name:'确认用途，开始使用'}).click();
  console.log('Running a complete fixture-only extra minute');
  const deadline=Date.now()+75000;let exhausted=false;
  while(Date.now()<deadline){await wait(2000);const status=(await api(port,'status')).data;if(status.groups.find(g=>g.id==='social').blocked){exhausted=true;break;}}
  checks.completeMinuteConsumed=exhausted;
  checks.secondClaimRejected=(await api(port,'bonus',{group:'social'})).code===400;
  const stored=fs.readFileSync(path.join(data,'state.json'),'utf8');checks.purposeNotStored=!stored.includes('只用于隔离');
  checks.noPageErrors=errors.length===0;
  const result={checks,errors,fixture};fs.writeFileSync(path.join(fixture,'verification.json'),JSON.stringify(result,null,2));
  console.log(JSON.stringify(result,null,2));assert(Object.values(checks).every(Boolean));
 }finally{if(context)await context.close();if(server)server.kill();if(other)other.kill();}
})().catch(error=>{console.error(error);process.exitCode=1;});
