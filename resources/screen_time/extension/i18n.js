/* UI preferences only: never modify rules, usage, bonuses or data bindings. */
globalThis.FocuserI18n = (() => {
 const extension = globalThis.browser || globalThis.chrome;
 const inExtension = !!extension?.runtime?.id;
 let language = /^zh/i.test(globalThis.navigator?.language || 'en') ? 'zh' : 'en';
 let catalog = {messages:{}, patterns:[]};
 function t(value) {
  if(language !== 'en' || typeof value !== 'string') return value;
  if(Object.hasOwn(catalog.messages, value)) return catalog.messages[value];
  for(const [pattern, replacement] of catalog.patterns) {
   const re = new RegExp(pattern);
   if(re.test(value)) return value.replace(re, replacement.replace(/\\(\d+)/g, '$$$1'));
  }
  return value;
 }
 function translateMarkup() {
  document.documentElement.lang = language === 'zh' ? 'zh-CN' : 'en';
  const walker = document.createTreeWalker(document.documentElement, NodeFilter.SHOW_TEXT);
  let node;
  while((node = walker.nextNode())) {
   if(['SCRIPT','STYLE','CODE'].includes(node.parentElement?.tagName)) continue;
   const text = node.nodeValue, trimmed = text.trim();
   if(trimmed) node.nodeValue = text.replace(trimmed, t(trimmed));
  }
  for(const element of document.querySelectorAll('[aria-label],[placeholder],[title]'))
   for(const attr of ['aria-label','placeholder','title'])
    if(element.hasAttribute(attr)) element.setAttribute(attr, t(element.getAttribute(attr)));
  for(const select of document.querySelectorAll('[data-language]')) {
   select.value = language;
   select.onchange = async () => {
    if(inExtension) await extension.storage.local.set({language:select.value});
    else localStorage.setItem('focuser.language', select.value);
    location.reload();
   };
  }
 }
 const ready = (async () => {
  const saved = inExtension ? (await extension.storage.local.get('language')).language : localStorage.getItem('focuser.language');
  if(['en','zh'].includes(saved)) language = saved;
  const url = inExtension ? extension.runtime.getURL('i18n.json') : '/i18n.json';
  const response = await fetch(url, {signal:AbortSignal.timeout(3000)});
  if(!response.ok) throw Error('Could not load Focuser translations');
  catalog = await response.json();
  if(globalThis.document && (!inExtension || ['chrome-extension:','moz-extension:'].includes(location.protocol))) translateMarkup();
 })().catch(() => {language='zh';}); // Translation failure must never stop enforcement.
 // Background/content scripts never translate the host website's DOM.
 return {t, ready, get language(){return language;}};
})();
