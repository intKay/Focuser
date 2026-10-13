(async()=>{
if(globalThis.FocuserI18n) await FocuserI18n.ready;
const t=globalThis.FocuserI18n?.t||(value=>value);
const extension = globalThis.browser || globalThis.chrome;
const portInput = document.getElementById('port'), result = document.getElementById('result');
const browserInput = document.getElementById('browser-name');
async function load() {
 const base = await FocuserConnection.get();
 portInput.value = new URL(base).port;
 browserInput.value = (await extension.storage.local.get('browserName')).browserName || '';
 document.getElementById('panel').href = base + '/';
}
document.getElementById('save').onclick = async () => {
 const button = document.getElementById('save');button.disabled = true;
 try {
  const base = FocuserConnection.base('http://127.0.0.1:' + portInput.value);
  const response = await fetch(base + '/api/health', {cache:'no-store', signal:AbortSignal.timeout(3000)});
  const health = await response.json();
  if(!response.ok || health.service !== 'focuser' || health.api_version !== 1 || !/^[a-f0-9]{32}$/.test(health.instance_id || ''))throw Error(t('该端口不是兼容的 Focuser 服务，请先升级或启动本地服务'));
  const saved = await extension.storage.local.get('boundInstance');
  if(saved.boundInstance && saved.boundInstance !== health.instance_id)throw Error(t('此服务使用不同的数据目录。请让原服务使用原目录启动，保留已用时间与领取记录'));
  await extension.storage.local.set({apiBase:base, boundInstance:health.instance_id, browserName:browserInput.value});
  document.getElementById('panel').href = base + '/';
  result.textContent = t('已连接，打开控制页面配置规则。请刷新目标网页。');
 } catch(error) { result.textContent = error.message; }
 finally { button.disabled = false; }
};
load().catch(error => result.textContent = error.message);

})();
