<script setup lang="ts">
import {ref,computed} from 'vue';
import PageHeading from '../components/common/PageHeading.vue';
import Table from '../components/common/Table.vue';
import Notice from '../components/common/Notice.vue';
import {sourceApi} from '../api/source';
import {useTask} from '../hooks/useTask';
const p=defineProps<{studies:any[];specimens:any[];votes:any[];user:any;reloadSource:()=>Promise<void>}>();
const id=ref(0),study=computed(()=>p.studies.find(s=>s.id===(id.value||p.studies[0]?.id))),items=computed(()=>p.specimens.filter(s=>s.study_id===study.value?.id)),task=useTask();
const example={name:'备选票完整面板示例',filename:'sx-candidate-panel.json',description:'原票保留；部分票限定候选类别，用于精确边界分析',categories:['砂岩','泥岩'],raters:['A','B','C'],specimens:[['砂岩','砂岩','砂岩'],['砂岩','砂岩','泥岩'],['砂岩','泥岩','泥岩'],['泥岩','泥岩','泥岩']].map((labels,i)=>({reference:'ALT-'+(i+1),description:'独立试样图像',votes:labels.map((category,j)=>({rater:['A','B','C'][j],category,alternatives:i===1&&j===1?['砂岩','泥岩']:undefined}))}))};
const raw=ref(JSON.stringify(example,null,2));
const voteOf=(item:any,rater:string)=>p.votes.find(v=>v.specimen_id===item.id&&v.rater===rater);
const candidateCount=(item:any)=>study.value.raters.filter(r=>voteOf(item,r)?.alternatives).length;
const allowed=(v:any)=>v.alternatives||[v.category];
async function saveVote(v:any,e:Event){
 const next=(e.target as HTMLSelectElement).value;
 const extras=(v.alternatives||[]).filter((c:string)=>c!==v.category);
 const alternatives=extras.length?study.value.categories.filter((c:string)=>c===next||extras.includes(c)):null;
 await task.act(async()=>{await sourceApi.editVote(v.id,{category:next,alternatives});await p.reloadSource()},
  '逐票修订已保存，既有运行保留冻结结果');
}
async function toggleCandidate(v:any,category:string){
 const extras=allowed(v).filter((c:string)=>c!==v.category);
 const nextExtras=extras.includes(category)?extras.filter((c:string)=>c!==category):[...extras,category];
 const alternatives=nextExtras.length?study.value.categories.filter((c:string)=>c===v.category||nextExtras.includes(c)):null;
 await task.act(async()=>{await sourceApi.editVote(v.id,{category:v.category,alternatives});await p.reloadSource()},
  alternatives?`该票候选集合已更新（${alternatives.join('/')}）；原票仍是${v.category}`:`该票恢复为确定票：${v.category}`);
}
async function create(){await task.act(async()=>{const s=await sourceApi.create(JSON.parse(raw.value));await p.reloadSource();id.value=s.id},'完整面板研究已保存，可前往配置')}
function annotate(s:any){const d=prompt('试样说明',s.description);if(d!==null)task.act(async()=>{await sourceApi.editSpecimen(s.id,d);await p.reloadSource()},'试样说明已保存')}
</script>
<template>
<PageHeading index="02" title="逐票核对，面板不能少一人。" description="每试样相同三人各一票；类别按声明顺序计数，不丢弃未出现类别。备选票保留原票，只额外声明候选集合。"/>
<label>来源研究<select :value="study?.id||0" @change="id=Number(($event.target as HTMLSelectElement).value)"><option v-for="s in studies" :key="s.id" :value="s.id">{{s.name}}</option></select></label>
<p v-if="study">{{study.filename}} / {{study.description}}<br/>面板 {{study.raters.join(' / ')}} · 类别 {{study.categories.join(' / ')}}</p>
<div class="source-layout">
<section><h2>完整面板 / 前16试样</h2>
<Table :headers="['试样',...(study?.raters||[]),'候选集合','说明']">
<tr v-for="item in items.slice(0,16)" :key="item.id">
<td>{{item.reference}}</td>
<td v-for="r in study?.raters" :key="r">
 <select v-if="user.role!=='viewer'&&voteOf(item,r)" :aria-label="'类别-'+voteOf(item,r).id" :value="voteOf(item,r).category" @change="saveVote(voteOf(item,r),$event)"><option v-for="c in study.categories" :key="c">{{c}}</option></select>
 <span v-else>{{voteOf(item,r)?.category||'缺票'}}</span>
 <small v-if="voteOf(item,r)?.alternatives">备选票</small>
</td>
<td>
 <details v-if="user.role!=='viewer'" class="candidate-cell">
  <summary>{{candidateCount(item)}}张备选票</summary>
  <div v-for="r in study?.raters" :key="r" class="candidate-group">
   <strong>{{r}}</strong>
   <label v-for="c in study.categories" :key="c" class="candidate-toggle"><input type="checkbox" :checked="voteOf(item,r)?allowed(voteOf(item,r)).includes(c):false" :disabled="!voteOf(item,r)||c===voteOf(item,r).category" @change="voteOf(item,r)&&toggleCandidate(voteOf(item,r),c)"/>{{c}}<em v-if="voteOf(item,r)&&c===voteOf(item,r).category">原票</em></label>
  </div>
 </details>
 <span v-else>{{study?.raters.map(r=>voteOf(item,r)?.alternatives?r+':'+voteOf(item,r).alternatives.join('/'):'').filter(Boolean).join('；')||'全部确定票'}}</span>
</td>
<td><button v-if="user.role!=='viewer'" @click="annotate(item)">补注</button></td>
</tr>
</Table></section>
<section class="input-sheet"><small>NEW FIXED-PANEL STUDY</small><h2>导入独立试样逐票</h2>
<p>2–240个试样、声明2–6类和固定3人；缺票、重复人、未知类、重复试样编号均拒绝。备选票须含原票类别、至少两个候选且都在声明类别内。</p>
<form v-if="user.role!=='viewer'" @submit.prevent="create"><label>研究 JSON<textarea v-model="raw" rows="20"/></label><button class="primary" :disabled="task.state.busy">保存完整面板研究 →</button></form>
<p v-else>观察员可读底稿；导入和改票由分析员处理。</p><Notice v-bind="task.state"/></section>
</div>
</template>
