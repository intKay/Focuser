/* Synthetic configuration, independent backend/port/profile, no user data. */
const {chromium}=require(process.env.FOCUSER_PLAYWRIGHT_MODULE||'playwright');
const fs=require('fs'),path=require('path'),net=require('net'),http=require('http'),assert=require('assert'),{spawn}=require('child_process');
const root=path.resolve(__dirname,'..'),wait=ms=>new Promise(r=>setTimeout(r,ms));
const temp=path.join(root,'outputs/screen_time/test-temp');fs.mkdirSync(temp,{recursive:true});const fixture=fs.mkdtempSync(path.join(temp,'config-ui-'));
async function freePort(){return new Promise(resolve=>{const s=net.createServer();s.listen(0,'127.0.0.1',()=>{const port=s.address().port;s.close(()=>resolve(port));});});}
function status(port){return new Promise((resolve,reject)=>http.get({hostname:'127.0.0.1',port,path:'/api/status'},r=>{let text='';r.on('data',x=>text+=x);r.on('end',()=>resolve(JSON.parse(text)));}).on('error',reject));}
(async()=>{
 let browser,server;const port=await freePort(),data=path.join(fixture,'data');fs.mkdirSync(data);
 const day=new Date().toLocaleDateString('sv-SE'),groups=[{id:'fixture',name:'Private fixture',mode:'limit',minutes:30,enabled:true,color:'#5856d6',domains:['private.example'],apps:[]}];
 fs.writeFileSync(path.join(data,'state.json'),JSON.stringify({version:1,groups,history:{[day]:{fixture:1860}},bonus:{[day]:'fixture'},paused:false}));
 server=spawn(process.env.FOCUSER_TEST_PYTHON||'python',[path.join(root,'scripts/screen_time_server.py'),'--data-dir',data,'--port',String(port),'--no-apps','--background'],{windowsHide:true});
 try{
  for(let i=0;i<50;i++){try{await status(port);break;}catch{await wait(150);}}
  browser=await chromium.launch({headless:true,...(process.env.FOCUSER_TEST_CHROMIUM?{executablePath:process.env.FOCUSER_TEST_CHROMIUM}:{})});
  const page=await browser.newPage({locale:'en-US',viewport:{width:1100,height:900}}),requests=[],errors=[];
  page.on('request',r=>{if(r.postData())requests.push(r.postData());});page.on('pageerror',e=>errors.push(e.message));
  await page.goto(`http://127.0.0.1:${port}/`);await page.getByRole('button',{name:'Connect & settings',exact:true}).click();
  const before=await status(port),password='Only synthetic test password!';
  await page.getByRole('button',{name:'Export encrypted configuration',exact:true}).click();
  await page.locator('#transfer-password').fill(password);await page.locator('#repeat-password').fill('Mismatch fixture password');await page.locator('#password-submit').click();
  await page.getByText('Passwords do not match',{exact:true}).waitFor();
  await page.locator('#repeat-password').fill(password);const download=page.waitForEvent('download');await page.locator('#password-submit').click();
  const exported=await download,original=path.join(fixture,'original.focuser');await exported.saveAs(original);
  assert.equal(exported.suggestedFilename(),'focuser-config.focuser');const ciphertext=fs.readFileSync(original,'utf8');
  for(const secret of [password,'private.example','Private fixture','history','bonus','paused'])assert(!ciphertext.includes(secret));
  async function select(file,secret){await page.locator('#config-file').setInputFiles(file);await page.locator('#transfer-password').fill(secret);await page.locator('#password-submit').click();}
  await select(original,'Incorrect fixture password');await page.locator('#transfer-status').filter({hasText:'Incorrect password'}).waitFor();
  assert.deepEqual((await status(port)).groups,before.groups);
  await select(original,password);await page.getByRole('heading',{name:'Import this configuration?'}).waitFor();await page.locator('#confirm-no').click();
  assert.deepEqual((await status(port)).groups,before.groups);
  await select(original,password);await page.getByRole('heading',{name:'Import this configuration?'}).waitFor();await page.locator('#confirm-yes').click();
  await page.locator('#transfer-status').filter({hasText:'Configuration imported.'}).waitFor();
  const tighter=await page.evaluate(async password=>{const config=await(await fetch('/api/config/export')).json();config.groups[0].minutes=20;return FocuserConfigTransfer.encrypt(config,password);},password);
  const tightFile=path.join(fixture,'tight.focuser');fs.writeFileSync(tightFile,tighter);
  await select(tightFile,password);await page.locator('#confirm-yes').click();await page.locator('#transfer-status').filter({hasText:'Configuration imported.'}).waitFor();
  const tightened=await status(port);assert.equal(tightened.groups[0].minutes,20);assert.deepEqual(tightened.history,before.history);assert(tightened.bonus_used);assert(tightened.groups[0].blocked);
  await select(original,password);await page.locator('#confirm-text').filter({hasText:'requires the integral challenge'}).waitFor();await page.locator('#confirm-yes').click();
  await page.getByRole('heading',{name:'Complete the integral challenge first'}).waitFor();assert(await page.getByRole('button',{name:'Verify and apply'}).isDisabled());
  await page.getByRole('button',{name:'Cancel and keep limits'}).click();
  await page.locator('#transfer-status').filter({hasText:'Cancelled.'}).waitFor();assert.equal((await status(port)).groups[0].minutes,20);
  assert.equal(await page.locator('#transfer-password').inputValue(),'');assert.equal(await page.locator('#repeat-password').inputValue(),'');
  assert(requests.every(body=>!body.includes(password)));assert.deepEqual(errors,[]);
  await page.locator('[data-language]').selectOption('zh');await page.getByRole('button',{name:'连接与设置',exact:true}).click();
  await page.getByRole('button',{name:'加密导出配置',exact:true}).waitFor();await page.setViewportSize({width:390,height:844});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await page.screenshot({path:path.join(fixture,'config-panel.png'),fullPage:true,animations:'disabled'});
  console.log(JSON.stringify({encryptedDownload:true,passwordMismatch:true,wrongPassword:true,previewCancel:true,roundTrip:true,stricterImport:true,usageAndBonusPreserved:true,relaxationGate:true,passwordNotSent:true,bilingualUI:true,narrowLayout:true}));
 }finally{if(browser)await browser.close();if(server)server.kill();}
})().catch(error=>{console.error(error);process.exitCode=1});
