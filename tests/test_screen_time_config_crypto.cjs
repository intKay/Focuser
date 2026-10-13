const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync(path.join(__dirname,'../resources/screen_time/web/config-transfer.js'),'utf8');
async function main(){
 const context=vm.createContext({crypto:require('crypto').webcrypto,TextEncoder,TextDecoder,Uint8Array,
  btoa:s=>Buffer.from(s,'binary').toString('base64'),atob:s=>Buffer.from(s,'base64').toString('binary')});
 vm.runInContext(source,context);const transfer=context.FocuserConfigTransfer;
 const config={format:'focuser-config',version:1,groups:[{id:'fixture',name:'Private category',domains:['private.example'],apps:['private.exe']}]},password='Fixture password only!';
 const first=await transfer.encrypt(config,password),second=await transfer.encrypt(config,password);
 assert.notEqual(first,second,'fresh random salt and IV for every export');
 for(const secret of ['Private category','private.example','private.exe',password])assert(!first.includes(secret));
 assert.deepEqual(JSON.parse(JSON.stringify(await transfer.decrypt(first,password))),config);
 await assert.rejects(transfer.encrypt(config,'short'));
 await assert.rejects(transfer.decrypt(first,'Incorrect fixture password'));
 const tampered=JSON.parse(first);tampered.ciphertext=(tampered.ciphertext[0]==='A'?'B':'A')+tampered.ciphertext.slice(1);
 await assert.rejects(transfer.decrypt(JSON.stringify(tampered),password));
 const excessive=JSON.parse(first);excessive.iterations=999999999;await assert.rejects(transfer.decrypt(JSON.stringify(excessive),password));
 await assert.rejects(transfer.encrypt({...config,history:{}},password));
 await assert.rejects(transfer.decrypt('x'.repeat(262145),password));
 console.log('Encrypted config checks passed: round trip, privacy, randomness, wrong password, tampering, size and KDF bounds');
}
module.exports=main;if(require.main===module)main().catch(error=>{console.error(error);process.exitCode=1});
