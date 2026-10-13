const assert=require('assert'),vm=require('vm'),fs=require('fs'),path=require('path');
const root=path.join(__dirname,'../resources/screen_time/extension');
const source=fs.readFileSync(path.join(root,'i18n.js'),'utf8'),catalog=JSON.parse(fs.readFileSync(path.join(root,'i18n.json'),'utf8'));
async function run({language='en-US',saved,broken=false}={}){
 const stored={language:saved,boundInstance:'a'.repeat(32),status:{paused:false,groups:[]}},before=JSON.stringify(stored);
 const context=vm.createContext({navigator:{language},location:{protocol:'chrome-extension:'},AbortSignal,
  chrome:{runtime:{id:'test',getURL:n=>'chrome-extension://test/'+n},storage:{local:{get:async()=>({...stored}),set:async x=>Object.assign(stored,x)}}},
  fetch:async()=>{if(broken)throw new Error('missing translation file');return{ok:true,json:async()=>catalog}}});
 vm.runInContext(source,context);await context.FocuserI18n.ready;
 assert.equal(JSON.stringify(stored),before,'Language loading cannot edit cached policy or bindings');
 return context.FocuserI18n;
}
async function main(){
 let i18n=await run();assert.equal(i18n.t('暂停限制'),'Pause limits');assert.equal(i18n.t('120秒'),'120 s');
 assert.equal(i18n.t('已选择 2 个 · 共 5 个 App'),'2 selected · 5 apps total');
 i18n=await run({language:'zh-CN'});assert.equal(i18n.t('暂停限制'),'暂停限制');
 i18n=await run({language:'en-US',saved:'zh'});assert.equal(i18n.t('暂停限制'),'暂停限制');
 i18n=await run({broken:true});assert.equal(i18n.t('暂停限制'),'暂停限制','Missing translations fall back without stopping enforcement');
 console.log('Language regression checks passed: auto/manual language, patterns, state isolation, failure fallback');
}
module.exports=main;
if(require.main===module)main().catch(e=>{console.error(e);process.exitCode=1});
