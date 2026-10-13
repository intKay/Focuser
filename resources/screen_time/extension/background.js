import {canonicalHost,canonicalSet,setCovers} from './vendor/rules.js';
import './connection.js';
const chrome=globalThis.browser||globalThis.chrome;
let API='http://127.0.0.1:18765',boundInstance=null;
const detectedBrowser=/Vivaldi\//.test(navigator.userAgent)?'Vivaldi':/Firefox\//.test(navigator.userAgent)?'Firefox':/Edg\//.test(navigator.userAgent)?'Edge':/OPR\//.test(navigator.userAgent)?'Opera':'Chrome';
const browserLabel=value=>['Chrome','Edge','Firefox','Brave','Opera','Chromium','Vivaldi'].includes(value)?value:detectedBrowser;
let browserName=detectedBrowser;
const ready=chrome.storage.local.get(['apiBase','boundInstance','browserName']).then(saved=>{API=FocuserConnection.base(saved.apiBase||API);boundInstance=saved.boundInstance||null;browserName=browserLabel(saved.browserName);});
let status=null,lastFetch=0,pending=null,lastRules='';
const session=crypto.randomUUID().replaceAll('-','');
const offlineDefaults={paused:false,groups:[
{id:'douyin',name:'抖音',enabled:true,blocked:true,domains:['douyin.com','iesdouyin.com']},
{id:'social',name:'社区与视频',enabled:true,blocked:false,domains:['xiaohongshu.com','xhslink.com','x.com','twitter.com','t.co','xiaoheihe.cn','heybox.com','zhihu.com','youtube.com','youtu.be']}]};
async function request(path,body){
 await ready;
 if(!boundInstance){
  const healthResponse=await fetch(API+'/api/health',{cache:'no-store',signal:AbortSignal.timeout(2500)});
  const health=await healthResponse.json();
  if(!healthResponse.ok||health.service!=='focuser'||health.api_version!==1||!/^[a-f0-9]{32}$/.test(health.instance_id||''))throw Error('请启动兼容的 Focuser 服务');
  boundInstance=health.instance_id;await chrome.storage.local.set({boundInstance});
 }
 const r=await fetch(API+path,{cache:'no-store',signal:AbortSignal.timeout(2500),...(body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...body,instance_id:boundInstance})}:{})});
 const data=await r.json();if(!r.ok){const error=Error(data.error||'请求失败');if(r.status!==409)error.httpStatus=r.status;throw error;}return data;
}
async function accept(candidate){
 if(candidate.api_version!==1||!candidate.instance_id)throw Error('请升级本地 Focuser 服务');
 if(boundInstance&&boundInstance!==candidate.instance_id)throw Error('数据目录发生变化，保留已有规则并等待原服务');
 if(!boundInstance){boundInstance=candidate.instance_id;await chrome.storage.local.set({boundInstance});}
 status=candidate;return status;
}
function groupFor(host){return status?.groups.find(g=>setCovers(canonicalSet(g.domains),canonicalHost(host)));}
async function enforceRules(offline=false){
 if(!status)return;
 const domains=status.groups.filter(g=>g.blocked||(offline&&g.enabled&&!status.paused)).flatMap(g=>g.domains);
 const signature=JSON.stringify(domains);if(signature===lastRules)return;
 const old=await chrome.declarativeNetRequest.getDynamicRules();
 await chrome.declarativeNetRequest.updateDynamicRules({removeRuleIds:old.map(r=>r.id),addRules:domains.map((domain,i)=>({id:i+1,priority:1,
 action:{type:'redirect',redirect:{regexSubstitution:chrome.runtime.getURL('blocked.html')+'?target=\\0'}},
 condition:{requestDomains:[domain],regexFilter:'^https?://.*',resourceTypes:['main_frame']}}))});lastRules=signature;
}
async function refresh(force=false){
 await ready;
 if(pending)return pending;if(!force&&Date.now()-lastFetch<900)return;
 pending=(async()=>{try{await accept(await request('/api/heartbeat',{client:session+':health',group:null,active:false,browser:browserName}));lastFetch=Date.now();await chrome.storage.local.set({status});await enforceRules();await chrome.action.setBadgeText({text:status.paused?'暂停':''});}
 catch{if(!status)status=(await chrome.storage.local.get('status')).status||offlineDefaults;await enforceRules(true);await chrome.action.setBadgeText({text:'离线'});}finally{pending=null;}})();return pending;
}
chrome.runtime.onMessage.addListener((message,sender,reply)=>{
 if(!sender.tab)return;const intentFrame=(sender.url||'').startsWith(chrome.runtime.getURL('intent.html'));if(sender.frameId!==0&&!intentFrame)return;
 (async()=>{
 await refresh();let url=intentFrame?sender.tab.url:(sender.url||sender.tab.url);const blockedPage=url.startsWith(chrome.runtime.getURL('blocked.html'));
 if(blockedPage)url=new URL(url).search.startsWith('?target=')?new URL(url).search.slice(8):'';
 if(!/^https?:\/\//i.test(url))return reply({group:null});
 const group=groupFor(canonicalHost(url));if(!group)return reply({group:null});
 if(!/^[a-zA-Z0-9_-]{1,40}$/.test(message.document||''))throw Error('会话标识无效');
 const client=session+':'+sender.tab.id+':'+message.document;
 try{
 if(message.kind==='bonus')await request('/api/bonus',{group:group.id});
 if(message.kind==='intent')await request('/api/intent',{client,group:group.id,purpose:message.purpose});
 const tab=await chrome.tabs.get(sender.tab.id),win=await chrome.windows.get(tab.windowId);
 const result=await request('/api/heartbeat',{client,group:group.id,active:!blockedPage&&!intentFrame&&!!message.active&&tab.active&&win.focused,browser:browserName});await accept(result);await enforceRules();
 const current=status.groups.find(g=>g.id===group.id);
 reply({...current,group:group.id,client,panel_url:API+'/',instance_id:boundInstance,needs_intent:current.enabled&&!status.paused&&!result.intent_granted,paused:status.paused,offline:false});
 }catch(error){if(error.httpStatus){await refresh(true);const current=status.groups.find(g=>g.id===group.id);reply({...current,group:group.id,paused:status.paused,offline:false,error:error.message});}else reply({group:group.id,name:group.name,blocked:group.enabled&&!status.paused,offline:true,error:error.message});}
 })().catch(error=>reply({error:error.message,offline:true,blocked:true}));return true;
});
chrome.storage.onChanged.addListener((changes,area)=>{if(area==='local'&&(changes.apiBase||changes.boundInstance||changes.browserName)){if(changes.apiBase)API=FocuserConnection.base(changes.apiBase.newValue);if(changes.boundInstance)boundInstance=changes.boundInstance.newValue;if(changes.browserName)browserName=browserLabel(changes.browserName.newValue);lastFetch=0;refresh(true);}});
chrome.alarms.create('sync',{periodInMinutes:0.5});chrome.alarms.onAlarm.addListener(()=>refresh(true));chrome.runtime.onStartup.addListener(()=>refresh(true));chrome.runtime.onInstalled.addListener(()=>refresh(true));chrome.action.onClicked.addListener(async()=>{await ready;chrome.tabs.create({url:API+'/'});});refresh(true);
