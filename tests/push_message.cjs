const assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
(async()=>{
 const handlers={},shown=[],opened=[];
 const self={location:{origin:'https://erp.test'},addEventListener:(name,handler)=>handlers[name]=handler,skipWaiting:async()=>{},registration:{showNotification:async(title,options)=>shown.push({title,...options})}};
 const clients={claim:async()=>{},openWindow:async url=>opened.push(url)};
 vm.runInNewContext(fs.readFileSync('snrg_credit_control/public/teamspace_push/worker.js','utf8'),{self,clients,URL});
 let pending;const waitUntil=p=>pending=p;
 handlers.push({data:{json:()=>({title:'Kajal completed: Collect email addresses',body:'Outcome: Collected 24 email addresses. · In Progress → Completed',url:'/teamspace?task=CA-1',tag:'LOG-1'})},waitUntil});await pending;
 assert.match(shown[0].title,/Kajal completed/);assert.match(shown[0].body,/24 email/);
 handlers.notificationclick({notification:{data:shown[0].data,close(){}},waitUntil});await pending;assert.equal(opened[0],'/teamspace?task=CA-1');
 for(const url of ['https://evil.test/teamspace','//evil.test/teamspace','javascript:alert(1)','/teamspace-evil']){
  handlers.push({data:{json:()=>({url,title:'x'.repeat(200),body:'y'.repeat(500)})},waitUntil});await pending;
  assert.equal(shown.at(-1).data.url,'/teamspace');assert.equal(shown.at(-1).title.length,120);assert.equal(shown.at(-1).body.length,280);
 }
 handlers.push({data:{json(){throw Error('bad json')}},waitUntil});await pending;assert.equal(shown.at(-1).title,'Teamspace update');
 handlers.notificationclick({notification:{data:{url:'https://evil.test'},close(){}},waitUntil});await pending;assert.equal(opened.at(-1),'/teamspace');
 console.log('PASS readable payload, exact-task click, size limits, malformed data and external-link rejection');
})().catch(e=>{console.error(e);process.exit(1)});
