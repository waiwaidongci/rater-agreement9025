from fastapi import HTTPException
from src.models import ReviewMemo
from src.services.audit import record
from src.utils.csv_export import csv_response

def _alternatives_rows(memo,r):
 rows=[]
 for item in r['min']['assignments']:
  choices='/'.join(f"{v['rater']}={v['category']}" for v in item['votes'])
  original='/'.join(f"{v['rater']}={v['original_category']}" for v in item['votes'])
  rows.append([memo.name,r['source_study']['name'],r['fingerprint'],r['range']['kappa_min_rational']['decimal'],r['range']['kappa_max_rational']['decimal'],r['range']['kappa_min_rational']['text'],r['range']['kappa_max_rational']['text'],r['candidate_vote_count'],r['legal_scheme_count'],r['defined_scheme_count'],r['undefined_schemes']['count'],r['undefined_schemes']['exists'],item['reference'],str(item['counts']),item['item_agreement'],choices,original,memo.interpretation,memo.next_step,memo.review_note,'min'])
 for item in r['max']['assignments']:
  choices='/'.join(f"{v['rater']}={v['category']}" for v in item['votes'])
  original='/'.join(f"{v['rater']}={v['original_category']}" for v in item['votes'])
  rows.append([memo.name,r['source_study']['name'],r['fingerprint'],r['range']['kappa_min_rational']['decimal'],r['range']['kappa_max_rational']['decimal'],r['range']['kappa_min_rational']['text'],r['range']['kappa_max_rational']['text'],r['candidate_vote_count'],r['legal_scheme_count'],r['defined_scheme_count'],r['undefined_schemes']['count'],r['undefined_schemes']['exists'],item['reference'],str(item['counts']),item['item_agreement'],choices,original,memo.interpretation,memo.next_step,memo.review_note,'max'])
 headers=['复核说明','研究','冻结指纹','有定义κ下限','有定义κ上限','下限精确分数','上限精确分数','备选票数','合法方案总数','有定义方案数','κ未定义方案数','存在未定义方案','试样','类别计数','逐项Pᵢ','端点方案逐票','原票逐票','人工解释','下一步','审核意见','端点']
 return rows,headers

def export_memo(db,id,actor):
 memo=db.get(ReviewMemo,id)
 if not memo:raise HTTPException(404,'说明不存在')
 if memo.status!='approved':raise HTTPException(409,'仅批准说明可导出')
 r=memo.result_snapshot
 if r.get('analysis_mode')=='alternatives_exact':
  rows,headers=_alternatives_rows(memo,r);record(db,actor,'memo.exported',{'memo_id':id,'mode':'alternatives_exact'});return csv_response(f'rater-review-{id}.csv',rows,headers)
 b=r['bootstrap'];ci=b['interval'];rows=[[memo.name,r['source_study']['name'],r['fingerprint'],r['kappa'],r['pbar'],r['pe'],b['valid_repeats'],b['invalid_repeats'],ci[0] if ci else '',ci[1] if ci else '',item['reference'],item['agreement'],str(item['counts']),memo.interpretation,memo.next_step,memo.review_note] for item in r['items']]
 record(db,actor,'memo.exported',{'memo_id':id});return csv_response(f'rater-review-{id}.csv',rows,['复核说明','研究','指纹','Fleissκ','Pbar','Pe','有效重复','退化重复','经验区间下限','经验区间上限','试样','逐项P','类别计数','人工解释','下一步','审核意见'])
