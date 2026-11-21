import DatePicker from './date_picker.js';
import {ref,onMounted} from 'vue';
const endpoint='snrg_credit_control.customer_workspace.team_activity.';
export default {
 components:{DatePicker},props:{today:String},emits:['open-record'],
 setup(props){
  const filters=ref({from_date:props.today,to_date:props.today,user:'',activity_type:'',party_type:'',search:'',call_outcome:''});
  const data=ref(null),loading=ref(false),error=ref(''),page=ref(0),applied=ref(null);let token=0;
  async function load(reset=false,selection={...filters.value}){if(reset)page.value=0;const mine=++token;loading.value=true;error.value='';try{const args={...selection,start:page.value*50};const result=(await frappe.call({method:endpoint+'report',args})).message;if(mine!==token)return;data.value=result;applied.value={...selection}}catch(e){if(mine===token){error.value=e.message||'Unable to load team activity.';data.value=null;applied.value=null}}finally{if(mine===token)loading.value=false}}
  function drill(user,type){filters.value={...(applied.value||filters.value),user,activity_type:type};load(true)}
  function next(n){page.value+=n;load(false,{...applied.value})}
  function reset(){filters.value={from_date:props.today,to_date:props.today,user:'',activity_type:'',party_type:'',search:'',call_outcome:''};load(true)}
  function exportRows(){if(!applied.value)return;const query=new URLSearchParams(applied.value);window.open('/api/method/'+endpoint+'export?'+query.toString(),'_blank','noopener,noreferrer')}
  function stamp(value){return new Date(String(value).replace(' ','T')).toLocaleString('en-IN',{day:'numeric',month:'short',year:'numeric',hour:'2-digit',minute:'2-digit'})}
  onMounted(()=>load());return {filters,data,loading,error,page,load,drill,next,reset,exportRows,stamp};
 },
 template:`<section class="team-activity" aria-label="Private team activity">
 <p class="hint">Private to your login · Recorded entries and task completion history</p>
 <form class="activity-filters" @submit.prevent="load(true)">
 <div class="activity-date-field"><span>From date</span><DatePicker label="From date" :today="today" v-model="filters.from_date"/></div><div class="activity-date-field"><span>To date</span><DatePicker label="To date" :today="today" v-model="filters.to_date"/></div>
 <label>Team member<select v-model="filters.user"><option value="">Everyone</option><option v-for="person in data?.people||[]" :key="person.user" :value="person.user">{{person.name}}</option></select></label>
 <label>Activity<select v-model="filters.activity_type"><option value="">All activity</option><option>Interaction</option><option>Calls</option><option>Connected calls</option><option>Task created</option><option>Task completed</option></select></label>
 <label>Relationship<select v-model="filters.party_type"><option value="">All relationships</option><option>Customer</option><option>Supplier</option><option>General</option></select></label>
 <label>Customer / supplier<input v-model="filters.search" placeholder="Name or code" maxlength="100"></label>
 <label>Call outcome<select v-model="filters.call_outcome"><option value="">All outcomes</option><option>Connected</option><option>No answer</option><option>Busy</option><option>Call back</option><option>Wrong number</option></select></label>
 <div class="activity-filter-actions"><button class="primary" :disabled="loading">Apply filters</button><button type="button" @click="reset" :disabled="loading">Reset</button></div></form>
 <p v-if="error" role="alert" class="late">{{error}}</p><p v-if="loading" role="status" class="hint">Loading activity…</p>
 <template v-if="data"><div class="feed-heading"><h2>By team member</h2><button type="button" :disabled="loading" @click="exportRows">Export Excel</button></div>
 <p class="hint">Counts follow the applied filters. Click a count to see the entries.</p>
 <div class="compact-table-wrap" :aria-busy="loading"><table class="compact-table activity-summary"><caption class="sr-only">Activity counts by team member</caption><thead><tr><th scope="col">Team member</th><th scope="col">Interactions</th><th scope="col">Calls attempted</th><th scope="col">Connected</th><th scope="col">Tasks created</th><th scope="col">Task completions</th></tr></thead><tbody><tr v-for="person in data.summary" :key="person.user"><th scope="row">{{person.name}}</th><td v-for="metric in [{key:'interactions',label:'interactions',type:'Interaction'},{key:'calls',label:'calls',type:'Calls'},{key:'connected',label:'connected calls',type:'Connected calls'},{key:'created',label:'tasks created',type:'Task created'},{key:'completed',label:'task completions',type:'Task completed'}]" :key="metric.key"><button class="activity-count" :disabled="loading||!person[metric.key]" :aria-label="person.name+': '+person[metric.key]+' '+metric.label" @click="drill(person.user,metric.type)">{{person[metric.key]}}</button></td></tr></tbody></table></div>
 <div class="feed-heading"><h2>Entries <span class="hint">{{data.count}}</span></h2></div>
 <details class="hint activity-counting-note"><summary>How counts work</summary><p>Interactions count the person who recorded them; “Spoken by” is shown separately. Automatic task updates are excluded. Each responsible person’s linked task counts separately. Completions use the audit actor and time; reopening and completing again records another completion. Task details show their current state. Dates use the site’s recorded timestamps; interaction filters use the time logged, not a backdated conversation time. Older completions without retained audit history cannot be counted.</p></details>
 <p v-if="!data.count" class="empty">No activity matches these filters.</p>
 <div class="compact-table-wrap" v-else :aria-busy="loading"><table class="compact-table activity-entries"><caption class="sr-only">Recorded team activity entries</caption><thead><tr><th scope="col">Recorded at</th><th scope="col">Team member</th><th scope="col">Activity</th><th scope="col">Customer / supplier</th><th scope="col">Summary and next step</th></tr></thead><tbody><tr v-for="entry in data.rows" :key="entry.key"><td>{{stamp(entry.timestamp)}}</td><td>{{entry.actor_name}}<small v-if="entry.spoken_by&&entry.spoken_by!==entry.actor">Spoken by {{entry.spoken_by_name}}</small></td><td>{{entry.activity_type}}<small v-if="entry.channel">{{entry.channel}}<template v-if="entry.call_outcome"> · {{entry.call_outcome}}</template></small></td><td>{{entry.party_name}}<small>{{entry.party_type}}</small></td><td><details><summary>{{entry.summary||'View entry'}}</summary><p v-if="entry.instructions" class="activity-instructions">{{entry.instructions}}</p><p v-if="entry.assigned_to">Responsible: {{entry.assigned_to_name}}<br>Due: {{entry.due_date||'—'}} · Current status: {{entry.status}}<br>Created by: {{entry.logged_by_name}}</p><p v-if="entry.happened_on">Conversation time: {{stamp(entry.happened_on)}}</p><button type="button" @click="$emit('open-record',entry.doctype,entry.name)">Open record ↗</button></details></td></tr></tbody></table></div>
 <div class="pagination" v-if="page||data.has_more"><button :disabled="loading||!page" @click="next(-1)">Previous</button><span>{{data.count}} entries · Page {{page+1}}</span><button :disabled="loading||!data.has_more" @click="next(1)">Next</button></div>
 </template></section>`
};
