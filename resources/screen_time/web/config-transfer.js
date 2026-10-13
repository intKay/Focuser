/* Plain configuration files, saved and managed by the user. No cloud/storage APIs. */
globalThis.FocuserConfigTransfer = (() => {
 const MAX_BYTES=262144, encoder=new TextEncoder();
 const t=value=>globalThis.FocuserI18n?.t(value)||value;
 function validate(config){
  if(config?.format==='focuser-encrypted-config')throw Error(t('旧加密配置不能直接导入，请重新导出普通 JSON 配置'));
  if(!config||typeof config!=='object'||Array.isArray(config)||Object.keys(config).sort().join(',')!=='format,groups,version'||config.format!=='focuser-config'||config.version!==1||!Array.isArray(config.groups))throw Error(t('配置文件格式或版本不支持'));
  if(encoder.encode(JSON.stringify({groups:config.groups})).length>60000)throw Error(t('配置文件过大'));
  return config;
 }
 function encode(config){return JSON.stringify(validate(config),null,2)+'\n';}
 function decode(text){
  if(typeof text!=='string'||encoder.encode(text).length>MAX_BYTES)throw Error(t('配置文件过大'));
  let config;try{config=JSON.parse(text.replace(/^\uFEFF/,''));}catch{throw Error(t('配置文件格式或版本不支持'));}
  return validate(config);
 }
 return {encode,decode,MAX_BYTES};
})();
