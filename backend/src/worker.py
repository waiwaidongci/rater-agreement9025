import json
from pathlib import Path
from celery import Celery
from src.config.database import SessionLocal
from src.config.settings import REDIS_URL,ARTIFACT_DIR
from src.models import AgreementRun,AlternativesRun
from src.services.source import source_data
from src.services.analysis import analyze
from src.services.alternatives import analyze_alternatives,AlternativesRefused,AlternativesAnalysisError
from src.services.audit import record
app=Celery('rater_agreement',broker=REDIS_URL,backend=REDIS_URL)
app.conf.update(task_track_started=True,worker_prefetch_multiplier=1,task_acks_late=True)
@app.task(name='rater.analyze',soft_time_limit=120,time_limit=150)
def analyze_run(id):
 with SessionLocal() as db:
  run=db.get(AgreementRun,id)
  if not run or run.status=='completed':return
  run.status='running';db.commit()
  try:
   study,items,votes=source_data(db,run.study_id);result=analyze(study,items,votes,run.config)
   Path(ARTIFACT_DIR).mkdir(parents=True,exist_ok=True);Path(ARTIFACT_DIR,f'rater-{id}.json').write_text(json.dumps(result,ensure_ascii=False,allow_nan=False));run.result=result;run.kappa=result['kappa'];run.pbar=result['pbar'];run.pe=result['pe'];run.status='completed';run.error=None;db.commit();record(db,'worker','run.completed',{'run_id':id,'kappa':run.kappa,'valid_repeats':result['bootstrap']['valid_repeats']})
  except Exception as error:
   db.rollback();run=db.get(AgreementRun,id);run.status='failed';run.error=str(error)[:1000];db.commit();record(db,'worker','run.failed',{'run_id':id,'error':run.error})

@app.task(name='rater.alternatives',soft_time_limit=40,time_limit=55)
def analyze_alternatives_run(id):
 with SessionLocal() as db:
  run=db.get(AlternativesRun,id)
  if not run or run.status=='completed':return
  run.status='running';db.commit()
  try:
   study,items,votes=source_data(db,run.study_id);result=analyze_alternatives(study,items,votes,run.config)
   Path(ARTIFACT_DIR).mkdir(parents=True,exist_ok=True);Path(ARTIFACT_DIR,f'alternatives-{id}.json').write_text(json.dumps(result,ensure_ascii=False,allow_nan=False));run.result=result;run.kappa_min=result['range']['kappa_min'] if result['range'] else None;run.kappa_max=result['range']['kappa_max'] if result['range'] else None;run.status='completed';run.error=None;db.commit();record(db,'worker','alternatives.completed',{'alternatives_run_id':id,'kappa_min':run.kappa_min,'kappa_max':run.kappa_max,'candidate_votes':result['candidate_vote_count']})
  except AlternativesRefused as error:
   db.rollback();run=db.get(AlternativesRun,id);run.status='failed';run.error=str(error)[:1000];db.commit();record(db,'worker','alternatives.refused',{'alternatives_run_id':id,'error':run.error,'guards':getattr(error,'details',{})})
  except AlternativesAnalysisError as error:
   db.rollback();run=db.get(AlternativesRun,id);run.status='failed';run.error=str(error)[:1000];db.commit();record(db,'worker','alternatives.invalid',{'alternatives_run_id':id,'error':run.error})
  except Exception as error:
   db.rollback();run=db.get(AlternativesRun,id);run.status='failed';run.error=str(error)[:1000];db.commit();record(db,'worker','alternatives.failed',{'alternatives_run_id':id,'error':run.error})
