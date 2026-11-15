from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from src.config.database import get_db
from src.controllers.dependencies import current_user,writers
from src.models import AlternativesRun
from src.schemas.alternatives_run import AlternativesPreflightInput,AlternativesRunInput,PlanVerifyInput
from src.services.alternatives import AlternativesRefused,preflight
from src.services.alternatives_runs import create_alternatives_run,verify_endpoint
from src.services.source import source_data
from src.utils.serialize import row
router=APIRouter()

def _summary(run):
 # 列表只带状态与端点；完整两端方案按需读取详情，避免轮询传输大JSON。
 row_data=row(run);row_data.pop('result',None);return row_data

@router.get('/alternatives-runs')
def runs(db:Session=Depends(get_db),user=Depends(current_user)):return [_summary(r) for r in db.scalars(select(AlternativesRun).order_by(AlternativesRun.id.desc()))]

@router.get('/alternatives-runs/{id}')
def one(id:int,db:Session=Depends(get_db),user=Depends(current_user)):
 run=db.get(AlternativesRun,id)
 if not run:raise HTTPException(404,'备选票运行不存在')
 return row(run)

@router.post('/alternatives-runs')
def create(data:AlternativesRunInput,db:Session=Depends(get_db),user=Depends(writers)):return create_alternatives_run(db,data,user.email)

@router.post('/alternatives-runs/preflight')
def check(data:AlternativesPreflightInput,db:Session=Depends(get_db),user=Depends(writers)):
 study,items,votes=source_data(db,data.study_id)
 try:return preflight(study,items,votes)
 except AlternativesRefused as error:raise HTTPException(422,{'detail':str(error),'refused':True,'guards':error.details})
 except ValueError as error:raise HTTPException(422,str(error))

@router.post('/alternatives-runs/{id}/verify')
def verify(id:int,data:PlanVerifyInput,db:Session=Depends(get_db),user=Depends(current_user)):
 run=db.get(AlternativesRun,id)
 if not run:raise HTTPException(404,'备选票运行不存在')
 if run.status!='completed' and data.endpoint!='custom':raise HTTPException(422,'仅在完成运行上核对端点方案')
 result=verify_endpoint(db,run,[v.model_dump() for v in data.assignments],data.endpoint)
 if data.note:
  from src.services.audit import record
  record(db,user.email,'alternatives.plan_verified',{'alternatives_run_id':id,'endpoint':data.endpoint,'defined':result['defined'],'matches_endpoint':result.get('matches_endpoint'),'note':data.note})
 return result
