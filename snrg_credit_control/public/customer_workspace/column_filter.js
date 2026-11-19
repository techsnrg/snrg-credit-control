import {ref, nextTick, onMounted, onUnmounted} from 'vue';
import ListFilter from '@lucide/vue/dist/esm/icons/list-filter.mjs';
export default {
  components:{ListFilter},
  props:{label:String, field:String, value:{type:Object,default:()=>({})}, text:Boolean},
  emits:['apply','sort'],
  setup(props,{emit}){
    const root=ref(null),trigger=ref(null),panel=ref(null),open=ref(false),minimum=ref(''),maximum=ref(''),query=ref(''),error=ref(''),position=ref({});
    function place(){if(!open.value||!trigger.value||!panel.value)return;const r=trigger.value.getBoundingClientRect(),w=Math.min(280,innerWidth-24),h=panel.value.scrollHeight;position.value={position:'fixed',width:w+'px',left:Math.max(12,Math.min(r.left,innerWidth-w-12))+'px',top:Math.max(12,Math.min(r.bottom+8,innerHeight-h-12))+'px'};}
    function show(){minimum.value=props.value.min??'';maximum.value=props.value.max??'';query.value=props.value.query??'';error.value='';open.value=!open.value;nextTick(()=>{place();panel.value?.querySelector('input')?.focus()});}
    function close(){open.value=false;nextTick(()=>trigger.value?.focus());}
    function apply(){if(!props.text&&minimum.value!==''&&maximum.value!==''&&Number(minimum.value)>Number(maximum.value)){error.value='Minimum cannot exceed maximum.';return;}emit('apply',props.text?{query:query.value}:{min:minimum.value,max:maximum.value});close();}
    function clear(){emit('apply',{});close();}
    function sort(direction){emit('sort',direction);close();}
    function outside(e){if(open.value&&!root.value?.contains(e.target))open.value=false;}
    onMounted(()=>{document.addEventListener('pointerdown',outside);document.addEventListener('scroll',place,true);window.addEventListener('resize',place);});
    onUnmounted(()=>{document.removeEventListener('pointerdown',outside);document.removeEventListener('scroll',place,true);window.removeEventListener('resize',place);});
    return {root,trigger,panel,open,minimum,maximum,query,error,position,show,close,apply,clear,sort};
  },
  template:`<div class="column-filter" ref="root" @keydown.esc.stop.prevent="close"><span>{{label}}</span><button type="button" ref="trigger" class="column-filter-trigger" :class="{'is-filtered':value.query||value.min!==undefined&&value.min!==''||value.max!==undefined&&value.max!==''}" :aria-label="'Filter '+label" aria-haspopup="dialog" :aria-expanded="open" @click="show"><ListFilter aria-hidden="true"/></button><div v-if="open" ref="panel" class="column-filter-panel" :style="position" role="dialog" :aria-label="'Filter '+label"><strong>{{label}}</strong><form @submit.prevent="apply"><label v-if="text">Name, code or mobile<input v-model="query" type="search"></label><template v-else><label>Minimum amount<input type="number" step="any" v-model="minimum"></label><label>Maximum amount<input type="number" step="any" v-model="maximum"></label></template><p v-if="error" class="late" role="alert">{{error}}</p><div class="column-filter-actions"><button type="button" @click="clear">Clear</button><button type="submit" class="primary">Apply</button></div></form><div class="column-filter-sort"><button type="button" @click="sort('asc')">{{text?'Sort A–Z':'Sort low to high'}}</button><button type="button" @click="sort('desc')">{{text?'Sort Z–A':'Sort high to low'}}</button></div></div></div>`
};
