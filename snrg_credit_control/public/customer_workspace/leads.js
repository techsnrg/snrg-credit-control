import {nextTick, onMounted, onUnmounted, ref, watch} from 'vue';
import Plus from '@lucide/vue/dist/esm/icons/plus.mjs';
import X from '@lucide/vue/dist/esm/icons/x.mjs';
import './leads.css';

const endpoint = 'snrg_credit_control.customer_workspace.leads.';
const activityEndpoint = 'snrg_credit_control.customer_workspace.lead_activity.';
const activityFields = () => ({rate: '', currency: 'INR', rate_basis: ''});

const ActivityInputs = {
  props: {rate: [String, Number], currency: String, basis: String},
  emits: ['update:rate', 'update:currency', 'update:basis', 'files'],
  template: `
    <label>Rate given (optional)
      <input :value="rate" type="number" min="0" max="999999999999.999999" step="0.000001"
        @input="$emit('update:rate', $event.target.value)">
    </label>
    <template v-if="rate !== ''">
      <label>Currency<input :value="currency" required maxlength="3"
        @input="$emit('update:currency', $event.target.value.toUpperCase())"></label>
      <label>Rate for<input :value="basis" required maxlength="140" placeholder="Product, unit, or pricing basis"
        @input="$emit('update:basis', $event.target.value)"></label>
    </template>
    <label>Attachments (optional)<input type="file" multiple @change="$emit('files', Array.from($event.target.files))"></label>
  `,
};
const scopes = [
  {value: 'all', label: 'All Leads'},
  {value: 'mine', label: 'My Leads'},
  {value: 'due', label: 'Due for Follow-up'},
  {value: 'rates', label: 'Rates given'},
];

export default {
  components: {Plus, X, ActivityInputs},
  props: {user: String, today: String, person: Function},
  setup() {
    const scope = ref('all');
    const search = ref('');
    const divisionFilter = ref('');
    const duplicates = ref([]);
    let checkedDraft;
    const rows = ref([]);
    const page = ref(0);
    const hasMore = ref(false);
    const loading = ref(false);
    const error = ref('');
    const dialog = ref(null);
    const mode = ref('');
    const details = ref(null);
    const sources = ref([]);
    const divisions = ref([]);
    const form = ref({});
    const followUp = ref({});
    const contactForm = ref(null);
    const activityFiles = ref([]);
    const preview = ref(null);
    const busy = ref(false);
    const formError = ref('');
    const notice = ref('');
    let listRequest = 0;
    let searchTimer;
    let opener;

    async function request(method, args = {}, type = 'GET', files = []) {
      const methodName = method.includes('.') ? method : endpoint + method;
      if (files.length) {
        const body = new FormData();
        for (const [field, value] of Object.entries(args)) body.append(field, value ?? '');
        for (const file of files) body.append('attachments', file);
        const response = await fetch('/api/method/' + methodName, {
          method: 'POST', body, credentials: 'same-origin',
          headers: {'X-Frappe-CSRF-Token': frappe.csrf_token || window.csrf_token || ''},
        });
        const result = await response.json();
        if (!response.ok) throw new Error('Could not save the activity and attachments.');
        return result.message;
      }
      const result = await frappe.call({method: methodName, args, type, silent: true});
      return result.message;
    }

    function attachmentUrl(file, download = false) {
      return '/api/method/' + activityEndpoint + 'attachment?' + new URLSearchParams({
        name: file.name, download: Number(download),
      });
    }

    function canPreview(file) {
      return /\.(pdf|png|jpe?g|gif|webp)$/i.test(file.file_name);
    }

    function formatRate(rate) {
      return new Intl.NumberFormat('en-IN', {maximumFractionDigits: 6}).format(rate);
    }

    function selectFiles(files) {
      activityFiles.value = files;
      formError.value = files.length > 5 ? 'Attach up to five files per activity.' : '';
    }

    function message(error, fallback) {
      return error instanceof Error ? error.message : fallback;
    }

    async function load() {
      clearTimeout(searchTimer);
      const requestId = ++listRequest;
      loading.value = true;
      error.value = '';
      try {
        const filters = {start: page.value * 50, division: divisionFilter.value};
        const result = scope.value === 'rates'
          ? await request(activityEndpoint + 'rates', filters)
          : await request('list_leads', {...filters, scope: scope.value, search: search.value.trim()});
        if (requestId !== listRequest) return;
        rows.value = result.rows;
        divisions.value = result.divisions;
        hasMore.value = result.has_more;
      } catch (err) {
        if (requestId === listRequest) error.value = message(err, 'Could not load leads. Try again.');
      } finally {
        if (requestId === listRequest) loading.value = false;
      }
    }

    function changeScope(value) {
      scope.value = value;
      page.value = 0;
      load();
    }

    function changePage(offset) {
      page.value += offset;
      load();
    }

    async function show(value, event) {
      opener = event.currentTarget;
      mode.value = value;
      details.value = null;
      contactForm.value = null;
      duplicates.value = [];
      activityFiles.value = [];
      preview.value = null;
      formError.value = '';
      await nextTick();
      dialog.value.showModal();
    }

    function close() {
      preview.value = null;
      dialog.value.close();
      mode.value = '';
      opener?.focus();
    }

    function setDetails(result) {
      details.value = result;
      activityFiles.value = [];
      followUp.value = {kind: 'Call', note: '', follow_up: result.lead.follow_up || '', spoke_with: '', ...activityFields()};
    }

    async function work(operation, fallback) {
      busy.value = true;
      formError.value = '';
      try {
        await operation();
      } catch (err) {
        formError.value = message(err, fallback);
      } finally {
        busy.value = false;
      }
    }

    async function add(event) {
      form.value = {contact: '', organization: '', mobile: '', email: '', source: '', division: '', city: '', state: '', initial_discussion: '', ...activityFields()};
      await show('new', event);
      await loadOptions();
    }

    async function loadOptions() {
      await work(async () => {
        const options = await request('intake_options');
        sources.value = options.sources;
        divisions.value = options.divisions;
      }, 'Could not load lead options.');
    }

    async function edit() {
      const lead = details.value.lead;
      form.value = {
        contact: lead.lead_name || '', organization: lead.organization || '',
        mobile: lead.mobile_no || '', email: lead.email || '',
        source: lead.source || '', division: lead.division || '',
        city: lead.city || '', state: lead.state || '',
      };
      mode.value = 'edit';
      await nextTick();
      dialog.value.querySelector('form input')?.focus();
      await loadOptions();
    }

    function cancelEdit() {
      mode.value = 'detail';
      formError.value = '';
      nextTick(() => dialog.value.querySelector('.ts-edit-lead')?.focus());
    }

    async function open(name, event) {
      await show('detail', event);
      await work(async () => setDetails(await request('detail', {name})), 'Could not open this lead.');
    }

    async function save(confirmDuplicate = false) {
      if (mode.value === 'new' && activityFiles.value.length > 5) return;
      await work(async () => {
        if (mode.value === 'edit') {
          const {name, modified} = details.value.lead;
          details.value = await request('edit_details', {name, modified, ...form.value}, 'POST');
          cancelEdit();
          notice.value = 'Lead details saved';
          await load();
          return;
        }
        const draft = JSON.stringify(form.value);
        const result = await request('create_lead', {
          ...form.value, confirm_duplicate: Number(confirmDuplicate && checkedDraft === draft),
        }, 'POST', activityFiles.value);
        if (result.possible_duplicates?.length) {
          checkedDraft = draft;
          duplicates.value = result.possible_duplicates;
          await nextTick();
          dialog.value.querySelector('.ts-lead-duplicates')?.focus();
          return;
        }
        duplicates.value = [];
        setDetails(result);
        mode.value = 'detail';
        notice.value = 'Lead added';
        changeScope('all');
      }, mode.value === 'edit' ? 'Could not save the details. Reopen the lead and try again.' : 'Could not add the lead. Check the details and try again.');
    }

    async function update(action) {
      if (action === 'follow_up' && activityFiles.value.length > 5) return;
      const {name, modified} = details.value.lead;
      await work(async () => {
        const result = await request('update_lead', {
          name, modified, action, ...(action === 'follow_up' ? followUp.value : {}),
        }, 'POST', action === 'follow_up' ? activityFiles.value : []);
        setDetails(result);
        notice.value = {pick_up: 'Lead picked up', follow_up: 'Follow-up saved', close: 'Lead closed'}[action];
        await load();
      }, 'Could not update the lead. Reopen it and try again.');
    }

    function startContact() {
      contactForm.value = {contact: '', designation: '', mobile: '', email: ''};
    }

    async function saveContact() {
      if (!contactForm.value.mobile.trim() && !contactForm.value.email.trim()) {
        formError.value = 'Enter a phone number or an email.';
        return;
      }
      await work(async () => {
        details.value = await request('add_contact', {
          name: details.value.lead.name, ...contactForm.value,
        }, 'POST');
        contactForm.value = null;
        notice.value = 'Contact added';
        await load();
      }, 'Could not add the contact. Check the details and try again.');
    }

    async function moreHistory() {
      await work(async () => {
        const result = await request('detail', {name: details.value.lead.name, start: details.value.history.length});
        details.value.history.push(...result.history);
        details.value.has_more = result.has_more;
      }, 'Could not load earlier activity.');
    }

    function formatDate(value) {
      if (!value) return '';
      return new Intl.DateTimeFormat('en-IN', {day: 'numeric', month: 'short', year: 'numeric'})
        .format(new Date(value.slice(0, 10) + 'T12:00:00'));
    }

    watch(form, () => { duplicates.value = []; }, {deep:true});
    watch(search, () => {
      clearTimeout(searchTimer);
      ++listRequest;
      loading.value = true;
      page.value = 0;
      searchTimer = setTimeout(load, 250);
    });
    onMounted(load);
    onUnmounted(() => clearTimeout(searchTimer));
    return {
      scopes, scope, search, divisionFilter, duplicates, rows, page, hasMore, loading, error, dialog, mode, details, sources, divisions, form,
      followUp, busy, formError, notice, changeScope, changePage, load, close, add, open,
      edit, cancelEdit, save, update, moreHistory, formatDate, contactForm, startContact, saveContact,
      preview, attachmentUrl, canPreview, formatRate, selectFiles, activityFiles,
    };
  },
  template: `
    <section class="ts-leads" aria-label="Leads" :aria-busy="loading">
      <div class="ts-leads-toolbar">
        <div class="tabs ts-lead-tabs" role="group" aria-label="Lead view">
          <button v-for="item in scopes" :key="item.value" type="button"
            :class="{active:scope===item.value}" :aria-pressed="scope===item.value"
            @click="changeScope(item.value)">{{item.label}}</button>
        </div>
        <button type="button" class="primary" @click="add"><Plus aria-hidden="true"/>Add lead</button>
      </div>
      <label v-if="scope!=='rates'" class="ts-lead-search">Search leads
        <input v-model="search" type="search" maxlength="140" placeholder="Name, mobile, company or lead ID">
      </label>
      <label class="ts-lead-search">Division
        <select v-model="divisionFilter" @change="changeScope(scope)">
          <option value="">All divisions</option>
          <option v-for="division in divisions" :key="division">{{division}}</option>
        </select>
      </label>
      <p v-if="error" role="alert">{{error}} <button type="button" @click="load">Retry</button></p>
      <p v-else-if="loading" role="status">Loading leads…</p>
      <p v-else-if="!rows.length" class="ts-lead-empty">
        {{scope==='rates'?'No rates recorded for this view.':search.trim() || divisionFilter?'No leads match your filters.':scope==='due'?'No leads due for follow-up.':scope==='mine'?'You haven’t picked up any leads.':'No leads yet.'}}
      </p>
      <div v-else-if="scope==='rates'" class="ts-lead-rates">
        <table aria-label="Rates given">
          <thead><tr><th>Lead</th><th>Rate for</th><th>Rate</th><th>Recorded</th></tr></thead>
          <tbody>
            <tr v-for="quote in rows" :key="quote.name">
              <td><button type="button" @click="open(quote.lead_id, $event)">{{quote.organization || quote.lead_name}}</button>
                <small>{{quote.lead_id}}<template v-if="quote.division"> · {{quote.division}}</template></small></td>
              <td>{{quote.rate_basis}}</td>
              <td>{{quote.currency}} {{formatRate(quote.rate)}}</td>
              <td>{{formatDate(quote.creation)}}<small>{{person(quote.owner)}}</small></td>
            </tr>
          </tbody>
        </table>
      </div>
      <ul v-else class="ts-lead-list">
        <li v-for="lead in rows" :key="lead.name">
          <button type="button" class="ts-lead-row" @click="open(lead.name, $event)">
            <span><strong>{{lead.organization || lead.lead_name}}</strong>
              <small v-if="lead.organization">{{lead.lead_name}}</small>
              <small>{{lead.mobile_no || lead.email}}</small><small>{{lead.name}}</small><small v-if="lead.division">{{lead.division}}</small></span>
            <span><small>Handled by</small>{{lead.lead_owner ? person(lead.lead_owner) : 'Unassigned'}}</span>
            <span><small>Next follow-up</small><span :class="{late:!lead.closed && lead.follow_up && lead.follow_up<today}">
              {{lead.closed?'Closed':formatDate(lead.follow_up)||'No date'}}
            </span></span>
            <span class="ts-lead-last"><small>Last activity</small>{{lead.last_activity || 'Lead added'}}</span>
          </button>
        </li>
      </ul>
      <div v-if="page || hasMore" class="ts-lead-pagination">
        <button type="button" :disabled="loading || !page" @click="changePage(-1)">Previous</button>
        <button type="button" :disabled="loading || !hasMore" @click="changePage(1)">Next</button>
      </div>
      <p class="ts-lead-announcement" role="status">{{notice}}</p>

      <dialog ref="dialog" class="ts-lead-drawer" :class="{'ts-lead-split':preview}" aria-labelledby="ts-lead-title" @cancel.prevent="!busy && close()">
        <div class="ts-lead-main">
        <header class="ts-lead-drawer-heading">
          <h2 id="ts-lead-title">{{mode==='new'?'Add lead':mode==='edit'?'Edit lead details':details?.lead.organization || details?.lead.lead_name || 'Lead'}}</h2>
          <button type="button" class="ts-lead-close" aria-label="Close lead drawer" :disabled="busy" @click="close"><X aria-hidden="true"/></button>
        </header>
        <p v-if="formError" role="alert" class="late">{{formError}}</p>
        <form v-if="mode==='new' || mode==='edit'" class="ts-lead-form" @submit.prevent="save()">
          <label>Company<input v-model="form.organization" required maxlength="140" autofocus></label>
          <label>City<input v-model="form.city" required maxlength="140" autocomplete="address-level2"></label>
          <label>State<input v-model="form.state" required maxlength="140" autocomplete="address-level1"></label>
          <label>Division<select v-model="form.division" required><option value="">Choose a division</option>
            <option v-for="division in divisions" :key="division">{{division}}</option>
          </select></label>
          <label>Contact name<input v-model="form.contact" required maxlength="140"></label>
          <label>Phone<input v-model="form.mobile" required type="tel" maxlength="140"></label>
          <label>Email (optional)<input v-model="form.email" type="email" maxlength="140"></label>
          <label>Source<select v-model="form.source" required><option value="">Choose a source</option>
            <option v-for="source in sources" :key="source">{{source}}</option>
          </select></label>
          <template v-if="mode==='new'">
            <label>Initial discussion (optional)<textarea v-model="form.initial_discussion" rows="3" maxlength="2000"></textarea></label>
            <ActivityInputs v-model:rate="form.rate" v-model:currency="form.currency" v-model:basis="form.rate_basis" @files="selectFiles"/>
          </template>
          <section v-if="duplicates.length" class="ts-lead-duplicates" tabindex="-1" aria-label="Possible duplicate leads">
            <h3>Possible duplicate leads</h3>
            <p>These leads share the phone number or company and city. Save separately if this is a different enquiry.</p>
            <ul>
              <li v-for="match in duplicates" :key="match.name">
                {{match.organization || match.lead_name}}<span v-if="match.city"> · {{match.city}}</span> · {{match.name}}
              </li>
            </ul>
          </section>
          <div class="ts-lead-actions">
            <button v-if="duplicates.length" type="button" class="primary" :disabled="busy" @click="save(true)">Save as separate lead</button>
            <button v-else type="submit" class="primary" :disabled="busy">{{mode==='edit'?'Save changes':'Save lead'}}</button>
            <button v-if="mode==='edit'" type="button" :disabled="busy" @click="cancelEdit">Cancel</button>
          </div>
        </form>
        <template v-else-if="details">
          <div class="ts-lead-contact">
            <strong>{{details.lead.lead_name}}</strong>
            <span class="muted">Lead ID {{details.lead.name}}</span>
            <span v-if="details.lead.city || details.lead.state">{{[details.lead.city, details.lead.state].filter(Boolean).join(', ')}}</span>
            <span v-if="details.lead.division">{{details.lead.division}}</span>
            <a v-if="details.lead.mobile_no" :href="'tel:'+details.lead.mobile_no">{{details.lead.mobile_no}}</a>
            <a v-if="details.lead.email" :href="'mailto:'+details.lead.email">{{details.lead.email}}</a>
            <span v-if="details.lead.source">{{details.lead.source}}</span>
          </div>
          <button v-if="details.can_edit_details" type="button" class="ts-edit-lead" :disabled="busy"
            @click="edit">Edit details</button>
          <section class="ts-lead-contacts" aria-labelledby="ts-contacts-title">
            <div class="ts-lead-drawer-heading">
              <h3 id="ts-contacts-title">Additional contacts</h3>
              <button v-if="details.can_add_contact && !contactForm" type="button" :disabled="busy"
                @click="startContact"><Plus aria-hidden="true"/>Add contact</button>
            </div>
            <ul v-if="details.contacts.length" class="ts-lead-history">
              <li v-for="contact in details.contacts" :key="contact.name" class="ts-lead-contact">
                <strong>{{contact.full_name}}</strong>
                <small v-if="contact.designation">{{contact.designation}}</small>
                <a v-if="contact.mobile_no || contact.phone" :href="'tel:'+(contact.mobile_no || contact.phone)">
                  {{contact.mobile_no || contact.phone}}
                </a>
                <a v-if="contact.email_id" :href="'mailto:'+contact.email_id">{{contact.email_id}}</a>
              </li>
            </ul>
            <form v-if="contactForm" class="ts-lead-form" @submit.prevent="saveContact">
              <label>Contact name<input v-model="contactForm.contact" required maxlength="140"></label>
              <label>Role<input v-model="contactForm.designation" maxlength="140"></label>
              <label>Phone<input v-model="contactForm.mobile" type="tel" maxlength="140"></label>
              <label>Email<input v-model="contactForm.email" type="email" maxlength="140"></label>
              <div class="ts-lead-actions">
                <button type="submit" class="primary" :disabled="busy">Save contact</button>
                <button type="button" :disabled="busy" @click="contactForm=null">Cancel</button>
              </div>
            </form>
          </section>
          <p>{{details.lead.closed?'Closed':details.lead.lead_owner?'Handled by '+person(details.lead.lead_owner):'Unassigned'}}</p>
          <p v-if="details.lead.follow_up">Next follow-up · {{formatDate(details.lead.follow_up)}}</p>
          <button v-if="!details.lead.closed && !details.lead.lead_owner" type="button" class="primary"
            :disabled="busy" @click="update('pick_up')">Pick up lead</button>
          <form v-if="!details.lead.closed && details.lead.lead_owner===user" class="ts-lead-form" @submit.prevent="update('follow_up')">
            <h3>Follow up</h3>
            <label>Activity<select v-model="followUp.kind"><option>Call</option><option>Note</option></select></label>
            <label v-if="followUp.kind==='Call'">Spoke with<select v-model="followUp.spoke_with">
              <option value="">{{details.lead.lead_name}} (Primary contact)</option>
              <option v-for="contact in details.contacts" :key="contact.name" :value="contact.name">
                {{contact.full_name}}{{contact.designation ? ' · '+contact.designation : ''}}
              </option>
            </select></label>
            <label>What happened?<textarea v-model="followUp.note" rows="3" maxlength="2000"></textarea></label>
            <label>Next follow-up<input type="date" v-model="followUp.follow_up"></label>
            <ActivityInputs :key="details.lead.modified" v-model:rate="followUp.rate" v-model:currency="followUp.currency"
              v-model:basis="followUp.rate_basis" @files="selectFiles"/>
            <div class="ts-lead-actions">
              <button type="submit" class="primary" :disabled="busy">Save follow-up</button>
              <button type="button" :disabled="busy" @click="update('close')">Close lead</button>
            </div>
          </form>
          <h3 class="ts-lead-activity-heading">Activity</h3>
          <p v-if="!details.history.length" class="muted">No activity logged yet.</p>
          <ul v-else class="ts-lead-history">
            <li v-for="entry in details.history" :key="entry.name">
              <small>{{entry.comment_by || person(entry.owner)}} · {{formatDate(entry.creation)}}</small>
              <p>{{entry.content}}</p>
              <p v-if="entry.rate != null"><strong>{{entry.currency}} {{formatRate(entry.rate)}}</strong> · {{entry.rate_basis}}</p>
              <ul v-if="entry.attachments.length" class="ts-activity-files">
                <li v-for="file in entry.attachments" :key="file.name">
                  <button type="button" @click="preview=file">{{file.file_name}}</button>
                </li>
              </ul>
            </li>
          </ul>
          <button v-if="details.has_more" type="button" :disabled="busy" @click="moreHistory">Earlier activity</button>
        </template>
        <p v-else-if="busy" role="status">Loading lead…</p>
        </div>
        <aside v-if="preview" class="ts-attachment-preview" aria-label="Attachment preview">
          <div class="ts-lead-drawer-heading">
            <strong>{{preview.file_name}}</strong>
            <button type="button" @click="preview=null" aria-label="Close attachment preview"><X aria-hidden="true"/></button>
          </div>
          <a :href="attachmentUrl(preview, true)">Download</a>
          <iframe v-if="canPreview(preview)" :src="attachmentUrl(preview)" :title="'Preview '+preview.file_name"></iframe>
          <p v-else>Download this file to open it.</p>
        </aside>
      </dialog>
    </section>
  `,
};
