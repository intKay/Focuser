const extensionAPI=globalThis.browser||globalThis.chrome;
const documentId=crypto.randomUUID().replaceAll('-','');
const target=location.search.startsWith('?target=')?location.search.slice(8):'';
let pending=false;
FocuserConnection.get().then(base=>document.getElementById('panel').href=base+'/').catch(()=>{});
async function inspect(){if(pending)return;pending=true;try{const r=await extensionAPI.runtime.sendMessage({kind:'inspect',document:documentId,active:false});document.getElementById('reason').textContent=r.offline?'本地服务未连接，请启动屏幕使用时间。':r.curfew_active?'当前处于禁用时段，稍后再来。':r.mode==='block'?'这个分类默认禁用，可领取当天唯一的一分钟。':'今日额度已用完，先停在这里。';document.getElementById('bonus').hidden=!r.bonus_available;if(r.group&&!r.blocked&&!r.offline&&/^https?:\/\//i.test(target))location.replace(target);}finally{pending=false;}}
document.getElementById('bonus').onclick=async()=>{const button=document.getElementById('bonus');button.disabled=true;const r=await extensionAPI.runtime.sendMessage({kind:'bonus',document:documentId,active:false});if(r.error){document.getElementById('reason').textContent=r.error;button.disabled=false;return;}if(!r.blocked&&/^https?:\/\//i.test(target))location.replace(target);};
document.getElementById('ok').onclick=()=>{window.close();setTimeout(()=>{location.href='about:blank'},150);};
inspect();setInterval(inspect,1500);
