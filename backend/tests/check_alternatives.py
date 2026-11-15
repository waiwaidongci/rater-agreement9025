"""Exhaustive cross-check of the alternatives solver against brute force.

Run with:  python3 -I -m backend.tests.check_alternatives   (from repo root)
or:        PYTHONPATH=backend python3 -I backend/tests/check_alternatives.py
No third-party packages are required.
"""
from fractions import Fraction
from itertools import product
import json
import random
import resource
import sys
import time

sys.path.insert(0, __file__.rsplit('/tests/', 1)[0])

from src.services.alternatives import (  # noqa: E402
    AlternativesAnalysisError, AlternativesRefused, analyze_alternatives,
    verify_plan)

def brute(categories, raters, specimens, votes):
    by_specimen = {s['id']: {} for s in specimens}
    for vote in votes:
        by_specimen[vote['specimen_id']][vote['rater']] = vote
    option_rows = []
    for specimen in specimens:
        for rater in raters:
            vote = by_specimen[specimen['id']][rater]
            option_rows.append(
                list(vote['alternatives']) if vote.get('alternatives') else [vote['category']])
    minimum = maximum = None
    undefined = 0
    total = 0
    N = len(specimens)
    for combo in product(*option_rows):
        total += 1
        totals = [0] * len(categories)
        pair_sum = 0
        for start in range(0, len(combo), 3):
            counts = [0] * len(categories)
            for label in combo[start:start + 3]:
                counts[categories.index(label)] += 1
            pair_sum += sum(v * (v - 1) for v in counts)
            for j, v in enumerate(counts):
                totals[j] += v
        total_square = sum(v * v for v in totals)
        if total_square == (N * 3) ** 2:
            undefined += 1
            continue
        kappa = Fraction(3 * N * pair_sum - 2 * total_square,
                         2 * ((N * 3) ** 2 - total_square))
        minimum = kappa if minimum is None or kappa < minimum else minimum
        maximum = kappa if maximum is None or kappa > maximum else maximum
    return minimum, maximum, undefined, total

def build(categories, raters, items):
    specimens = [{'id': i + 1, 'reference': f'S{i + 1:03d}', 'description': ''}
                 for i in range(len(items))]
    votes = []
    for i, item in enumerate(items):
        for j, rater in enumerate(raters):
            category, alternatives = item[j]
            votes.append({'id': i * 3 + j + 1, 'specimen_id': i + 1,
                          'rater': rater, 'category': category,
                          'alternatives': list(alternatives) if alternatives else None})
    return {'categories': categories, 'raters': raters}, specimens, votes

def check_case(name, categories, raters, items):
    study, specimens, votes = build(categories, raters, items)
    expected = brute(categories, raters, specimens, votes)
    result = analyze_alternatives(study, specimens, votes, {})
    got_min = Fraction(result['min']['kappa_rational']['numerator'],
                       result['min']['kappa_rational']['denominator'])
    got_max = Fraction(result['max']['kappa_rational']['numerator'],
                       result['max']['kappa_rational']['denominator'])
    got = (got_min, got_max, result['undefined_schemes']['count'],
           int(result['legal_scheme_count']))
    assert got == expected, (name, got, expected)
    for endpoint_name in ('min', 'max'):
        endpoint = result[endpoint_name]
        assert endpoint['recomputed_from_plan']['matches_bound'] is True
        plan = [{'vote_id': v['vote_id'], 'category': v['category']}
                for a in endpoint['assignments'] for v in a['votes']]
        verified = verify_plan(study, specimens, votes, endpoint_name, plan)
        assert verified['legal'] and verified['defined']
        assert Fraction(verified['kappa_rational']['numerator'],
                        verified['kappa_rational']['denominator']) == \
            Fraction(endpoint['kappa_rational']['numerator'],
                     endpoint['kappa_rational']['denominator'])
        # Definite votes keep the original label, candidate votes stay in range.
        for vote in votes:
            chosen = next(v['category'] for v in plan if v['vote_id'] == vote['id'])
            if vote.get('alternatives'):
                assert chosen in vote['alternatives']
            else:
                assert chosen == vote['category']
    print(f'ok  {name:<42} legal={expected[3]:>5} undefined={expected[2]} '
          f'kappa=[{got_min}, {got_max}]')
    return result

def random_case(seed, specimens_n, candidate_specimens, categories_n):
    rng = random.Random(seed)
    categories = [chr(65 + i) for i in range(categories_n)]
    items = []
    candidates = set(rng.sample(range(specimens_n), candidate_specimens))
    for i in range(specimens_n):
        row = []
        for j in range(3):
            category = rng.choice(categories)
            alternatives = None
            if i in candidates and rng.random() < 0.5:
                size = rng.choice([2, 3]) if categories_n >= 3 else 2
                others = [c for c in categories if c != category]
                rng.shuffle(others)
                alternatives = [category] + others[:size - 1]
                rng.shuffle(alternatives)
            row.append((category, tuple(alternatives) if alternatives else None))
        items.append(row)
    return categories, items

def random_full_check(trials=120, seed=99):
    """Random small studies where every legal assignment can be enumerated."""
    rng = random.Random(seed)
    tested = 0
    for trial in range(trials):
        categories = ['A', 'B', 'C'][:rng.choice([2, 3])]
        specimens_n = rng.randint(2, 4)
        items = []
        for _ in range(specimens_n):
            row = []
            for _ in range(3):
                category = rng.choice(categories)
                if rng.random() < 0.45:
                    size = rng.randint(2, len(categories))
                    others = [c for c in categories if c != category]
                    alternatives = [category] + rng.sample(others, size - 1)
                    rng.shuffle(alternatives)
                    row.append((category, tuple(alternatives)))
                else:
                    row.append((category, None))
            items.append(row)
        if not any(alt for row in items for _, alt in row):
            continue
        space = 1
        for row in items:
            for _, alt in row:
                space *= len(alt) if alt else 1
        if space > 20000:
            continue
        check_case(f'random exhaustive trial={trial}', categories,
                   ['x', 'y', 'z'], items)
        tested += 1
    assert tested >= 100, tested
    print(f'ok  randomized exhaustive cross-check: {tested} studies')


def main():
    check_case('two specimens, one candidate each',
               ['A', 'B'], ['x', 'y', 'z'],
               [[('A', None), ('B', ('A', 'B')), ('A', None)],
                [('B', None), ('A', ('A', 'B')), ('B', None)]])
    check_case('three categories, mixed candidate sizes',
               ['A', 'B', 'C'], ['x', 'y', 'z'],
               [[('A', None), ('A', ('A', 'B', 'C')), ('B', ('A', 'B', 'C'))],
                [('C', None), ('B', ('A', 'B')), ('A', None)],
                [('B', ('A', 'B')), ('C', None), ('A', ('A', 'C'))]])
    check_case('undefined schemes exist',
               ['A', 'B'], ['x', 'y', 'z'],
               [[('A', ('A', 'B')), ('B', ('A', 'B')), ('A', ('A', 'B'))],
                [('B', ('A', 'B')), ('B', ('A', 'B')), ('A', ('A', 'B'))]])
    check_case('many undefined schemes alongside defined ones',
               ['A', 'B', 'C'], ['x', 'y', 'z'],
               [[('A', ('A', 'B', 'C')), ('A', ('A', 'B', 'C')), ('A', ('A', 'B', 'C'))],
                [('B', ('A', 'B', 'C')), ('B', ('A', 'B', 'C')), ('C', ('A', 'B', 'C'))]])
    for seed in range(6):
        categories, items = random_case(seed, 4, 3, 3)
        check_case(f'random small seed={seed}', categories, ['x', 'y', 'z'], items)
    random_full_check()

    # Full documented workload: 240 specimens, 3 categories, 48 candidate
    # votes with 3 alternatives each.  No brute force at this size.
    rng = random.Random(7)
    categories = ['砂岩', '粉砂岩', '泥岩']
    specimens = [{'id': i + 1, 'reference': f'IMG-{i + 1:03d}', 'description': ''}
                 for i in range(240)]
    candidate_specimens = set(rng.sample(range(240), 48))
    votes = []
    for i in range(240):
        for j, rater in enumerate(['标记者甲', '标记者乙', '标记者丙']):
            category = rng.choice(categories)
            alternatives = None
            if i in candidate_specimens and j == 0:
                alternatives = [category] + [c for c in categories if c != category]
                rng.shuffle(alternatives)
            votes.append({'id': i * 3 + j + 1, 'specimen_id': i + 1, 'rater': rater,
                          'category': category, 'alternatives': alternatives})
    study = {'categories': categories,
             'raters': ['标记者甲', '标记者乙', '标记者丙']}
    started = time.monotonic()
    result = analyze_alternatives(study, specimens, votes, {})
    elapsed = time.monotonic() - started
    assert result['range_status'] == 'defined'
    assert result['min']['kappa'] <= result['max']['kappa']
    for endpoint_name in ('min', 'max'):
        endpoint = result[endpoint_name]
        plan = [{'vote_id': v['vote_id'], 'category': v['category']}
                for a in endpoint['assignments'] for v in a['votes']]
        assert len(plan) == 720
        verified = verify_plan(study, specimens, votes, endpoint_name, plan)
        assert verified['legal'] and verified['defined']
        assert verified['matches_endpoint'] is None or verified['matches_endpoint'] is True
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
    assert elapsed < 30, elapsed
    assert peak < 256, peak
    print(f'ok  full workload 240x3, 48 candidates x3: elapsed={elapsed:.2f}s '
          f'peak_rss={peak:.1f}MB states={result["guards"]["state_count"]} '
          f'kappa=[{result["min"]["kappa_rational"]["text"]}, '
          f'{result["max"]["kappa_rational"]["text"]}]')

    # Candidate votes that make the recorded label illegal are rejected.
    bad = [dict(v) for v in votes[:6]]
    bad[0] = {**bad[0], 'alternatives': [c for c in categories if c != bad[0]['category']]}
    bad_study = {'categories': categories, 'raters': ['标记者甲', '标记者乙', '标记者丙']}
    try:
        analyze_alternatives(bad_study, specimens[:2], bad, {})
        raise AssertionError('expected recording-label validation to fail')
    except AlternativesAnalysisError as error:
        print(f'ok  illegal candidate set rejected: {error}')

    # Refusal: too many candidate votes for the documented envelope.
    categories = ['A', 'B', 'C', 'D']
    specimens = [{'id': i + 1, 'reference': f'R{i + 1:03d}'} for i in range(240)]
    votes = []
    for i in range(240):
        for j, rater in enumerate(['x', 'y', 'z']):
            category = categories[(i + j) % 4]
            alternatives = categories if i < 48 else None
            votes.append({'id': i * 3 + j + 1, 'specimen_id': i + 1, 'rater': rater,
                          'category': category, 'alternatives': alternatives})
    study = {'categories': categories, 'raters': ['x', 'y', 'z']}
    started = time.monotonic()
    try:
        analyze_alternatives(study, specimens, votes, {})
        raise AssertionError('expected an explicit refusal')
    except AlternativesRefused as error:
        refused = str(error)
    print(f'ok  refusal raised in {time.monotonic() - started:.2f}s: {refused}')
    print('ALL CHECKS PASSED')

if __name__ == '__main__':
    main()
