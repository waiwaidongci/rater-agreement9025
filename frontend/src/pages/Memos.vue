<script setup lang="ts">
import {ref,computed} from 'vue';
import PageHeading from '../components/common/PageHeading.vue';
import Notice from '../components/common/Notice.vue';
import Status from '../components/common/Status.vue';
import {useTask} from '../hooks/useTask';
import {researchApi} from '../api/research';
import {download} from '../api/client';
import {fmt} from '../utils/format';
const p=defineProps<{runs:any[];alternativesRuns?:any[];memos:any[];user:any;reloadResearch:()=>Promise<void>}>();
const success=computed(()=>p.runs.filter(r=>r.status==='completed'));
const altSuccess=computed(()=>(p.alternativesRuns||[]).filter(r=>r.status==='completed'));
const source=ref<'definite'|'alternatives'>('definite');
const id=ref(0);
const name=ref('分类边界复核 '+new Date().toLocaleTimeString());
const interpretation=ref('κ是相对类别基率的一致性，不是与金标准对照的准确率。');
const next=ref('保持原三位标记者，独立复核争议试样，明确图谱类别边界。');
const task=useTask();
const run=computed(()=>success.value.find(r=>r.id===(id.value||success.value[0]?.id)));
const altRun=computed(()=>altSuccess.value.find(r=>r.id===(id.value||altSuccess.value[0]?.id)));
function switchSource(value:'definite'|'alternatives'){source.value=value;id.value=0}
async function create(){
 const payload=source.value==='definite'
  ?{run_id:run.value.id,name:name.value,interpretation:interpretation.value,next_step:next.value}
  :{alternatives_run_id:altRun.value.id,name:name.value,interpretation:alternativesInterpretation.value,next_step:alternativesNext.value};
 await task.act(async()=>{await researchApi.createMemo(payload);await p.reloadResearch()},
  source.value==='definite'?'口径复核说明已提交':'备选票复核说明已提交（快照含两端逐票方案）');
}
async function approve(m:any,status:string){await task.act(async()=>{await researchApi.approve(m.id,{status,review_note:status==='approved'?'批准固定面板口径复核；一致性不代表准确率。':'请补充试样独立性与类别边界说明。'});await p.reloadResearch()},status==='approved'?'说明已批准':'说明已退回')}
const alternativesInterpretation=ref('备选票只在候选集合内取值；报告的是全部合法方案中有定义κ的精确边界，不是抽样区间。');
const alternativesNext=ref('保持原三位标记者，逐票复核两个端点方案，确认候选集合是否完整表达类别边界。');
function snapshotLine(m:any){
 const s=m.result_snapshot;
 if(s.analysis_mode==='alternatives_exact')return `备选票精确边界 / ${s.source_study.name} / ${s.specimen_count}试样 / κ∈[${fmt(s.range?.kappa_min,6)}, ${fmt(s.range?.kappa_max,6)}] / ${s.candidate_vote_count}张备选票 / 未定义方案${s.undefined_schemes.count}个`;
 return `冻结研究 ${s.source_study.name} / ${s.specimen_count}试样 / κ${fmt(s.kappa,6)} / 有效${s.bootstrap.valid_repeats}次`;
}
</script>
<template>
<PageHeading index="06" title="把争议留给复核，把快照留在簿里。" description="人工解释和独立复核行动由负责人审阅；既有票修订不能改写已批准快照。"/>
<form v-if="user.role!=='viewer'" class="input-sheet memo-form" @submit.prevent="create">
 <div class="field-pair">
  <label>分析类型<select :value="source" @change="switchSource(($event.target as HTMLSelectElement).value as 'definite'|'alternatives')"><option value="definite">原确定票分析</option><option value="alternatives">备选票精确边界</option></select></label>
  <label>说明名称<input v-model="name" required/></label>
 </div>
 <template v-if="source==='definite'">
  <label>完成运行<select :value="run?.id||0" @change="id=Number(($event.target as HTMLSelectElement).value)"><option v-for="r in success" :key="r.id" :value="r.id">#{{r.id}} {{r.name}}</option></select></label>
  <div class="field-pair"><label>人工解释<textarea v-model="interpretation" rows="3" required/></label><label>独立复核行动<textarea v-model="next" rows="3" required/></label></div>
 </template>
 <template v-else>
  <label>完成备选票运行<select :value="altRun?.id||0" @change="id=Number(($event.target as HTMLSelectElement).value)"><option v-for="r in altSuccess" :key="r.id" :value="r.id">#{{r.id}} {{r.name}}</option></select></label>
  <div class="field-pair"><label>人工解释<textarea v-model="alternativesInterpretation" rows="3" required/></label><label>独立复核行动<textarea v-model="alternativesNext" rows="3" required/></label></div>
  <p class="range-lede">快照冻结两端逐票方案、合法/未定义方案数与精确有理数边界；不复制抽样区间。</p>
 </template>
 <button class="primary" :disabled="task.state.busy||(source==='definite'?!run:!altRun)">提交口径复核说明 →</button>
</form>
<Notice v-bind="task.state"/>
<article class="memo-record" v-for="m in memos" :key="m.id">
 <div class="section-head"><h2>{{m.name}}</h2><Status :value="m.status"/></div>
 <p>{{m.interpretation}}</p>
 <p><strong>下一步 / </strong>{{m.next_step}}</p>
 <div class="snapshot-line">{{snapshotLine(m)}}</div>
 <p v-if="m.review_note">审核 / {{m.review_note}}</p>
 <div class="memo-actions">
  <template v-if="user.role==='admin'&&m.status==='draft'"><button @click="approve(m,'approved')">批准口径复核 ✓</button><button @click="approve(m,'rejected')">退回补充</button></template>
  <button v-if="m.status==='approved'" @click="task.act(()=>download('/memos/'+m.id+'/export','rater-review-'+m.id+'.csv'),'已导出批准快照CSV')">导出批准快照 CSV ↗</button>
 </div>
</article>
</template>
