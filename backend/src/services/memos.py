from sqlalchemy import select
from fastapi import HTTPException
from src.models import AgreementRun,AlternativesRun,ReviewMemo
from src.utils.serialize import row
from .audit import record

def create_memo(db,data,actor):
 if data.run_id is not None:
  run=db.get(AgreementRun,data.run_id)
  if not run or run.status!='completed':raise HTTPException(422,'仅成功的确定票运行可建立口径复核说明')
  snapshot=run.result
 elif data.alternatives_run_id is not None:
  run=db.get(AlternativesRun,data.alternatives_run_id)
  if not run or run.status!='completed':raise HTTPException(422,'仅成功的备选票运行可建立口径复核说明')
  snapshot=run.result
 else:raise HTTPException(422,'说明须关联一个完成运行')
 if db.scalar(select(ReviewMemo).where(ReviewMemo.name==data.name)):raise HTTPException(409,'说明名已存在')
 memo=ReviewMemo(**data.model_dump(),result_snapshot=snapshot,created_by=actor);db.add(memo);db.commit();record(db,actor,'memo.created',{'memo_id':memo.id,'run_id':data.run_id,'alternatives_run_id':data.alternatives_run_id});return row(memo)

def approve_memo(db,id,data,actor):
 memo=db.scalar(select(ReviewMemo).where(ReviewMemo.id==id).with_for_update())
 if not memo:raise HTTPException(404,'说明不存在')
 if memo.status!='draft':raise HTTPException(409,'说明已审阅，不可重复审批')
 memo.status=data.status;memo.review_note=data.review_note;db.commit();record(db,actor,'memo.reviewed',{'memo_id':id,'status':memo.status});return row(memo)
