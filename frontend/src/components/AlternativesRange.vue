<script setup lang="ts">
import {fmt} from '../utils/format';
defineProps<{result:any}>();
const emit=defineEmits(['verify']);
function verify(name:'min'|'max',result:any){
 const plan=result[name].assignments.flatMap((a:any)=>a.votes.map((v:any)=>({vote_id:v.vote_id,category:v.category})));
 emit('verify',name,plan);
}
</script>
<template>
<section class="alternatives-range">
 <div class="section-head"><h2>备选票：全部合法定类方案的精确边界。</h2><span>{{result.candidate_vote_count}}张备选票 / {{result.candidate_specimen_count}}个受影响试样</span></div>
 <p class="range-lede">原票全部保留；每张备选票只在声明候选内取值。下列数值是<b>所有合法方案</b>中<b>有定义κ</b>的精确最小/最大值，不是抽样区间，也不是bootstrap经验区间。</p>
 <div class="range-panel">
  <div><small>有定义κ最小值</small><strong>{{result.min?fmt(result.min.kappa,6):'无'}}</strong><em v-if="result.min">精确 {{result.min.kappa_rational.text}}</em></div>
  <div><small>有定义κ最大值</small><strong>{{result.max?fmt(result.max.kappa,6):'无'}}</strong><em v-if="result.max">精确 {{result.max.kappa_rational.text}}</em></div>
  <div><small>端点方案</small><strong>2</strong><em>各含全部{{result.specimen_count}}试样的逐票选择</em></div>
 </div>
 <p class="scheme-counts">合法定类方案 <strong>{{result.legal_scheme_count}}</strong> 个；有定义κ <strong>{{result.defined_scheme_count}}</strong> 个；κ未定义 <strong>{{result.undefined_schemes.count}}</strong> 个（{{result.undefined_schemes.reason}}）。</p>
 <template v-if="result.range_status==='defined'">
  <div class="endpoint-grid">
   <article v-for="name in (['min','max'] as const)" :key="name" class="endpoint-card">
    <header><h3>{{name==='min'?'最小值端点方案':'最大值端点方案'}}</h3><button type="button" @click="verify(name,result)">录入该方案核对 ↗</button></header>
    <dl><div><dt>κ</dt><dd>{{fmt(result[name].kappa,6)}}</dd></div><div><dt>P̄</dt><dd>{{fmt(result[name].pbar,6)}}</dd></div><div><dt>Pe</dt><dd>{{fmt(result[name].pe,6)}}</dd></div></dl>
    <p>端点回算 {{result[name].recomputed_from_plan.matches_bound?'一致':'不一致'}}；S={{result[name].pair_sum_S}}，T={{result[name].total_square_T}}。</p>
    <details><summary>逐票方案（全部{{result[name].assignments.length}}个试样）</summary>
     <div class="plan-row" v-for="a in result[name].assignments" :key="a.reference"><strong>{{a.reference}}</strong><span>计数 {{a.counts.join(' / ')}}</span><span v-for="v in a.votes" :key="v.rater">{{v.rater}}={{v.category}}<em v-if="v.was_candidate">（备选，原票{{v.original_category}}）</em></span></div>
    </details>
   </article>
  </div>
 </template>
 <p v-else class="range-warning">{{result.range_reason}}</p>
 <div class="boundary-note"><strong>这不是抽样区间。</strong><p>边界由整数计数与有理数运算逐票回算。规模超出安全上限时系统明确拒绝并保留原因，绝不改用近似值。</p></div>
 <details class="provenance"><summary>冻结指纹、规模与算法边界</summary><p class="fingerprint">{{result.fingerprint}}</p><p>状态{{result.guards.state_count}} · 访问转移{{result.guards.transitions_visited}} · 上界{{result.guards.transition_upper_bound}} · 用时{{Number(result.guards.elapsed_seconds).toFixed(2)}}s · 峰值RSS {{Number(result.guards.rss_mb).toFixed(1)}}MB</p><p>{{result.interpretation}}</p></details>
</section>
</template>
