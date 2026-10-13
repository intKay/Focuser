/* Passwords and plaintext stay in this browser. No cloud or storage APIs. */
globalThis.FocuserConfigTransfer = (() => {
 const ITERATIONS=600000, MAX_BYTES=262144, encoder=new TextEncoder();
 const t=value=>globalThis.FocuserI18n?.t(value)||value;
 const keys=(obj,expected)=>obj&&typeof obj==='object'&&!Array.isArray(obj)&&Object.keys(obj).sort().join(',')===expected.slice().sort().join(',');
 const base64=bytes=>btoa(Array.from(new Uint8Array(bytes),x=>String.fromCharCode(x)).join(''));
 function decode(value,length){
  if(typeof value!=='string'||value.length>MAX_BYTES||!/^([A-Za-z0-9+/]{4})*([A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(value))throw Error(t('配置文件格式或版本不支持'));
  const bytes=Uint8Array.from(atob(value),x=>x.charCodeAt(0));
  if(length&&bytes.length!==length)throw Error(t('配置文件格式或版本不支持'));
  return bytes;
 }
 function validate(config){
  if(!keys(config,['format','version','groups'])||config.format!=='focuser-config'||config.version!==1||!Array.isArray(config.groups))throw Error(t('配置文件格式或版本不支持'));
  if(encoder.encode(JSON.stringify({groups:config.groups})).length>60000)throw Error(t('配置文件过大'));
  return config;
 }
 async function key(password,salt){
  if(typeof password!=='string'||password.length<12)throw Error(t('密码至少需要12个字符'));
  if(!globalThis.crypto?.subtle)throw Error(t('此浏览器无法加密配置，请使用现代浏览器打开本机控制页'));
  const material=await crypto.subtle.importKey('raw',encoder.encode(password),'PBKDF2',false,['deriveKey']);
  return crypto.subtle.deriveKey({name:'PBKDF2',salt,iterations:ITERATIONS,hash:'SHA-256'},material,{name:'AES-GCM',length:256},false,['encrypt','decrypt']);
 }
 const aad=encoder.encode('Focuser encrypted configuration v1');
 async function encrypt(config,password){
  validate(config);
  const salt=crypto.getRandomValues(new Uint8Array(16)),iv=crypto.getRandomValues(new Uint8Array(12));
  const ciphertext=await crypto.subtle.encrypt({name:'AES-GCM',iv,additionalData:aad},await key(password,salt),encoder.encode(JSON.stringify(config)));
  return JSON.stringify({format:'focuser-encrypted-config',version:1,kdf:'PBKDF2-SHA256',iterations:ITERATIONS,salt:base64(salt),iv:base64(iv),ciphertext:base64(ciphertext)});
 }
 async function decrypt(text,password){
  if(typeof text!=='string'||encoder.encode(text).length>MAX_BYTES)throw Error(t('配置文件过大'));
  let file;try{file=JSON.parse(text);}catch{throw Error(t('配置文件格式或版本不支持'));}
  if(!keys(file,['format','version','kdf','iterations','salt','iv','ciphertext'])||file.format!=='focuser-encrypted-config'||file.version!==1||file.kdf!=='PBKDF2-SHA256'||file.iterations!==ITERATIONS)throw Error(t('配置文件格式或版本不支持'));
  const salt=decode(file.salt,16),iv=decode(file.iv,12),ciphertext=decode(file.ciphertext);
  const derived=await key(password,salt);
  let plaintext;try{plaintext=await crypto.subtle.decrypt({name:'AES-GCM',iv,additionalData:aad},derived,ciphertext);}catch{throw Error(t('密码错误或配置文件已损坏'));}
  try{return validate(JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(plaintext)));}catch(error){throw Error(t('配置文件格式或版本不支持'));}
 }
 return {encrypt,decrypt,MAX_BYTES};
})();
