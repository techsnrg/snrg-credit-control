import {computed, onMounted} from 'vue';

export function legacySections(html) {
  const document = new DOMParser().parseFromString(html || '', 'text/html');
  const sections = [];
  for (const node of document.body.childNodes) {
    if (node.nodeType === 1 && node.matches('h1,h2,h3')) {
      sections.push({id: 'section-' + (sections.length + 1), title: node.textContent, body: ''});
    } else if (node.textContent.trim() || node.nodeType === 1) {
      if (!sections.length) sections.push({id: 'overview', title: 'Overview', body: ''});
      const fragment = document.createElement('div');
      fragment.append(node.cloneNode(true));
      sections.at(-1).body += fragment.innerHTML;
    }
  }
  return sections;
}

export default {
  props: {sections: Array, body: String, prefix: String},
  setup(props) {
    const items = computed(() => props.sections?.length ? props.sections : legacySections(props.body));
    const anchor = section => props.prefix + '-' + section.id;
    function jump(section) {
      const id = anchor(section);
      window.history.replaceState(window.history.state, '', '#' + id);
      document.getElementById(id)?.focus({preventScroll: true});
      document.getElementById(id)?.scrollIntoView({block: 'start'});
    }
    onMounted(() => {
      const section = items.value.find(item => '#' + anchor(item) === location.hash);
      if (section) jump(section);
    });
    return {items, anchor, jump};
  },
  template: `
    <div class="guide-reader">
      <nav class="guide-toc" aria-label="On this page" v-if="items.length > 1">
        <details open>
          <summary>On this page</summary>
          <ol><li v-for="section in items" :key="section.id">
            <a :href="'#'+anchor(section)" @click.prevent="jump(section)">{{section.title}}</a>
          </li></ol>
        </details>
      </nav>
      <div class="guide-sections">
        <section v-for="section in items" :key="section.id" class="guide-section">
          <h3 :id="anchor(section)" tabindex="-1">{{section.title}}</h3>
          <div :class="{'guide-beside': section.image && section.layout==='beside'}">
            <div class="knowledge-body" v-html="section.body"></div>
            <figure v-if="section.image">
              <a :href="section.image" :download="section.id+'-screenshot'"><img :src="section.image" :alt="section.alt" loading="lazy"></a>
              <figcaption v-if="section.caption">{{section.caption}}</figcaption>
            </figure>
          </div>
          <figure v-if="section.video_src || section.video_url" class="guide-video">
            <video :src="section.video_src || section.video_url" controls playsinline preload="none" :aria-label="'Video for '+section.title"></video>
            <figcaption><a :href="section.video_src || section.video_url" target="_blank" rel="noopener noreferrer">Open video in a new tab</a></figcaption>
            <details :open="section.video_text_kind==='Written summary'">
              <summary>{{section.video_text_kind}}</summary>
              <p class="guide-video-text">{{section.video_text}}</p>
            </details>
          </figure>
        </section>
      </div>
    </div>
  `,
};
