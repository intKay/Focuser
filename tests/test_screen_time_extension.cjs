const fs=require('fs'),vm=require('vm'),assert=require('assert'),path=require('path');
const source=fs.readFileSync(path.join(__dirname,'../resources/screen_time/extension/intent.js'),'utf8');
async function run({runtime,client=true,response={ok:true},network=false}={}){
 const nodes={purpose:{value:'查询一道题',focus(){}},submit:{disabled:false},error:{textContent:''}};
 const body={textContent:''};let requests=0;
 const href='chrome-extension://'+ 'a'.repeat(32) +'/intent.html?document=doc'+(client?'&client=session:1:doc&group=social':'');
 const context=vm.createContext({URL,AbortSignal,TypeError,location:{href,protocol:'chrome-extension:'},document:{getElementById:id=>nodes[id],body},chrome:runtime?{runtime:{sendMessage:async()=>({ok:true})}}:{},fetch:async()=>{requests++;if(network)throw new TypeError('Failed to fetch');return{ok:response.ok,json:async()=>response};}});
 vm.runInContext(source,context);await nodes.submit.onclick();return{nodes,body,requests};
}
(async()=>{
 let r=await run({runtime:true});assert(r.body.textContent.includes('已确认'));assert.equal(r.requests,0);
 r=await run();assert(r.body.textContent.includes('已确认'));assert.equal(r.requests,1);
 r=await run({client:false});assert(r.nodes.error.textContent.includes('重新加载'));assert.equal(r.requests,0);
 r=await run({response:{ok:false,error:'当前分类已限制'}});assert.equal(r.nodes.error.textContent,'当前分类已限制');assert.equal(r.nodes.submit.disabled,false);
 r=await run({network:true});assert(r.nodes.error.textContent.includes('本地服务'));assert.equal(r.nodes.submit.disabled,false);
 console.log('5 extension intention regression checks passed');
 await require('./extension_portable_checks.cjs')();
 await require('./test_screen_time_i18n.cjs')();
 await require('./test_screen_time_config_crypto.cjs')();
})().catch(error=>{console.error(error);process.exitCode=1;});
