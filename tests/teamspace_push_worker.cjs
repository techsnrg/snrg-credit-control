/* Unit-only browser mocks: never read or control a real browser. */
const assert=require('node:assert/strict');
(async()=>{
 let calls=[],unsubscribed=0;
 const subscription={endpoint:'https://fcm.googleapis.com/unit-fixture',unsubscribe:async()=>{unsubscribed++}};
 let registration={active:{scriptURL:'https://erp.test/service-worker.js'},pushManager:{getSubscription:async()=>subscription}};
 global.window={isSecureContext:true,PushManager:{},Notification:{},location:{origin:'https://erp.test'}};
 Object.defineProperty(global,'navigator',{value:{serviceWorker:{getRegistration:async()=>registration}},configurable:true});
 global.frappe={call:async args=>{calls.push(args);return {message:{enabled:false}}}};
 const {default:component}=await import('../snrg_credit_control/public/customer_workspace/notifications.js');
 const warn=console.warn;console.warn=()=>{};const preferences=component.setup();console.warn=warn;
 await preferences.disable();
 assert.equal(unsubscribed,0,'Disabling Teamspace must not unsubscribe another app’s worker');
 assert.equal(calls.length,0,'Another app’s push token must not be sent to Teamspace');
 registration.active.scriptURL='https://erp.test/assets/snrg_credit_control/teamspace_push/worker.js';
 await preferences.disable();
 assert.equal(unsubscribed,1);
 assert.equal(calls.length,1);
 assert.equal(calls[0].method,'snrg_credit_control.customer_workspace.notifications.unsubscribe');
 console.log('PASS: Teamspace push controls only its own service worker');
})().catch(error=>{console.error(error);process.exit(1)});
