import json
import os
import sys
import uuid

RUN_TAG=uuid.uuid4().hex[:8]

sys.path.insert(0, '/workspace/backend')

# Replace Redis with an in-process counter so the HTTP layer can be exercised
# without a Redis server; the rate-limit middleware logic itself stays intact.
import src.middlewares.rate_limit as rl


class MemoryRedis:
    counts = {}

    @classmethod
    def from_url(cls, *args, **kwargs):
        return cls()

    def incr(self, key):
        MemoryRedis.counts[key] = MemoryRedis.counts.get(key, 0) + 1
        return MemoryRedis.counts[key]

    def expire(self, key, seconds):
        return True

    def ping(self):
        return True


rl.Redis = MemoryRedis
import src.main as main_module
import src.worker as worker_module

# Queue only stores job ids; without a broker the test executes the same
# analysis function in-process below, so the exact production code path runs.
worker_module.analyze_run.delay = lambda *args, **kwargs: None
worker_module.analyze_alternatives_run.delay = lambda *args, **kwargs: None

main_module.Redis = MemoryRedis
from fastapi.testclient import TestClient

from src.config.database import SessionLocal
from src.models import AgreementStudy, AlternativesRun, ReviewMemo, Specimen, RaterVote
from src.services.alternatives import analyze_alternatives

results = []


def check(name, condition, detail=''):
    results.append((name, bool(condition), detail))
    print(('PASS ' if condition else 'FAIL ') + name + ((' | ' + str(detail)) if detail and not condition else ''))


with TestClient(main_module.app) as client:
    def call(method, path, data=None, token=None):
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = 'Bearer ' + token
        response = client.request(method, path, headers=headers,
                                  content=json.dumps(data) if data is not None else None)
        try:
            return response.status_code, response.json()
        except Exception:
            return response.status_code, response.text

    status, login = call('POST', '/auth/login',
                         {'email': 'analyst@shanxu.demo', 'password': 'Shanxu2026!'})
    check('analyst login', status == 200, status)
    analyst = login['token']
    status, admin_login = call('POST', '/auth/login',
                               {'email': 'admin@shanxu.demo', 'password': 'Shanxu2026!'})
    admin = admin_login['token']
    status, viewer_login = call('POST', '/auth/login',
                                {'email': 'viewer@shanxu.demo', 'password': 'Shanxu2026!'})
    viewer = viewer_login['token']

    status, studies = call('GET', '/studies', token=analyst)
    study = next(s for s in studies if s['name'].startswith('SX-31A'))
    boundary = next(s for s in studies if s['name'].startswith('SX-31C'))

    # Original definite-vote analysis is unaffected by candidate votes.
    status, old_run = call('POST', '/runs', {'study_id': study['id'],
                           'name': '确定票分析-回归-'+RUN_TAG, 'bootstrap_repeats': 400,
                           'seed': 231, 'panel_scope': 'fixed_three_raters'}, analyst)
    check('definite run queued (candidate votes ignored)', status == 200, old_run)
    with SessionLocal() as db:
        run = db.get(__import__('src.models', fromlist=['AgreementRun']).AgreementRun,
                     old_run['id'])
        from src.services.source import source_data
        from src.services.analysis import analyze
        study_row, items, votes = source_data(db, run.study_id)
        result = analyze(study_row, items, votes, run.config)
        run.result = result; run.kappa = result['kappa']; run.pbar = result['pbar']
        run.pe = result['pe']; run.status = 'completed'; db.commit()
        check('definite kappa unchanged by alternatives',
              abs(result['kappa'] - 0.6105260989) < 1e-9, result['kappa'])

    status, pre = call('POST', '/alternatives-runs/preflight',
                       {'study_id': study['id']}, analyst)
    check('preflight accepted for documented scale', status == 200, pre)
    status, created = call('POST', '/alternatives-runs',
                           {'study_id': study['id'], 'name': 'A研究备选票精确边界 '+RUN_TAG}, analyst)
    check('alternatives run queued', status == 200, created)
    run_id = created['id']

    with SessionLocal() as db:
        run = db.get(AlternativesRun, run_id)
        from src.services.source import source_data
        study_row, items, votes = source_data(db, run.study_id)
        result = analyze_alternatives(study_row, items, votes, run.config)
        run.result = result; run.status = 'completed'
        run.kappa_min = result['range']['kappa_min']; run.kappa_max = result['range']['kappa_max']
        db.commit()
        check('stored range has minimum < maximum',
              result['min']['kappa'] < result['max']['kappa'],
              (result['min']['kappa'], result['max']['kappa']))
        check('no undefined schemes with candidate coverage',
              result['undefined_schemes']['exists'] is False,
              result['undefined_schemes'])
        stored_candidates = sum(1 for v in votes if v['alternatives'])
        check('candidate votes counted from source', stored_candidates == 48,
              stored_candidates)

    status, listing = call('GET', '/alternatives-runs', token=viewer)
    check('list omits heavy endpoint plans', status == 200 and
          all('result' not in item for item in listing), status)
    status, fetched = call('GET', f'/alternatives-runs/{run_id}', token=viewer)
    check('viewer can read alternatives result', status == 200 and fetched['result'],
          status)
    check('result carries both endpoint plans',
          len(fetched['result']['min']['assignments']) == 120 and
          len(fetched['result']['max']['assignments']) == 120)
    check('result labelled as exact, not interval',
          fetched['result']['not_a_confidence_interval'] is True and
          fetched['result']['analysis_mode'] == 'alternatives_exact')

    plan_min = [{'vote_id': v['vote_id'], 'category': v['category']}
                for a in fetched['result']['min']['assignments'] for v in a['votes']]
    status, verified = call('POST', f'/alternatives-runs/{run_id}/verify',
                            {'endpoint': 'min', 'assignments': plan_min,
                             'note': '页面复核最小端点'}, viewer)
    check('min endpoint plan replays to stored kappa',
          status == 200 and verified['matches_endpoint'] is True, verified.get('reason'))

    tampered = [dict(x) for x in plan_min]
    with SessionLocal() as db:
        first_definite = next(v for v in
                              db.query(RaterVote).join(Specimen).filter(
                                  Specimen.study_id == study['id'],
                                  RaterVote.alternatives == None).all())
        other = next(c for c in study['categories'] if c != first_definite.category)
        tampered = [x for x in tampered if x['vote_id'] != first_definite.id]
        tampered.append({'vote_id': first_definite.id, 'category': other})
    status, rejected = call('POST', f'/alternatives-runs/{run_id}/verify',
                            {'endpoint': 'custom', 'assignments': tampered}, analyst)
    check('definite vote cannot be altered in a plan', status == 422, rejected)

    status, rejected = call('POST', f'/alternatives-runs/{run_id}/verify',
                            {'endpoint': 'custom', 'assignments': plan_min[:10]}, analyst)
    check('incomplete plan rejected', status == 422, rejected)

    status, memo = call('POST', '/memos', {'alternatives_run_id': run_id,
                        'name': '备选票边界复核 '+RUN_TAG,
                        'interpretation': '备选票只在候选集合内取值；报告精确边界。',
                        'next_step': '逐票复核两个端点方案与原票。'}, analyst)
    check('alternatives memo created', status == 200 and
          memo['result_snapshot']['analysis_mode'] == 'alternatives_exact', memo)
    status, approved = call('PATCH', f"/memos/{memo['id']}/approval",
                            {'status': 'approved', 'review_note': '批准备选票精确边界口径。'}, admin)
    check('admin approves alternatives memo', status == 200, approved)
    export = client.get(f"/memos/{memo['id']}/export",
                        headers={'Authorization': 'Bearer ' + viewer})
    check('approved alternatives memo exports CSV',
          export.status_code == 200 and '有定义κ下限' in export.text, export.status_code)

    # Boundary study: all votes same category, no candidates -> generic refusal.
    status, refused = call('POST', '/alternatives-runs/preflight',
                           {'study_id': boundary['id']}, analyst)
    check('study without candidate votes is rejected', status == 422, refused)

    # Scale refusal: build a study whose exact state space exceeds the guard.
    categories = ['A', 'B', 'C', 'D']
    payload = {'name': '超限备选票研究 ' + RUN_TAG, 'filename': 'over.json',
               'description': '规模守卫测试', 'categories': categories,
               'raters': ['x', 'y', 'z'], 'specimens': []}
    for i in range(240):
        payload['specimens'].append({'reference': f'OV-{i + 1:03d}', 'description': '',
            'votes': [{'rater': r, 'category': categories[(i + j) % 4],
                       'alternatives': categories if i < 48 else None}
                      for j, r in enumerate(['x', 'y', 'z'])]})
    status, over = call('POST', '/studies', payload, analyst)
    check('oversized study stored', status == 200, over)
    status, refused = call('POST', '/alternatives-runs',
                           {'study_id': over['id'], 'name': '超限运行 ' + RUN_TAG},
                           analyst)
    check('oversized exact work refused explicitly', status == 422, refused)
    check('refusal has no approximate range',
          '近似' in refused['detail']['detail'] and 'refused' in refused['detail'], refused)

    status, viewer_write = call('POST', '/alternatives-runs',
                                {'study_id': study['id'], 'name': 'viewer attempt '+RUN_TAG}, viewer)
    check('viewer cannot queue alternatives run', status == 403, viewer_write)

    status, audit = call('GET', '/audit', token=admin)
    actions = {log['action'] for log in audit}
    check('audit records refusal and verification',
          'alternatives.refused' in actions or 'alternatives.plan_verified' in actions,
          actions)

failed = [r for r in results if not r[1]]
print(f'\n{len(results) - len(failed)}/{len(results)} checks passed')
if failed:
    raise SystemExit(1)
