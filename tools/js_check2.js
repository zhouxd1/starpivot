const fs=require('fs');
const s=fs.readFileSync('C:/Users/love_/starpivot/static/index.html','utf8').match(/<script>([\s\S]*?)<\/script>/)[1];
const els={};
const mk=()=>({style:{},classList:{add(){},toggle(){},contains:()=>false},addEventListener(){},appendChild(){},append(){},value:"",textContent:"",innerHTML:"",placeholder:"",src:"",disabled:false,dataset:{},onclick:null,closest:()=>null});
global.document={getElementById:id=>els[id]||(els[id]=mk()),querySelector:()=>mk(),querySelectorAll:()=>[],createElement:()=>mk(),addEventListener(){},body:{classList:{add(){},toggle(){},contains:()=>false}}};
global.window=global; global.alert=m=>console.log('[alert]',m); global.confirm=()=>true;
global.fetch=(u,o)=>Promise.resolve({json:()=>Promise.resolve({ok:true,msg:'test',content:'# report'})});
global.location={host:'x'};
global.setInterval=()=>0; global.setTimeout=(f)=>0;
try{
  new Function(s)();
  // 模拟点保存
  (async()=>{ try{ await saveSettings(); console.log('saveSettings ✓ 执行完成(无异常)'); }catch(e){ console.log('saveSettings ✗', e.message); } })();
  (async()=>{ try{ await makeReport({target:mk()}); console.log('makeReport ✓ 执行完成(无异常)'); }catch(e){ console.log('makeReport ✗', e.message); } })();
}catch(e){ console.log('脚本载入失败:', e.message); }
