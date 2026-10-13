(async () => {
const t=globalThis.FocuserI18n?.t||(value=>value);

 const chrome=globalThis.browser||globalThis.chrome;
 const documentId=crypto.randomUUID().replaceAll('-','');
 let busy=false,overlay=null,root=null,mode='',known=false,toast=null;const warned=new Set();
 function send(kind,extra={}){return chrome.runtime.sendMessage({kind,document:documentId,active:!document.hidden&&!overlay,...extra});}
 function node(tag,text){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n;}
 function remove(){overlay?.remove();overlay=null;root=null;mode='';}
 function cover(type,data={}){
 if(!overlay){overlay=node('div');overlay.id='local-screen-time-cover';root=overlay.attachShadow({mode:'closed'});}
 if(!overlay.isConnected&&document.documentElement)document.documentElement.append(overlay);
 for(const media of document.querySelectorAll('video,audio')){try{media.pause();}catch{}}
 const key=type==='blocked'?JSON.stringify([type,data.group,data.mode,data.bonus_available,data.curfew_active]):type;if(mode===key)return;mode=key;
 const style=node('style');style.textContent=':host{all:initial!important;position:fixed!important;inset:0!important;z-index:2147483647!important;background:#f2f2f7!important;color:#1c1c1e!important;display:grid!important;place-items:center!important;font:16px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif!important}main{width:min(440px,80vw);text-align:center;padding:32px;background:white;border-radius:24px;box-shadow:0 12px 60px #0001}.icon{font-size:58px;color:#5856d6}h1{font-size:26px}p{color:#636366;line-height:1.8}textarea{box-sizing:border-box;width:100%;min-height:95px;border:1px solid #d1d1d6;border-radius:12px;padding:14px;font:inherit;resize:vertical}button,a{display:inline-block;background:#007aff;color:white;border:0;border-radius:12px;padding:13px 22px;margin:10px 4px;font:inherit;text-decoration:none;cursor:pointer}button:disabled{opacity:.4}small{display:block;color:#8e8e93}.error{color:#ff375f;font-size:13px}';
 const main=node('main'),icon=node('div','◷');icon.className='icon';main.append(icon);
 if(type==='loading')main.append(node('p',t('正在检查屏幕使用时间…')));
 else if(type==='intent'){
 const frame=node('iframe');frame.src=chrome.runtime.getURL('intent.html')+'?'+new URLSearchParams({document:documentId,client:data.client||'',group:data.group||'',port:new URL(data.panel_url||'http://127.0.0.1:18765/').port,instance:data.instance_id||''});frame.title=t('本次使用用途');frame.style.cssText='width:100%;height:310px;border:0';main.append(frame);
 }else{
 main.append(node('h1',type==='offline'?t('本地服务未连接'):t('已达到使用限额')),node('p',type==='offline'?t('请启动屏幕使用时间后重试。'):data.curfew_active?t('当前处于禁用时段，稍后再来。'):data.mode==='block'?t('这个分类默认禁用，可领取当天唯一的一分钟。'):t('今日额度已用完，先停在这里。')));
 if(type==='blocked'&&data.bonus_available){const button=node('button',t('再使用 1 分钟'));button.onclick=async()=>{button.disabled=true;try{const r=await send('bonus',{active:false});if(r.error){button.textContent=t(r.error);button.disabled=false;mode='';await tick();return;}remove();await tick();}catch{button.textContent=t('连接失败，请重试');button.disabled=false;}};main.append(button,node('small',t('每天全体分类合计仅一次，网站与 App 共享。')));}
 const link=node('a',t('查看屏幕使用时间'));link.href=data.panel_url||'http://127.0.0.1:18765/';main.append(link);
 }root.replaceChildren(style,main);
 }
 function notify(text){
 if(!document.documentElement)return;toast?.remove();toast=node('div');const shadow=toast.attachShadow({mode:'closed'}),style=node('style');
 style.textContent=':host{all:initial!important;position:fixed!important;right:20px!important;bottom:20px!important;z-index:2147483646!important}div{font:14px -apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",sans-serif;background:#1c1c1ef2;color:#fff;padding:12px 18px;border-radius:14px;box-shadow:0 8px 30px #0005}';
 shadow.append(style,node('div',text));document.documentElement.append(toast);const mine=toast;setTimeout(()=>{mine.remove();if(toast===mine)toast=null;},6000);
 }
 function warn(result){
 if(!result||result.blocked||result.paused||!result.enabled||result.mode!=='limit'||document.hidden)return;
 const left=result.remaining_seconds,soon=result.curfew_starts_in;
 if(left>300){warned.delete('r300');warned.delete('r60');}
 if(left>0&&left<=60&&!warned.has('r60')){warned.add('r60');warned.add('r300');notify(t('今日额度不足 1 分钟'));}
 else if(left>60&&left<=300&&!warned.has('r300')){warned.add('r300');notify(t('今日额度还剩约 ')+Math.ceil(left/60)+t(' 分钟'));}
 if(!(soon>0&&soon<=300))warned.delete('c');
 else if(!warned.has('c')){warned.add('c');notify(Math.ceil(soon/60)+t(' 分钟后进入禁用时段'));}
 }
 async function tick(){if(busy||!chrome.runtime?.id)return;busy=true;try{if(globalThis.FocuserI18n)await FocuserI18n.ready;const result=await send('tick');known=!!result?.group;if(result?.offline&&result.blocked)cover('offline',result);else if(result?.blocked)cover('blocked',result);else if(result?.needs_intent)cover('intent',result);else{remove();warn(result);}}catch{if(known)cover('offline');else remove();}finally{busy=false;}}
 cover('loading');setInterval(tick,1000);tick();window.addEventListener('focus',tick);window.addEventListener('blur',tick);document.addEventListener('visibilitychange',tick);
})();
