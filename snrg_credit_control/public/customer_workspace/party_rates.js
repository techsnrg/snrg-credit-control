import {onMounted, ref, watch} from 'vue';

const endpoint = 'snrg_credit_control.customer_workspace.party_rates.list_rates';

export default {
  props: {party: String, kind: String, person: Function, revision: Number},
  setup(props) {
    const source = ref('interaction');
    const offset = ref(0);
    const rows = ref([]);
    const hasMore = ref(false);
    const canQuote = ref(false);
    const loading = ref(true);
    const error = ref('');
    let requestId = 0;

    async function load() {
      const id = ++requestId;
      loading.value = true;
      error.value = '';
      try {
        const {message} = await frappe.call({
          method: endpoint,
          args: {[props.kind.toLowerCase()]: props.party, source: source.value, start: offset.value},
          type: 'GET',
          silent: true,
        });
        if (id !== requestId) return;
        rows.value = message.rows;
        hasMore.value = message.has_more;
        canQuote.value = message.can_quote;
      } catch {
        if (id === requestId) error.value = 'Could not load rates.';
      } finally {
        if (id === requestId) loading.value = false;
      }
    }

    function select(value) {
      source.value = value;
      offset.value = 0;
      load();
    }

    function changePage(direction) {
      offset.value += direction * (source.value === 'quotation' ? 10 : 25);
      load();
    }

    function quoteUrl(name) {
      const route = props.kind === 'Supplier' ? 'supplier-quotation' : 'quotation';
      return '/desk/' + route + '/' + encodeURIComponent(name);
    }

    function formatDate(date) {
      if (!date) return '';
      return new Intl.DateTimeFormat('en-IN', {dateStyle: 'medium'})
        .format(new Date(String(date).slice(0, 10) + 'T12:00:00'));
    }

    const formatRate = rate => new Intl.NumberFormat('en-IN', {maximumFractionDigits: 6}).format(rate);
    watch(() => props.revision, () => select('interaction'));
    onMounted(load);
    return {source, offset, rows, hasMore, canQuote, loading, error, load, select, changePage, quoteUrl, formatDate, formatRate};
  },
  template: `
    <section aria-label="Relationship rates">
      <div v-if="canQuote" class="tabs" role="group" aria-label="Rate source">
        <button type="button" :class="{active:source==='interaction'}" :aria-pressed="source==='interaction'"
          @click="select('interaction')">Logged rates</button>
        <button type="button" :class="{active:source==='quotation'}" :aria-pressed="source==='quotation'"
          @click="select('quotation')">ERPNext quotations</button>
      </div>
      <p v-if="error" role="alert">{{error}} <button type="button" @click="load">Retry</button></p>
      <p v-else-if="loading" role="status">Loading rates…</p>
      <p v-else-if="!rows.length">{{source==='quotation'?'No submitted quotations on this page.':'No rates logged yet.'}}</p>
      <div v-else class="ts-lead-rates">
        <table :aria-label="kind==='Supplier'?'Rates received':'Rates offered'">
          <thead><tr><th>Date</th><th>Item</th><th>Rate</th><th>Unit</th><th v-if="source==='quotation'">Quantity</th>
            <th>{{source==='quotation'?'Quotation':'Logged by'}}</th></tr></thead>
          <tbody>
            <tr v-for="row in rows" :key="row.name">
              <td>{{formatDate(row.date)}}</td>
              <td>{{row.item || row.item_code}}<small v-if="row.item_code && row.item_code!==row.item">{{row.item_code}}</small></td>
              <td>{{row.currency}} {{formatRate(row.rate)}}</td>
              <td>{{row.unit}}</td>
              <td v-if="source==='quotation'">{{row.qty}}</td>
              <td v-if="source==='quotation'"><a :href="quoteUrl(row.quotation)" target="_blank" rel="noopener">{{row.quotation}} ↗</a></td>
              <td v-else>{{person(row.spoken_by)}}<small>{{row.channel}}</small></td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="offset || hasMore" class="ts-lead-pagination">
        <button type="button" :disabled="loading || !offset" @click="changePage(-1)">Previous</button>
        <button type="button" :disabled="loading || !hasMore" @click="changePage(1)">Next</button>
      </div>
    </section>
  `,
};
