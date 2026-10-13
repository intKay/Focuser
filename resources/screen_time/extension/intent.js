const params=new URL(location.href).searchParams;
const documentId=params.get('document');
const input=document.getElementById('purpose'),button=document.getElementById('submit');
input.oninput=()=>button.disabled=input.value.trim().length<2;
async function confirmPurpose(purpose){
 const extension=globalThis.browser||globalThis.chrome;
 if(extension?.runtime?.sendMessage){
  return extension.runtime.sendMessage({kind:'intent',document:documentId,purpose,active:false});
 }
 // Some embedded extension frames do not expose runtime. Send directly from
 // the isolated extension origin, never through the target website's window.
 const client=params.get('client'),group=params.get('group');
 if(!['chrome-extension:','moz-extension:'].includes(location.protocol)||!client||!group){
  throw Error('扩展连接已失效，请重新加载扩展并刷新目标网页。');
 }
 try{
  const port=params.get('port')||'18765';
  if(!/^\d+$/.test(port)||Number(port)<1024||Number(port)>65535)throw Error('本地服务端口无效');
  const response=await fetch('http://127.0.0.1:'+port+'/api/intent',{
   method:'POST',headers:{'Content-Type':'application/json'},
   body:JSON.stringify({client,group,purpose,...(params.get('instance')?{instance_id:params.get('instance')}: {})}),signal:AbortSignal.timeout(3000)
  });
  const result=await response.json();
  if(!response.ok)throw Error(result.error||'用途确认失败');
  return result;
 }catch(error){
  if(error instanceof TypeError||error.name==='TimeoutError'){
   throw Error('无法连接本地服务，请启动屏幕使用时间；如仍失败，请重新加载扩展并刷新网页。');
  }
  throw error;
 }
}
button.onclick=async()=>{
 button.disabled=true;
 try{
  const r=await confirmPurpose(input.value.trim());
  if(!r||r.error)throw Error(r?.error||'扩展未响应，请重新加载扩展并刷新网页。');
  document.body.textContent='用途已确认，即将开始使用…';
 }catch(e){document.getElementById('error').textContent=e.message;button.disabled=false;}
};
input.focus();
