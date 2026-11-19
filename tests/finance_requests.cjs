const assert=require('node:assert/strict'),fs=require('node:fs');
(async()=>{
 const source=fs.readFileSync('snrg_credit_control/public/customer_workspace/finance_requests.js','utf8');
 const {financeRequests}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
 let clock=0,calls=0,release;const request=()=>{calls++;return new Promise(resolve=>release=resolve)};
 const cache=financeRequests(request,{now:()=>clock});
 const a=cache.load('AR',{company:'A',columns:{min:0,max:5}},'one'),b=cache.load('AR',{columns:{max:5,min:0},company:'A'},'one');
 await Promise.resolve();assert.equal(calls,1);release({rows:[1]});await Promise.all([a,b]);
 await cache.load('AR',{company:'A',columns:{min:0,max:5}},'one');assert.equal(calls,1);
 clock=15001;const expired=cache.load('AR',{company:'A',columns:{min:0,max:5}},'one');await Promise.resolve();assert.equal(calls,2);release({});await expired;
 const different=cache.load('AP',{company:'A'},'two');await Promise.resolve();assert.equal(calls,3);cache.clear();release({});await different;
 const fresh=cache.load('AP',{company:'A'},'two');await Promise.resolve();assert.equal(calls,4);release({});await fresh;
 let fails=0;const errors=financeRequests(async()=>{fails++;throw Error('denied')});for(let i=0;i<2;i++)await assert.rejects(errors.load('AR',{},'one'));assert.equal(fails,2);
 console.log('PASS: duplicate requests merge; 15s expiry, refresh, user/filter separation and errors');
})().catch(e=>{console.error(e);process.exit(1)});
