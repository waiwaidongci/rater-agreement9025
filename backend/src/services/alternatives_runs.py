from sqlalchemy import select
from fastapi import HTTPException
from src.models import AlternativesRun
from src.utils.serialize import row
from .source import source_data
from .validation import validate_source
from .alternatives import (AlternativesAnalysisError,AlternativesRefused,
 preflight,verify_plan)
from .audit import record

def _config(data):
 return {'analysis_mode':'alternatives_exact','requested_via':'exact_range'}

def create_alternatives_run(db,data,actor):
 study,items,votes=source_data(db,data.study_id);config=_config(data)
 try:
  validate_source(study,items,votes);preflight(study,items,votes)
 except AlternativesRefused as error:
  record(db,actor,'alternatives.refused',{'study_id':data.study_id,'reason':str(error),**error.details})
  raise HTTPException(422,{'detail':str(error),'refused':True,'guards':error.details})
 except AlternativesAnalysisError as error:raise HTTPException(422,str(error))
 except ValueError as error:raise HTTPException(422,str(error))
 if db.scalar(select(AlternativesRun).where(AlternativesRun.name==data.name)):raise HTTPException(409,'备选票运行名已存在')
 run=AlternativesRun(study_id=data.study_id,name=data.name,config=config,created_by=actor);db.add(run);db.commit()
 try:
  from src.worker import analyze_alternatives_run
  analyze_alternatives_run.delay(run.id)
 except Exception:
  run.status='failed';run.error='队列不可用，请稍后重建任务';db.commit();raise HTTPException(503,run.error)
 record(db,actor,'alternatives.queued',{'alternatives_run_id':run.id});return row(run)

def verify_endpoint(db,run,assignments,endpoint):
 study,items,votes=source_data(db,run.study_id)
 try:result=verify_plan(study,items,votes,endpoint,assignments)
 except AlternativesAnalysisError as error:raise HTTPException(422,str(error))
 if result['defined'] and run.result and endpoint in ('min','max'):
  stored=run.result[endpoint]
  result['matches_endpoint']=(
   result['kappa_rational']['numerator']==stored['kappa_rational']['numerator'] and
   result['kappa_rational']['denominator']==stored['kappa_rational']['denominator'])
 return result
