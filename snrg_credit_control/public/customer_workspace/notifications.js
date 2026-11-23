import {ref,onMounted} from 'vue';
const method='snrg_credit_control.customer_workspace.notifications.';
const call=async(name,args={})=>(await frappe.call({method:method+name,args})).message;
const worker='/assets/snrg_credit_control/teamspace_push/worker.js';
async function ownRegistration(){const registration=await navigator.serviceWorker.getRegistration(worker);const script=registration?.active||registration?.installing||registration?.waiting;return script&&new URL(script.scriptURL).href===new URL(worker,window.location.origin).href?registration:null;}
export async function refreshPushWorker(){if(window.isSecureContext && 'serviceWorker' in navigator){const registration=await ownRegistration();if(registration)await registration.update()}}
export default {
 setup(){
  const configured=ref(false),enabled=ref(false),busy=ref(false),error=ref(''),message=ref(''),email=ref(null);
  const supported=window.isSecureContext && 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window;
  let publicKey;
  async function refresh(){const state=await call('status');configured.value=state.configured;publicKey=state.public_key;email.value=state.email;if(supported){const reg=await ownRegistration();const existing=await reg?.pushManager.getSubscription();enabled.value=!!existing;if(existing&&configured.value)await call('subscribe',{subscription:JSON.stringify(existing.toJSON())})}}
  async function enable(){busy.value=true;error.value='';try{if(Notification.permission==='denied')throw new Error('Notifications are blocked. Allow them in this browser’s site settings, then try again.');const permission=await Notification.requestPermission();if(permission!=='granted')throw new Error('Permission was not granted. You can enable notifications later.');const registration=await navigator.serviceWorker.register(worker);const active=registration.active||await new Promise((resolve,reject)=>{const installing=registration.installing||registration.waiting;if(!installing)return reject(new Error('Please reopen this panel and retry.'));installing.addEventListener('statechange',()=>{if(installing.state==='activated')resolve(installing);if(installing.state==='redundant')reject(new Error('Unable to activate notifications.'))})});const key=Uint8Array.from(atob(publicKey.replace(/-/g,'+').replace(/_/g,'/')),c=>c.charCodeAt(0));const subscription=await registration.pushManager.getSubscription()||await registration.pushManager.subscribe({userVisibleOnly:true,applicationServerKey:key});await call('subscribe',{subscription:JSON.stringify(subscription.toJSON())});enabled.value=true;message.value='Push enabled for this browser. Repeat this on each device you use.'}catch(e){error.value=e.message||'Unable to enable push.'}finally{busy.value=false}}
  async function disable(){busy.value=true;error.value='';try{const reg=await ownRegistration(),subscription=await reg?.pushManager.getSubscription();if(subscription){await call('unsubscribe',{endpoint:subscription.endpoint});await subscription.unsubscribe()}enabled.value=false;message.value='Push disabled on this browser.'}catch(e){error.value=e.message||'Unable to disable push.'}finally{busy.value=false}}
  async function test(){busy.value=true;error.value='';try{const result=await call('send_test');message.value='Test notification created.'+(result.email_enabled?' Email delivery requested.':' Email is off in your notification settings.')+(result.push_devices?' Push queued for registered devices.':' Enable push on a device to test it.')}catch(e){error.value=e.message||'Unable to send test.'}finally{busy.value=false}}
  function emailSettings(){frappe.set_route('Form','Notification Settings',frappe.session.user)}
  onMounted(()=>refresh().catch(e=>error.value=e.message||'Unable to load notification preferences.'));
  return {supported,configured,enabled,busy,error,message,email,enable,disable,test,emailSettings};
 },
 template:`<section class="notification-preferences"><h3>Email notifications</h3><p>Assignments, updates, mentions and due reminders use your ERPNext email preferences.</p><p v-if="email" class="hint">Assignments: {{email.assignment?'On':'Off'}} · Mentions: {{email.mention?'On':'Off'}}</p><button type="button" @click="emailSettings">Manage email preferences ↗</button><h3>Push on this device</h3><p>Receive updates on desktop, Android or your installed iPhone app, even when Teamspace is not open. Notifications show the task, who updated it and a short summary; your device settings control lock-screen previews.</p><p v-if="!supported" class="hint">This browser does not support Web Push. Use Chrome, Edge or Firefox on a secure connection.</p><p v-else-if="!configured" class="hint">Push setup is pending on this site.</p><button v-else type="button" :disabled="busy" :class="{primary:!enabled}" @click="enabled?disable():enable()">{{busy?'Working…':enabled?'Disable push on this device':'Enable push on this device'}}</button><hr><button type="button" :disabled="busy" @click="test">Send me a test notification</button><p v-if="message" role="status" class="hint">{{message}}</p><p v-if="error" role="alert" class="late">{{error}}</p></section>`
};

export const NotificationInbox = {
 emits: ['settings'],
 props: {openTask: {type: Function, required: true}},
 setup(props){
  const rows=ref([]), loading=ref(true), error=ref(''), scope=ref('all'), marking=ref(false);
  let request=0;
  async function load(filter=scope.value){
   const id=++request;
   scope.value=filter;
   rows.value=[];
   loading.value=true;
   error.value='';
   try{const result=await call('inbox',{scope:filter}); if(id===request)rows.value=result}
   catch{if(id===request)error.value='Unable to load notifications.'}
   finally{if(id===request)loading.value=false}
  }
  async function markAll(){
   if(marking.value)return;
   marking.value=true;
   error.value='';
   try{
    await frappe.call({method:method+'mark_inbox_read',type:'POST',args:{scope:scope.value}});
    await load();
   }catch{error.value='Unable to mark all notifications as read.'}
   finally{marking.value=false}
  }
  async function markRead(row){
   if(row.read)return;
   try{
    await frappe.call({method:'frappe.desk.doctype.notification_log.notification_log.mark_as_read',type:'POST',args:{docname:row.tag}});
    row.read=true;
   }catch{error.value='Unable to mark the notification as read.'}
  }
  async function open(row){
   error.value='';
   const url=row.url && new URL(row.url,window.location.origin);
   const task=url?.pathname==='/teamspace' && url.searchParams.get('task');
   if(task){
    try{await props.openTask(task,()=>markRead(row))}
    catch{error.value='Unable to open this task. It may have been removed or you may no longer have access.'}
    return;
   }
   await markRead(row);
   if(url && url.origin===window.location.origin)window.location.assign(url.href);
   else error.value='This notification has no linked record.';
  }
  onMounted(load);
  return {rows,loading,error,scope,load,open,markAll,marking,when:value=>new DOMParser().parseFromString(frappe.datetime.comment_when(value),'text/html').body.textContent};
 },
 template:`<section class="notification-inbox">
  <div class="notification-tools"><div role="group" aria-label="Filter notifications" class="notification-filters"><button v-for="filter in ['all','teamspace']" :key="filter" type="button" :aria-pressed="scope===filter" :disabled="marking" @click="load(filter)">{{filter==='all'?'All':'Teamspace'}}</button></div><button type="button" @click="$emit('settings')">Settings</button></div>
  <button type="button" :disabled="loading || marking" @click="markAll">Mark all as read</button>
  <p v-if="loading" role="status">Loading notifications…</p>
  <p v-if="error" role="alert">{{error}} <button type="button" @click="load()">Retry</button></p>
  <p v-if="!loading && !error && !rows.length">{{scope==='all'?'No notifications yet.':'No Teamspace notifications yet.'}}</p>
  <ul v-if="rows.length">
   <li v-for="row in rows" :key="row.tag" :class="{unread:!row.read}">
    <component :is="row.url?'a':'button'" :href="row.url || undefined" :type="row.url?undefined:'button'" class="notification-item" @click.prevent="open(row)"><strong>{{row.title}}</strong><span v-if="row.body!==row.title">{{row.body}}</span><small>{{when(row.creation)}}<template v-if="!row.read"> · Unread</template></small></component>
   </li>
  </ul>
 </section>`
};
