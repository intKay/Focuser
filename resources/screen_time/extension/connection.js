/* Shared by extension pages. The only network destination is IPv4 loopback. */
globalThis.FocuserConnection = (() => {
 const defaultBase = 'http://127.0.0.1:18765';
 function base(value) {
  const url = new URL(value), port = Number(url.port || 80);
  if(url.protocol !== 'http:' || url.hostname !== '127.0.0.1' || url.username || url.password || url.search || url.hash || !['','/'].includes(url.pathname) || !Number.isInteger(port) || port < 1024 || port > 65535)
   throw Error('只允许本机 127.0.0.1 的1024到65535端口');
  return url.origin;
 }
 async function get() {
  const api = globalThis.browser || globalThis.chrome;
  const saved = await api.storage.local.get('apiBase');
  return base(saved.apiBase || defaultBase);
 }
 return {defaultBase, base, get};
})();
