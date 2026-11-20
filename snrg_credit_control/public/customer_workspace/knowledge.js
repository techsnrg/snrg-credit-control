import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue';
import './knowledge.css';
import BookOpen from '@lucide/vue/dist/esm/icons/book-open.mjs';
import ArrowRight from '@lucide/vue/dist/esm/icons/arrow-right.mjs';
import GuideReader, {legacySections} from './guide_reader.js';

const endpoint = 'snrg_credit_control.customer_workspace.knowledge.';

export default {
  components: {GuideReader, BookOpen, ArrowRight},
  props: {canManage: Boolean},
  setup() {
    const search = ref('');
    const department = ref('');
    const searching = ref(true);
    const searchError = ref('');
    let searchRequest = 0;
    const guides = ref([]);
    const catalogue = ref([]);
    const departments = ref([]);
    const guide = ref(null);
    const editing = ref(false);
    const editorHost = ref(null);
    const correctionOpen = ref(false);
    const correction = ref('');
    const busy = ref(false);
    const error = ref('');
    const notice = ref('');
    const createOptions = ref(null);
    const newGuide = ref({});
    const reviewQueue = ref(false);
    const changeSummary = ref('');
    let editor;
    const sections = ref([]);
    const currentSection = ref(0);
    const activeSection = computed(() => sections.value[currentSection.value]);
    const template = ref('');
    const uploadingVideo = ref(false);
    const newSection = (title = '') => ({id: crypto.randomUUID(), title, body: ''});

    function captureSection() {
      if (editor && activeSection.value) activeSection.value.body = editor.get_input_value();
    }

    async function selectSection(index) {
      captureSection();
      currentSection.value = index;
      await editor.set_value(activeSection.value.body || '');
    }

    async function addSection() {
      sections.value.push(newSection());
      await selectSection(sections.value.length - 1);
    }

    async function applyTemplate() {
      const titles = template.value === 'sop'
        ? ['Purpose', 'Before you start', 'Steps', 'Exceptions']
        : ['Overview', 'Common questions'];
      sections.value = titles.map(title => newSection(title));
      currentSection.value = 0;
      await editor.set_value('');
      template.value = '';
    }

    function moveSection(direction) {
      const from = currentSection.value;
      const to = from + direction;
      const [section] = sections.value.splice(from, 1);
      sections.value.splice(to, 0, section);
      currentSection.value = to;
    }

    async function removeSection() {
      const index = currentSection.value;
      sections.value.splice(index, 1);
      currentSection.value = Math.min(index, sections.value.length - 1);
      await editor.set_value(activeSection.value.body || '');
    }

    async function uploadVideo(event) {
      const file = event.target.files[0];
      event.target.value = '';
      if (!file || uploadingVideo.value) return;
      if (!/\.(mp4|webm)$/i.test(file.name) || file.size > 50 * 1024 * 1024) {
        error.value = 'Choose an MP4 or WebM video up to 50 MB.';
        return;
      }
      const section = activeSection.value;
      uploadingVideo.value = true;
      error.value = '';
      try {
        const data = new FormData();
        data.append('name', guide.value.name);
        data.append('file', file);
        const response = await fetch('/api/method/' + endpoint + 'upload_section_video', {
          method: 'POST', body: data, credentials: 'same-origin',
          headers: {'X-Frappe-CSRF-Token': frappe.csrf_token || window.csrf_token || ''},
        });
        if (!response.ok) throw new Error('Video upload failed. Check the format and size, then retry.');
        const {message} = await response.json();
        if (!message?.name) throw new Error('The video upload did not complete.');
        section.video_file = message.name;
        section.video_filename = message.filename;
        section.video_url = '';
      } catch (exception) {
        error.value = exception.message;
      } finally {
        uploadingVideo.value = false;
      }
    }

    function addScreenshot(event) {
      const file = event.target.files[0];
      if (!file) return;
      event.target.value = '';
      const section = activeSection.value;
      if (!['image/png', 'image/jpeg', 'image/webp'].includes(file.type) || file.size > 2000000) {
        error.value = 'Choose a PNG, JPEG, or WebP screenshot under 2 MB.';
        return;
      }
      error.value = '';
      const reader = new FileReader();
      reader.onload = () => { section.image = reader.result; };
      reader.onerror = () => { error.value = 'Unable to read the screenshot.'; };
      reader.readAsDataURL(file);
    }
    const filtered = computed(() => guides.value.filter(row => (!department.value || row.department === department.value) &&
      (!reviewQueue.value || row.pending_review || row.review_overdue)));

    const related = computed(() => guide.value ? catalogue.value.filter(item =>
      item.published && item.name !== guide.value.name && item.department === guide.value.department
    ).slice(0, 5) : []);

    async function run(operation) {
      if (busy.value) return;
      busy.value = true;
      error.value = '';
      notice.value = '';
      try {
        await operation();
      } catch (exception) {
        error.value = exception.message || 'Unable to complete this action.';
      } finally {
        busy.value = false;
      }
    }

    async function call(method, args = {}, type = 'GET') {
      const result = await frappe.call({method: endpoint + method, args, type});
      return result.message;
    }

    async function find() {
      const request = ++searchRequest;
      const query = search.value.trim();
      searching.value = true;
      searchError.value = '';
      try {
        const results = await call('search', {query});
        if (request !== searchRequest) return;
        guides.value = results;
        if (!query) {
          catalogue.value = results;
          departments.value = [...new Set(results.map(row => row.department))].sort();
        }
      } catch (exception) {
        if (request === searchRequest) searchError.value = exception.message || 'Unable to search guides.';
      } finally {
        if (request === searchRequest) searching.value = false;
      }
    }

    watch(search, (_query, _previous, onCleanup) => {
      ++searchRequest;
      searching.value = true;
      searchError.value = '';
      const timer = setTimeout(find, 200);
      onCleanup(() => clearTimeout(timer));
    });
    onUnmounted(() => { ++searchRequest; });

    async function startCreate() {
      await run(async () => {
        createOptions.value = await call('guide_options');
        newGuide.value = {title: '', department: '', owner: '', audience_role: '', reference_doctype: ''};
      });
    }

    async function createGuide() {
      let saved;
      await run(async () => {
        saved = await call('create', newGuide.value, 'POST');
        createOptions.value = null;
      });
      if (saved) {
        await open(saved.name);
        await edit();
      }
    }

    async function open(name) {
      await run(async () => {
        guide.value = await call('read', {name});
        editing.value = false;
        correctionOpen.value = false;
        correction.value = '';
        const url = new URL(window.location.href);
        if (url.searchParams.get('guide') !== name) url.hash = '';
        url.searchParams.set('guide', name);
        history.replaceState(history.state, '', url);
        await nextTick();
        document.querySelector('#cw .knowledge-title')?.focus();
      });
    }

    function back() {
      guide.value = null;
      editing.value = false;
      const url = new URL(window.location.href);
      url.searchParams.delete('guide');
      history.replaceState(history.state, '', url);
      find();
      nextTick(() => document.querySelector('#cw .knowledge-search input')?.focus());
    }

    async function edit() {
      await run(async () => {
        changeSummary.value = guide.value.change_summary || '';
        await frappe.require('controls.bundle.js');
        const structured = guide.value.draft ? guide.value.draft_sections : guide.value.sections;
        sections.value = structured?.length ? structured.map(section => ({...section}))
          : legacySections(guide.value.draft || guide.value.body);
        if (!sections.value.length) sections.value.push(newSection());
        currentSection.value = 0;
        editing.value = true;
        await nextTick();
        editor = frappe.ui.form.make_control({
          parent: editorHost.value,
          df: {
            fieldname: 'guide_body', fieldtype: 'Text Editor', label: 'Instructions', hide_label: 1,
            get_toolbar_options: () => [
              [{header: [false, 2, 3]}], ['bold', 'italic'],
              [{list: 'ordered'}, {list: 'bullet'}, {list: 'check'}], ['link', 'clean'],
            ],
          },
          render_input: true,
        });
        await editor.set_value(activeSection.value.body || '');
        editor.quill.root.setAttribute('aria-label', 'Instructions');
        editor.quill.focus();
      });
    }

    async function saveDraft() {
      if (uploadingVideo.value) return;
      await run(async () => {
        captureSection();
        guide.value = await call('save_draft', {
          name: guide.value.name, version: guide.value.version, sections: sections.value,
          change_summary: changeSummary.value,
        }, 'POST');
        editing.value = false;
        notice.value = 'Draft saved. Review it below before publishing.';
      });
    }

    async function requestReview() {
      await run(async () => {
        guide.value = await call('request_review', {name: guide.value.name, version: guide.value.version}, 'POST');
        notice.value = 'Draft added to the review queue.';
      });
    }

    async function publish() {
      await run(async () => {
        guide.value = await call('publish', {name: guide.value.name, version: guide.value.version}, 'POST');
        notice.value = 'Guide published.';
      });
    }

    async function suggest() {
      await run(async () => {
        const task = await call('suggest', {name: guide.value.name, note: correction.value}, 'POST');
        correction.value = '';
        correctionOpen.value = false;
        notice.value = 'Correction sent to the guide owner. Teamspace task ' + task + '.';
      });
    }

    onMounted(async () => {
      const name = new URLSearchParams(location.search).get('guide');
      await find();
      if (name) await open(name);
    });

    return {search, department, departments, filtered, related, guide, editing, editorHost, correctionOpen,
      correction, busy, searching, searchError, error, notice, open, back, edit, saveDraft, publish, suggest,
      sections, currentSection, activeSection, template, selectSection, addSection, applyTemplate, moveSection, removeSection, addScreenshot, uploadVideo, uploadingVideo,
      createOptions, newGuide, reviewQueue, changeSummary, startCreate, createGuide, requestReview};
  },
  template: `
    <section class="knowledge" aria-label="Knowledge" :aria-busy="busy">
      <p v-if="error" class="knowledge-message late" role="alert">{{error}}</p>
      <p v-if="notice" class="knowledge-message" role="status">{{notice}}</p>
      <form v-if="createOptions" class="knowledge-guide" @submit.prevent="createGuide">
        <h2>New guide</h2>
        <div class="knowledge-fields">
          <label>Title<input v-model.trim="newGuide.title" required maxlength="140"></label>
          <label>Department<input v-model.trim="newGuide.department" required maxlength="140"></label>
          <label>Owner<select v-model="newGuide.owner"><option value="">Me</option>
            <option v-for="person in createOptions.people" :key="person.user" :value="person.user">{{person.label}}</option>
          </select></label>
          <label>Audience<select v-model="newGuide.audience_role"><option value="">All Teamspace staff</option>
            <option v-for="role in createOptions.roles" :key="role">{{role}}</option>
          </select></label>
          <label>ERPNext form<select v-model="newGuide.reference_doctype"><option value="">None</option>
            <option>Customer</option>
          </select></label>
        </div>
        <div class="knowledge-actions">
          <button class="primary" :disabled="busy">Create guide</button>
          <button type="button" @click="createOptions=null">Cancel</button>
        </div>
      </form>
      <template v-else-if="!guide">
        <div class="knowledge-library">
          <div class="knowledge-search" role="search" aria-label="Search guides">
            <label>Search guides<input v-model="search" type="search" placeholder="Search titles and instructions"></label>
            <label>Department<select v-model="department"><option value="">All departments</option>
              <option v-for="item in departments" :key="item">{{item}}</option>
            </select></label>
          </div>
          <div class="knowledge-library-bar">
            <h2>{{reviewQueue ? 'Review queue' : 'Guides'}} <small v-if="!searching && !searchError">{{filtered.length}}</small></h2>
            <div class="knowledge-actions" v-if="canManage">
              <button :aria-pressed="reviewQueue" @click="reviewQueue=!reviewQueue">{{reviewQueue ? 'Show all guides' : 'Review queue'}}</button>
              <button class="primary" @click="startCreate" :disabled="busy">New guide</button>
            </div>
          </div>
          <ul class="knowledge-results" v-if="filtered.length" :aria-busy="searching">
            <li v-for="item in filtered" :key="item.name">
              <button class="knowledge-card" :disabled="busy" @click="open(item.name)">
                <span class="knowledge-card-top"><span class="knowledge-card-icon"><BookOpen aria-hidden="true"/></span>
                  <span class="knowledge-card-department">{{item.department}}</span><ArrowRight class="knowledge-card-arrow" aria-hidden="true"/>
                </span>
                <strong>{{item.title}}</strong>
                <span v-if="item.excerpt" class="knowledge-card-excerpt">{{item.excerpt}}</span>
                <small class="knowledge-card-meta">{{item.published ? item.owner : 'Draft'}}<template v-if="item.pending_review"> · Awaiting review</template><template v-else-if="item.review_overdue"> · Review due</template></small>
              </button>
            </li>
          </ul>
          <p v-if="searchError" role="alert">{{searchError}}</p>
          <p v-else-if="searching && !filtered.length" role="status">Finding guides…</p>
          <p v-else-if="!filtered.length" class="knowledge-library-empty" role="status">{{reviewQueue && !search && !department ? 'No guides are due for review.' : 'No guides found.'}}</p>
        </div>
      </template>
      <div v-else class="knowledge-reading" :class="{'has-related': !editing && !correctionOpen && related.length}">
      <article class="knowledge-guide">
        <button class="knowledge-back" :disabled="busy" @click="back">← All guides</button>
        <h2 class="knowledge-title" tabindex="-1">{{guide.title}}</h2>
        <p class="muted">{{guide.department}} · {{guide.owner}}<template v-if="guide.reviewed_on"> · Reviewed {{guide.reviewed_on}}</template></p>
        <form v-if="editing" @submit.prevent="saveDraft">
          <div class="guide-editor">
            <div v-if="!guide.draft && !guide.published" class="knowledge-actions">
              <label>Start from a template<select v-model="template"><option value="">Choose template</option><option value="sop">SOP</option><option value="faq">Quick reference</option></select></label>
              <button type="button" :disabled="!template" @click="applyTemplate">Use template</button>
            </div>
            <div class="guide-section-list" aria-label="Sections">
              <button v-for="(section, index) in sections" :key="section.id" type="button" :aria-pressed="currentSection===index" @click="selectSection(index)">{{section.title || 'Untitled section'}}</button>
              <button type="button" :disabled="sections.length>=24" @click="addSection">Add section</button>
            </div>
            <label>Section heading<input v-model.trim="activeSection.title" maxlength="140" required></label>
            <div class="knowledge-actions">
              <button type="button" :disabled="currentSection===0" @click="moveSection(-1)">Move up</button>
              <button type="button" :disabled="currentSection===sections.length-1" @click="moveSection(1)">Move down</button>
              <button type="button" :disabled="sections.length===1" @click="removeSection">Remove section</button>
            </div>
            <label>Instructions</label>
            <div ref="editorHost"></div>
            <label>Section screenshot<input type="file" accept="image/png,image/jpeg,image/webp" @change="addScreenshot"></label>
            <div v-if="activeSection.image" :key="activeSection.id" class="guide-media-fields">
              <img :src="activeSection.image" :alt="activeSection.alt || ''">
              <label>Image description<input v-model.trim="activeSection.alt" maxlength="250" required></label>
              <label>Caption<input v-model.trim="activeSection.caption" maxlength="500"></label>
              <label>Image placement<select v-model="activeSection.layout"><option value="full">Below instructions</option><option value="beside">Beside instructions</option></select></label>
              <button type="button" @click="activeSection.image=''">Remove screenshot</button>
            </div>
            <fieldset class="guide-media-fields guide-video-fields">
              <legend>Section video</legend>
              <label>Upload video<input type="file" accept=".mp4,.webm,video/mp4,video/webm" :disabled="uploadingVideo" @change="uploadVideo"></label>
              <small class="muted">MP4 or WebM, up to 50 MB.</small>
              <span v-if="uploadingVideo" role="status">Uploading video…</span>
              <template v-if="activeSection.video_file">
                <span>{{activeSection.video_filename}}</span>
                <button type="button" :disabled="uploadingVideo" @click="activeSection.video_file=''">Remove uploaded video</button>
              </template>
              <label v-else>Video link<input type="url" v-model.trim="activeSection.video_url" maxlength="2048" placeholder="https://…/walkthrough.mp4"></label>
              <small v-if="!activeSection.video_file" class="muted">Use a direct HTTPS link to an MP4 or WebM your readers can access.</small>
              <template v-if="activeSection.video_file || activeSection.video_url">
                <label>Text format<select v-model="activeSection.video_text_kind" required>
                  <option value="" disabled>Choose a format</option><option>Transcript</option><option>Written summary</option>
                </select></label>
                <label>{{activeSection.video_text_kind || 'Transcript or written summary'}}<textarea v-model.trim="activeSection.video_text" maxlength="12000" required></textarea></label>
              </template>
            </fieldset>
          </div>
          <label>Change summary<textarea v-model="changeSummary" maxlength="1000"></textarea></label>
          <div class="knowledge-actions">
            <button class="primary" :disabled="busy || uploadingVideo">Save draft</button>
            <button type="button" :disabled="busy" @click="editing=false">Cancel</button>
          </div>
        </form>
        <template v-else>
          <div class="knowledge-actions" v-if="guide.can_edit">
            <button :disabled="busy" @click="edit">{{guide.draft ? 'Edit draft' : 'Edit guide'}}</button>
            <button v-if="guide.draft && guide.can_publish" class="primary" :disabled="busy" @click="publish">Publish draft</button>
            <button v-else-if="guide.draft && !guide.pending_review" class="primary" :disabled="busy" @click="requestReview">Request review</button>
            <span v-if="guide.pending_review" role="status">Awaiting manager review</span>
          </div>
          <details v-if="guide.draft" class="knowledge-preview" open>
            <summary>Draft preview</summary>
            <p v-if="guide.change_summary" class="muted">{{guide.change_summary}}</p>
            <GuideReader :sections="guide.draft_sections" :body="guide.draft" prefix="draft"/>
          </details>
          <div v-if="guide.published" class="knowledge-body">
            <h3 v-if="guide.draft">Published guide</h3>
            <GuideReader :sections="guide.sections" :body="guide.body" prefix="guide"/>
          </div>
          <form v-if="correctionOpen" @submit.prevent="suggest">
            <label>What should change?<textarea v-model="correction" required maxlength="2000"></textarea></label>
            <div class="knowledge-actions">
              <button class="primary" :disabled="busy">Send to guide owner</button>
              <button type="button" :disabled="busy" @click="correctionOpen=false">Cancel</button>
            </div>
          </form>
          <button v-else-if="guide.published" :disabled="busy" @click="correctionOpen=true">Suggest a correction</button>
        </template>
      </article>
      <aside v-if="!editing && !correctionOpen && related.length" class="knowledge-related" aria-label="Related guides">
        <h2>Related guides</h2>
        <ul>
          <li v-for="item in related" :key="item.name">
            <button :disabled="busy" @click="open(item.name)"><span>{{item.title}}</span><ArrowRight aria-hidden="true"/></button>
          </li>
        </ul>
      </aside>
      </div>
    </section>
  `,
};
