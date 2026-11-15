<script setup lang="ts">
import {computed,ref,watch} from 'vue';
import PageHeading from '../components/common/PageHeading.vue';
import Notice from '../components/common/Notice.vue';
import Status from '../components/common/Status.vue';
import Empty from '../components/common/Empty.vue';
import AlternativesRange from '../components/AlternativesRange.vue';
import AlternativesPlan from '../components/AlternativesPlan.vue';
import {useTask} from '../hooks/useTask';
import {researchApi} from '../api/research';
import {fmt} from '../utils/format';

const p=defineProps<{studies:any[];alternativesRuns:any[];user:any;reloadResearch:()=>Promise<void>}>(),emit=defineEmits(['open']);
const studyId=ref(0);
const runId=ref(0);
const name=ref('备选票精确边界 '+new Date().toLocaleTimeString());
const task=useTask();
const prefill=ref<{endpoint:'min'|'max';plan:{vote_id:number;category:string}[]}|null>(null);
const preflight=ref<any>(null);
const study=computed(()=>p.studies.find(s=>s.id===(studyId.value||p.studies[0]?.id)));
const completed=computed(()=>p.alternativesRuns.filter(r=>r.status==='completed'));
const run=ref<any>(null);
async function loadRun(){
 const listing=p.alternativesRuns.find(r=>r.id===runId.value)||completed.value[0]||null;
 if(!listing){run.value=null;return}
 try{run.value=await researchApi.alternativesRun(listing.id)}catch(e){run.value=listing}
}
const runKey=computed(()=>`${runId.value}|${p.alternativesRuns.map(r=>r.id+':'+r.status).join(',')}`);
watch(runKey,loadRun,{immediate:true});

async function check(){
 preflight.value=null;
 await task.act(async()=>{preflight.value=await researchApi.preflight({study_id:study.value.id})},
  '规模检查通过：可精确计算全部合法方案');
}
async function queue(){
 prefill.value=null;
 await task.act(async()=>{
  const created=await researchApi.createAlternativesRun({study_id:study.value.id,name:name.value});
  await p.reloadResearch();
  runId.value=created.id;
 },'备选票精确分析已排队；超限会明确拒绝，不返回近似值');
}
function onVerify(endpoint:'min'|'max',plan:{vote_id:number;category:string}[]){prefill.value={endpoint,plan}}
</script>
<template>
<PageHeading index="05" title="备选票：给出结论的精确范围。" description="原票不动，逐票限定可选类别；求所有合法方案中有定义κ的精确最小/最大值。">
 <a class="primary" href="#results">原确定票分析 →</a>
</PageHeading>

<div class="config-layout">
 <form class="input-sheet" @submit.prevent="queue">
  <small>EXACT RANGE OVER CANDIDATE VOTES</small>
  <h2>排队备选票分析</h2>
  <label>研究<select :value="study?.id||0" @change="studyId=Number(($event.target as HTMLSelectElement).value);preflight=null"><option v-for="s in studies" :key="s.id" :value="s.id">{{s.name}}</option></select></label>
  <label>运行名称<input v-model="name" required/></label>
  <p>只统计声明了备选集合的票；确定票保持原票。规模超时或超内存时明确拒绝并记录原因，不输出近似值。</p>
  <div v-if="user.role!=='viewer'" class="plan-toolbar">
   <button type="button" @click="check" :disabled="task.state.busy||!study">先检查精确规模</button>
   <button class="primary" :disabled="task.state.busy||!study">送入精确边界队列 →</button>
  </div>
  <p v-else>观察员只读已有备选票运行。</p>
  <div v-if="preflight" class="verify-result">
   <dl><div><dt>备选票</dt><dd>{{preflight.candidate_vote_count}}</dd></div><div><dt>受影响试样</dt><dd>{{preflight.candidate_specimen_count}}</dd></div><div><dt>合法方案</dt><dd>{{preflight.legal_scheme_count}}</dd></div><div><dt>状态数</dt><dd>{{preflight.state_count}}</dd></div></dl>
   <p>转移上界 {{preflight.transition_upper_bound}}；已按25秒/256MB安全包络预检通过。</p>
  </div>
  <Notice v-bind="task.state"/>
 </form>
 <aside class="method-note">
  <small>EXACT / NOT SAMPLING</small>
  <h2>κ = (3NS − 2T)<br/>÷ 2((3N)² − T)</h2>
  <p>S=ΣᵢΣⱼnᵢⱼ(nᵢⱼ−1)，T=Σⱼ类别总票数²。对每个类别总数，只需可达S的最小/最大值，用精确动态规划穷尽全部合法组合。</p>
  <p>Pe=1（全票同类）方案κ未定义，单独计数并从边界中排除；不存在有定义方案时明确说明。</p>
  <p>这是定类方案边界，不是抽样区间，也不替代原确定票分析。</p>
 </aside>
</div>

<section class="section">
 <div class="section-head"><h2>备选票运行</h2><span>{{alternativesRuns.length}} 个</span></div>
 <label>查看运行<select :value="run?.id||0" @change="runId=Number(($event.target as HTMLSelectElement).value)"><option v-for="r in alternativesRuns" :key="r.id" :value="r.id">#{{r.id}} {{r.name}} · {{r.status}}<template v-if="r.kappa_min!==null"> · [{{fmt(r.kappa_min,4)}}, {{fmt(r.kappa_max,4)}}]</template></option></select></label>
 <p v-if="run"><Status :value="run.status"/>　<span v-if="run.error" class="error-text">{{run.error}}</span></p>
</section>

<template v-if="run?.result">
 <AlternativesRange :result="run.result" @verify="onVerify"/>
 <AlternativesPlan :run="run" :prefill="prefill"/>
 <p class="text-action"><a href="#memos">用该端点方案写口径复核说明 →</a></p>
</template>
<Empty v-else-if="run" title="备选票分析尚未完成" help="队列完成后这里会显示精确边界与两端逐票方案；失败时保留明确原因。"/>
</template>
