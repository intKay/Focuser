const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync(path.join(__dirname,'../resources/screen_time/web/config-transfer.js'),'utf8');
async function main(){
 const context=vm.createContext({TextEncoder});vm.runInContext(source,context);const transfer=context.FocuserConfigTransfer;
 const config={format:'focuser-config',version:1,groups:[{id:'fixture',name:'Private category',domains:['private.example'],apps:['private.exe']}]};
 const text=transfer.encode(config);assert(text.includes('private.example'));
 assert.deepEqual(JSON.parse(JSON.stringify(transfer.decode(text))),config);
 assert.deepEqual(JSON.parse(JSON.stringify(transfer.decode('\uFEFF'+text))),config);
 assert.throws(()=>transfer.encode({...config,history:{}}));
 assert.throws(()=>transfer.decode('{broken JSON'));
 assert.throws(()=>transfer.decode('x'.repeat(262145)));
 assert.throws(()=>transfer.decode(JSON.stringify({format:'focuser-encrypted-config',version:1,ciphertext:'fixture'})));
 console.log('Plain config checks passed: no password/crypto dependency, round trip, BOM, malformed and oversized files, private-state rejection');
}
module.exports=main;if(require.main===module)main().catch(error=>{console.error(error);process.exitCode=1});
