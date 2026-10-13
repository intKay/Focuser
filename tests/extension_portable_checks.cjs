const fs=require('fs'),vm=require('vm'),assert=require('assert'),path=require('path');
const root=path.join(__dirname,'../resources/screen_time/extension');
const read=name=>fs.readFileSync(path.join(root,name),'utf8');
const identity='a'.repeat(32);
async function worker({offline=false,mismatch=false,firefox=false,userAgent,browserName}={}){
 const listeners={},requests=[],stored={apiBase:'http://127.0.0.1:19876',boundInstance:identity},updates=[];
 if(browserName!==undefined)stored.browserName=browserName;
 const snapshot={instance_id:identity,api_version:1,paused:false,groups:[{id:'social',name:'测试',enabled:true,blocked:false,domains:['example.com']}]};
 stored.status=snapshot;
 const api={storage:{local:{get:async keys=>typeof keys==='string'?{[keys]:stored[keys]}:{...stored},set:async data=>Object.assign(stored,data)},onChanged:{addListener:f=>listeners.storage=f}},
  runtime:{getURL:name=>(firefox?'moz-extension://12345678-abcd-1234-abcd-123456789abc/':'chrome-extension://'+identity+'/')+name,onMessage:{addListener:f=>listeners.message=f},onStartup:{addListener(){}},onInstalled:{addListener(){}}},
  declarativeNetRequest:{getDynamicRules:async()=>[],updateDynamicRules:async data=>updates.push(data)},
  action:{setBadgeText:async()=>{},onClicked:{addListener(){}}},alarms:{create(){},onAlarm:{addListener(){}}},
  tabs:{get:async()=>({active:true,windowId:1}),create:async()=>{}},windows:{get:async()=>({focused:true})}};
 const context=vm.createContext({URL,AbortSignal,Date,crypto:require('crypto'),navigator:{userAgent:userAgent||(firefox?'Firefox/128.0':'Chrome/130.0')},...(firefox?{browser:api}:{chrome:api}),fetch:async(url,options)=>{
  requests.push({url,body:options?.body?JSON.parse(options.body):null});
  if(offline)throw new TypeError('offline');
  if(mismatch)return{ok:false,status:409,json:async()=>({error:'数据不一致'})};
  return{ok:true,status:200,json:async()=>({...snapshot,intent_granted:false})};
 }});
 vm.runInContext(read('connection.js'),context);
 vm.runInContext(read('vendor/rules.js').replaceAll('export ',''),context);
 vm.runInContext(read('background.js').replace(/^import .*;\r?\n/gm,'').replace('if(globalThis.FocuserI18n) await FocuserI18n.ready;',''),context);
 await vm.runInContext('refresh(true)',context);
 const reply=await new Promise(resolve=>listeners.message({kind:'tick',document:'doc',active:true},{frameId:0,url:'https://example.com/',tab:{id:1,url:'https://example.com/'}},resolve));
 return{reply,requests,stored,updates};
}

async function optionsChecks(){
 const nodes={port:{value:'19876'},'browser-name':{value:''},result:{},panel:{},save:{}};
 const stored={apiBase:'http://127.0.0.1:18765',boundInstance:identity};let candidate=identity;
 const context=vm.createContext({URL,AbortSignal,document:{getElementById:id=>nodes[id]},chrome:{storage:{local:{get:async()=>({...stored}),set:async data=>Object.assign(stored,data)}}},fetch:async()=>({ok:true,json:async()=>({service:'focuser',api_version:1,instance_id:candidate})})});
 vm.runInContext(read('connection.js'),context);vm.runInContext(read('options.js'),context);
 await new Promise(resolve=>setImmediate(resolve));nodes.port.value='19876';nodes['browser-name'].value='Vivaldi';await nodes.save.onclick();
 assert.equal(stored.apiBase,'http://127.0.0.1:19876');
 assert.equal(stored.browserName,'Vivaldi');
 candidate='b'.repeat(32);nodes.port.value='19877';await nodes.save.onclick();
 assert.equal(stored.apiBase,'http://127.0.0.1:19876');assert(nodes.result.textContent.includes('不同的数据'));
 assert.equal(stored.browserName,'Vivaldi');
 assert(!('status' in stored));
}

async function main(){
 const rulesContext=vm.createContext({});
 vm.runInContext(read('vendor/rules.js').replaceAll('export ',''),rulesContext);
 assert.equal(vm.runInContext("setCovers(canonicalSet(['tieba.com']), 'tieba.baidu.com')",rulesContext),false);
 for(const host of ['tieba.baidu.com','www.tieba.baidu.com','c.tieba.baidu.com'])
  assert.equal(vm.runInContext(`setCovers(canonicalSet(['tieba.baidu.com']), ${JSON.stringify(host)})`,rulesContext),true);
 for(const host of ['baidu.com','www.baidu.com','not-tieba.baidu.com','tieba.baidu.com.evil.example'])
  assert.equal(vm.runInContext(`setCovers(canonicalSet(['tieba.baidu.com']), ${JSON.stringify(host)})`,rulesContext),false);
 const context=vm.createContext({URL});vm.runInContext(read('connection.js'),context);
 for(const value of ['https://127.0.0.1:19876','http://localhost:19876','http://evil.example:19876','http://127.0.0.1:80','http://user@127.0.0.1:19876','http://127.0.0.1:19876/path','http://127.0.0.1:19876/?x=1'])
  assert.throws(()=>context.FocuserConnection.base(value));
 assert.equal(context.FocuserConnection.base('http://127.0.0.1:19876/'),'http://127.0.0.1:19876');
 let result=await worker();assert.equal(result.reply.needs_intent,true);assert.equal(result.reply.panel_url,'http://127.0.0.1:19876/');
 assert(result.requests.every(req=>req.url.startsWith('http://127.0.0.1:19876/')));assert(result.requests.every(req=>req.body.instance_id===identity));
 assert(!JSON.stringify(result.stored).includes('purpose'));
 result=await worker({firefox:true});assert(result.requests.every(req=>req.body.browser==='Firefox'));assert.equal(result.reply.group,'social');
 for(const settings of [{userAgent:'Chrome/130.0 Vivaldi/7.0'},{userAgent:'Chrome/130.0',browserName:'Vivaldi'}]){
  result=await worker(settings);assert(result.requests.every(req=>req.body.browser==='Vivaldi'));assert.equal(result.reply.group,'social');assert.equal(result.stored.boundInstance,identity);
 }
 result=await worker({offline:true});assert.equal(result.reply.offline,true);assert(result.updates.at(-1).addRules.length>0);
 result=await worker({mismatch:true});assert.equal(result.reply.offline,true);assert(result.updates.at(-1).addRules.length>0);
 await optionsChecks();
 console.log('Portable extension checks passed: loopback bounds, custom port, identity binding, Firefox namespace, offline blocking, options retention');
}
module.exports=main;
if(require.main===module)main().catch(error=>{console.error(error);process.exitCode=1;});
