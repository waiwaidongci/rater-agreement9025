<script setup lang="ts">
import {computed,ref,watch} from 'vue';
import Notice from './common/Notice.vue';
import {useTask} from '../hooks/useTask';
import {researchApi} from '../api/research';
import {fmt} from '../utils/format';

const p=defineProps<{run:any;prefill:{endpoint:'min'|'max';plan:{vote_id:number;category:string}[]}|null}>();
const task=useTask();
const endpoint=ref<'min'|'max'|'custom'>('min');
const text=ref('');
const verification=ref<any>(null);

function render(plan:{vote_id:number;category:string}[]){return plan.map(v=>`${v.vote_id}=${v.category}`).join('\n')}

function loadPrefill(){
 if(p.prefill){endpoint.value=p.prefill.endpoint;text.value=render(p.prefill.plan);verification.value=null}
}
watch(()=>p.prefill,loadPrefill,{immediate:true});
watch(()=>p.run?.id,()=>{verification.value=null});

const parsed=computed(()=>{
 const rows:{vote_id:number;category:string}[]=[];const errors:string[]=[];
 text.value.split('\n').forEach((line,index)=>{
  const trimmed=line.trim();if(!trimmed)return;
  const match=trimmed.match(/^(\d+)\s*[=,:：]\s*(.+)$/);
  if(!match){errors.push(`第${index+1}行无法解析：${trimmed}`);return}
  rows.push({vote_id:Number(match[1]),category:match[2].trim()});
 });
 return {rows,errors};
});

function fillStored(name:'min'|'max'){
 const stored=p.run?.result?.[name];
 if(!stored)return;
 endpoint.value=name;
 text.value=render(stored.assignments.flatMap((a:any)=>a.votes.map((v:any)=>({vote_id:v.vote_id,category:v.category}))));
}

async function verify(){
 verification.value=null;
 await task.act(async()=>{
  const result=await researchApi.verifyPlan(p.run.id,{endpoint:endpoint.value,assignments:parsed.value.rows,note:'页面复核端点方案'});
  verification.value=result;
  if(!result.defined)throw Error(result.reason);
 },'方案已逐票回算');
}
</script>
<template>
<section class="plan-verify">
 <div class="section-head"><h2>录入端点方案，逐票回算。</h2><span>每行 vote_id=类别；确定票必须保持原票，备选票须在候选集合内</span></div>
 <div class="plan-toolbar">
  <label>核对目标<select v-model="endpoint"><option value="min">最小值端点</option><option value="max">最大值端点</option><option value="custom">自定义完整方案</option></select></label>
  <button type="button" @click="fillStored('min')">带入最小端点</button>
  <button type="button" @click="fillStored('max')">带入最大端点</button>
 </div>
 <label>逐票方案<textarea v-model="text" rows="8" spellcheck="false" placeholder="12=砂岩&#10;13=粉砂岩&#10;…"/></label>
 <p v-if="parsed.errors.length" class="invalid-reason">{{parsed.errors.join('；')}}</p>
 <p v-else>{{parsed.rows.length}}票待核对<template v-if="run?.result?.total_votes">（研究共{{run.result.total_votes}}票）</template></p>
 <button class="primary" type="button" :disabled="task.state.busy||!parsed.rows.length||parsed.errors.length>0" @click="verify">逐票回算该方案 →</button>
 <Notice v-bind="task.state"/>
 <div v-if="verification" class="verify-result">
  <dl>
   <div><dt>κ</dt><dd>{{verification.defined?fmt(verification.kappa,6):'未定义'}}</dd></div>
   <div><dt>P̄</dt><dd>{{verification.defined?fmt(verification.pbar,6):'—'}}</dd></div>
   <div><dt>Pe</dt><dd>{{verification.defined?fmt(verification.pe,6):'—'}}</dd></div>
   <div><dt>端点比对</dt><dd>{{verification.matches_endpoint===true?'与存储端点一致':verification.matches_endpoint===false?'与存储端点不一致':'自定义方案'}}</dd></div>
  </dl>
  <p>{{verification.reason}}<template v-if="verification.defined">（精确 {{verification.kappa_rational.text}}）</template></p>
  <p v-if="!verification.defined" class="invalid-reason">该方案全票同类，Pe=1，κ未定义；不计入最小值/最大值。</p>
 </div>
</section>
</template>
